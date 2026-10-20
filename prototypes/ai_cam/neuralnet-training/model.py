"""Fixed-shape face detector. No pretrained weights or inference framework export."""
import cv2
import numpy as np
import torch
from torch import nn

WIDTH, HEIGHT, STRIDE = 128, 96, 8


class TinyFace(nn.Module):
    def __init__(self):
        super().__init__()
        def conv(ci, co, kernel, stride=1, groups=1):
            return [nn.Conv2d(ci, co, kernel, stride, kernel // 2,
                              groups=groups, bias=False),
                    nn.BatchNorm2d(co), nn.ReLU()]
        layers = conv(1, 8, 3, 2)
        for ci, co, stride in [(8, 16, 2), (16, 24, 2), (24, 32, 1),
                               (32, 32, 1), (32, 32, 1)]:
            layers += conv(ci, ci, 3, stride, ci) + conv(ci, co, 1)
        self.backbone = nn.Sequential(*layers)
        self.head = nn.Conv2d(32, 5, 1)
        nn.init.constant_(self.head.bias, 0)
        with torch.no_grad():
            self.head.bias[0] = -4.6  # Low initial foreground probability.
            self.head.bias[1:] = 0.2  # Positive normalized box distances.

    def forward(self, x):
        return self.head(self.backbone(x))


def preprocess(image):
    """BGR -> gray -> direct 128x96 resize -> float32 [0,1], CHW."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)
    return torch.from_numpy(gray.astype(np.float32) / 255.0).unsqueeze(0)


def targets(boxes):
    """Center-cell assignment; smallest box wins collisions. Input normalized xyxy."""
    score = torch.zeros(HEIGHT // STRIDE, WIDTH // STRIDE)
    distances = torch.zeros(4, *score.shape)
    # Grid reference is (cell + .5)*stride; signed distances allow tiny boxes
    # whose assigned grid reference falls just outside their boundaries.
    for x1, y1, x2, y2 in sorted(boxes, key=lambda b: -(b[2]-b[0])*(b[3]-b[1])):
        ix = min(15, int((x1+x2)*0.5*16))
        iy = min(11, int((y1+y2)*0.5*12))
        cx, cy = (ix+.5)/16, (iy+.5)/12
        score[iy, ix] = 1
        distances[:, iy, ix] = torch.tensor([cx-x1, cy-y1, x2-cx, y2-cy])
    return score, distances


def loss_fn(pred, score, distances, return_parts=False):
    logits = pred[:, 0]
    probability = logits.sigmoid()
    bce = nn.functional.binary_cross_entropy_with_logits(logits, score, reduction='none')
    pt = torch.where(score.bool(), probability, 1-probability)
    alpha = torch.where(score.bool(), 0.75, 0.25)
    positives = score.sum().clamp_min(1)
    classification = (alpha * (1-pt).square() * bce).sum() / positives
    regression = nn.functional.smooth_l1_loss(pred[:, 1:], distances, reduction='none', beta=.05)
    regression = (regression * score[:, None]).sum() / positives
    total = classification + 5 * regression
    return (total, classification, regression) if return_parts else total


def iou(box, boxes):
    if len(boxes) == 0:
        return np.empty(0)
    lo = np.maximum(box[:2], boxes[:, :2])
    hi = np.minimum(box[2:], boxes[:, 2:])
    intersection = np.maximum(hi-lo, 0).prod(axis=1)
    area = np.maximum(box[2:]-box[:2], 0).prod()
    areas = np.maximum(boxes[:, 2:]-boxes[:, :2], 0).prod(axis=1)
    return intersection / np.maximum(area + areas - intersection, 1e-9)


def decode(pred, threshold=.5, nms=.3):
    """Return normalized xyxy + score, greedy NMS, highest score first."""
    pred = pred.detach().float().cpu()
    scores = pred[0].sigmoid().numpy()
    candidates = []
    for y, x in zip(*np.where(scores >= threshold)):
        l, t, r, b = pred[1:, y, x].numpy()
        cx, cy = (x+.5)/16, (y+.5)/12
        box = np.clip([cx-l, cy-t, cx+r, cy+b], 0, 1)
        if box[2] > box[0] and box[3] > box[1]:
            candidates.append([*box, scores[y, x]])
    remaining = sorted(candidates, key=lambda b: -b[4])
    kept = []
    while remaining:
        best = np.asarray(remaining.pop(0))
        kept.append(best)
        if remaining:
            remaining = [b for b, overlap in zip(remaining, iou(best[:4], np.asarray(remaining)[:, :4])) if overlap <= nms]
    return np.asarray(kept, dtype=np.float32).reshape(-1, 5)


def load_model(path, device='cpu'):
    checkpoint = torch.load(path, map_location='cpu', weights_only=True)
    if checkpoint.get('architecture') != 'tinyface-v1':
        raise ValueError('Unsupported checkpoint architecture')
    model = TinyFace().to(device)
    model.load_state_dict(checkpoint['model'])
    return model.eval()
