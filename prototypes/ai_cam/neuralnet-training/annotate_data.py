"""Annotate new or failed images in a reusable collection; preserve completed work."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

import cv2
from utils.annotation import EXTENSIONS, detect, load_detector


def atomic_json(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_progress(out):
    """Reviewed labels win over the teacher journal, including after a crash."""
    labels = out/'labels.json'
    original = labels.read_bytes() if labels.exists() else None
    rows = json.loads(original) if original is not None else []
    if not isinstance(rows, list):
        raise ValueError('labels.json must contain a list')
    known = {}
    for row in rows:
        path = (out/row['image']).resolve()
        if path in known:
            raise ValueError('Duplicate image paths in labels.json')
        known[path] = row
    journal = out/'detections.jsonl'
    if journal.exists():
        lines = journal.read_bytes().splitlines(keepends=True)
        valid_bytes = 0
        for index, line in enumerate(lines):
            try:
                row = json.loads(line)
            except (ValueError, UnicodeError):
                if index == len(lines)-1 and not line.endswith(b'\n'):
                    # A crash may leave a torn final record; never discard earlier corruption.
                    with journal.open('r+b') as stream: stream.truncate(valid_bytes)
                    break
                raise ValueError('Invalid annotation journal; earlier records were not modified')
            path = (out/row['image']).resolve()
            current = known.get(path)
            if current is None or current.get('review_status') in ('error', 'unreadable'):
                known[path] = row
            valid_bytes += len(line)
        # Separate a complete last record lacking a newline from the next append.
        if journal.stat().st_size and not journal.read_bytes().endswith(b'\n'):
            with journal.open('ab') as stream: stream.write(b'\n')
    return known, original


def annotate_collection(root, out, detector_name='yunet', threshold=.8, size=640, cache=None):
    root, out = Path(root).resolve(), Path(out).resolve()
    if not root.is_dir():
        raise ValueError(f'Not an image directory: {root}')
    if out.is_relative_to(root):
        raise ValueError('Output must be outside the input tree')
    if not 0 < threshold < 1 or size < 32 or (detector_name=='retinaface' and size!=640):
        raise ValueError('Require threshold in (0,1), size >= 32; RetinaFace requires size 640')
    if out.exists() and not (out/'collection.json').is_file():
        raise ValueError('Existing output is not an annotation collection; choose a new directory')
    paths = sorted({p.resolve() for p in root.rglob('*')
                    if p.is_file() and p.suffix.lower() in EXTENSIONS})
    if not paths:
        raise ValueError('No supported images found')
    if any(not p.is_relative_to(root) for p in paths):
        raise ValueError('Image symlinks must resolve inside the input tree')
    out.mkdir(parents=True, exist_ok=True)
    # Prevent simultaneous annotation runs; editor saves are checked separately below.
    with (out/'.annotation.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another annotation run is using this output directory')
        return update_collection(root, out, paths, detector_name, threshold, size, cache)


def update_collection(root, out, paths, detector_name, threshold, size, cache):
    metadata_path = out/'collection.json'
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
    if metadata is not None:
        if metadata.get('filtered_from'):
            raise ValueError('This is a filtered collection. Add images to the original collection and filter it again into a new output.')
        if metadata.get('format')!='face-annotations-v1' or Path(metadata.get('input','')).resolve()!=root:
            raise ValueError('Existing collection belongs to a different input directory or format')
        if (metadata.get('detector'), metadata.get('threshold'), metadata.get('input_size')) != (detector_name,threshold,size):
            raise ValueError('Use the same detector/threshold/size for this collection, or choose a new output')
    else:
        # Save identity before detection so even an interrupted first run can resume.
        metadata=dict(format='face-annotations-v1',input=str(root),detector=detector_name,
                      threshold=threshold,input_size=size)
        atomic_json(metadata_path,metadata)
    known, original = read_progress(out)
    pending=[]; new=retry=0
    for path in paths:
        row=known.get(path)
        if row and row.get('review_status') == 'excluded':
            continue
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if row and row.get('image_sha256') and row['image_sha256']!=digest and row.get('review_status') not in ('error','unreadable'):
            raise ValueError(f'Completed image contents changed: {path}. Keep originals unchanged or use a new collection.')
        if row is None or row.get('review_status') in ('error','unreadable'):
            pending.append((path,digest))
            new+=row is None;retry+=row is not None
    missing=sum(not p.is_file() for p in known)
    print(f'Images: {len(paths)}; completed={len(paths)-len(pending)}, new={new}, retry={retry}, missing={missing}',flush=True)
    if missing:
        print('Missing source records are retained; no annotations are deleted.',flush=True)
    started=time.monotonic();processed=0
    if pending:
        detector,provenance=load_detector(detector_name,threshold,size,cache)
        metadata.update(provenance)
        atomic_json(metadata_path,metadata)
    try:
        with (out/'detections.jsonl').open('a') as log:
            for path,digest in pending:
                relative=path.relative_to(root)
                row=dict(image=os.path.relpath(path,out),boxes=[],scores=[],review_status='pending',
                         group=relative.parts[0] if len(relative.parts)>1 else '__root__',image_sha256=digest)
                try:
                    image=cv2.imread(str(path))
                    if image is None: raise ValueError('Unreadable image')
                    row['boxes'],row['scores']=detect(detector,image,size)
                except (ValueError,cv2.error) as exc:
                    row.update(review_status='error',error=str(exc))
                log.write(json.dumps(row)+'\n');log.flush();os.fsync(log.fileno())
                known[path]=row;processed+=1
                if processed%50==0 or processed==len(pending):
                    print(f'Annotated {processed}/{len(pending)} new/retry images',flush=True)
    finally:
        labels=out/'labels.json'
        current=labels.read_bytes() if labels.exists() else None
        if current!=original:
            raise ValueError('labels.json changed in the editor during annotation. Saved edits were preserved; close the editor and rerun to merge new journal records.')
        rows=list(known.values())
        if original is None or json.loads(original)!=rows:
            atomic_json(labels,rows)
        metadata.update(images=len(rows),errors=sum(r.get('review_status') in ('error','unreadable') for r in rows),
                        with_faces=sum(bool(r['boxes']) for r in rows),
                        last_run=dict(new=new,retry=retry,processed=processed,seconds=round(time.monotonic()-started,2)))
        atomic_json(metadata_path,metadata)
    print(f'Collection ready: {out}. Review with: uv run annotator/annotate.py --data "{out}"')
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--detector',choices=('yunet','retinaface'),default='yunet')
    p.add_argument('--threshold',type=float,default=.8)
    p.add_argument('--size',type=int,default=640)
    p.add_argument('--cache',type=Path)
    a=p.parse_args()
    try:
        annotate_collection(a.input,a.out,a.detector,a.threshold,a.size,a.cache)
    except (ValueError,OSError) as exc:
        p.exit(1,f'Error: {exc}\n')
    except KeyboardInterrupt:
        p.exit(130,'Interrupted. Completed annotations are saved; rerun the same command to continue.\n')


if __name__=='__main__': main()
