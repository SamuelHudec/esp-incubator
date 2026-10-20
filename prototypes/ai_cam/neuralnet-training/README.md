# TinyFace Python experiment

## Purpose and status

2026-10-19: a from-scratch face detector for desktop experiments before any C
implementation or quantization. No trained face model is included. Synthetic
smoke tests verify the code path, not face accuracy. ESP32 firmware is unchanged.

Use Python 3.12. Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. No GPU is required;
Training defaults to `--device auto`: MPS when available on macOS, otherwise
CUDA when available, otherwise CPU. Override with `--device cpu`, `mps`, or `cuda`.
An explicitly requested unavailable accelerator produces a clear error. The selected
device is printed and saved in the run configuration. Inference still defaults to
CPU; pass `--device mps` to `infer.py` to use MPS.

```sh
cd prototypes/ai_cam/neuralnet-training
uv run python -m unittest discover -v
```

`uv run` automatically uses the project `.venv` and synchronizes dependencies;
manual activation is unnecessary. Run commands from this directory. `.python-version`
selects Python 3.12. For strict lockfile checking use `uv run --locked ...`.
`requirements.txt` is a generated compatibility export; update dependencies with
`uv add` and regenerate it with `uv export --format requirements-txt --no-hashes
--output-file requirements.txt`.

The local `.venv`, `data`, and `runs` directories are ignored by the repository's
root `.gitignore`. Store images, checkpoints and annotated outputs there. Do not
commit personal captures or model binaries. Commands below are relative to this
training directory.

## Architecture

`model.py` implements the architecture proposed in the
[research notes](../docs/face-detection-research.md). It is an original experimental
graph, inspired by efficient face detection approaches; no UltraFace code or
pretrained weights are copied.

Input: BGR image converted with OpenCV to grayscale, resized directly to 128x96
with INTER_AREA, converted to float32 [0,1]. Non-4:3 inputs are stretched; box
coordinates use normalized x/y values so they map back to the original image.

- 3x3 convolution, stride 2: 1 -> 8 channels.
- Depthwise 3x3 + pointwise 1x1 blocks: 8 -> 16 (stride 2), 16 -> 24
  (stride 2), 24 -> 32, 32 -> 32, 32 -> 32.
- Batch normalization and ReLU after each hidden convolution.
- Linear 1x1 head: 32 -> 5 channels on a 16x12 grid.

Kernel weights: 4,568; convolution MACs: 1,199,616. Total trainable parameters:
5,085 including batch normalization and head biases. Training also includes batch
normalization parameters and head biases; these are not an INT8 footprint.
Receptive field: 63x63 input pixels. This is intentionally small and unproven.

The five head channels are face logit and left/top/right/bottom distances,
normalized by image width/height from grid reference `(column+.5)/16,
(row+.5)/12`. Distances are **linear and signed** to represent small boxes whose
assigned reference falls outside the box. Decode clips boxes to the image and
rejects nonpositive width/height. A sigmoid is applied only to the face score.
Greedy NMS uses IoU 0.3. One face center is assigned per cell; the smallest box
wins collisions. Crowded/tiny faces are a known limitation of this single-scale
baseline. The full annotated boxes remain in evaluation, so collisions are not
silently removed from recall denominators.

Training uses focal binary cross-entropy plus 5x smooth-L1 box loss at positive
cells, AdamW, gradient clipping, random horizontal flips and brightness/contrast
augmentation. Learning rate follows an epoch-wise cosine schedule; multi-scale augmentation
is not implemented.

## Step zero: automatic labels for an existing image collection

`autolabel.py` selects a reproducible random subset from a directory (recursive),
downloads the official [OpenCV YuNet model on Hugging Face](https://huggingface.co/opencv/face_detection_yunet),
and runs face detection locally using the already installed OpenCV. No additional
packages or Hugging Face account are required. Images are not uploaded. The model
and its MIT license are cached locally; the script pins repository revision
`3cc26e7f1014a5ee5d74a42acee58bafc9d0a310` and records the model SHA-256.

```sh
uv run autolabel.py --input /absolute/path/to/synthetic-faces --count 1000 --seed 42 --out data/autolabel-1000
```

- `--count`: optional number to sample without replacement, before detection.
  Omit it to process all supported images recursively in sorted path order. If fewer
  images exist than the specified count, use all available images. Supported: JPG/JPEG, PNG, BMP, WebP.
- `--seed`: reproduces subset selection for the same sorted input file list.
- `--test-count`: fixed held-out comparison sample size (default 16, range 1–100).
  Small datasets reserve at least one training and one validation image.
- `--val-fraction`: validation fraction (default 0.2); the seed also fixes the split.
  At least three positive labeled images are needed to create `dataset.json`.
- `--threshold`: minimum teacher score (default 0.8); higher values may miss more
  faces. This score is not calibrated label correctness.
- `--size`: detector's longest image side (default 640), keeping aspect ratio.
  Larger values can help small faces but cost time; very large faces may need a
  smaller value. This setting is independent of the student's 128x96 input.
- `--cache`: optional model cache directory. Default is inside ignored `data/`.

The script enumerates filenames, then decodes only selected images one at a time.
It does not copy or modify originals. Output must be a new directory outside the
input tree, so reruns cannot overwrite reviewed labels or sample generated previews.
An unreadable image is reported, not replaced by a different sampled image.

Outputs:

| File | Purpose |
| --- | --- |
| `dataset.json` | Single input with disjoint train/validation/test records |
| `labels.json` | Full positive-image annotations before splitting |
| `review_no_faces.json` | Images with no detections, excluded from training by default |
| `detections.jsonl` | Incrementally saved detections, scores and source paths |
| `selected.json` | Exact sampled source list, including unreadable images |
| `summary.json` | Counts, settings, model revision/hash, duration |
| `errors.json` | Unreadable images or OpenCV errors |
| `test_teacher.jpg` | Fixed held-out images with teacher boxes and scores |

Open `test_teacher.jpg` in an image viewer. Rectangle aspect ratios follow the predicted
face boxes; boxes are not artificially forced square. JSON coordinates refer to
original image dimensions, not thumbnail or detector dimensions. Manifest image
paths are relative to the output directory; moving originals breaks those links.
No YOLO/Ultralytics export is needed for our existing trainer.

These are **pseudo-labels**, not ground truth. A no-detection image in a synthetic
face collection is probably a teacher miss, not a verified negative. Inspect the
misses separately and correct wrong/incomplete boxes before training. A montage
is a spot check, not a measured annotation accuracy score. Multi-face images may
still contain missed faces even when at least one face was labeled.

`dataset.json` stores all three splits and normalized boxes; image paths are relative
 to that file. Originals remain in place. The default split is random by image,
with 16 test images, approximately 20% of the full labeled set for validation,
and the remainder for training, reproducible using `--seed`. For 1,000 positive
images this is 784 train / 200 validation / 16 test. Related synthetic
identities or generation groups can leak across this split; use a group-separated,
manually reviewed validation set for meaningful accuracy claims. Add verified
negative examples when available; teacher misses remain excluded.

With fewer than three positive images autolabeling still exports labels
but does not create a training dataset. A schema tag, split seed and fraction
are saved alongside the records. Existing output directories are not overwritten.

Interrupted runs keep their completed `detections.jsonl` records; automatic resume
is not implemented. Use a new output directory for a complete rerun. Keep outputs
under ignored `data/` or `runs/`, especially when originals contain private images.

## Train and evaluate

```sh
uv run train.py --data data/autolabel-1000 --epochs 100 --batch-size 32
uv run train.py --data data/autolabel-1000 --evaluate runs/autolabel-1000/best.pt
```

`--data` points to the output directory created by `autolabel.py`. The trainer
automatically loads `dataset.json` from that directory. The file contains
train, validation and test records, including image paths and boxes. With
`--evaluate`, the same file's validation split is evaluated without training.

`best.pt` is selected by validation loss, not test metrics. `last.pt` contains the
last model. They store architecture, state dictionary, epoch, configuration and
validation metrics; optimizer state/resuming are not implemented. The trainer
starts from scratch on every invocation. By default output is `runs/<dataset-name>`
(e.g. `runs/autolabel-1000`), followed by `-2`, `-3`, etc. when already present.
Use `--out runs/my-experiment` for an explicit name; an existing explicit directory
is rejected to prevent overwriting or mixing histories.
`config.json` and `metrics.jsonl` record configuration and epoch results.

Evaluation reports precision/recall using score-sorted one-to-one matching at
IoU >= 0.5, TP/FP/FN counts, and the fraction of negative images with at least one
false detection. No negative images means `negative_fp_rate: null`, not zero.
These are fixed-threshold metrics, **not WIDER official AP**. Choose the score
threshold on validation data (`--threshold`); freeze it before testing.

## Inference

```sh
uv run infer.py --checkpoint runs/autolabel-1000/best.pt --source data/example.jpg --output runs/autolabel-1000/example.jpg
uv run infer.py --checkpoint runs/autolabel-1000/best.pt --source 0
uv run infer.py --checkpoint runs/autolabel-1000/best.pt --source http://ai-cam.local/
```

For ESP32 close other stream viewers first (one viewer supported). Use the camera
IP if mDNS fails. Press `q` to exit video preview. Images can be saved headlessly
with `--output`; live preview needs a desktop window. Video is not recorded.
The displayed time covers preprocessing, inference, CPU output transfer and box
decoding, excluding source capture and drawing. It is desktop time, not ESP32
performance. First inference can include warm-up overhead.

This version detects independently on each frame. It does not yet implement
tracking, smoothing, reconnect retries or a latest-frame capture queue. If Python
cannot keep up with MJPEG, capture buffering can make preview lag. Validate
single-image detection first; then measure stream latency before adding tracking.

## Verification and next steps

Run `uv run python -m unittest discover -v` for target/decode round trips, empty
frames, checkpoint reload, finite gradients and a small synthetic overfit test.
The synthetic foreground is a rectangle, not a face. A passing test demonstrates
numerical wiring and learning behavior only.

Next: train on labeled faces, inspect held-out overlays and failure cases, compare
thresholds, and measure accuracy by face size. Widen the network if the tiny
baseline lacks capacity. Only after float accuracy is useful should we freeze
preprocessing and layer semantics, add INT8/export to C arrays and compare a
parallel C inference implementation against Python golden outputs.

2026-10-19 local verification: all three unit tests passed on Python 3.12 /
PyTorch 2.9.1 CPU. A separate temporary-data CLI smoke run completed two training
epochs, checkpoint evaluation, saved image inference and WIDER conversion
(including an empty-image dummy annotation). The short CLI run produced no
detections, as expected for this untrained smoke run; it is not an accuracy test.
Live camera preview and real-face training have not been tested.

## Fixed teacher/student comparison after training

The annotator saves a fixed `test` list inside `dataset.json` and renders those
images in their stored order in `test_teacher.jpg`. Their paths and teacher scores
are retained. The test images are excluded from optimization and checkpoint
selection. Keep the same dataset file across training runs for fair comparisons.

After the final epoch, `train.py` reloads **best.pt** (selected on validation loss),
evaluates the test split, and automatically saves in the training run directory:

- `test_comparison.jpg`: teacher montage on the left, student montage on the right.
- `test_predictions.json`: source paths, predicted normalized boxes and scores.
- `test_metrics.json`: test metrics against the teacher pseudo-labels.

The training threshold controls student detections. Teacher boxes/scores are
loaded from the dataset, not recomputed. This small positive-image sample is a
visual check of agreement, not independent face accuracy or false-positive testing.
Test scores must not guide checkpoint or threshold selection. Related identities
can still leak across image-level splits; a manually reviewed group-separated
holdout is needed for a reliable accuracy claim. Do not edit the source images
between annotation and comparison.

## Learning rate and training diagnostics

Defaults: `--lr 0.001`, `--min-lr 0.00001`, `--epochs 100`. Cosine decay changes
the learning rate once per epoch: the first epoch uses `lr`, the final epoch uses
`min-lr`. A one-epoch run uses `lr`. There is no warm-up or early stopping.
`metrics.jsonl` records the LR actually used, not the next epoch's scheduled value.

`training_curves.png` is updated after each completed epoch, so completed history
is also visible during training:

- Total train/validation loss.
- Train/validation focal classification loss.
- Train/validation Smooth L1 box loss, before its x5 weight.
- Learning rate over epochs.
- Validation precision and recall at the configured score threshold and IoU 0.5.
- Mean batch gradient norm before clipping, with the clipping threshold (10).

Loss curves use image-weighted batch averages; each batch loss is normalized by
its positive cells. Train uses augmentation and training-mode batch normalization;
validation does not, so their losses need not have identical scales or ordering.
Validation metrics measure agreement with pseudo-labels. These plots show the
schedule actually used; they do not compare hypothetical training strategies.

Only `test_comparison.jpg` is written as a test image in the training run. Its
teacher/student panels are assembled in memory. Autolabeling still produces its
fixed `test_teacher.jpg` inside the dataset directory for initial label review.
Older run artifacts are preserved.
