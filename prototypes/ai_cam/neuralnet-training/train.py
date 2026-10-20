"""Train from scratch and evaluate with one-to-one IoU matching."""
import argparse
import json
import random
import math
from training_report import plot_history
from pathlib import Path
import numpy as np
import cv2
from autolabel import render_montage
import torch
from torch.utils.data import DataLoader
from data import Faces, collate
from model import TinyFace, loss_fn, decode, iou, load_model, preprocess


@torch.no_grad()
def evaluate(model, loader, device, threshold):
    model.eval()
    tp = fp = fn = negative = negative_fp = 0
    loss = cls_loss = box_loss = 0.
    for images, score, distances, boxes in loader:
        pred = model(images.to(device))
        total, cls, box = loss_fn(pred, score.to(device), distances.to(device), return_parts=True)
        loss += total.item()*len(images)
        cls_loss += cls.item()*len(images)
        box_loss += box.item()*len(images)
        for output, truth in zip(pred, boxes):
            detections = decode(output, threshold)
            used = set()
            if len(truth) == 0:
                negative += 1
                negative_fp += int(len(detections) > 0)
            for detection in detections:
                overlaps = iou(detection[:4], truth)
                for index in used:
                    overlaps[index] = -1
                match = int(overlaps.argmax()) if len(overlaps) else -1
                if match >= 0 and overlaps[match] >= .5:
                    used.add(match)
                    tp += 1
                else:
                    fp += 1
            fn += len(truth)-len(used)
    return dict(loss=loss/len(loader.dataset), cls_loss=cls_loss/len(loader.dataset),
                box_loss=box_loss/len(loader.dataset), tp=tp, fp=fp, fn=fn,
                precision=tp/max(tp+fp,1), recall=tp/max(tp+fn,1),
                negative_images=negative, negative_false_positive_images=negative_fp,
                negative_fp_rate=negative_fp/negative if negative else None)


def cosine_factor(step, epochs, minimum_ratio):
    # Epoch 1 uses lr; the final epoch uses min-lr. A one-epoch run uses lr.
    progress = min(step / max(epochs-1, 1), 1.0)
    return minimum_ratio + (1-minimum_ratio)*(1+math.cos(math.pi*progress))/2


def create_run_dir(requested, dataset_name):
    base = Path(requested) if requested else Path('runs')/dataset_name
    candidate = base
    suffix = 2
    while True:
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            if requested:
                raise ValueError(f'Output already exists: {candidate}. Choose a new --out directory.')
            candidate = base.with_name(f'{base.name}-{suffix}')
            suffix += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, help='Autolabel output directory containing dataset.json')
    parser.add_argument('--evaluate', help='Checkpoint to evaluate without training')
    parser.add_argument('--out', help='Custom new output directory; default runs/<dataset-name>[-N]')
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=.001)
    parser.add_argument('--min-lr', type=float, default=.00001, help='Final cosine learning rate')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--device', choices=['auto','cpu','mps','cuda'], default='auto',
                        help='auto selects MPS, then CUDA, otherwise CPU')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--threshold', type=float, default=.5)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.threads < 1 or not 0 < args.threshold < 1:
        parser.error('epochs, batch-size, threads must be positive; threshold in (0,1)')
    if not (math.isfinite(args.lr) and math.isfinite(args.min_lr) and 0 <= args.min_lr <= args.lr and args.lr > 0):
        parser.error('Require finite 0 <= min-lr <= lr and lr > 0')
    data_dir = Path(args.data).resolve()
    if not data_dir.is_dir():
        parser.error('--data must be an autolabel output directory')
    manifest = data_dir / 'dataset.json'
    if not manifest.is_file():
        parser.error(f'Missing {manifest}; run autolabel.py first')
    args.requested_device = args.device
    if args.device == 'auto':
        args.device = ('mps' if torch.backends.mps.is_available() else
                       'cuda' if torch.cuda.is_available() else 'cpu')
    elif args.device == 'mps' and not torch.backends.mps.is_available():
        parser.error('MPS is unavailable in this environment; use --device cpu')
    elif args.device == 'cuda' and not torch.cuda.is_available():
        parser.error('CUDA is unavailable in this environment; use --device cpu')
    print(f'Device: {args.device} (requested: {args.requested_device})', flush=True)
    torch.set_num_threads(args.threads)
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    val = Faces(manifest, split='val')
    val_loader = DataLoader(val, batch_size=args.batch_size, collate_fn=collate)
    if args.evaluate:
        print(json.dumps(evaluate(load_model(args.evaluate, args.device), val_loader, args.device, args.threshold), indent=2))
        return
    train = Faces(manifest, augment=True, split='train')
    test = Faces(manifest, split='test')
    if (train.image_paths() & val.image_paths() or
        test.image_paths() & (train.image_paths() | val.image_paths())):
        raise ValueError('Train, validation and test image paths must not overlap')
    loader = DataLoader(train, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    model = TinyFace().to(args.device)
    print(f'Trainable parameters: {sum(p.numel() for p in model.parameters())}')
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda step: cosine_factor(step, args.epochs, args.min_lr / args.lr))
    out = create_run_dir(args.out, data_dir.name)
    args.out = str(out)
    args.scheduler = 'cosine'
    print(f'Output: {out}', flush=True)
    (out/'config.json').write_text(json.dumps(vars(args), indent=2))
    best = float('inf')
    history = []
    for epoch in range(1, args.epochs+1):
        model.train()
        train_loss = train_cls = train_box = grad_norm = 0.
        epoch_lr = optimizer.param_groups[0]['lr']
        for images, score, distances, _ in loader:
            optimizer.zero_grad(set_to_none=True)
            loss, cls, box = loss_fn(model(images.to(args.device)), score.to(args.device),
                                     distances.to(args.device), return_parts=True)
            if not torch.isfinite(loss):
                raise RuntimeError('Nonfinite training loss')
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 10)
            grad_norm += norm.item()*len(images)
            optimizer.step()
            train_loss += loss.item()*len(images)
            train_cls += cls.item()*len(images)
            train_box += box.item()*len(images)
        metrics = evaluate(model, val_loader, args.device, args.threshold)
        record = dict(epoch=epoch, lr=epoch_lr, train_loss=train_loss/len(train),
                      train_cls_loss=train_cls/len(train), train_box_loss=train_box/len(train),
                      grad_norm=grad_norm/len(train), **metrics)
        history.append(record)
        print(json.dumps(record), flush=True)
        with (out/'metrics.jsonl').open('a') as f:
            f.write(json.dumps(record)+'\n')
        checkpoint = dict(architecture='tinyface-v1', model=model.state_dict(),
                          epoch=epoch, metrics=metrics, config=vars(args))
        torch.save(checkpoint, out/'last.pt')
        if metrics['loss'] < best:
            best = metrics['loss']
            torch.save(checkpoint, out/'best.pt')
        plot_history(history, out/'training_curves.png')
        scheduler.step()

    # Test is used only after selecting best.pt by validation loss.
    model = load_model(out/'best.pt', args.device)
    test_loader = DataLoader(test, batch_size=args.batch_size, collate_fn=collate)
    metrics = evaluate(model, test_loader, args.device, args.threshold)
    metrics['reference'] = 'teacher pseudo-labels, not human ground truth'
    (out/'test_metrics.json').write_text(json.dumps(metrics, indent=2))
    teacher_rows, student_rows = [], []
    with torch.inference_mode():
        for row in test.records:
            source = str((test.path.parent/row['image']).resolve())
            image = cv2.imread(source)
            if image is None:
                raise ValueError(f'Cannot read test image: {source}')
            predictions = decode(model(preprocess(image)[None].to(args.device))[0], args.threshold)
            teacher_rows.append(dict(source=source, boxes=row['boxes'], scores=row['scores']))
            student_rows.append(dict(source=source, boxes=predictions[:,:4].tolist(),
                                     scores=predictions[:,4].tolist()))
    left, right = render_montage(teacher_rows), render_montage(student_rows)
    comparison = np.concatenate([left, right], axis=1)
    banner = np.full((40,comparison.shape[1],3),32,np.uint8)
    for text,x in [('YuNet teacher',8),('TinyFace best.pt',left.shape[1]+8)]:
        cv2.putText(banner,text,(x,27),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),1)
    if not cv2.imwrite(str(out/'test_comparison.jpg'),np.concatenate([banner,comparison])):
        raise RuntimeError('Cannot save test comparison')
    (out/'test_predictions.json').write_text(json.dumps(student_rows,indent=2))
    print(f"Test comparison: {out/'test_comparison.jpg'}", flush=True)


if __name__ == '__main__':
    main()
