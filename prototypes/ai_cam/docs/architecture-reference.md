# TinyFace technical reference and deferred experiments

Reviewed: 2026-10-30. Optional detail for the [three-step plan](architecture-experiment-plan.md).
This file records implementation facts and possible later experiments. It is not
an approved implementation queue. No training, export or hardware test was run.

Code references: [model](../neuralnet-training/model.py),
[trainer](../neuralnet-training/train.py), [data](../neuralnet-training/data.py),
[autolabeler](../neuralnet-training/autolabel.py),
[quantizer](../neuralnet-training/quantize.py) and
[C pipeline](../firmware/neuralnet/nn_pipeline.c).

## What the baseline actually does

`TinyFace`, checkpoint architecture ID `tinyface-v1`, has **5,085 trainable
parameters**, including BatchNorm and head biases. Weights start from scratch;
UltraFace was inspiration, not a source of pretrained weights.

Preprocessing is BGR → grayscale → direct INTER_AREA resize to 128×96 → float
[0,1], CHW. Non-4:3 inputs are stretched. C uses grayscale INT8 [0,127], with
symmetric zero point zero. The exact QVGA 5:2 preprocessing fast path preserves
the Python operation order. Existing generic verification tolerates one INT8
unit of rounding difference; the optimized QVGA path was historically exact on
200 validation images. This does not establish parity for every possible input.

| Stage | Output W×H×C | Stride | Kernel weights | MACs | Theoretical receptive field |
|---|---|---:|---:|---:|---:|
| Conv 3×3, 1→8 + BN/ReLU | 64×48×8 | 2 | 72 | 221,184 | 3 |
| DW 3×3 + PW 1×1, 8→16 | 32×24×16 | 2 | 200 | 153,600 | 7 |
| DW + PW, 16→24 | 16×12×24 | 2 | 528 | 101,376 | 15 |
| DW + PW, 24→32 | 16×12×32 | 1 | 984 | 188,928 | 31 |
| DW + PW, 32→32 | 16×12×32 | 1 | 1,312 | 251,904 | 47 |
| DW + PW, 32→32 | 16×12×32 | 1 | 1,312 | 251,904 | 63 |
| Linear Conv 1×1, 32→5, bias | 16×12×5 | 1 | 160 | 30,720 | 63 |
| Total | | | **4,568** | **1,199,616** | |

Each hidden DW and PW convolution has its own BN/ReLU. Depthwise convolution
filters each channel spatially; pointwise convolution mixes channels. This
separation reduces arithmetic compared with dense spatial convolutions, as in
[MobileNets](https://arxiv.org/abs/1704.04861); the paper does not establish
latency or quality for this ESP32 implementation.

The head produces **5×12×16** values: face logit and signed normalized
left/top/right/bottom distances from `(column+.5)/16, (row+.5)/12`. Distances
are linear, not sigmoid outputs: signed values allow a grid reference just
outside a tiny assigned face. Sigmoid applies only to score. Decoding clips
coordinates, rejects invalid boxes and applies greedy NMS (IoU 0.30).
Firmware threshold is 0.30; Python training/inference/export defaults are 0.50.
Score is not calibrated probability; changing the threshold moves the operating
point and does not improve the trained model.

During training, each face gets only its center cell; the smaller face wins a
collision. Other cells, including cells inside the same face, are classification
negatives. Evaluation still counts every annotated face. A cell has only one
output box, so two faces assigned to it compete for supervision and only the
smaller target survives. Other cells can still produce detections; target
collisions are not a complete recall bound. Grid spacing is 8 input pixels, but
box edges are continuous regressions: stride 8 is not an 8-pixel box-edge limit.
The 63×63 theoretical receptive field limits visible context per prediction;
it is neither a hard maximum box size nor the effective learned receptive field.

Loss = focal-like BCE (gamma 2, positive alpha .75, negative .25) + 5× SmoothL1
(beta .05). Both are normalized by positive-cell count clamped to at least one;
regression is positive-only. Negative-only batches therefore have different
normalization pressure and need monitoring. [Focal Loss](https://arxiv.org/abs/1708.02002)
addresses easy-negative imbalance; it does not replace representative negative
images. Training defaults: AdamW weight decay 1e-4, batch 32, 100 epochs,
cosine LR .001→.00001, gradient clipping 10, seed 42. Augmentation: horizontal
flip and modest intensity gain/offset, not geometric scale augmentation or a
camera noise model. Auto device chooses MPS, then CUDA, then CPU. Best checkpoint
uses validation loss. There is no resume/fine-tune CLI, warm-up or early stopping;
every normal training invocation constructs a fresh model.

### What the data and metrics establish

The reported source pool is about 100,000 synthetic faces; initial training used
1,000 selected images. `--count N` randomly samples before annotation; omitting
it processes all images. YuNet positives alone enter the default dataset;
no-detection images go to `review_no_faces.json`. **Teacher misses are not verified
negatives.** Even a positive image may contain additional unlabeled faces, which
would incorrectly become background. `Faces` already accepts `boxes: []`, and
`train.py` reports negative-image false-positive rate, but default autolabel output
does not supply these negative examples.

Default split for 1,000 labeled images is 784/200/16 train/val/test, random by
image, not by identity/session. The trainer checks path overlap, not copied images,
near duplicates or related identities. `test_teacher.jpg` and
`test_comparison.jpg` help inspection but are a tiny teacher-agreement sample.
YuNet pseudo-labels are not independent human ground truth.

Historical `autolabel-1000-4` export: 200 teacher-val images, score .5, IoU .5;
float precision/recall 91.43/78.43%, INT8 89.30/81.86%. This is neither real-camera
accuracy nor evidence that quantization improves quality. The user also exported
run -3; the checkpoint actually on the board during timing observations is
unknown. Do not infer its identity from these run names.

### Quantization and deployed cost

BN folds into convolution. Weights use symmetric per-output-channel INT8;
hidden activations use per-tensor scales; the five final channels use separate
scales. Bias/accumulation use INT32; requantization uses INT64 with ties-away
rounding and checked bounds. Calibration currently uses maxima over a random
training subset (default 128). Export emits `nn_model.h`, `report.json` and
`golden.npz`, verifies C/Python layers and **automatically replaces the local
firmware model header atomically**, even with custom `--out`. Do not invoke this
CLI merely to inspect a candidate: use a future isolated/no-install evaluation
path or isolated checkout. No exporter was run for this plan.

Historical folded integer parameters: 7,700 B, including 4,568 B convolution
weights; two 24,576 B activation buffers total 49,152 B. Firmware places the input
in an activation buffer; do not add a fictitious separate input allocation to that
implementation. Additional allocations include 230,400 B QVGA BGR and a 65,536 B
JPEG slot, decoder workspace, boxes, stacks and camera/network buffers. Roughly
4 MB PSRAM is not a guarantee of sufficient contiguous allocations/internal RAM.

Observed optimized latency: approximately 350–370 ms total, JPEG 110–115 ms,
preprocessing 33–37 ms, network 198–211 ms, about 2.5 completed inferences/s.
Earlier total was about 836 ms. L0 costs about 72 ms; depthwise layers together
about 70 ms. These generic paths remain optimization candidates in the separate
runtime workstream. Parameter counts/MACs are not ESP latency measurements.

Inference is sequential on CPU1 with between-layer yields, accepting a free slot
without a queue. About 23 video FPS does not mean inference on every frame.
Historical CPU0/1 occupancy was about 22%/91%; stream comparison was 25.24 FPS
without and 23.06 with inference. Network/hotspot issues remain unresolved and
must not be interpreted as detector quality or guaranteed throughput.

## Optional experiments: choose one after diagnosing the failure

All comparisons use fixed real development images, human-reviewed boxes and the
same threshold-selection rule. Keep a separate final holdout. Change only the
named experimental setting; record its unavoidable side effects. Small gains
require repeated paired runs before a deployment decision.

Cost: **small** = analysis/calibration; **medium** = a matched training comparison;
**large** = training plus graph/export/C integration and hardware verification.
Data-only changes preserve the network's deployed arithmetic and tensor memory;
postprocessing time can still vary with the number of detections.

| Experiment / evidence needed | Single change and hypothesis | Python / export / C work | Resource expectation and stop condition |
|---|---|---|---|
| Real-data mix / float misses real faces | Replace some synthetic training positives with reviewed real positives; test transfer to this camera. | New equal-length manifest; same model, exporter and C. **Medium**, annotation dominates. | Same network cost. Stop if held-out real misses do not improve at comparable false detections, or improvement is only on training people/scenes. |
| Verified negatives / observed false alarms | Replace 25% of training records with confirmed empty scenes; test background rejection. | Empty boxes already supported. Keep total record count and training settings; monitor classification loss normalized by positive cells. Same exporter/C. **Medium**. | Same network cost; fewer positive examples is an explicit tradeoff. Stop if false alarms do not improve or useful face recall falls. This is a composition test, not proof that negative content alone caused the change. |
| Calibration / float clearly better than INT8 | Keep weights fixed; replace the 128 calibration images with 128 training-only images covering relevant light/scene conditions. Test clipping and overly coarse quantization steps. | Explicit calibration selection and isolated/no-install export; same C arithmetic. **Small**, no training. | Same graph/RAM. Stop if the real-dev float–INT8 gap does not narrow; do not keep changing ranges based on final test results. |
| Wider late layers / persistent underfitting after label and training checks | Change 24→32→32→32 to 24→48→48→48, head 48→5. Test capacity without changing spatial geometry. | New architecture ID/model loader; regenerate folded graph, bounds and fixtures. Existing sequential C kernels/decode remain usable. **Large** end to end. | 7,880 kernel B; 1,835,520 MACs (~1.53×); two activation buffers remain 49,152 B. Stop before C integration if no repeatable float gain; reject deployment if measured latency cost is unacceptable. |
| Extra depth / mainly large-face or context misses | Add one final DS 32→32 block. Test additional processing/context. | New ID/loader; updated layer schedule/export/fixtures, existing C operators. **Large**. | +1,312 kernel B, +251,904 MACs (~21%); same 49,152 B buffers; theoretical receptive field 63→79. Stop without the expected subgroup gain. Depth and receptive field change together. |
| Higher resolution / mainly small-face misses | Change 128×96 to 160×120; test preserved facial detail. | New ID and Python dimensions; resize, exporter, C decoder, candidate counts, buffers and fixtures all need updates. **Large**. | 1,874,400 MACs (1.5625×); 76,800 B two-buffer capacity; 300 cells. Stop without small-face gain or if measured runtime cost is unacceptable. Relative receptive field shrinks; QVGA resize becomes 2:1 and needs a verified path. |
| Assignment / actual collisions or boundary sensitivity | Replace single-cell targets with a small central region, retaining a fallback for tiny faces and deterministic collision handling. Test supervision density. | Python targets/loss normalization tests; same 5-channel export and C graph. **Medium**. | Same network cost, potentially more duplicate candidates. Stop if duplicates/false alarms outweigh recall gains. This is not automatically the next experiment after data work. |
| Localization loss / detection exists but boxes have poor overlap | Replace SmoothL1 with an overlap-based loss such as GIoU. Test localization objective. | Python loss, valid-box handling and gradients; same inference/export/C. **Medium**. | No inference cost increase. Specify loss weight before the run; retaining 5 does not make loss/gradient scales equivalent. Stop for unstable learning or no box-quality gain at comparable false detections. |
| Separate head / persistent classification-localization conflict | Replace the linear head with score and box branches, each PW32→16 + BN/ReLU then a linear output. | New ID, branch-aware folding/export and C schedule/output assembly. **Large**. | +944 kernel B, +181,248 MACs; additional live tensors need a memory schedule. Stop without repeatable float gain; no general graph framework for this trial. |
| Distillation / teacher demonstrably helps difficult real examples | Add one teacher-supervision term with a fixed alignment and weighting rule. | Inspect/capture teacher outputs, align them to the student grid and modify training; deployed student unchanged. **Medium–large**. | Same deployed graph. Stop if teacher errors transfer or real-dev results do not improve. YuNet post-NMS scores are not dense logits; existing hard pseudo-label training is not soft-target distillation. |
| More synthetic data / diversity looks limiting | Expand a nested synthetic pool from 1,000 to 10,000, with the same review policy. | New manifests; standard model/export/C. **Medium** plus annotation. | Same deployment cost. Equal epochs now mean more updates: either explicitly compare complete training recipes or add a fixed-update control at this later stage. Stop without real-dev improvement; do not immediately process all 100,000. |

These are our hypotheses. [MobileNets](https://arxiv.org/abs/1704.04861) motivates
width/resolution tradeoffs; [FCOS](https://arxiv.org/html/1904.01355v5) motivates
studying assignment and box-distance prediction. Its multi-level design and
centerness are absent here, so its reported gains do not validate our assignment
variant. [GIoU](https://arxiv.org/abs/1902.09630) motivates the overlap loss;
[distillation](https://arxiv.org/abs/1503.02531) motivates teacher transfer, without
establishing that our available teacher outputs are suitable targets.

Lower resolution (96×72: 674,784 MACs, 27,648 B activation buffers) or removing a
final DS block (947,712 MACs, receptive field 47) are later speed/quality tradeoffs.
Multi-scale heads, residuals, dilation, attention, quality-focal loss and QAT stay
deferred. They require specific evidence and may add operators, output formats
or live tensors. [Integer quantization research](https://arxiv.org/abs/1712.05877)
supports examining quantization error; it does not guarantee our C parity or
make QAT the first response to low scores.

## Minimal implementation and evaluation notes

- Existing `train.py --evaluate` evaluates the manifest's **val** split. Grouped
  manifests can be prepared without a new sampler. For equal-length replacement
  experiments, unchanged epochs/batch size give the same update count and current
  epoch-wise LR schedule. Preserve label policy, validation data, checkpoint
  selection by validation loss and seed across the pair.
  For the INT8 comparison, explicitly reuse calibration images shared by both
  training manifests: the same random seed alone does not preserve image identity
  after record replacement. Selecting those exact records may need a small
  calibration-selection helper; do not silently change calibration as well.
- `train.py` automatically evaluates its `test` split after every run. Keep the
  sealed final real holdout outside these routine training manifests; the existing
  synthetic comparison set can remain there. A later explicit evaluator should
  identify human annotations correctly: current test reporting hardcodes
  "teacher pseudo-labels". Montage records also expect a `scores` list; prepare
  schema-compatible human records and label their provenance explicitly.
- Review original JPEGs **and the actual 128×96 grayscale input**. If float/INT8
  differ, compare the same checkpoint and image pipeline first. A float run on
  dequantized INT8 input can separate input rounding from network quantization.
  Compare host C with Python INT8 at identical integer inputs. OpenCV JPEG decode
  and the board's JPEG decoder need not produce bit-identical BGR pixels.
- Existing host tests check arithmetic and preprocessing, not camera-domain
  accuracy. New graph variants need per-layer parity fixtures, overflow bounds,
  decoder checks and representative dim/bright inputs before board testing.
- `load_model` accepts only `tinyface-v1`; shape/topology variants require explicit
  new IDs. Folding expects sequential Conv/BN/ReLU triples plus one head. Export
  hardcodes input 96×128, five output scales, 960 head values and 24,576 B buffers.
  C decoding hardcodes 192 cells/channel offsets. Resolution changes must update
  Python, exporter, C, firmware score scans/scratch and verification wrappers
  together. Width/depth variants can reuse the sequential operators. Branches,
  residual addition or dilation need new scheduling/arithmetic support.
- The current export CLI automatically installs `nn_model.h`, even for custom
  output directories. Experimental exports need isolation or a small no-install
  option before use. This document does not run the exporter.
- For each run keep checkpoint/export hashes, code revision plus local diff,
  dataset/split identity, seed/config, raw counts and representative failures.
  Store private captures/checkpoints locally in ignored paths. No universal
  experiment framework is needed.
- Benchmark a surviving candidate and baseline on the same runtime revision,
  camera/light/network conditions and Arduino core. Record network and total
  latency, IPS separately from video FPS, internal RAM/PSRAM and errors; exclude
  SD-write windows. The separate runtime optimization workstream must not change
  kernels during this comparison. Historical means are not a p95 baseline.
  Decide an acceptable measured quality/speed tradeoff before deployment.
