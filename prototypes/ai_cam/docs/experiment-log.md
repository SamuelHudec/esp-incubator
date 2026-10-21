# AI camera experiment log

Record changes, verification and hardware observations here. Measurements below
were supplied by the user on 2026-10-20 and summarized on 2026-10-21. They are
selected observation windows, not controlled benchmarks. Do not store credentials
or raw serial captures here.

## Current state — 2026-10-21

- AI Thinker ESP32-CAM, classic ESP32 at 240 MHz, QVGA JPEG (320x240), PSRAM.
- Arduino sketch: `../firmware/firmware.ino`; recent builds verified with core
  3.3.12. No claim of testing these changes with the original 3.3.7 setup.
- `/` streams without inference; `/inf` displays the stream with detections.
- INT8 inference runs sequentially on CPU1, only while its stream is active.
  One owned JPEG slot prevents queued stale frames. RTOS yields remain enabled.
- Detection threshold: 0.30; NMS IoU: 0.30. Model quality work is deferred while
  optimizing runtime speed. Checkpoint identity of the hardware samples below
  was not recorded; do not infer it from the available training runs.

## Work completed through 2026-10-20

| Area | Change | Verification / limitation |
|---|---|---|
| Training | Local annotation, deterministic train/validation/test split, training and comparison images; MPS support and cosine learning-rate schedule | Python workflow and tests implemented |
| Quantization | INT8 weights/activations, folded BatchNorm, INT32 accumulation and fixed-point requantization; validation against float model | Exact C/Python layer comparisons; quality measured against teacher labels |
| Export | Keep only model header, quality/provenance report and golden fixtures; install firmware model atomically after successful checks | Failure-path test preserves previous firmware model |
| Layout | Separate `firmware/` from `neuralnet-training/`; group Python tests and utilities | Avoids Arduino scanning PyTorch headers; Arduino build passed |
| Integration | JPEG decode, grayscale resize, C inference, score/box decoding and NMS; browser overlay | User observed live detections with zero reported inference errors |
| HTTP stability | Move 1800-byte response buffer off task stack; increase detection-server stack from 4 to 8 KiB | User panic reported `Stack canary watchpoint triggered (httpd)`; later supplied windows show operation without reported crashes, not a long-duration stability test |
| Diagnostics | Peak candidate score, threshold, status, counters and latency; five-second mean phase/layer timings | Timings are wall time, including preemption; CPU occupancy is measured separately |
| Scheduling | Remove the 500 ms attempt timer; accept the next available frame after completion | CPU1 occupancy rose toward 95%; initial inference remained about 825 ms |
| Fast paths | Integer 5:2 QVGA preprocessing and tiled 1x1 convolution | 15 tests passed; exact whole-network INT8 layer parity on four inputs; exact preprocessing on 200 validation images |
| A/B routes | `/` never submits frames; `/inf` does | Mode printed as `Stream started: inference=off/on`; one pending inference may finish after closing the viewer |

## Inference optimization measurements — 2026-10-20

Before: three six-inference timing windows around 17:42. After: windows of 12 and
13 inferences around 17:54. Values are means of reported window means, rounded;
after-values here are not weighted by sample count. Scene and network conditions
were not held constant across the two sessions.

| Phase | Before fast paths | After fast paths |
|---|---:|---:|
| JPEG inspection and decode | 120.48 ms | 109.53 ms |
| Preprocessing | 180.11 ms | 33.26 ms |
| Network | 526.74 ms | 198.39 ms |
| Between-layer yields | 8.17 ms | 7.66 ms |
| Box postprocessing | 0.38 ms | 0.38 ms |
| Total sample-to-result | 836.42 ms | 349.65 ms |

Observed total latency improved by about **2.39x**. Preprocessing improved by about
5.42x and network execution by about 2.66x. No model weights, score threshold or
RTOS yields were changed by these fast paths. JPEG decode was not optimized, so
its timing variation should not be credited to a JPEG implementation change.
Later inference windows around 18:05 measured about 370 ms total and 2.5 completed
inferences/s. Remaining measured costs include JPEG decode (~112 ms), L0 (~72 ms)
and depthwise layers. Specialized L0/3x3 and depthwise kernels are **not yet done**.

## Stream A/B comparison — 2026-10-20, 18:04–18:05

Without inference: five equal 5.02-second windows ending 18:04:48–18:05:08.
The first supplied window ending 18:04:43 (10.95 FPS) was excluded as a possible
startup/partial-activity window; that interpretation is not confirmed.
With inference: two equal 5.03-second windows ending 18:05:23 and 18:05:28.
Means below are arithmetic means of reported window metrics. `send_avg` is the
mean of window means, not a recomputed per-frame weighted average.

| Metric | Without inference (`/`) | With inference (`/inf`) |
|---|---:|---:|
| Stream FPS | **25.24** | **23.06** |
| Observed FPS range | 23.28–27.27 | 22.66–23.45 |
| Send time per frame | **10.16 ms** | **13.56 ms** |
| CPU0 busy | **16.2%** | **22.6%** |
| CPU1 busy | **2.4%** | **91.3%** |
| Reported stream errors | 0 | 0 |

The selected windows show **2.18 FPS lower throughput (8.65%)** with inference.
This compares inference disabled/enabled on the optimized firmware; it does not
isolate the effect of the optimization itself. The inference viewer also polls
metadata and renders an overlay, unlike the raw-stream viewer.

An earlier optimized-firmware window at 17:54:35 showed 11.54 FPS and 50.77 ms send
time. That slowdown did **not recur in the later supplied inference windows**.
It is consistent with a transient event, but its cause is unconfirmed. Do not
conclude either that Wi-Fi caused it or that optimization has no effect on stream
performance. Send wall time includes network backpressure and scheduling delays;
RSSI alone does not distinguish them. The raw stream also varied without inference.

Working decision: continue optimizing inference independently of model quality;
monitor stream FPS and errors during subsequent hardware runs. Current observed
operation is approximately 23 FPS video plus 2.5 detections/s.

## Future entry format

For each change record:

1. Date, change and hypothesis; firmware commit/build and checkpoint/export identity
   when available.
2. Desktop checks and Arduino compilation result.
3. Hardware route/mode, scene, capture settings, warm-up and sample/window count.
4. FPS, send time, CPU0/CPU1, phase/layer times, memory and errors.
5. Conclusion, uncertainties and the next action. Separate measured results from
   expectations; preserve earlier results rather than overwriting them.
