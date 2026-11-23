"""Stage 3: mix reviewed collections into an independent train/val/test snapshot."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random

import cv2

SPLITS = ('train', 'val', 'test')


def validate_boxes(boxes):
    if not isinstance(boxes, list):
        raise ValueError('boxes must be a list')
    for b in boxes:
        if (not isinstance(b, list) or len(b) != 4 or
                not all(type(v) in (int, float) and math.isfinite(v) for v in b) or
                not (0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1)):
            raise ValueError(f'Invalid normalized box: {b}')


def read_collection(directory, role):
    directory = Path(directory).resolve()
    path = directory/'labels.json'
    content = path.read_bytes()
    rows = json.loads(content)
    if not isinstance(rows, list):
        raise ValueError(f'Expected a labels list: {path}')
    metadata_path = directory/'collection.json'
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
    if metadata is not None and metadata.get('format') != 'face-annotations-v1':
        raise ValueError(f'Unsupported annotation collection format: {directory}')
    # A collection has no fixed role. Ignore kind/source tags from older standalone collections.
    # Legacy mixed runs can be used twice, once for their real and once for extra rows.
    if not metadata:
        marked = any(r.get('dataset_source') == 'real' for r in rows)
        if role == 'real' and not marked and any(r.get('dataset_source') in ('extra','synthetic') for r in rows):
            raise ValueError(f'No camera records in this collection: {directory}')
        if marked:
            rows = [r for r in rows if (r.get('dataset_source') == 'real') == (role == 'real')]
    records = []
    for row in rows:
        if row.get('review_status') != 'reviewed':
            continue
        validate_boxes(row['boxes'])
        image = (directory/row['image']).resolve()
        if not image.is_file():
            raise ValueError(f'Missing reviewed image: {image}')
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        # Empty reviewed boxes are explicit negatives; pending teacher misses never enter.
        records.append(dict(image=str(image), boxes=row['boxes'], scores=[1.0]*len(row['boxes']),
                            dataset_source=role, annotation_source='human-reviewed', review_status='reviewed',
                            source_collection=str(directory), image_sha256=digest,
                            group=row.get('group') if role == 'real' else None))
    return records, dict(collection=str(directory), role=role, labels_sha256=hashlib.sha256(content).hexdigest(),
                         available=len(rows), reviewed=len(records), pending=len(rows)-len(records), duplicates=0)


def deduplicate(records, inventories):
    unique = {}
    for row in records:
        digest = row['image_sha256']
        if digest in unique:
            prior = unique[digest]
            if sorted(prior['boxes']) != sorted(row['boxes']):
                raise ValueError(f'Conflicting reviewed annotations for identical image: '
                                 f'{prior["image"]} and {row["image"]}. '
                                 'Choose consistent source collections or reconcile labels first.')
            if (prior['dataset_source'] == row['dataset_source'] == 'real' and
                    prior['group'] != row['group']):
                raise ValueError(f'Identical real image has different capture groups: {row["image"]}')
            for info in inventories:
                if info['collection'] == row['source_collection'] and info['role'] == row['dataset_source']:
                    info['duplicates'] += 1
                    break
        else:
            unique[digest] = row  # Real collections are read first and win duplicate priority.
    return list(unique.values())


def priority_sample(records, count, seed):
    # Stable seeded ranks make selection independent of input collection order.
    def rank(row):
        return hashlib.sha256(f'{seed}:{row["image_sha256"]}'.encode()).hexdigest()
    real = sorted((r for r in records if r['dataset_source']=='real'), key=rank)
    extra = sorted((r for r in records if r['dataset_source']!='real'), key=rank)
    # Prefix sampling gives nested selections for size experiments on unchanged pools.
    return (real+extra)[:count] if count is not None else real+extra


def split_records(records, seed, val_fraction, test_count, mode):
    rng = random.Random(seed)
    real = [r for r in records if r['dataset_source']=='real']
    groups = sorted({r['group'] for r in real if r['group'] is not None})
    grouped = mode == 'group' or (mode == 'auto' and len(groups)>=3 and all(r['group'] for r in real))
    if grouped:
        if len(groups)<3 or not all(r['group'] for r in real):
            raise ValueError('Group splitting requires at least three selected real groups and a group on every real row')
        rng.shuffle(groups)
        splits = {s:[] for s in SPLITS}
        remaining = list(groups)
        for name, reserve, target in [('test',2,min(test_count,max(1,round(len(real)*.2)))),
                                       ('val',1,max(1,round(len(real)*val_fraction)))]:
            while len(remaining)>reserve and (not splits[name] or len(splits[name])<target):
                group=remaining.pop(0)
                splits[name].extend(r for r in real if r['group']==group)
        splits['train']=[r for r in real if r['group'] in remaining]
        extra=[r for r in records if r['dataset_source']!='real'];rng.shuffle(extra)
        nt=min(len(extra),max(0,test_count-len(splits['test'])))
        nv=min(len(extra)-nt,max(0,round(len(records)*val_fraction)-len(splits['val'])))
        splits['test'].extend(extra[:nt]);splits['val'].extend(extra[nt:nt+nv]);splits['train'].extend(extra[nt+nv:])
        return splits, 'real-group/extra-random-image'
    if real:
        print('Using image-level splits: related real frames can leak across splits. '
              'Use capture groups and --split-mode group for independent evaluation.',flush=True)
    shuffled=list(records);rng.shuffle(shuffled)
    nt=min(test_count,len(shuffled)-2)
    nv=max(1,min(len(shuffled)-nt-1,round(len(shuffled)*val_fraction)))
    return dict(test=shuffled[:nt],val=shuffled[nt:nt+nv],train=shuffled[nt+nv:]), 'random-image'


def create_dataset(real_data, extra_data, out, count=None, seed=42, val_fraction=.2,
                   test_count=16, split_mode='auto'):
    out=Path(out).resolve()
    if out.exists(): raise ValueError('Output already exists; choose a new dataset directory')
    if count is not None and count<3: raise ValueError('count must be at least 3 for train/val/test')
    if not 0<val_fraction<1 or test_count<1: raise ValueError('Invalid validation fraction or test count')
    if split_mode not in ('auto','group','image'): raise ValueError('Invalid split mode')
    inputs=([(real_data,'real')] if real_data else [])+[(p,'extra') for p in extra_data]
    if not inputs: raise ValueError('Supply at least one annotated collection')
    inventories=[];records=[];seen_inputs=set()
    for directory,role in inputs:
        key=(str(Path(directory).resolve()),role)
        if key in seen_inputs: raise ValueError(f'Collection supplied twice: {directory}')
        seen_inputs.add(key)
        if out.is_relative_to(Path(directory).resolve()):
            raise ValueError('Training output must be outside annotation collections')
        rows,info=read_collection(directory,role);records.extend(rows);inventories.append(info)
    records=deduplicate(records,inventories)
    if len(records)<3: raise ValueError('Need at least three distinct reviewed images; review collections first')
    selected=priority_sample(records,count,seed)
    splits,method=split_records(selected,seed,val_fraction,test_count,split_mode)
    split_info=dict(method=method, val_fraction=val_fraction, requested_test_count=test_count)
    if any(not splits[s] for s in SPLITS): raise ValueError('Each split must contain at least one image')
    for name in SPLITS:
        for row in splits[name]:
            if cv2.imread(row['image']) is None:
                raise ValueError(f'Unreadable selected image: {row["image"]}')
    selected_rows=[r for s in SPLITS for r in splits[s]]
    for info in inventories:
        own=[r for r in selected_rows if r['source_collection']==info['collection'] and r['dataset_source']==info['role']]
        info['selected']=len(own)
        print(f'{info["role"]} {info["collection"]}: available={info["available"]}, reviewed={info["reviewed"]}, '
              f'pending={info["pending"]}, duplicates={info["duplicates"]}, selected={info["selected"]}',flush=True)
    for name in SPLITS:
        rows=splits[name];real=sum(r['dataset_source']=='real' for r in rows)
        print(f'{name}: {len(rows)} (real={real}, extra={len(rows)-real})',flush=True)
        for row in rows: row['image']=os.path.relpath(row['image'],out)
    manifest=dict(format='tinyface-dataset-v1',split=dict(seed=seed,**split_info),sources=inventories,**splits)
    summary=dict(requested_count=count,selected=len(selected_rows),available_reviewed=len(records),sources=inventories,
                 split_counts={s:len(splits[s]) for s in SPLITS})
    # Only create output after all input validation and split checks succeeded.
    out.mkdir(parents=True,exist_ok=False)
    (out/'dataset.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(f'Training dataset ready: {out}/dataset.json',flush=True)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--real-data',type=Path,help='One preferred reviewed camera collection')
    p.add_argument('--extra-data',nargs='+',action='extend',type=Path,default=[],help='One or more additional reviewed collections')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--count',type=int,help='Total including val/test; omit for all eligible reviewed images')
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--val-fraction',type=float,default=.2)
    p.add_argument('--test-count',type=int,default=16)
    p.add_argument('--split-mode',choices=('auto','group','image'),default='auto')
    a=p.parse_args()
    try:
        create_dataset(a.real_data,a.extra_data,a.out,a.count,a.seed,a.val_fraction,a.test_count,a.split_mode)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        p.exit(1,f'Error: {exc}\n')


if __name__=='__main__': main()
