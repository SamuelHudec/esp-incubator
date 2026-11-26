"""Import COCO bounding boxes into a pending annotation collection for review."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import cv2


def import_coco(source, out, category='face'):
    source, out = Path(source).resolve(), Path(out).resolve()
    if not source.exists():
        raise ValueError(f'Input does not exist: {source}')
    root = source if source.is_dir() else source.parent
    if out.exists() or out.is_relative_to(root):
        raise ValueError('Output must be a new directory outside the input tree')
    files = sorted(source.rglob('_annotations.coco.json')) if source.is_dir() else [source]
    if not files:
        raise ValueError('No _annotations.coco.json found; supply a COCO JSON file or a Roboflow export directory')
    rows, seen, provenance = [], set(), []
    ignored = 0
    for path in files:
        content = path.read_bytes()
        data = json.loads(content)
        categories = {c['id']: c['name'] for c in data['categories']}
        selected = {key for key, name in categories.items() if name.casefold() == category.casefold()}
        if not selected:
            raise ValueError(f'{path}: category {category!r} not found; available: {list(categories.values())}. Use --category NAME')
        images = {}
        for item in data['images']:
            if item['id'] in images:
                raise ValueError(f'{path}: duplicate image ID {item["id"]}')
            image = (path.parent/item['file_name']).resolve()
            if not image.is_relative_to(root) or not image.is_file():
                raise ValueError(f'Missing image or path outside input: {image}')
            if image in seen:
                raise ValueError(f'Duplicate image path across input records: {image}')
            seen.add(image)
            width, height = item['width'], item['height']
            if type(width) is not int or type(height) is not int or min(width, height) <= 0:
                raise ValueError(f'Invalid image dimensions: {image}')
            decoded = cv2.imread(str(image))
            if decoded is None or decoded.shape[:2] != (height, width):
                raise ValueError(f'Unreadable image or dimensions disagree with COCO: {image}')
            row = dict(image=os.path.relpath(image, out), boxes=[], scores=[], review_status='pending',
                       annotation_source='coco', image_sha256=hashlib.sha256(image.read_bytes()).hexdigest())
            images[item['id']] = (row, width, height)
            rows.append(row)
        for annotation in data['annotations']:
            if annotation['image_id'] not in images:
                raise ValueError(f'{path}: annotation references unknown image ID')
            if annotation['category_id'] not in categories:
                raise ValueError(f'{path}: annotation references unknown category ID')
            if annotation['category_id'] not in selected:
                ignored += 1
                continue
            row, width, height = images[annotation['image_id']]
            box = annotation['bbox']
            if (not isinstance(box, list) or len(box) != 4 or
                    not all(type(v) in (int, float) and math.isfinite(v) for v in box)):
                raise ValueError(f'Invalid COCO box: {box}')
            x, y, w, h = box
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > width+1e-6 or y+h > height+1e-6:
                raise ValueError(f'Box outside image bounds: {box} in {row["image"]}')
            row['boxes'].append([x/width, y/height, min(1., (x+w)/width), min(1., (y+h)/height)])
            row['scores'].append(1.0)
        provenance.append(dict(file=str(path), sha256=hashlib.sha256(content).hexdigest()))
    if not rows:
        raise ValueError('No images in the supplied COCO files')
    metadata = dict(format='face-annotations-v1', input=str(source), annotation_source='coco',
                    category=category, sources=provenance, images=len(rows),
                    with_faces=sum(bool(r['boxes']) for r in rows), errors=0)
    out.mkdir(parents=True, exist_ok=False)
    (out/'labels.json').write_text(json.dumps(rows, indent=2)+'\n')
    (out/'collection.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(f'Imported {len(rows)} images from {len(files)} COCO files; boxes={sum(len(r["boxes"]) for r in rows)}; '
          f'without boxes={sum(not r["boxes"] for r in rows)}; other-class boxes skipped={ignored}')
    print(f'All images pending review. Collection: {out}')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='Roboflow export directory or one COCO JSON file (images relative to JSON)')
    parser.add_argument('--out', required=True, type=Path, help='New annotation collection')
    parser.add_argument('--category', default='face', help='COCO category to import as face (default: face; case-insensitive)')
    args = parser.parse_args()
    try:
        import_coco(args.input, args.out, args.category)
    except (ValueError, OSError, KeyError, TypeError, cv2.error) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
