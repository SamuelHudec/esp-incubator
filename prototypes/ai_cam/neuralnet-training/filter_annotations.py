"""Filter an annotation collection by the largest face area relative to the image."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path

from create_dataset import validate_boxes


def parse_ratio(value):
    try:
        ratio = float(Fraction(value))
        if not 0 <= ratio <= 1:
            raise ValueError()
        return ratio
    except (ValueError, ZeroDivisionError, OverflowError):
        raise argparse.ArgumentTypeError('Use a fraction or decimal between 0 and 1, e.g. 1/30 or 0.05')


def filter_annotations(data, out, min_face_ratio=1/30, exclude_empty=False):
    data, out = Path(data).resolve(), Path(out).resolve()
    if not math.isfinite(min_face_ratio) or not 0 <= min_face_ratio <= 1:
        raise ValueError('Minimum face ratio must be between 0 and 1')
    if out.exists() or out.is_relative_to(data):
        raise ValueError('Output must be a new directory outside the source collection')
    path = data/'labels.json'
    if not path.is_file():
        raise ValueError('Supply an annotation collection containing labels.json, before mixing/splitting')
    content = path.read_bytes()
    rows = json.loads(content)
    if not isinstance(rows, list):
        raise ValueError('labels.json must contain a list')
    kept, removed = [], []
    without_boxes = 0
    empty_removed = 0
    for row in rows:
        if row.get('review_status') == 'excluded':
            removed.append(dict(image=os.path.relpath((data/row['image']).resolve(), out), reason='excluded'))
            continue
        boxes = row['boxes']
        validate_boxes(boxes)
        source = (data/row['image']).resolve()
        if not source.is_file():
            raise ValueError(f'Missing source image: {source}')
        image = os.path.relpath(source, out)
        if boxes:
            # Largest means area, not the number of faces or the average size.
            box = max(boxes, key=lambda b:(b[2]-b[0])*(b[3]-b[1]))
            ratio = (box[2]-box[0])*(box[3]-box[1])
            if ratio < min_face_ratio and not math.isclose(ratio, min_face_ratio, rel_tol=1e-12, abs_tol=0):
                removed.append(dict(image=image, largest_face_ratio=ratio))
                continue
        else:
            if exclude_empty:
                removed.append(dict(image=image, reason='empty_annotations'))
                empty_removed += 1
                continue
            # Preserve negatives; an unreviewed teacher miss remains unreviewed.
            without_boxes += 1
        kept.append(dict(row, image=image))
    report = dict(source=str(path), source_labels_sha256=hashlib.sha256(content).hexdigest(),
                  min_face_ratio=min_face_ratio, exclude_empty=exclude_empty,
                  rule='largest box area / image area; inclusive threshold; ' + ('exclude' if exclude_empty else 'keep') + ' empty annotations',
                  input_images=len(rows), kept_images=len(kept), removed_images=len(removed),
                  without_boxes_kept=without_boxes, without_boxes_removed=empty_removed, removed=removed)
    metadata = None
    if (data/'collection.json').exists():
        metadata = json.loads((data/'collection.json').read_text())
        if metadata.get('format') != 'face-annotations-v1':
            raise ValueError('Unsupported annotation collection format')
        metadata.update(filtered_from=str(data), images=len(kept),
                        with_faces=sum(bool(r['boxes']) for r in kept),
                        errors=sum(r.get('review_status') in ('error','unreadable') for r in kept))
    out.mkdir(parents=True, exist_ok=False)
    (out/'labels.json').write_text(json.dumps(kept, indent=2)+'\n')
    (out/'filter.json').write_text(json.dumps(report, indent=2)+'\n')
    if metadata is not None:
        (out/'collection.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(f'Images: {len(rows)}; kept={len(kept)}, removed={len(removed)}, without boxes kept={without_boxes}, without boxes removed={empty_removed}')
    print(f'Rule: largest face area / image area >= {min_face_ratio:g} ({min_face_ratio:.2%})')
    print(f'Filtered collection: {out}')
    return kept, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', required=True, type=Path, help='Annotated collection containing labels.json')
    p.add_argument('--out', required=True, type=Path, help='New filtered collection')
    p.add_argument('--min-face-ratio', type=parse_ratio, default=1/30, help='Minimum face/image area ratio, e.g. 1/30 or 0.05 (default 1/30)')
    p.add_argument('--exclude-empty', action='store_true', help='Exclude images with no boxes, including reviewed negatives')
    a = p.parse_args()
    try:
        filter_annotations(a.data, a.out, a.min_face_ratio, exclude_empty=a.exclude_empty)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        p.exit(1, f'Error: {exc}\n')


if __name__ == '__main__': main()
