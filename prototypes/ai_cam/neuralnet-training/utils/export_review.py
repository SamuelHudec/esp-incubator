"""Export real-image annotations as viewable PNG copies without changing labels."""
import argparse
import json
import math
from pathlib import Path

import cv2


def export_review(data, output):
    labels = data / 'labels.json'
    records = json.loads(labels.read_text())
    real = [(i, row) for i, row in enumerate(records, 1)
            if row.get('dataset_source') == 'real']
    if not real:
        raise ValueError('No real images found in labels.json; use a mixed autolabel run')
    output.mkdir(parents=True, exist_ok=False)
    saved = empty = 0
    errors = []
    for index, row in real:
        source = (labels.parent / row['image']).resolve()
        try:
            image = cv2.imread(str(source))
            if image is None:
                raise ValueError('Unreadable image')
            height, width = image.shape[:2]
            for box in row['boxes']:
                if (len(box) != 4 or not all(math.isfinite(v) for v in box)
                        or not 0 <= box[0] < box[2] <= 1
                        or not 0 <= box[1] < box[3] <= 1):
                    raise ValueError(f'Invalid normalized box: {box}')
                x1, y1, x2, y2 = box
                start = (round(x1 * (width - 1)), round(y1 * (height - 1)))
                end = (round(x2 * (width - 1)), round(y2 * (height - 1)))
                cv2.rectangle(image, start, end, (0, 165, 255), max(1, round(width / 320)))
            # Prefix is the 1-based record number in labels.json, avoiding name collisions.
            destination = output / f'{index:06d}_{source.stem}.png'
            if not cv2.imwrite(str(destination), image):
                raise ValueError('Could not write output image')
            saved += 1
            empty += not row['boxes']
        except (ValueError, TypeError, cv2.error) as exc:
            errors.append(f'Record {index}, {source}: {exc}')
    print(f'Saved {saved}/{len(real)} real images to {output} ({empty} without boxes).')
    if errors:
        (output / 'errors.txt').write_text('\n'.join(errors) + '\n')
        raise ValueError(f'{len(errors)} images failed; see {output / "errors.txt"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, type=Path,
                        help='Mixed autolabel directory containing labels.json')
    parser.add_argument('--out', type=Path, help='New output directory; default: DATA/review-images')
    args = parser.parse_args()
    try:
        export_review(args.data, args.out or args.data / 'review-images')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
