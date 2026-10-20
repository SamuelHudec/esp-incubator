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
    if not 0 < val_fraction < 1:
        raise ValueError('Validation fraction must be between 0 and 1')
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
        converted.append(dict(image=os.path.relpath(source, output.parent), boxes=row['boxes'], scores=row.get('scores', [1.0]*len(row['boxes']))))
    random.Random(seed).shuffle(converted)
    ntest = min(test_count, len(converted)-2)
    nval = max(1, min(len(converted)-ntest-1, round(len(converted)*val_fraction)))
    dataset = dict(format='tinyface-dataset-v1', split=dict(method='random-image',
                   seed=seed, val_fraction=val_fraction, test_count=ntest),
                   test=converted[:ntest], val=converted[ntest:ntest+nval],
                   train=converted[ntest+nval:])
    output.parent.mkdir(parents=True, exist_ok=True)
    # Do not silently overwrite a reviewed split.
    with output.open('x') as f:
        json.dump(dataset, f, indent=2)
    return len(dataset['train']), len(dataset['val']), len(dataset['test'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,help='Image directory, searched recursively')
    parser.add_argument('--out',default='data/autolabel-1000',help='New output directory')
    parser.add_argument('--count',type=int,default=None,help='Random subset size; omit to process all images')
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--test-count',type=int,default=16,help='Fixed held-out comparison images (1-100)')
    parser.add_argument('--val-fraction',type=float,default=.2)
    parser.add_argument('--threshold',type=float,default=.8)
    parser.add_argument('--size',type=int,default=640,help='Detector longest input side')
    parser.add_argument('--cache',default='data/models/yunet/'+REVISION)
    args=parser.parse_args()
    if (args.count is not None and args.count<1) or args.size<32 or not 0<args.threshold<1:
        parser.error('count >= 1, size >= 32, threshold in (0,1) required')
    if not 1 <= args.test_count <= 100:
        parser.error('--test-count must be between 1 and 100')
    if not 0 < args.val_fraction < 1:
        parser.error('--val-fraction must be between 0 and 1')
    root=Path(args.input).resolve();out=Path(args.out).resolve()
    if not root.is_dir():
        parser.error('--input must be a directory')
    if out.exists():
        parser.error('--out already exists; choose a new directory to preserve previous labels')
    if out.is_relative_to(root):
        parser.error('--out must be outside the input directory to avoid sampling generated previews')
    selected,total=select_images(root,args.count,args.seed)
    print(f'Selected {len(selected)} of {total} images (seed={args.seed})',flush=True)
    model=download_model(Path(args.cache))
    detector=cv2.FaceDetectorYN.create(str(model),'',(args.size,args.size),args.threshold,.3,5000)
    out.mkdir(parents=True)
    (out/'selected.json').write_text(json.dumps([str(p) for p in selected],indent=2))
    rows=[];errors=[];started=time.perf_counter()
    # Persist each completed result, even if a later image fails or run is interrupted.
    with (out/'detections.jsonl').open('w') as log:
        for i,path in enumerate(selected,1):
            try:
                image=cv2.imread(str(path))
                if image is None:
                    raise ValueError('Unreadable image')
                boxes,scores=detect(detector,image,args.size)
                row=dict(source=str(path),image=os.path.relpath(path,out),boxes=boxes,scores=scores)
                rows.append(row);log.write(json.dumps(row)+'\n');log.flush()
            except (ValueError,cv2.error) as exc:
                errors.append(dict(image=str(path),error=str(exc)))
            if i%50==0 or i==len(selected):
                print(f'{i}/{len(selected)} processed; {len(errors)} errors',flush=True)
    positive=[r for r in rows if r['boxes']]
    missing=[r for r in rows if not r['boxes']]
    # A teacher miss is not a verified negative example.
    for name,group in [('labels.json',positive),('review_no_faces.json',missing)]:
        (out/name).write_text(json.dumps([dict(image=r['image'],boxes=r['boxes'],scores=r['scores']) for r in group],indent=2))
    split_counts = None
    if len(positive) >= 3:
        split_counts = export_dataset(out/'labels.json', out/'dataset.json', args.val_fraction, args.seed, args.test_count)
        test_rows = json.loads((out/'dataset.json').read_text())['test']
        for row in test_rows:
            row['source'] = str((out/row['image']).resolve())
        render_montage(test_rows, out/'test_teacher.jpg')
    else:
        print('WARNING: fewer than three labeled images; dataset.json was not created.')
    (out/'errors.json').write_text(json.dumps(errors,indent=2))
    summary=dict(model='opencv/face_detection_yunet',revision=REVISION,
                 model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                 opencv=cv2.__version__,seed=args.seed,threshold=args.threshold,input_size=args.size,
                 test_images=split_counts[2] if split_counts else 0,
                 train_images=split_counts[0] if split_counts else 0,
                 val_images=split_counts[1] if split_counts else 0,
                 available=total,selected=len(selected),processed=len(rows),errors=len(errors),
                 with_faces=len(positive),without_faces=len(missing),
                 multiple_faces=sum(len(r['boxes'])>1 for r in rows),
                 total_faces=sum(len(r['boxes']) for r in rows),
                 elapsed_seconds=round(time.perf_counter()-started,2))
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    if split_counts:
        print(f'Review {out}/test_teacher.jpg before training with --data "{out}".')
    if not positive:
        print('WARNING: no positive labels; labels.json is empty and cannot train the model.')


if __name__=='__main__':
    main()
