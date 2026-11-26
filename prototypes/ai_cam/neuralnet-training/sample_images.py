"""Copy a random sample of raw images into a new directory for annotation."""
import argparse
from pathlib import Path
import random
import shutil


EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def sample_images(source, out, count, seed=None):
    source, out = Path(source).resolve(), Path(out).resolve()
    if not source.is_dir():
        raise ValueError(f'Not an image directory: {source}')
    if count < 1:
        raise ValueError('Count must be positive')
    if out.exists() or out.is_relative_to(source):
        raise ValueError('Output must be a new directory outside the input tree')
    images = sorted(p for p in source.rglob('*')
                    if p.is_file() and p.suffix.lower() in EXTENSIONS)
    if not images:
        raise ValueError('No supported images found')
    selected = random.Random(seed).sample(images, min(count, len(images)))
    out.mkdir(parents=True, exist_ok=False)
    for image in selected:
        # Preserve subdirectories to avoid collisions between identical filenames.
        target = out/image.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, target)
    print(f'Available: {len(images)}; requested: {count}; copied: {len(selected)}')
    print(f'Raw sample: {out}')
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--count', required=True, type=int)
    parser.add_argument('--seed', type=int, help='Optional seed to repeat the same selection')
    args = parser.parse_args()
    try:
        sample_images(args.input, args.out, args.count, args.seed)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
