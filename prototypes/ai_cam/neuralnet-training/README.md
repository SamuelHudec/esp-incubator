# AI cam model training

Annotate images with YuNet or RetinaFace, train the TinyFace detector, and export INT8 weights
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

Choose `--detector yunet` (default) or `--detector retinaface` (ResNet50).
Both run locally on CPU using OpenCV. RetinaFace downloads a roughly 109 MB ONNX
model on first use, then reuses its cache; its checksum is verified. Model source:
[clibdev/Pytorch_Retinaface release 1.0.0](https://github.com/clibdev/Pytorch_Retinaface/releases/tag/1.0.0).
`summary.json` records the detector, revision and model hash. Both default to
`--threshold 0.8`; scores are not directly comparable between models. `--size 640`
controls the longest image side. This RetinaFace export requires size 640 and
pads to a square without stretching the image. Existing labels and review/finalize workflows
are unchanged. For example:

```sh
uv run autolabel.py --real-input /absolute/path/to/camera-photos --extra-input data/wider-single-face --detector retinaface --count 1000 --out data/mixed-retinaface-1000
```

The script downloads the selected model and runs detection locally. `--count` samples
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

## Mix camera images with an extra image pool

```sh
uv run autolabel.py --real-input /absolute/path/to/camera-photos --extra-input data/wider-single-face --count 1000 --out data/mixed-1000
```

Camera images take priority within the total count; extra images fill the rest.
The extra pool can contain real photos (such as WIDER FACE) or synthetic images.
New records use `dataset_source: "extra"`; older datasets remain readable.
Omit `--count` to use both pools in full. Roots must be separate and non-nested.
Organize real images in top-level capture-session folders. With at least three real groups, each whole folder stays in one split.
With fewer groups, finalization randomly splits all images using the saved seed;
subfolders are optional. Similar frames can then appear in both training and
evaluation, making metrics optimistic. Files in the input root form one group.

Export full-size annotated copies of all real images for visual review:

```sh
uv run utils/export_review.py --data data/mixed-1000
```

Open `data/mixed-1000/review-images/`. Orange boxes come from `labels.json`;
images with empty annotations have no overlay. PNG names start with the 1-based
record number in `labels.json`, followed by the original filename stem.
Synthetic images are skipped. Originals and annotations are unchanged; this does
not mark images as reviewed or rerun detection. Unreadable images are listed in
`errors.txt` and cause a nonzero exit. Use `--out` for a different new output
folder, including when exporting again after correcting annotations.

Review and edit camera and extra-source annotations in the [local annotation editor](annotator/README.md):

```sh
uv run annotator/annotate.py --data data/mixed-1000
```

Draw, move or resize boxes with the mouse; Delete removes a box. Arrow keys save
and confirm before switching images; Enter confirms the current image. Empty
confirmed boxes mean a reviewed negative. Once all real images are reviewed:

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

## WIDER FACE single-face collection

`data/wider-single-face/` contains 5,749 original JPEGs in one flat directory,
selected using exactly one valid face annotation. Labels are not exported; use
this folder as input to `autolabel.py`. Original train/validation images are
combined, so this is no longer an official benchmark split. Download provenance
and source counts are in `summary.json`.

Rebuild from the downloaded archives into a new directory:

```sh
uv run utils/filter_wider.py --archives data/wider-cache --out data/wider-single-face
```

Source: [CUHK-CSE/WIDER FACE](https://huggingface.co/datasets/CUHK-CSE/wider_face),
CC BY-NC-ND 4.0 as stated by the source. The filter checks archive SHA-256 values.
DARK FACE is not included. Images are not cropped, resized or filtered by brightness.
