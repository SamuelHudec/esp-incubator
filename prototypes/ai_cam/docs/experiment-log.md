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

## Dataset capture page — 2026-10-21

Added `/camera`: live raw stream without inference and a **Take photo** button.
Downloads are created by the browser from the currently displayed frame at native
resolution, re-encoded as JPEG quality 0.95, with UTC timestamp and sequence names.
Browser settings determine the destination; Downloads is typical, not guaranteed.
No additional camera-buffer owner, ESP image storage or capture endpoint was added.
Browser logic checks covered successful download requests, encoding failure,
native dimensions and disconnect handling. Arduino compilation passed; actual
browser MJPEG capture and file saving remain to be verified on the user's device.

User also reports occasional Wi-Fi dips. This is an additional observation, not
proof that Wi-Fi caused the earlier isolated stream slowdown.

## Stable detection dashboard — 2026-10-30

Replaced the changing inline diagnostics sentence on `/inf` with three fixed-grid
fields: stream FPS (last five-second sent-frame window), inference milliseconds
and maximum candidate score. Monospaced tabular digits, fixed precision and a
reserved error-message area prevent routine status transitions from shifting the
layout. Running/threshold/box counts and other diagnostics remain in the JSON and
serial logs, but are omitted from the normal page display. Missing or stale
inference results show a dash; request failures clear the displayed measurements.
JavaScript checks cover formatting, status transitions, stale data and errors.
Actual browser/device appearance remains to be checked after flashing.

## Vertical metrics panel — 2026-10-30

Changed the detection dashboard to five separate fixed-height rows: stream FPS,
inference milliseconds, maximum score, CPU0 and CPU1 utilization. Values occupy
an aligned fixed-width column with monospaced digits. CPU readings reuse the
existing five-second serial measurement; no additional CPU sampling was added.
Unavailable readings show a dash. JSON and serial diagnostic details remain.

## Compact serial summaries — 2026-10-30

Added compile-time NORMAL/PROFILE logging in `firmware/logging_config.h`.
NORMAL prints synchronized stream/AI rows every five seconds (including measured
AI completion FPS and mean latency); memory moves to once per minute. PROFILE
retains phase/layer timings and detailed stream metrics. Window statistics are
copied/reset atomically; serial printing moved out of the inference worker.
Errors are reported as nonzero window counts with the latest inference error
stage. Constant camera/CPU/threshold settings print at startup. Frame scheduling
and inference arithmetic are unchanged; new behavior needs hardware verification.

## SD capture replaces browser downloads — 2026-10-30

`/camera` now requests saving the next original JPEG to `/photos/` on the onboard
SD card. The port-81 control server accepts a POST and exposes pending/saving/
saved/error status via GET; browser confirmation follows completion, not merely
request acceptance. The stream task remains the only camera-buffer owner and
SD writer. One-bit SDMMC, no autoformat, collision-checked filenames and temporary
files preserve existing photos. Writes briefly pause stream throughput.
UI checks passed for confirmed save and unavailable card; physical FAT32 card
mounting, actual JPEG contents and persistence across reboot remain unverified.
See `sd-capture.md` for the hardware assumptions and verification procedure.
This supersedes the browser-download workflow recorded earlier.

## Inferences per second on the dashboard — 2026-10-30

Replaced the browser's inference-duration row with IPS (successful inference
completions per actual elapsed second over the shared five-second metrics window).
This is measured throughput, not 1000 divided by the last inference duration.
The JSON adds `ips` and retains `latency_ms`; serial latency and profiling timings
remain unchanged. Zero completions displays 0.00 even when the last result is stale;
unavailable/initial readings display a dash.

## Memory utilization dashboard — 2026-10-30

Added separate internal-RAM and PSRAM heap-used percentages alongside IPS. Each
uses free/total heap from the same capability pool, sampled every five seconds.
This avoids merging scarce internal memory with the larger PSRAM pool. Values
are heap utilization, not total physical-memory utilization; unavailable pools
show a dash. Existing serial memory reporting remains unchanged.

## SD startup diagnostics — 2026-10-30

User reported the combined mount/directory failure message. Split startup stages
and added successful-mount capacity/usage details. Existing `/photos` is checked
to be an accessible directory, rather than treating any existing file as ready.
Removed the unsupported assumption that mount failure implies FAT32 formatting
is needed. Hardware root cause remains unknown pending card details and startup
logs. No card format, voltage, pin or SD timing changes were made.

## SD initialization timeout observed — 2026-10-30

User supplied `sdmmc_init_ocr: send_op_cond (1) returned 0x107` followed by
`sdmmc_card_init failed (0x107)`. In the installed core, 0x107 is ESP_ERR_TIMEOUT.
Failure is during card protocol initialization, before filesystem mounting or
creation of `/photos`. Card filesystem format is therefore not established as
the cause; do not recommend formatting from this log alone. Investigate powered-off
reseating, computer readability and an alternate known-working card first. Card
capacity/model and comparative results are still missing. Driver advice about
pull-ups is generic, not proof of a missing resistor. No electrical modifications
or speculative SD clock changes were made.

## DAT3 pull-up initialization experiment — 2026-10-30

User confirmed the computer reads the card and can create `/photos`; no alternate
card is available. Added INPUT_PULLUP on onboard DAT3/GPIO13 before SDMMC begin,
based on Espressif pull-state requirements and matching AI Thinker issue #4680.
This is a diagnostic hypothesis, not a confirmed repair. GPIO13 must be free of
external peripherals. No filesystem, autoformat, clock, GPIO12 or LED changes.
Requires a full card/board power-cycle and hardware startup log comparison.

## Upload boot-mode failure after SD tests — 2026-10-30

User reports esptool wrong boot mode 0xb and unusually bright LED during upload.
Suspect SD/socket influence on GPIO2 strapping; unconfirmed pending upload with
card removed. Advised powered-off card removal and the established GPIO0-low
upload procedure, then powered-off reinsertion for normal operation. No flash
contents, pins, pull-ups or supply changes were made in response. LED cause is
unknown.

## SD capture hardware confirmed; dashboard encoding — 2026-10-30

User confirmed upload succeeds with the SD card removed and actual photo saving
on the inserted card works. Adopt powered-off SD removal during flashing for this
setup. Card influence on boot strapping is consistent with the symptoms; this does
not prove the earlier SD initialization timeout had the same cause or isolate the
DAT3 pull-up's effect. Cross-reboot file retention was not separately reported.

User observed `Â·` in `/inf` labels. The inference page lacked an explicit charset;
added an early UTF-8 meta declaration and `text/html; charset=utf-8` response type.
The camera capture page already declares UTF-8. Browser verification after flashing
is pending; no inference or metric computation changes were made.

## Automatic illumination research — 2026-10-30

Reviewed primary project code for PWM, image-based night detection and exposure
settling. See [illumination research](illumination-research.md) for concrete source
parameters and proposed adaptations. Found established 5 kHz/8-bit PWM settings,
but no universal validated face-detection brightness target. Some auto-lamp modes
only follow stream activity. No LED control firmware changes were made in this
research step; initial duty, feedback timing and thresholds still need board tests.

## Manual and automatic illumination implemented — 2026-10-30

Added a master LIGHT_ENABLED setting and tuning constants in firmware.ino.
Raw `/` keeps LED off; `/camera` now uses a distinct Manual stream and slider;
`/inf` runs Auto from existing preprocessed input. PWM uses separate LEDC timer
1/channel2 at 5kHz/8bits on GPIO4; initial cap25%, steps8, deadband20–35%, settling2s.
These feedback values are trial settings, not externally validated tuning.
Validation: all 17 tests passed, including host checks for master Off, stream
teardown, heartbeat timeout and controller limits. Manual UI/SD request checks
and Arduino core 3.3.12 compilation passed. No upload was performed.
Stream teardown and a four-second heartbeat turn the lamp off. Photo saving waits
for light settling. Added origin-checked port81 light controls and UI disable/error
states. Tests/compilation are recorded below; physical LED/SD coexistence and
model-quality effects remain unverified. See [illumination](illumination.md).

## Illumination glare feedback — 2026-10-30

User confirmed illumination control works as intended, but perceived direct LED
glare with little image-brightness benefit. Lowered the shared manual/auto cap
from 25% to 5% PWM and auto step from 8 to 2 counts. Camera exposure, thresholds
and model settings remain unchanged. Revised brightness and actual image/detection
benefit need a new hardware comparison; initial functional confirmation does not
establish an improvement in image quality.

## Illumination setting reduction reverted — 2026-10-30

At the user's request, reverted only the latest brightness reduction: the shared
cap is again 25% PWM and the auto step is again 8 counts. The user will continue
testing and collecting data with the original illumination settings. The glare
observation remains recorded; no quality conclusion or further tuning is implied.

## Architecture discussion plan — 2026-10-30

Reviewed the current Python training/annotation/quantization code, portable C
pipeline, firmware integration and existing observations. Added the
[TinyFace architecture and experiment plan](architecture-experiment-plan.md)
with a verified baseline, a proposed session-separated human-reviewed real
holdout, one-factor experiment matrix, integration costs and decision gates.
Primary papers support the hypotheses; their results are not ESP32 predictions.
Recommended first contrasts are real/synthetic mixing and verified negatives,
with calibration or assignment selected next from measured failure evidence.
This is a discussion proposal, not approval to implement every option. Only
Markdown documentation changed; no training, export, model-header replacement,
firmware edit, upload or new hardware verification was performed. Existing
illumination settings and user changes were preserved.

## Architecture plan reviewed and simplified — 2026-10-30

Re-reviewed the proposal against current training, annotation, quantization and
firmware code and the primary research. Replaced the long execution matrix with
[three steps](architecture-experiment-plan.md): diagnose a known float/INT8 model
on real captures, test data composition, then select one architecture change.
Moved implementation detail and deferred comparisons into an optional
[technical reference](architecture-reference.md).

Corrections: missing whole-image negatives do not by themselves explain low face
scores; positive images already supply negative grid cells. A float/INT8 check
comes before retraining. Assignment changes are conditional, not the default
third experiment. Removed premature 1% FP / 3-point improvement / 500 ms p95
acceptance gates and the requirement for a large initial collection. Equal-length
replacement datasets can use the existing epoch schedule without a new sampler.
Clarified session/identity leakage, the trainer's automatic test evaluation,
quantization score shifts versus quality loss, and the distinction between target
collisions and an absolute detector recall bound. Hardware and final quality
claims still require measurements. Documentation only; no training, export,
firmware changes or hardware tests were performed.

## Real-first mixed dataset sampling — 2026-11-02

Added `--real-input` and `--synthetic-input` to the annotator. Real images take
priority within `--count`: include all when they fit, otherwise sample only real
images; randomly fill remaining places from synthetic data. Console and summary
report per-source available/selected counts and annotation outcomes. Existing
single-directory `--input` remains supported. Selection does not copy images.

Every selected real image is retained for manual review, including teacher misses
and unreadable files. `--finalize` validates reviewed boxes/confirmed negatives
and creates the manifest without rerunning detection. Top-level real capture
folders stay intact across splits, with at least three selected groups required;
exact image copies crossing splits are rejected. Near-duplicate and identity
grouping remain the user's responsibility. Selection counts precede annotation;
synthetic misses can reduce final dataset size. Training reports/montage labels
now identify reviewed references instead of labeling every test as teacher-only.
See the [mixed-data workflow](../neuralnet-training/README.md#mix-real-camera-images-with-a-synthetic-pool).

Verification: all 22 Python/host-C tests passed, including new sampling overflow,
shortage, repeatability, negative loading, group isolation, copy leakage and a
mocked end-to-end annotation/review/finalization test. The latter checks that
teacher misses and unreadable real images are retained, dropped rows are rejected,
and corrected boxes survive export. No real-data annotation/training run, teacher
download, firmware modification or upload was performed. The suite includes its
existing tiny synthetic learning test, not a face-model training experiment.

## Future entry format

For each change record:

1. Date, change and hypothesis; firmware commit/build and checkpoint/export identity
   when available.
2. Desktop checks and Arduino compilation result.
3. Hardware route/mode, scene, capture settings, warm-up and sample/window count.
4. FPS, send time, CPU0/CPU1, phase/layer times, memory and errors.
5. Conclusion, uncertainties and the next action. Separate measured results from
   expectations; preserve earlier results rather than overwriting them.
