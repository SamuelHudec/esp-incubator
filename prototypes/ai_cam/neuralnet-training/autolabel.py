"""Seeded subset selection and local YuNet pseudo-labeling with visual review."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
import urllib.request
import cv2
import numpy as np

REVISION = '3cc26e7f1014a5ee5d74a42acee58bafc9d0a310'
BASE = f'https://huggingface.co/opencv/face_detection_yunet/resolve/{REVISION}/'
MODEL = 'face_detection_yunet_2023mar.onnx'
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def download_model(cache):
    cache.mkdir(parents=True, exist_ok=True)
    for name in (MODEL, 'LICENSE'):
        target = cache / name
        if not target.exists():
            temporary = target.with_suffix(target.suffix + '.partial')
            try:
                with urllib.request.urlopen(BASE+name, timeout=60) as response:
                    temporary.write_bytes(response.read())
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    return cache / MODEL


def select_images(root, count, seed):
    paths = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS)
    if not paths:
        raise ValueError('No supported images found')
    if count is None:
        return paths, len(paths)
    return random.Random(seed).sample(paths, min(count,len(paths))), len(paths)


def select_mixed_images(real_root, synthetic_root, count, seed):
    """Real-first sampling without replacement; first-level real folders are sessions."""
    real_root, synthetic_root = Path(real_root).resolve(), Path(synthetic_root).resolve()
    if real_root.is_relative_to(synthetic_root) or synthetic_root.is_relative_to(real_root):
        raise ValueError('Real and synthetic directories must be separate, non-nested directories')
    def inventory(root):
        return sorted({p.resolve() for p in root.rglob('*')
                       if p.is_file() and p.suffix.lower() in EXTENSIONS})
    real = inventory(real_root)
    # A file reachable through both sources belongs to the real source only.
    synthetic = sorted(set(inventory(synthetic_root)) - set(real))
    if not real and not synthetic:
        raise ValueError('No supported images found')
    rng = random.Random(seed)
    chosen_real = real if count is None or len(real) <= count else rng.sample(real, count)
    remaining = len(synthetic) if count is None else max(0, count-len(chosen_real))
    chosen_synthetic = rng.sample(synthetic, min(remaining, len(synthetic)))
    records = []
    for path in chosen_real:
        if not path.is_relative_to(real_root):
            raise ValueError('Real image symlinks must resolve inside the real directory')
        relative = path.relative_to(real_root)
        group = relative.parts[0] if len(relative.parts) > 1 else '__root__'
        records.append(dict(source=str(path), dataset_source='real', group=group))
    records.extend(dict(source=str(p), dataset_source='synthetic') for p in chosen_synthetic)
    return records, dict(real=dict(available=len(real), selected=len(chosen_real)),
                         synthetic=dict(available=len(synthetic), selected=len(chosen_synthetic)))


def detect(detector, image, size):
    h,w = image.shape[:2]
    scale = size/max(h,w)
    nw,nh = max(1,round(w*scale)), max(1,round(h*scale))
    resized = cv2.resize(image,(nw,nh),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_LINEAR)
    detector.setInputSize((nw,nh))
    _, faces = detector.detect(resized)
    boxes, scores = [], []
    for face in faces if faces is not None else []:
        x,y,bw,bh = map(float,face[:4])
        box = np.clip([x/nw,y/nh,(x+bw)/nw,(y+bh)/nh],0,1).tolist()
        if box[2]>box[0] and box[3]>box[1]:
            boxes.append(box); scores.append(float(face[-1]))
    return boxes,scores


def render_montage(rows, output=None):
    chosen = rows
    if not chosen:
        raise ValueError('Cannot render an empty montage')
    tiles=[]
    for row in chosen:
        image=cv2.imread(row['source'])
        if image is None:
            raise ValueError(f"Cannot read montage image: {row['source']}")
        h,w=image.shape[:2]
        scale=min(320/w,240/h)
        tile=np.full((280,320,3),32,np.uint8)
        nw,nh=max(1,round(w*scale)),max(1,round(h*scale))
        small=cv2.resize(image,(nw,nh))
        for box,score in zip(row['boxes'],row['scores']):
            x1,y1,x2,y2=box
            a=(int(x1*nw),int(y1*nh)); b=(min(nw-1,int(x2*nw)),min(nh-1,int(y2*nh)))
            cv2.rectangle(small,a,b,(0,255,0),2)
            cv2.putText(small,f'{score:.2f}',a,cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,0),1)
        tile[:nh,:nw]=small
        cv2.putText(tile,Path(row['source']).name[:38],(4,257),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
        cv2.putText(tile,f"faces={len(row['boxes'])}",(4,274),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,255),1)
        tiles.append(tile)
    if tiles:
        cols=min(4,len(tiles)); grid=np.full((math.ceil(len(tiles)/cols)*280,cols*320,3),32,np.uint8)
        for i,tile in enumerate(tiles):
            y,x=divmod(i,cols);grid[y*280:(y+1)*280,x*320:(x+1)*320]=tile
        if output is not None and not cv2.imwrite(str(output),grid):
            raise RuntimeError('Failed to write preview')
    return grid



def export_dataset(labels, output, val_fraction=.2, seed=42, test_count=16):
    labels, output = Path(labels).resolve(), Path(output).resolve()
    if not 0 < val_fraction < 1 or test_count < 1:
        raise ValueError('Require validation fraction in (0,1) and positive test count')
    records = json.loads(labels.read_text())
    if not isinstance(records, list) or len(records) < 3:
        raise ValueError('At least three labeled images are required for train/validation/test')
    seen = set()
    converted = []
    for row in records:
        source = (labels.parent / row['image']).resolve()
        if source in seen:
            raise ValueError('Duplicate image paths in labels')
        if not source.is_file():
            raise ValueError(f'Missing image: {source}')
        seen.add(source)
        boxes = row['boxes']
        if not isinstance(boxes, list):
            raise ValueError('boxes must be a list')
        for box in boxes:
            if len(box) != 4 or not np.isfinite(box).all():
                raise ValueError(f'Invalid box: {box}')
            x1,y1,x2,y2 = box
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                raise ValueError(f'Expected normalized xyxy: {box}')
        real = row.get('dataset_source') == 'real'
        if real:
            if row.get('review_status') != 'reviewed':
                raise ValueError('Review every real image and set review_status to reviewed first')
            if not row.get('group'):
                raise ValueError('Real images require a capture group')
            if cv2.imread(str(source)) is None:
                raise ValueError(f'Unreadable real image: {source}')
        converted_row = dict(image=os.path.relpath(source, output.parent), boxes=boxes,
                             scores=[1.0]*len(boxes) if real else row.get('scores', [1.0]*len(boxes)))
        for key in ('dataset_source', 'group', 'review_status'):
            if key in row:
                converted_row[key] = row[key]
        if real:
            converted_row['annotation_source'] = 'human-reviewed'
        converted.append(converted_row)
    rng = random.Random(seed)
    real_rows = [r for r in converted if r.get('dataset_source') == 'real']
    if real_rows:
        groups = sorted({r['group'] for r in real_rows})
        if len(groups) < 3:
            raise ValueError('Need at least three selected real capture groups for train/val/test; '
                             'keep related photos together in top-level real subdirectories')
        rng.shuffle(groups)
        grouped = {g: [r for r in real_rows if r['group'] == g] for g in groups}
        # Targets are approximate: never cut a real capture group to meet a count.
        splits = dict(test=[], val=[], train=[])
        remaining = list(groups)
        targets = dict(test=min(test_count, max(1, round(len(real_rows)*.2))),
                       val=max(1, round(len(real_rows)*val_fraction)))
        for split, reserve in [('test',2), ('val',1)]:
            while len(remaining) > reserve and (not splits[split] or len(splits[split]) < targets[split]):
                splits[split].extend(grouped[remaining.pop(0)])
        for group in remaining:
            splits['train'].extend(grouped[group])
        synthetic = [r for r in converted if r.get('dataset_source') != 'real']
        rng.shuffle(synthetic)
        ntest = min(len(synthetic), max(0, test_count-len(splits['test'])))
        nval = min(len(synthetic)-ntest,
                   max(0, round(len(converted)*val_fraction)-len(splits['val'])))
        splits['test'].extend(synthetic[:ntest])
        splits['val'].extend(synthetic[ntest:ntest+nval])
        splits['train'].extend(synthetic[ntest+nval:])
        # Path checks cannot detect copies under different names or sources.
        hashes = {}
        for split, rows in splits.items():
            for row in rows:
                source = (output.parent/row['image']).resolve()
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                if digest in hashes and hashes[digest] != split:
                    raise ValueError('Identical image contents cross splits; remove copies or group them together')
                hashes[digest] = split
        method = 'real-capture-group/synthetic-random-image'
    else:
        rng.shuffle(converted)
        ntest = min(test_count, len(converted)-2)
        nval = max(1, min(len(converted)-ntest-1, round(len(converted)*val_fraction)))
        splits = dict(test=converted[:ntest], val=converted[ntest:ntest+nval],
                      train=converted[ntest+nval:])
        method = 'random-image'
    dataset = dict(format='tinyface-dataset-v1', split=dict(method=method,
                   seed=seed, val_fraction=val_fraction, test_count=len(splits['test'])), **splits)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f:
        json.dump(dataset, f, indent=2)
    return len(dataset['train']), len(dataset['val']), len(dataset['test'])


def finalize_run(directory):
    """Export reviewed labels without rerunning the teacher or changing selection."""
    directory = Path(directory).resolve()
    summary = json.loads((directory/'summary.json').read_text())
    selected = json.loads((directory/'selection.json').read_text())
    labels = json.loads((directory/'labels.json').read_text())
    expected = {Path(r['source']).resolve(): r for r in selected if r['dataset_source'] == 'real'}
    actual = {(directory/r['image']).resolve(): r for r in labels if r.get('dataset_source') == 'real'}
    if expected.keys() != actual.keys():
        raise ValueError('labels.json must retain every selected real image; do not drop or reclassify rows')
    if any(actual[path].get('group') != row['group'] for path,row in expected.items()):
        raise ValueError('Keep the original real capture groups from selection.json')
    counts = export_dataset(directory/'labels.json', directory/'dataset.json',
                            summary['val_fraction'], summary['seed'], summary['requested_test_count'])
    summary.update(train_images=counts[0], val_images=counts[1], test_images=counts[2],
                   real_review_pending=0, finalized=True)
    (directory/'summary.json').write_text(json.dumps(summary, indent=2))
    print_dataset_counts(directory)
    return counts


def print_dataset_counts(directory):
    dataset = json.loads((directory/'dataset.json').read_text())
    for split in ('train','val','test'):
        rows = dataset[split]
        real = sum(r.get('dataset_source') == 'real' for r in rows)
        print(f'{split}: {len(rows)} images (real={real}, synthetic/legacy={len(rows)-real})', flush=True)
    print(f'Dataset ready: {directory}/dataset.json. Real labels are human-reviewed; '
          'synthetic labels remain teacher pseudo-labels.', flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',help='Legacy single image directory, searched recursively')
    parser.add_argument('--real-input',help='Real images, grouped in top-level capture-session directories')
    parser.add_argument('--synthetic-input',help='Synthetic images used to fill the requested count')
    parser.add_argument('--finalize',help='Existing mixed run directory after reviewing labels.json')
    parser.add_argument('--out',default='data/autolabel-1000',help='New output directory')
    parser.add_argument('--count',type=int,default=None,help='Total sample size; real images take priority; omit for all')
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--test-count',type=int,default=16,help='Test target (1-100); whole real groups may exceed it')
    parser.add_argument('--val-fraction',type=float,default=.2)
    parser.add_argument('--threshold',type=float,default=.8)
    parser.add_argument('--size',type=int,default=640,help='Detector longest input side')
    parser.add_argument('--cache',default='data/models/yunet/'+REVISION)
    args=parser.parse_args()
    if args.finalize:
        if args.input or args.real_input or args.synthetic_input:
            parser.error('--finalize cannot be combined with input directories')
        try:
            finalize_run(args.finalize)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            parser.error(str(exc))
        return
    mixed = bool(args.real_input or args.synthetic_input)
    if mixed:
        if args.input or not (args.real_input and args.synthetic_input):
            parser.error('Use both --real-input and --synthetic-input, without --input')
        roots = [Path(args.real_input).resolve(), Path(args.synthetic_input).resolve()]
    else:
        if not args.input:
            parser.error('Use --input or both --real-input and --synthetic-input')
        roots = [Path(args.input).resolve()]
    if (args.count is not None and args.count<1) or args.size<32 or not 0<args.threshold<1:
        parser.error('count >= 1, size >= 32, threshold in (0,1) required')
    if not 1 <= args.test_count <= 100 or not 0 < args.val_fraction < 1:
        parser.error('test-count must be 1-100 and val-fraction in (0,1)')
    out=Path(args.out).resolve()
    for root in roots:
        if not root.is_dir():
            parser.error(f'Input must be a directory: {root}')
        if out.is_relative_to(root):
            parser.error('--out must be outside both input trees to avoid sampling generated previews')
    if out.exists():
        parser.error('--out already exists; choose a new directory to preserve reviewed labels')
    try:
        if mixed:
            selection, source_counts = select_mixed_images(*roots, args.count, args.seed)
            for name,counts in source_counts.items():
                print(f'{name}: selected {counts["selected"]} / available {counts["available"]}',flush=True)
            total = sum(c['available'] for c in source_counts.values())
        else:
            paths,total=select_images(roots[0],args.count,args.seed)
            selection=[dict(source=str(p),dataset_source='legacy') for p in paths]
            source_counts={'legacy':dict(available=total,selected=len(paths))}
    except ValueError as exc:
        parser.error(str(exc))
    print(f'Selected {len(selection)} of {total} images (requested={args.count}, seed={args.seed})',flush=True)
    model=download_model(Path(args.cache))
    detector=cv2.FaceDetectorYN.create(str(model),'',(args.size,args.size),args.threshold,.3,5000)
    out.mkdir(parents=True)
    (out/'selected.json').write_text(json.dumps([r['source'] for r in selection],indent=2))
    (out/'selection.json').write_text(json.dumps(selection,indent=2))
    rows=[];errors=[];started=time.perf_counter()
    with (out/'detections.jsonl').open('a') as log:
        for i,item in enumerate(selection,1):
            path=Path(item['source'])
            row=dict(item, image=os.path.relpath(path,out), boxes=[], scores=[])
            try:
                image=cv2.imread(str(path))
                if image is None:
                    raise ValueError('Unreadable image')
                row['boxes'],row['scores']=detect(detector,image,args.size)
                if item['dataset_source']=='real':
                    row['review_status']='pending'
                rows.append(row)
            except (ValueError,cv2.error) as exc:
                row['error']=str(exc)
                errors.append(dict(image=str(path),dataset_source=item['dataset_source'],error=str(exc)))
                if item['dataset_source']=='real':
                    row['review_status']='unreadable'
                    rows.append(row)
            log.write(json.dumps(row)+'\n');log.flush()
            if i%50==0 or i==len(selection):
                print(f'{i}/{len(selection)} processed; {len(errors)} errors',flush=True)
    readable=[r for r in rows if r.get('review_status')!='unreadable']
    positive=[r for r in readable if r['boxes']]
    missing=[r for r in readable if not r['boxes']]
    # Every real selection survives, including misses and unreadable images.
    labels=[r for r in rows if r['dataset_source']=='real' or r['boxes']]
    for name,group in [('labels.json',labels),('review_no_faces.json',missing)]:
        (out/name).write_text(json.dumps([{k:v for k,v in r.items() if k!='source'} for r in group],indent=2))
    (out/'errors.json').write_text(json.dumps(errors,indent=2))
    pending=sum(r['dataset_source']=='real' for r in labels)
    for name,counts in source_counts.items():
        counts.update(with_faces=sum(r['dataset_source']==name for r in positive),
                      without_faces=sum(r['dataset_source']==name for r in missing),
                      errors=sum(e['dataset_source']==name for e in errors))
    split_counts=None
    if not pending and len(positive)>=3:
        split_counts=export_dataset(out/'labels.json',out/'dataset.json',args.val_fraction,args.seed,args.test_count)
        test_rows=json.loads((out/'dataset.json').read_text())['test']
        for row in test_rows:
            row['source']=str((out/row['image']).resolve())
        render_montage(test_rows,out/'test_teacher.jpg')
    summary=dict(model='opencv/face_detection_yunet',revision=REVISION,
                 model_sha256=hashlib.sha256(Path(model).read_bytes()).hexdigest(),
                 opencv=cv2.__version__,seed=args.seed,threshold=args.threshold,input_size=args.size,
                 val_fraction=args.val_fraction,requested_test_count=args.test_count,
                 requested_count=args.count,source_counts=source_counts,real_review_pending=pending,
                 test_images=split_counts[2] if split_counts else 0,
                 train_images=split_counts[0] if split_counts else 0,
                 val_images=split_counts[1] if split_counts else 0,
                 available=total,selected=len(selection),processed=len(readable),errors=len(errors),
                 with_faces=len(positive),without_faces=len(missing),
                 multiple_faces=sum(len(r['boxes'])>1 for r in readable),
                 total_faces=sum(len(r['boxes']) for r in readable),
                 elapsed_seconds=round(time.perf_counter()-started,2))
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    if pending:
        print(f'Review all {pending} real rows in {out}/labels.json, correct boxes, then set '
              'review_status to reviewed. Empty boxes mean a HUMAN-CONFIRMED negative.',flush=True)
        groups={r['group'] for r in labels if r['dataset_source']=='real'}
        if len(groups)<3:
            print('Dataset pending: fewer than three selected real capture groups. '
                  'Collect/organize independent groups and create a new run; never split a burst randomly.',flush=True)
        print(f'After review: python autolabel.py --finalize "{out}"',flush=True)
    elif split_counts:
        print_dataset_counts(out)
        print(f'Review {out}/test_teacher.jpg before training with --data "{out}".')
    else:
        print('Fewer than three usable labels; dataset.json was not created.')


if __name__=='__main__':
    main()
