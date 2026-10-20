# Plain C face detection research

Research date: 2026-10-09. Status: design proposal, no trained model or ESP32
inference benchmark yet. Firmware is unchanged.

## Objective and constraints

Detect a human face, draw a bounding box in the live browser stream, and track
its position between detector updates. Identity recognition is not required.
Start with one selected face, ordinary indoor lighting and mostly frontal faces.
These are proposed initial test conditions, not an established accuracy claim.

Keep classic ESP32 / OV2640 / Arduino IDE. Train in Python; implement the small,
fixed inference graph in portable C without a neural-network runtime. Arduino's
`.ino` remains C++; a future `.c` implementation can expose an `extern "C"`
interface. No framework migration is needed. Camera and network drivers remain.

The measured baseline is 25.29 stream FPS, CPU 0/1 approximately 15.76%/2.51%,
and 4,156,888 bytes free PSRAM. Internal free RAM averaged only 116,957 bytes.
These measurements do not predict inference latency or prove that all PSRAM is
available as one contiguous allocation. See [baseline](../README.md#first-streaming-baseline--2026-10-08).

## Findings from existing work

| Candidate | Published evidence | Implication for this experiment |
| --- | --- | --- |
| YuNet | Paper reports 75,856 parameters and a lightweight anchor-free detector; its 1.6 ms result is on an Intel i7-12700K at 320x320 | Useful accuracy/reference model on the training computer. Porting requires auditing the exact graph and operators; desktop timing is not ESP32 timing. |
| UltraFace slim/RFB | Repository reports approximately 300 KB INT8 and 90–109 MFLOPs at 320x240 | Small storage does not imply low enough computation. Not the first plain-C target. |
| pico | Cascade of decision trees using pixel comparisons, with C inference | Relevant non-neural comparison, but not the selected route because the requested experiment is a neural network. |
| Custom tiny depthwise CNN | Architecture and arithmetic below are our proposal | Small operator set and explicit memory plan; accuracy is entirely unverified. |

Sources: [YuNet paper](https://link.springer.com/article/10.1007/s11633-023-1423-y),
[OpenCV YuNet models](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet),
[UltraFace author repository](https://github.com/Linzaer/Ultra-Light-Fast-Generic-Face-Detector-1MB),
[pico author repository](https://github.com/nenadmarkus/pico).
Published FLOP counts and our MAC counts are different units; one MAC comprises
one multiply plus one addition. Neither is a CPU cycle count.

## Recommended first architecture experiment

Start with a fully convolutional grayscale detector operating on **128x96** input.
Use a single 16x12 output grid; each cell predicts a face score and four distances
from its cell center to box edges. Apply score thresholding, decode boxes, and
suppress overlapping candidates. Track one selected detection. A spatial output
preserves localization; a global face/no-face classifier alone would not do this.

The following is a deliberately small lower-bound experiment, not a proven
"smallest usable network". All 3x3 convolutions use padding 1. DS means a 3x3
depthwise convolution followed by a 1x1 pointwise convolution. ReLU follows hidden
layers. Fold any training batch normalization into convolution weights at export.

| Stage | Output W x H x C | Stride | Kernel weights | MACs |
| --- | --- | --- | --- | --- |
| 3x3 convolution, 1 to 8 channels | 64x48x8 | 2 | 72 | 221,184 |
| DS, 8 to 16 | 32x24x16 | 2 | 200 | 153,600 |
| DS, 16 to 24 | 16x12x24 | 2 | 528 | 101,376 |
| DS, 24 to 32 | 16x12x32 | 1 | 984 | 188,928 |
| DS, 32 to 32 | 16x12x32 | 1 | 1,312 | 251,904 |
| DS, 32 to 32 | 16x12x32 | 1 | 1,312 | 251,904 |
| 1x1 score/box head, 32 to 5 | 16x12x5 | 1 | 160 | 30,720 |
| Total | | | **4,568** | **1,199,616** |

Calculation: ordinary convolution uses `Hout * Wout * Cout * Cin * K*K` MACs;
a DS block uses `Hout * Wout * (Cin * 9 + Cin * Cout)`. Counts exclude biases,
activation/clamping, requantization, decoding, tracking, and image preprocessing.
The theoretical receptive field is 63x63 input pixels. Large faces, tiny faces,
profiles, and occlusion are likely failure cases to test, not claim as supported.
Initially evaluate faces roughly 16–48 pixels wide at model input (40–120 pixels
in the 320x240 stream). If accuracy fails, widen channels or increase receptive
field/input resolution one change at a time. Do not spend weeks optimizing C for
an architecture that cannot learn the task in Python.

### Memory budget, not measured allocation

- INT8 kernel weights: 4,568 bytes; biases, scales and integer multipliers add
  storage. Keep immutable parameters in flash where practical; benchmark access.
- Grayscale input: 12,288 bytes. Largest INT8 activation: 24,576 bytes.
- Two reusable activation buffers of 24,576 bytes each plus the separate input:
  61,440 bytes. Schedule the input/DW/PW tensors so each live tensor has a buffer;
  hidden tensors shrink after the first layer. Avoid full-image im2col buffers.
- Use INT32 accumulators per output element, not a full INT32 activation copy.
  Output head occupies 960 bytes in INT8, or additional space if dequantized.
- Initial inference allocation allowance: approximately 80–100 KiB including
  metadata, alignment, outputs and small scratch storage, to be verified.
- JPEG decoding is separate: full 320x240 RGB888 is another 230,400 bytes, plus
  decoder workspace and any copied JPEG. Prefer reduced/streamed grayscale
  preprocessing if supported and verified in the installed camera decoder.
- Keep large image buffers in PSRAM. Do not consume most remaining internal RAM
  just because the arithmetic fits. Measure allocation failures, largest free
  blocks and low-water marks with streaming active.

The [camera driver documentation](https://github.com/espressif/esp32-camera)
warns about memory/throughput pressure from RGB capture, particularly with Wi-Fi.
Preserve the working JPEG capture initially and benchmark decoding separately.

## Python to plain C

1. Train the fixed architecture in Python, with annotated face boxes and negative
   images. Use a face score loss and box regression loss on assigned positive grid
   cells; handle overlapping assignments deterministically. Include hard negatives.
2. Validate float accuracy on held-out people and recording sessions. Adjacent
   frames from the same recording must not leak between train and test splits.
   WIDER FACE is a possible annotated source; add representative OV2640 footage.
3. Fold batch normalization, calibrate on representative camera-like inputs, then
   quantize weights and activations to INT8 with INT32 biases/accumulators. Use
   quantization-aware training if post-training quantization loses too much accuracy.
4. Freeze input normalization, tensor layout, padding, rounding, saturation,
   per-channel weight scales and per-tensor activation scales. Export fixed-point
   multipliers/shifts. Test overflow bounds; C signed overflow is not acceptable.
5. Generate C constant arrays and a fixed layer schedule. Export golden input,
   intermediate outputs and final detections for desktop-C versus Python tests.
6. Compile the same portable C on ESP32 and benchmark actual layers, preprocessing
   and total latency before integrating continuous detection.

[Safetensors](https://huggingface.co/docs/safetensors/index) stores tensors;
[ONNX](https://onnx.ai/onnx/intro/concepts.html) represents a computation graph.
Neither file extension performs quantization or supplies inference execution.
Keep either as an optional desktop artifact; the ESP needs generated arrays,
quantization metadata and C operations, not an ONNX/safetensors parser.
The [INT8 quantization specification](https://developers.google.com/edge/litert/conversion/tensorflow/quantization/quantization_spec)
is a useful numerical reference, without requiring its runtime.
Dataset reference: [WIDER FACE project](https://mmlab.ie.cuhk.edu.hk/projects/WIDERFace/).

## Live tracking and rendering

Detection and streaming should have independent rates. An initial experimental
target is 2–5 detector updates/s, subject to measurement, while video continues
as fast as feasible. This is a target, not a prediction for the proposed model.
Use a bounded latest-frame mailbox; skip work when inference is busy instead of
building a queue. Never let the network and inference tasks concurrently own or
return the same camera buffer. Copy an occasional JPEG to a bounded owned buffer
or finish preprocessing before returning it; measure the cost of either approach.

Between detections, a small grayscale template search near the last box can
provide actual image-based tracking. Limit search area and update templates only
when confidence is adequate. Reacquire with the detector after loss; periodically
run global detection to prevent drift. Box smoothing or constant-velocity
prediction alone is not visual tracking. Hide stale boxes after a short timeout.

Draw a rectangle using browser canvas over the JPEG stream to avoid decoding and
re-encoding video solely to paint a box. Send frame/time identifiers, source
coordinates, confidence and box age. Convert coordinates for browser scaling.
Native MJPEG image rendering does not give reliable per-frame synchronization;
initial overlays may lag. Exact alignment would need a frame-aware browser
transport/parser and matching metadata.

The current HTTP handler occupies its server task for the entire stream. Adding
a metadata URL to that same synchronous server is insufficient. Plan a separate
control server/task or a deliberately redesigned asynchronous transport. Keep
this change separate from the first inference benchmark.

## Decision gates and next step

The next concrete experiment is **the proposed model trained and evaluated on the
computer, plus C kernel timing on ESP32**, before full integration. Do not start
with a universal neural-network interpreter.

Proposed usability gate: on a held-out, documented indoor test set in the chosen
face-size range, at least 90% recall at IoU >= 0.5 and at most one false-positive
frame per 100 negative frames. Report sample sizes, precision and failure cases;
these thresholds are a starting proposal, not achieved results.

Measure float versus INT8 accuracy, per-stage latency, detector update rate,
tracking drift/loss, box age, stream FPS, CPU per core and memory. Require camera
buffer ownership and reconnect tests. Establish attainable latency on the actual
chip; if the tiny model fails accuracy, widen it and remeasure rather than
claiming that fitting in RAM makes it usable. No training, deployment or hardware
inference test was performed in this research step.
