"""Load train/validation records from an autolabel dataset.json."""
import json
import random
from pathlib import Path
import cv2
import numpy as np
from torch.utils.data import Dataset
from model import preprocess, targets


class Faces(Dataset):
    def __init__(self, manifest, split, augment=False):
        self.path = Path(manifest).resolve()
        self.records = json.loads(self.path.read_text())
        if not isinstance(self.records, dict) or self.records.get('format') != 'tinyface-dataset-v1':
            raise ValueError('Expected a tinyface-dataset-v1 manifest')
        self.records = self.records.get(split)
        self.augment = augment
        if not isinstance(self.records, list) or not self.records:
            raise ValueError('Manifest must be a nonempty list')
        for row in self.records:
            if not isinstance(row['boxes'], list):
                raise ValueError('boxes must be a list (empty for negative images)')
            for box in row['boxes']:
                if len(box) != 4 or not np.isfinite(box).all():
                    raise ValueError(f'Invalid box: {box}')
                x1,y1,x2,y2 = box
                if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                    raise ValueError(f'Expected normalized xyxy: {box}')

    def image_paths(self):
        return {(self.path.parent / r['image']).resolve() for r in self.records}

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        row = self.records[index]
        image = cv2.imread(str(self.path.parent / row['image']))
        if image is None:
            raise ValueError(f"Cannot read image: {row['image']}")
        boxes = np.asarray(row['boxes'], dtype=np.float32).reshape(-1,4).copy()
        if self.augment:
            if random.random() < .5:
                image = cv2.flip(image, 1)
                boxes[:, [0,2]] = 1-boxes[:, [2,0]]
            image = np.clip(image.astype(np.float32)*random.uniform(.7,1.3)
                            + random.uniform(-15,15), 0,255).astype(np.uint8)
        score, distances = targets(boxes)
        return preprocess(image), score, distances, boxes


def collate(batch):
    import torch
    x, score, distances, boxes = zip(*batch)
    return torch.stack(x), torch.stack(score), torch.stack(distances), boxes
