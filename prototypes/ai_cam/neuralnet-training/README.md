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

## Data preparation: annotate once, review once, mix many times

Annotation collections and training datasets are separate directories. Collections
hold reusable `labels.json`; training datasets contain a snapshot `dataset.json`
with train/val/test. Original images stay in place. Creating a new experiment
never edits a collection, reruns its teacher, or changes an existing dataset.

### 1. Raw images → annotated collection

If you already have COCO bounding-box annotations (for example a Roboflow export),
import them instead of running a detector:

```bash
uv run import_coco.py --input data/roboflow-export --out data/annotations-roboflow
uv run annotator/annotate.py --data data/annotations-roboflow
```

The importer finds `_annotations.coco.json` recursively, including in `train`,
`valid` and `test`, or accepts one JSON file as `--input`. Image paths are relative
to each JSON file. It converts COCO pixel `[x, y, width, height]` boxes to our
normalized corners, validates image dimensions and preserves multiple faces.
The default category is `face` (case-insensitive); use `--category NAME` for another
name. Other classes are skipped and counted. Every image starts **pending review**,
including images without matching boxes. Scores of 1.0 are placeholders for
imported annotations, not detector confidence or review approval.

The new collection references original images without copying or changing them.
Keep the export directory available. Existing output directories are refused.
Original COCO splits are combined for review; `create_dataset.py` later creates
new splits from reviewed records. Do not treat this remix as the original benchmark
split. After review, use this collection with the existing filtering/mixing flow.

To select raw images before annotation, optionally create a random sample:

```bash
uv run sample_images.py --input data/synthetic --count 500 --out data/synthetic-sample
```

This copies images from the input and its subdirectories, preserving relative
paths and leaving originals untouched. Only image files are copied. The output
must be new and outside the input tree. If fewer images are available, all are
copied and counts are printed. Add `--seed 42` for a repeatable selection;
otherwise each run uses a fresh random selection. Use the output as the input
to `annotate_data.py`.

Annotate the camera and each additional source independently:

```sh
uv run annotate_data.py --input /absolute/path/to/camera-photos --detector retinaface --out data/annotations-camera
uv run annotate_data.py --input data/wider-single-face --detector retinaface --out data/annotations-wider
```

This processes **all** supported images recursively. Sampling belongs to step 3.
It writes `labels.json`, `collection.json` (teacher settings and initial counts),
and an incrementally flushed `detections.jsonl`. Errors stay on their image records,
without separate duplicate reports. Every image stays in labels, including
teacher misses and errors; all start unreviewed. No training splits are created.
Output must be outside the raw input tree. **Rerun the same command with the same
input/output to add images**: existing successful annotations (including empty
teacher detections and human-reviewed records) are skipped; new and failed images
are processed. No extra resume flag is needed. A no-op does not load the detector.
The console reports completed, new, retry and missing counts.

Completed results are journaled as they finish and labels are saved atomically.
Interrupted runs recover completed journal entries; reviewed labels always take
precedence. New detections remain pending review. Do not run the editor while
annotating: concurrent edits are preserved and annotation asks you to rerun after
closing it. Two annotation processes cannot write the same collection together.

Existing collections must match the input directory and detector/threshold/size.
Use a new output for a different teacher configuration. Do not replace completed
source images in place: new records have content hashes and changed images are
reported instead of silently keeping stale boxes. Older records without hashes
are recognized by their resolved paths and cannot detect earlier content changes.
Missing source records are retained, never automatically deleted. Collections
created by the preceding version are supported when they have `collection.json`;
old combined autolabel runs still use their legacy workflow.

YuNet remains the default (`--detector yunet`). RetinaFace ResNet50 runs locally
on CPU through ONNX/OpenCV, downloads about 109 MB once and verifies its checksum.
Both default to threshold 0.8. RetinaFace requires `--size 640` and pads without
stretching. Teacher revision/hash/settings are recorded in `collection.json`.
The teacher settings and quantization process are unchanged by this refactor.

For every collection, top-level input folders are recorded as potential groups; nested folders
belong to their top-level group. Files in a flat root share `__root__`. Keep
related frames and paired light conditions together. Extra sources are sampled
by image; group related identities manually or use an independently collected
holdout when needed. No automatic near-duplicate or identity detection is claimed.

### 2. Review the collection

```sh
uv run annotator/annotate.py --data data/annotations-camera
uv run annotator/annotate.py --data data/annotations-wider
```

The [existing editor](annotator/README.md) retains drawing/moving/resizing boxes,
keyboard navigation, the zero/multiple-box filter and bulk confirmation. Edits
are saved to the collection, with `labels.before-review.json` as backup.
A confirmed empty annotation is a negative example. A teacher miss remains
unreviewed until checked. Bulk confirmation accepts existing boxes (including
empty ones); it is a user decision, not an independent quality guarantee.

There is **no finalize step** in this workflow. Reviewed records are ready for
mixing. Pending/error records are excluded and counted explicitly for every
source; the builder rejects invalid boxes or missing reviewed files. Selected
images must be readable. Review additional records later and create another
training snapshot; previous experiments remain intact.

### Optional: filter out images with small faces

```bash
uv run filter_annotations.py --data data/annotations-wider --min-face-ratio 1/30 --out data/annotations-wider-min30
```

The threshold is the largest face bounding-box area divided by the whole image
area, independent of resolution. `1/30` means at least one thirtieth (about 3.33%)
of the image; decimals such as `0.05` (5%) also work. The default is `1/30`, and
an exact match passes. With multiple faces, only the largest decides whether to
keep the image; areas are not summed and all boxes are preserved. Images with no
boxes are kept, with review status unchanged. Add `--exclude-empty` to remove
images without boxes as well (including reviewed negatives).

The output references the original images and preserves review work; it does not
modify the source. `filter.json` records the rule and removed images. Use the
filtered directory as an input to the mixing step below. Add new raw images to
the original annotation collection, then filter again into a new output directory.

### 3. Mix reviewed collections and split in one command

```sh
uv run create_dataset.py --real-data data/annotations-camera --extra-data data/annotations-wider --count 1000 --out data/train-1000
```

Collections have no permanent real/extra role: choose their role only here.
One optional `--real-data` collection has priority. `--extra-data` accepts any
number of reviewed sources, e.g. `--extra-data data/annotations-wider
data/annotations-other`. Extras are sampled uniformly from their combined unique
image pool; a larger collection will generally contribute more. No per-source
weights are applied. You can also repeat the `--extra-data` flag; all its paths
are combined. Either camera-only or extra-only experiments are supported.

`--count` is the **total** across train/val/test. If 150 reviewed camera images
are available and count is 1000, take all 150 and fill with 850 extra images.
If camera images alone exceed count, sample only camera images. If fewer images
exist, use all eligible images and print actual counts. Omit count to use all.

Default seed is 42. Selection uses stable seeded image-content ranks, so larger
counts extend smaller selections when the source pool and seed are unchanged.
Console and `summary.json` report available, reviewed, pending, duplicate and
selected counts per source, plus real/extra counts per split.

Exact byte-identical images are deduplicated across collections, with camera
priority. Conflicting reviewed boxes for the same content are an error; choose
consistent source collections or reconcile the annotations. Dataset rows record
image SHA-256, collection provenance and copied annotations; collection label
hashes are saved. Images themselves are referenced, not copied: moving or editing
originals can invalidate a snapshot. Creating datasets requires no teacher model,
network access or training.

Splitting defaults to `--val-fraction 0.2`, `--test-count 16`, `--split-mode auto`:
with at least three selected camera groups, whole groups stay in separate splits;
otherwise a visible warning accompanies image-level random splitting, preserving
the existing flat-folder workflow. Use **`--split-mode group`** to require group
isolation and fail rather than fall back. `--split-mode image` explicitly requests
image-level splitting. Whole groups may exceed split-size targets. Random splits
can leak similar frames and need not include camera images in the small test set.

Each build creates its own train/val/test split. The same inputs, count and seed
reproduce the selection and splits. Changing the sample size can change validation
and test images as well. Equal epochs mean more optimizer updates on larger datasets.

### Reuse existing reviewed work

Older standalone collections with a stored `kind` are accepted in either role;
that old tag is ignored and their files are not rewritten. Old mixed-run
`labels.json` files are accepted directly. A legacy mixed directory
passed as `--real-data` contributes its real rows; as `--extra-data` it contributes
its non-real rows. Only reviewed entries are eligible in the new workflow, even
positive teacher boxes. For example, reuse already reviewed work without rerunning
RetinaFace or modifying its old `dataset.json`:

```sh
uv run create_dataset.py --real-data data/mixed-retinaface-5000 --extra-data data/mixed-retinaface-5000 --count 1000 --out data/remixed-1000
```

Several old runs may be supplied as extras; identical images are deduplicated,
and annotation conflicts are reported rather than silently choosing a version.
The editor still recovers missing records from old `review_no_faces.json` files.
Review/save these collections before mixing if those records should be included.

`autolabel.py` remains a **legacy compatibility command** for earlier scripts and
`--finalize` runs. The new workflow does not import or call that combined script.
Existing training manifests, checkpoints and exports remain usable.

## Train

```sh
uv run train.py --data data/train-1000
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
uv run train.py --data data/train-1000 --evaluate runs/train-1000/best.pt
uv run infer.py --checkpoint runs/train-1000/best.pt --source data/example.jpg --output runs/train-1000/example.jpg
uv run infer.py --checkpoint runs/train-1000/best.pt --source http://ai-cam.local/
```

Evaluation uses the validation split. Inference defaults to CPU; use
`--device mps` or `--device cuda` to override. `--source 0` selects a webcam.
Close other ESP32 stream viewers and press `q` to exit live preview.
Desktop timing is not ESP32 timing; preview has no tracking or reconnect logic.

## Quantize and install the firmware model

```sh
uv run quantize.py --checkpoint runs/train-1000/best.pt --data data/train-1000
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
uv run python -m utils.verify_pipeline --export runs/train-1000/int8 --data data/train-1000
```

Tests live in `tests/`, supporting tools in `utils/`, and the C runtime in
`../firmware/neuralnet/`. Tests check implementation correctness, not face quality.
Use `--help` on each script for additional options.

Next experiments: [data and architecture plan](../docs/architecture-experiment-plan.md).

## WIDER FACE single-face collection

`data/wider-single-face/` contains 5,749 original JPEGs in one flat directory,
selected using exactly one valid face annotation. Labels are not exported; use
this folder as input to `annotate_data.py`. Original train/validation images are
combined, so this is no longer an official benchmark split. Download provenance
and source counts are in `summary.json`.

Rebuild from the downloaded archives into a new directory:

```sh
uv run utils/filter_wider.py --archives data/wider-cache --out data/wider-single-face
```

Source: [CUHK-CSE/WIDER FACE](https://huggingface.co/datasets/CUHK-CSE/wider_face),
CC BY-NC-ND 4.0 as stated by the source. The filter checks archive SHA-256 values.
DARK FACE is not included. Images are not cropped, resized or filtered by brightness.
