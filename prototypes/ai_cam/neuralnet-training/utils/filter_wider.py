"""Extract WIDER FACE images with exactly one valid annotated face, into one flat image collection."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

import cv2
import numpy as np

REVISION = '833d07e7bf3860f294242312fe95eed0561eeb17'
HASHES = {
    'wider_face_split.zip': 'c7561e4f5e7a118c249e0a5c5c902b0de90bbf120d7da9fa28d99041f68a8a5c',
    'WIDER_train.zip': 'e23b76129c825cafae8be944f65310b2e1ba1c76885afe732f179c41e5ed6d59',
    'WIDER_val.zip': 'f9efbd09f28c5d2d884be8c0eaef3967158c866a593fc36ab0413e4b2a58a17a',
}


def annotations(text):
    lines = iter(text.splitlines())
    for name in lines:
        if not name.strip():
            continue
        count = int(next(lines))
        # WIDER includes a dummy zero row for zero-face images.
        boxes = [list(map(int, next(lines).split())) for _ in range(max(1, count))]
        yield name, boxes[:count]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archives', type=Path, default=Path('data/wider-cache'))
    parser.add_argument('--out', type=Path, default=Path('data/wider-single-face'))
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Output already exists; choose a new directory')
    for name, expected in HASHES.items():
        with (args.archives/name).open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            parser.error(f'Checksum mismatch: {name}')
    args.out.mkdir(parents=True)
    summary = {}
    with zipfile.ZipFile(args.archives/'wider_face_split.zip') as labels:
        for split in ('train', 'val'):
            counts = Counter()
            text = labels.read(f'wider_face_split/wider_face_{split}_bbx_gt.txt').decode()
            with zipfile.ZipFile(args.archives/f'WIDER_{split}.zip') as images:
                for name, boxes in annotations(text):
                    counts['total'] += 1
                    if len(boxes) != 1:
                        counts['not_single_face'] += 1
                        continue
                    x, y, w, h, blur, expression, illumination, invalid, occlusion, pose = boxes[0]
                    if invalid or w <= 0 or h <= 0:
                        counts['invalid'] += 1
                        continue
                    path = PurePosixPath(name)
                    if path.is_absolute() or '..' in path.parts:
                        raise ValueError('Unsafe archive path')
                    content = images.read(f'WIDER_{split}/images/{name}')
                    image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
                    if image is None:
                        raise ValueError(f'Unreadable selected image: {name}')
                    height, width = image.shape[:2]
                    bounds = [max(0,x), max(0,y), min(width,x+w), min(height,y+h)]
                    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                        counts['outside_image'] += 1
                        continue
                    destination = args.out / f'{split}__{path.name}'
                    with destination.open('xb') as stream:
                        stream.write(content)  # Original JPEG, no recompression.
                    counts['selected'] += 1
            summary[split] = dict(counts)
            print(split, dict(counts), flush=True)
    (args.out/'summary.json').write_text(json.dumps(dict(
        source=f'https://huggingface.co/datasets/CUHK-CSE/wider_face/tree/{REVISION}',
        license='CC BY-NC-ND 4.0 (as stated by source repository)',
        filter='Exactly one original annotation; valid flag; positive box intersecting image. No brightness/size filtering.',
        archives_sha256=HASHES, splits=summary), indent=2)+'\n')
    (args.out/'README.md').write_text('''# WIDER FACE: single-face subset

Original JPEG images with exactly one annotated face, excluding invalid boxes.
All images are in this directory; original splits are combined.
Annotations are used only for filtering and are not exported.
No YuNet relabeling, cropping or brightness filtering was applied.

Source: https://huggingface.co/datasets/CUHK-CSE/wider_face
Authors: Shuo Yang, Ping Luo, Chen Change Loy, Xiaoou Tang (CVPR 2016).
Source license: CC BY-NC-ND 4.0. See summary.json for pinned revision and checksums.

Use this directory as input to autolabel.py. It is no longer an official
WIDER train/validation benchmark split. One annotation does not guarantee that
no unannotated face appears in the scene.
''')


if __name__ == '__main__':
    main()
