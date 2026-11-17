# AI cam model training

Annotate images with YuNet, train the TinyFace detector, and export INT8 weights
for the [ESP32 firmware](../README.md). The current model uses 128×96 grayscale
input, 5,085 trainable parameters and a single-scale detection head.
See the [architecture reference](../docs/architecture-reference.md) for details.

## Setup

Run commands from `prototypes/ai_cam/neuralnet-training`. Install `uv`; it manages
Python 3.12, dependencies and `.venv` automatically. No environment activation is
needed. Dependencies are pinned in `uv.lock`.

Keep local images in `data/` and results in `runs/`; both are ignored by Git.

## Annotate a collection

```sh
uv run autolabel.py --input /absolute/path/to/images --count 1000 --out data/autolabel-1000
```

The script downloads OpenCV YuNet and runs detection locally. `--count` samples
images recursively; omit it to use all images. `--seed 42` is the default.
The output directory must be new and outside the input tree.

Images stay in their original locations. `dataset.json` contains relative image
paths, boxes and train/validation/test splits; moving the originals breaks them.
Defaults: teacher threshold 0.8, validation fraction 0.2, fixed test sample 16.
At least three positive images are needed to create a dataset.

Inspect `test_teacher.jpg`, `labels.json`, `review_no_faces.json` and
`summary.json`. Teacher misses are excluded, not treated as negative examples.
Labels are predictions and need review; random image splits can leak related
identities or near-duplicate images.

## Mix real camera images with a synthetic pool

```sh
uv run autolabel.py --real-input /absolute/path/to/camera-photos --synthetic-input /absolute/path/to/synthetic-faces --count 1000 --out data/mixed-1000
```

Real images take priority within the total count; synthetic images fill the rest.
Omit `--count` to use both pools in full. Roots must be separate and non-nested.
Organize real images in top-level capture-session folders. A whole folder stays
in one split; at least **three selected real groups** are required. Keep related
frames together. Files directly in the input root form one group.

Mixed runs require review before creating `dataset.json`:

1. Review **every real record in `labels.json`**, including teacher misses.
   Correct boxes using normalized `[x1, y1, x2, y2]` coordinates in [0,1].
2. Use `boxes: []` only for a confirmed negative; fix unreadable images.
3. Set `review_status` to `reviewed`. Preserve paths, sources, groups and records.
4. Finalize without rerunning detection:

```sh
uv run autolabel.py --finalize data/mixed-1000
```

Whole-group splits can exceed requested split sizes. Mixed runs do not create
`test_teacher.jpg`; training produces a reference/student comparison instead.
Keep the manifest fixed across experiments and reserve a separate final holdout
if the test sample is repeatedly used for development.

## Train

```sh
uv run train.py --data data/autolabel-1000
```

`--data` is the folder containing `dataset.json`. Default output:
`runs/<dataset-name>`, then `-2`, `-3`, etc. Use `--out runs/my-experiment` for a
custom new directory. Training starts from scratch; resume is not implemented.

| Setting | Default |
| --- | --- |
| Epochs / batch size | 100 / 32 |
| Optimizer | AdamW |
| Learning rate | Cosine decay from 0.001 to 0.00001 |
| Loss | Focal BCE + 5 × Smooth L1 box loss |
| Device | MPS on supported Macs, otherwise CUDA, otherwise CPU |
| Evaluation score threshold | 0.5 |

Override with `--epochs`, `--batch-size`, `--lr`, `--min-lr`, `--device` or
`--threshold`. There is no warm-up or early stopping.

| Output | Purpose |
| --- | --- |
| `best.pt`, `last.pt` | Best validation-loss model and final model |
| `config.json`, `metrics.jsonl` | Settings and epoch results |
| `training_curves.png` | Losses, learning rate, precision/recall and gradients |
| `test_comparison.jpg` | Fixed reference labels beside student predictions |
| `test_metrics.json`, `test_predictions.json` | Final test evaluation |

Training reloads `best.pt` for the final test. Metrics use IoU 0.5 and the chosen
score threshold; agreement with pseudo-labels is not independent face accuracy.
Choose thresholds on validation data, not the test sample.

## Evaluate and infer

```sh
uv run train.py --data data/autolabel-1000 --evaluate runs/autolabel-1000/best.pt
uv run infer.py --checkpoint runs/autolabel-1000/best.pt --source data/example.jpg --output runs/autolabel-1000/example.jpg
uv run infer.py --checkpoint runs/autolabel-1000/best.pt --source http://ai-cam.local/
```

Evaluation uses the validation split. Inference defaults to CPU; use
`--device mps` or `--device cuda` to override. `--source 0` selects a webcam.
Close other ESP32 stream viewers and press `q` to exit live preview.
Desktop timing is not ESP32 timing; preview has no tracking or reconnect logic.

## Quantize and install the firmware model

```sh
uv run quantize.py --checkpoint runs/autolabel-1000/best.pt --data data/autolabel-1000
```

Requires a local C compiler (`cc`; Xcode Command Line Tools on macOS).
Defaults: 128 training images for calibration, seed 42, validation threshold 0.5.
The exporter checks C/Python parity and evaluates float/INT8 on validation data.
It leaves the test split untouched.

Output is a new `int8/` folder beside the checkpoint (`--out` overrides it):
`nn_model.h`, `golden.npz` and `report.json`. Existing exports are not overwritten.
After successful checks, the model automatically replaces
`../firmware/neuralnet/nn_model.h`. Failure preserves the previous firmware model.
**Compile and upload the Arduino sketch to activate it on the board.**

## Checks and next steps

```sh
uv run python -m unittest discover -s tests -v
uv run python -m utils.verify_pipeline --export runs/autolabel-1000/int8 --data data/autolabel-1000
```

Tests live in `tests/`, supporting tools in `utils/`, and the C runtime in
`../firmware/neuralnet/`. Tests check implementation correctness, not face quality.
Use `--help` on each script for additional options.

Next experiments: [data and architecture plan](../docs/architecture-experiment-plan.md).
