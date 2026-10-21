# ESP32-CAM: simple local video stream

See the [experiment log](docs/experiment-log.md) for completed changes, timing
results, the stream/inference comparison and outstanding optimization work.

## First run

Open [firmware.ino](firmware/firmware.ino) in Arduino IDE. The sketch now includes
`firmware/ai_detection.h` and the portable C sources under `firmware/neuralnet/`. Local Wi-Fi
configuration remains in `firmware/secrets.h`. These files separate testable inference
from hardware access; no new framework is required. The original AI plan remains
below as background.

1. In Boards Manager, install **esp32 by Espressif Systems 3.3.7**.
2. Select **AI Thinker ESP32-CAM** and your programmer's serial port.
3. Edit local `firmware/secrets.h` with your 2.4 GHz Wi-Fi name and password. If missing,
   copy [secrets.example.h](firmware/secrets.example.h) to `firmware/secrets.h`. Git ignores secrets.
4. Upload. Follow your programmer's download/reset procedure; release GPIO0 from
   ground before resetting into normal operation (see wiring notes below).
5. Open Serial Monitor at **115200 baud**, reset, and wait for the printed URL.
6. On a phone connected to the same LAN, open **http://ai-cam.local/**.
   The browser shows the video directly. Close the tab to stop; reload to reconnect.
   If the phone or network cannot resolve mDNS names, use the printed IP address.
   The hostname is `ai-cam` (with a hyphen); change `HOSTNAME` in the sketch if needed.

No extra libraries, ESP-IDF installation, Docker or web files are needed.
The camera, HTTP and mDNS libraries are included in the ESP32 board package.

## Status and verification

2026-09-30: compilation passed with ESP32 Arduino core 3.3.7 and the
AI Thinker ESP32-CAM profile. The sketch includes the `ai-cam.local` mDNS name.
2026-10-07: the user confirmed that the hardware test passed and the stream
works as intended after flashing with the dedicated CH340 USB-C ESP32-CAM
programmer ([product](https://www.laskakit.cz/ch340-programator-pro-esp32-cam-usb-c/)).
Individual test timings, FPS and memory measurements were not recorded.
For future changes, verify moving video, closing/reopening the tab, power cycling,
and access by both mDNS name and IP address.

## Performance measurements

2026-10-07: added five-second Serial Monitor measurement windows. Hardware
verification was initially pending; the first streaming measurements are recorded
below on 2026-10-08. The earlier hardware test covers only the original stream. Compilation passed for AI Thinker ESP32-CAM with the
locally installed Arduino core **3.3.12** (1,055,957 bytes flash and 59,840 bytes
static RAM before hardware testing). The instrumented version has not been
compiled with the original **3.3.7** baseline. No board packages were changed.
No extra libraries or endpoints are required.

Each window reports:

- `image`: actual framebuffer dimensions; `0x0` until the first frame is acquired.
- `acquired` and `sent`: buffers acquired by the HTTP handler and complete JPEGs
  successfully passed to the HTTP send API in this window.
- `fps`: `sent / elapsed seconds`. This is server-side streaming throughput, not
  sensor capture FPS or confirmed browser display FPS. With `CAMERA_GRAB_LATEST`,
  camera frames can be discarded before the handler acquires them.
- `jpeg_avg`: average size of successfully sent JPEGs, in KiB; `payload`: JPEG
  payload throughput in KiB/s, excluding HTTP/TCP/Wi-Fi overhead.
- `acquire_avg`: wall time in `esp_camera_fb_get()` per successful acquisition,
  including waiting for a buffer; it is not sensor exposure time.
- `send_avg`: wall time in the two HTTP send calls per attempted frame, including
  blocking on network buffers and failed sends. Neither duration is CPU usage.
- `errors`: acquisition, header or frame-send failures. Disconnecting a viewer
  may produce a send error; this alone does not indicate a camera fault.
- `cpu0_busy` and `cpu1_busy`: approximate non-idle task time per core over the
  window, calculated as `100 * (1 - idle runtime delta / elapsed microseconds)`.
  Each core has its own 0–100% scale. This includes other tasks such as Wi-Fi;
  FreeRTOS task accounting does not separately measure interrupt execution.
  Scheduler accounting and sequential snapshots introduce small errors; values
  are clamped to 0–100%. Unsigned counter differences handle runtime rollover.
  If runtime statistics with the ESP timer are unavailable in the core build,
  the output explicitly says `cpu_busy=unavailable`.
- `cpu_clock`: CPU frequency, not utilization. `internal_free`, `internal_min`,
  `internal_largest`, `psram_free`, and `psram_min` are bytes. Minimum values are
  low-water marks since boot, not per-window minima. `rssi` is Wi-Fi signal level.

Counters are exchanged under a short critical section; Serial output occurs
outside it. Frame acquisition and sending can straddle a window boundary, so
`acquired` and `sent` can differ in an individual window. Reporting itself adds
some overhead. The existing 30 ms frame pause remains unchanged: these results
measure the current streaming configuration, not maximum hardware throughput.
Without a viewer, stream counters are zero while CPU and memory reporting continues.

### First streaming baseline — 2026-10-08

User-supplied hardware log: 11 consecutive reporting windows ending between
14:40:53 and 14:41:43 local time (Europe/Prague), totaling approximately **55.24 s**.
The first timestamp marks the end of the first window. All windows reported
320x240 JPEG and a 240 MHz CPU. The current sketch uses JPEG quality 12, two
PSRAM framebuffers, `CAMERA_GRAB_LATEST`, and a 30 ms frame pause. The flashed
Arduino core version and scene conditions were not confirmed in this log.

| Metric | Result |
| --- | --- |
| Acquired / successfully sent frames | 1,397 / 1,397 |
| Streaming throughput | **25.29 FPS**; window range 22.50–27.27 FPS |
| Mean JPEG size | Approximately 4.27 KiB/frame |
| Mean JPEG payload throughput | 108.31 KiB/s |
| Mean buffer acquisition wall time | 0.110 ms/frame |
| Mean HTTP send wall time | 9.83 ms/frame |
| CPU 0 non-idle time | **15.76%**; range 15.0–16.9% |
| CPU 1 non-idle time | **2.51%**; range 2.0–3.1% |
| Mean sampled free internal RAM | 116,957 bytes; range 110,700–120,848 |
| Lowest reported internal RAM low-water mark | 101,556 bytes |
| Largest free internal block | 110,580 bytes initially; 106,484 in the last sample |
| Free PSRAM | 4,156,888 bytes (approximately **3.96 MiB**) in every sample |
| PSRAM low-water mark | Reported 0; interpretation requires investigation |
| Mean sampled RSSI | -58 dBm; range -60 to -56 dBm |
| Reported errors | **0** |

Aggregates are approximate because the supplied window durations and averages
are rounded. FPS uses total sent frames divided by total window duration. CPU
and payload rates are weighted by window duration; JPEG size and send time by
sent frames, and acquisition time by acquired frames. With zero reported errors,
send attempts equal successful sends. RAM and RSSI averages use the 11 samples.

This confirms that streaming instrumentation runs on hardware. Individual windows
can differ by one acquired/sent frame because work crosses reporting boundaries;
the totals here match. The observed FPS includes the configured frame pause and
instrumentation overhead, so it is not maximum chip throughput. The log does not
establish long-term memory stability, reconnect behavior, measurement overhead,
or available capacity for neural-network inference. A zero `psram_min` alone is
not evidence of PSRAM exhaustion; the reported current free PSRAM stayed constant.

### Measurement procedure

1. Build for AI Thinker ESP32-CAM and open Serial Monitor at 115200 baud.
2. After Wi-Fi connects, leave the stream closed for 30 seconds; observe the
   idle CPU and memory baseline. The camera remains initialized during this test.
3. Open one viewer and let the stream settle for 10 seconds. Observe at least
   60 seconds with a static scene, then 60 seconds with motion. Record resolution,
   JPEG quality, frame pause, core version, FPS, CPU per core, memory, and RSSI.
4. Close and reopen the viewer, then power cycle. Confirm the stream resumes,
   dimensions become 320x240, and free memory does not keep falling after repeated
   reconnects. An in-progress send can take time to fail after disconnection.
5. Change only one setting per subsequent experiment. Treat CPU percentages as
   comparative measurements; do not infer spare inference capacity from FPS alone.

Local serial captures must remain untracked. Do not commit network identifiers
or secrets. Record sanitized observations and the hardware-test date here.

## Experimental C inference integration — 2026-10-20

Status: desktop validation and Arduino compilation passed; **hardware verification
of this integration is pending**. Original stream measurements predate inference.
No upload was performed. No pin, voltage or camera configuration changes were made.
Arduino IDE remains the development/flashing workflow; local compilation used
Espressif core **3.3.12**. The integrated version is not verified with 3.3.7.

The `firmware/neuralnet/` directory contains the category-neutral C runtime. The sketch-root
`firmware/neuralnet.c` includes its implementation for the Arduino sketch build, since
Arduino does not recursively compile arbitrary subdirectories. The current graph
remains a fixed single-class detector, and the bundled training labeler is
face-specific.

Portable C under `firmware/neuralnet/` now implements BGR-to-grayscale area downsampling,
INT8 network execution, head decoding, thresholding and greedy NMS. The generated
model is local and ignored by Git. After successful calibration, C parity checks
and validation, `quantize.py` automatically replaces `firmware/neuralnet/nn_model.h`
with the exported model, including when using a custom `--out` directory.
Failed quantization leaves the previous firmware model intact. The final console
message identifies the checkpoint and installed header. Compile and upload the
sketch afterwards; quantization does not update an already running board.

Without this header the firmware builds with detection disabled and keeps the
stream available. Keep generated weights out of commits; regenerate them from
the selected checkpoint using the documented Python quantization workflow.

- Raw MJPEG without inference: `http://ai-cam.local/` (port 80).
- Detection viewer: `http://ai-cam.local/inf` (or the printed IP with `/inf`).
- Metadata: `http://ai-cam.local:81/detections` with normalized xyxy boxes, scores,
  result age, end-to-end inference latency, completed/error/skipped counters.
- Threshold 0.3, NMS IoU 0.3, at most eight displayed boxes. The UI waits 500 ms between metadata requests
  and hides results older than two seconds. It draws the last detection without
  smoothing, visual tracking or exact frame synchronization. Fast motion may lag.

Only the stream handler acquires/returns camera framebuffers. Each successfully
streamed frame is offered to inference without waiting. When the worker slot is
free, the JPEG is copied into an owned 64 KiB PSRAM slot. There is no fixed
submission interval; the next available frame is accepted after completion. Frames
are skipped when inference is busy or the JPEG exceeds the slot size; no backlog
is built and streaming never waits on the inference mutex. Without a stream
viewer there are no new inference submissions. Inference runs on core 1 and yields
between layers. Busy inference can still reduce stream performance through shared
CPU/memory bandwidth; no throughput guarantee has been measured on hardware.

The worker bounds JPEG decoding to a 320x240x3 output buffer and checks decoded
dimensions. Large buffers use PSRAM: 65,536 bytes JPEG + 230,400 bytes BGR + 49,152
bytes activations = 345,088 bytes, excluding decoder workspace, task stack and
metadata. Allocation/task failure disables inference while preserving streaming.
The JPEG decoder remains the Espressif camera stack; inference and postprocessing
are plain C. The default decoder byte order matches BGR used for OpenCV input;
see [Espressif conversion source](https://github.com/espressif/esp32-camera/blob/master/conversions/to_bmp.c).

Desktop validation on 200 images resized to QVGA: C preprocessing exactly matched
Python INT8 input on this sample; C/Python box/score differences were at most
5.96e-8 on identical network heads. The C network matched the quantization golden
head exactly. Decoder implementations on desktop and ESP32 may differ slightly;
this is not a hardware JPEG equivalence test. Build with the selected model:
1,072,989 bytes program storage, 64,104 bytes static RAM.

### Hardware verification procedure

1. Build/upload in Arduino IDE and open Serial Monitor at 115200. Confirm no
   allocation, watchdog, brownout or server errors.
2. Close other stream viewers. Open the port-81 page and verify moving video,
   increasing completed count, inference latency and face boxes. Check face-free
   frames, entering/leaving the scene and rapid movement; stale boxes must clear.
3. Watch the existing five-second FPS/CPU/memory reports for at least two minutes
   and compare against the earlier 25.29 FPS baseline. Record detection latency,
   errors/skips, minimum internal RAM and PSRAM. Do not assume the old FPS persists.
4. Close/reopen the page, power-cycle, and test both mDNS and IP access. Confirm
   the direct port-80 stream still works and no repeated memory loss occurs.
5. Check one known colored subject/image against desktop detections if results
   differ unexpectedly; JPEG decode/preprocessing and source image distribution
   are separate from the already verified integer-network arithmetic.

Record the date and observations after hardware testing. This prototype now has
training/export tooling; if it becomes maintained work, consider extracting it
into its own repository rather than growing shared abstractions here.

## Known limitations and next steps

JPEG video at 320 × 240, one viewer at a time. Experimental face detection is
available with the locally exported model. No audio, recording or authentication. Use a trusted LAN without Internet port forwarding. Guest Wi-Fi
isolation can prevent the phone reaching the camera. Check 2.4 GHz availability
and credentials if connection dots continue; check power if the board resets.
Next step: add computer vision incrementally while preserving the working stream.

## Wiring and hardware assumptions

Recorded on 2026-09-30. The user identified the board as
[LaskaKit LA100069 ESP32-CAM](https://www.laskakit.cz/ai-thinker-esp32-cam-2-4ghz-wifi-bluetooth-modul/)
with an OV2640, already connected to their programmer. The physical PCB revision
has not been read from the hardware. The user identified the programmer via the
[LaskaKit CP2102 LA161015 product page](https://www.laskakit.cz/prevodnik-6pin-microusb-ttl-uart--cp2102--dtr-pin/).
That URL currently describes a USB-C/microUSB model; verify the actual board
markings before applying its specifications to an older revision.

The stream targets the AI-Thinker camera layout documented in the seller-linked
[manufacturer specification, pages 2–3](https://www.laskakit.cz/user/related_files/esp32-cam_product_specification.pdf)
and [V1.6 schematic](https://www.laskakit.cz/user/related_files/esp32_cam_v1-6.pdf).
The mapping agrees with Espressif's
[AI-Thinker camera definition](https://github.com/espressif/arduino-esp32/blob/3.2.1/libraries/ESP32/examples/Camera/CameraWebServer/camera_pins.h).
Verify the markings against these sources before flashing a different revision.

### Camera pin table

Numbers below are ESP32 GPIO numbers, not header positions. The ribbon cable
already carries these connections; no external camera jumpers are needed.

| Camera signal | ESP32 GPIO |
| --- | --- |
| D0 / Y2 | 5 |
| D1 / Y3 | 18 |
| D2 / Y4 | 19 |
| D3 / Y5 | 21 |
| D4 / Y6 | 36 |
| D5 / Y7 | 39 |
| D6 / Y8 | 34 |
| D7 / Y9 | 35 |
| XCLK | 0 |
| PCLK | 22 |
| VSYNC | 25 |
| HREF | 23 |
| SCCB SDA | 26 |
| SCCB SCL | 27 |
| PWDN | 32 |
| Reset | No software-controlled GPIO; use -1 |

### Power and programming

- The manufacturer specification lists a 5 V board supply and nominal consumption
  of 180 mA with the flash off, 310 mA at maximum flash brightness. These are not
  a guaranteed peak-current budget. The current CP2102 product page specifies
  a maximum output current of 500 mA, selectable 5 V/3.3 V VCC and fixed 3.3 V data signals.
- The seller lists 3.3 V logic. Never apply 5 V UART signals to the ESP32.
- The seller explicitly warns that newer boards have an unconnected GND beside
  U0T. Use the GND beside 5V for a wired power connection.
- For the matching CP2102 revision, select 5 V VCC with USB disconnected. Connect
  VCC to camera 5V, GND to GND beside 5V, TXD to U0R, and RXD to U0T. Leave DTR
  and RTS disconnected for manual programming. Follow printed labels, not header
  positions; do not add a second power source.
- For upload, connect camera GPIO0 to the same ground, reconnect USB, start Upload
  and press the camera RST button when Connecting appears. After successful upload,
  disconnect USB, remove GPIO0-to-ground and reconnect USB to run the sketch.
- Disconnect power before reseating the camera ribbon or changing jumpers.
- For manual download mode, GPIO0 is held low during reset; release its connection
  to ground before resetting into the application. GPIO0 becomes camera XCLK
  during normal operation. A programmer may handle this automatically; consult
  its own instructions. See Espressif's
  [ESP32 boot mode guide](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html).
- The firmware leaves the flash LED and microSD interface unused. Brownout
  detection remains enabled; fix the power supply if brownout resets occur.
- The AI Thinker Arduino board profile uses a 4 MB flash layout. The seller currently lists
  8 MB while the older manufacturer specification lists 4 MB. Check the actual
  flash size in the boot/upload output; this application does not require 8 MB.


## Python face detector prototype

2026-10-19: [Local Python training and inference](neuralnet-training/README.md) now implements
the proposed tiny detector, data loading, training, fixed-threshold evaluation and
image/MJPEG preview. Face accuracy is not yet validated; C inference and
quantization remain future work. Streaming firmware is unchanged.

## Current face detection research

2026-10-09: [Plain C face detection research](docs/face-detection-research.md)
compares candidate approaches and proposes a small trainable detector, INT8 export,
memory budget, tracking and browser overlay integration. This is an untested
design; the working streaming firmware has not changed.

## Future AI experiment plan

Embedded AI experiment running entirely on a low-cost **AI-Thinker ESP32-CAM**.

The goal is not only to build a working face-tracking camera, but to use the resource constraints of the classic ESP32 as a learning platform for deploying and optimizing machine-learning models on microcontrollers.

## Main Goal

Build an ESP32-CAM application that:

1. Captures video from the onboard OV2640 camera.
2. Detects a human face locally on the ESP32.
3. Tracks the detected face between inference frames.
4. Streams video over Wi-Fi using an HTTP/MJPEG server.
5. Exposes detection/tracking information such as bounding boxes.
6. Runs completely on-device without cloud inference or external compute.

No physical display is required.

Target architecture:

```text
OV2640
   |
   v
Camera capture
   |
   +------------------------+
   |                        |
   v                        v
JPEG / RGB frame       Face detector
   |                        |
   |                      bbox
   |                        |
   |                     tracker
   |                        |
   +-----------+------------+
               |
               v
         HTTP web server
               |
         Wi-Fi / browser
```

## Hardware

Primary development board:

**AI-Thinker ESP32-CAM**

Expected characteristics:

- Classic ESP32 SoC
- Dual-core Xtensa LX6
- Up to 240 MHz
- OV2640 2 MP camera
- 4 MB PSRAM
- 4 MB Flash
- 2.4 GHz Wi-Fi
- Bluetooth
- No onboard USB programmer on many variants

The classic ESP32 was chosen intentionally instead of ESP32-S3.

The ESP32-S3 offers significantly better neural-network acceleration, more modern ESP-DL support and commonly 8 MB PSRAM, but the goal of this project is partly to explore the constraints involved in embedding AI models on limited hardware.

## Why Classic ESP32?

The older ESP32 is expected to be substantially slower than ESP32-S3 for neural-network inference.

That is acceptable.

The project is intended to explore trade-offs between:

- model complexity
- model size
- quantization
- RAM usage
- PSRAM usage
- camera resolution
- pixel format
- preprocessing cost
- inference latency
- detection frequency
- video FPS
- tracking quality
- JPEG encoding cost
- Wi-Fi throughput

A face detector does not need to run for every captured frame.

An expected architecture may eventually look like:

```text
Camera:

F1 F2 F3 F4 F5 F6 F7 F8 F9 ...
|        |        |
D        D        D
|        |        |
+--T--T--+--T--T--+--T--T

D = neural-network face detection
T = lightweight tracking/interpolation
```

This allows the video stream to operate at a higher frame rate than the neural network.

## Expected Initial Performance

Exact performance will be measured rather than assumed.

Historical ESP-DL benchmarks suggest classic ESP32 face detection may take roughly hundreds of milliseconds depending on the model.

A realistic first target is therefore approximately:

```text
Detection: 2-6 FPS
Video stream: potentially higher
Tracking: between detection frames
```

A working system at even ~3 FPS detection rate is considered a successful first implementation.

## Software Stack

Current streaming baseline: Arduino IDE, using the ESP32 board package.

Potential framework for later AI experiments:

- ESP-IDF
- FreeRTOS
- esp32-camera
- esp_http_server
- ESP-DL where compatible
- legacy ESP-WHO components where required

Start with the Arduino sketch. Revisit native ESP-IDF only when the AI experiments require it.

Important: current ESP-WHO development primarily targets newer chips such as ESP32-S3 and ESP32-P4. Classic ESP32 support may require older ESP-WHO/ESP-IDF versions or selectively reusing components instead of depending on the latest ESP-WHO application stack.

Version compatibility must therefore be documented carefully.

## Video Streaming

Initial output:

```text
http://<esp32-ip>/
```

or:

```text
http://<esp32-ip>/stream
```

using MJPEG over HTTP.

Detection metadata may eventually be exposed separately:

```text
GET /detections
```

Example:

```json
{
  "face": {
    "x": 91,
    "y": 42,
    "width": 74,
    "height": 86,
    "confidence": 0.94
  }
}
```

Bounding boxes may alternatively be drawn directly into frames before JPEG encoding.

## Initial Resolution

Start conservatively.

Suggested camera configuration:

```text
QVGA
320 x 240
```

Inference input may be lower, for example:

```text
160 x 120
```

or another size required by the selected detector.

Do not optimize resolution prematurely. First obtain baseline measurements.

## Memory Constraints

Memory is one of the main engineering constraints.

The system may simultaneously require memory for:

- camera framebuffer
- JPEG frame
- RGB frame
- resized inference input
- neural-network weights
- intermediate tensors
- HTTP buffers
- Wi-Fi stack
- FreeRTOS stacks
- tracking state

For reference:

```text
320 x 240 RGB888
≈ 230 kB
```

Multiple uncompressed buffers can therefore consume internal memory quickly.

Prefer:

- PSRAM for large buffers where possible
- carefully controlled framebuffer count
- small inference inputs
- quantized models
- avoiding unnecessary RGB copies

Memory usage must be measured throughout development.

## Project Milestones

### M0 — Board Bring-Up

Goal:

- build the Arduino sketch
- flash firmware
- serial logging
- verify board configuration
- verify PSRAM
- connect to Wi-Fi

Deliverable:

```text
ESP32 boots reliably and reports available memory.
```

### M1 — Camera

Goal:

- initialize OV2640
- capture frames
- inspect camera timing
- experiment with resolution and pixel format

Deliverable:

```text
Camera frames captured reliably.
```

### M2 — HTTP/MJPEG Streaming

Goal:

- run esp_http_server
- expose MJPEG stream
- open stream from desktop browser

Measure:

- capture FPS
- JPEG size
- streaming FPS
- memory usage

Deliverable:

```text
Live browser stream from ESP32-CAM.
```

### M3 — Face Detection

Run face detection independently of streaming first.

Pipeline:

```text
camera
  |
preprocess
  |
face detector
  |
bbox
  |
serial output
```

Measure separately:

- capture time
- color conversion
- resize time
- inference time
- postprocessing time
- peak memory usage

Deliverable:

```text
Face bounding box detected locally.
```

### M4 — Detection + Streaming

Integrate both pipelines.

```text
camera
   |
   +--> stream
   |
   +--> detector
           |
          bbox
```

Display or transmit detected bounding boxes.

Deliverable:

```text
Browser shows video and current face detection.
```

### M5 — Profiling

Create reproducible benchmarks.

Measure at minimum:

```text
camera capture
preprocessing
inference
postprocessing
JPEG encoding
HTTP streaming
free SRAM
free PSRAM
minimum free heap
```

Benchmark multiple:

- resolutions
- pixel formats
- detector configurations

Deliverable:

```text
Performance table documenting hardware limits.
```

### M6 — Optimization

Explore:

- frame skipping
- lower inference resolution
- JPEG vs RGB capture strategies
- framebuffer count
- PSRAM placement
- task scheduling
- core affinity
- quantization
- detector thresholds

Target:

maximize useful user-visible tracking quality rather than raw detector FPS.

### M7 — Tracking

Run expensive detection only periodically.

Between detections use a lightweight tracking mechanism.

Possible approaches include:

- bounding-box smoothing
- constant velocity model
- exponential moving average
- correlation-based tracking if feasible
- optical-flow style tracking if computationally viable
- custom lightweight tracker

Initial implementation should stay simple.

Example:

```text
detect -> track -> track -> detect -> track -> track
```

Deliverable:

```text
Stable face box despite low detector frequency.
```

### M8 — Custom ML Model

Final learning phase:

```text
training
   |
PyTorch / other framework
   |
export
   |
quantization
   |
model conversion
   |
embedded inference
   |
ESP32
```

Possible experiments:

- custom tiny face detector
- INT8 quantization
- architecture simplification
- reduced input size
- pruning
- operator compatibility
- model memory profiling

The important goal is not simply accuracy.

The goal is to understand:

```text
accuracy
vs
latency
vs
RAM
vs
Flash
vs
power
vs
implementation complexity
```

## Development Philosophy

Always establish a working baseline before optimizing.

Prefer measurements over assumptions.

For every optimization, record:

```text
before
after
delta
```

Do not change camera resolution, model, buffering and task architecture simultaneously.

Where possible, benchmark components independently before integrating them.

## Success Criteria

The first complete version is successful when:

- ESP32-CAM connects to Wi-Fi
- browser receives live video
- face detection runs locally
- detected face bounding box is visible or exposed through an endpoint
- performance and memory usage are measured
- system runs reliably without external inference

High FPS is not required for V1.

The constraints are part of the experiment.

### Inference diagnostics

Open `http://ai-cam.local/inf` for the overlay and live diagnostics.
`http://ai-cam.local/` is the raw MJPEG stream with inference disabled.
Close the raw-stream tab before opening the detection viewer.

The viewer and `/detections` on port 81 show the highest raw candidate score
before box filtering/NMS, the 0.3 threshold, detected versus displayed box counts,
whether inference is running, latest result status, latency and sample age.
A score of -1 means no score is available. `below_threshold` means inference
completed but no candidate passed the score threshold; `no_valid_boxes` means
scores passed but box decoding rejected their geometry. Error statuses distinguish
JPEG inspection, JPEG decoding, preprocessing and box decoding. Displayed boxes
expire after two seconds even if the last inference found an object.

The worker also logs an `AI` summary after completion at most once every five
seconds. CPU utilization alone does not confirm successful inference. Diagnostics
have not yet been verified on hardware.

2026-10-20: A user log showed a crash/reboot followed by camera probe failure
`ESP_ERR_NOT_SUPPORTED`. The panic/backtrace preceding the ELF hash was missing,
so the crash cause is unconfirmed. As a precaution, the detection HTTP response
buffer was moved off the task stack and that server stack increased from 4096 to
8192 bytes. This is not a confirmed hardware fix; collect the full panic output.

Follow-up panic log confirms `Stack canary watchpoint triggered (httpd)` on core 1.
This establishes a stack-boundary violation in an HTTP task, consistent with the
response-buffer/stack-headroom issue above. Both HTTP servers use the task name
`httpd`; without symbolication against the exact crashing ELF, the task name alone
does not identify the handler. Stability after the change still requires a board
test. The subsequent camera probe failure remains a separate unconfirmed issue.

2026-10-20: Lowered the firmware score threshold to 0.30 for real-camera testing.
Removed the 500 ms submission-attempt timer, which also advanced while the worker
was busy and could delay the next inference after completion. The worker remains
single-threaded with one owned input slot and yields between layers. CPU load can
increase; compare stream FPS, latency and completed counts on hardware. Skipped
now counts each offered frame rejected while busy/invalid, not periodic attempts.

### Inference phase timing

`AI_TIMING` and `AI_LAYERS` accompany the five-second AI summary. Values are mean
wall-clock milliseconds over successful inferences since the previous summary;
`samples` is the denominator. JPEG includes header inspection and decoding.
`network` sums convolution times; `yield` separately measures the between-layer
RTOS delays, including scheduling time. Postprocessing includes peak-score
calculation, box decoding and NMS. `total` spans sample submission to completion,
including handoff and small unlisted overheads, but excludes diagnostic printing.
`L0` through `L(N-1)` follow generated `nn_layers` order, including the final head.
Preemption during a phase is included: these are elapsed times, not CPU-cycle
measurements. Timing uses clock reads per phase/layer, not per pixel or multiply;
its overhead has not been benchmarked on hardware.

Inference is pinned to core 1 and executes layers sequentially. CPU0's idle time
is not automatically usable by this worker; using both cores would require
explicit parallel work and measurement of stream/network contention.

### Integer fast paths — 2026-10-20

The QVGA BGR preprocessing path now uses integer 5:2 area-overlap weights instead
of floating-point geometry. Grayscale rounding still precedes area resizing; the
INT8 input contract is unchanged. Other source dimensions retain the generic path.
Dense 1x1, stride-1, unpadded convolutions process four spatial positions together,
sharing weight loads and channel-address arithmetic. Other convolutions retain
the generic implementation. Accumulation order per output, fixed-point rounding,
saturation, network weights, threshold and RTOS yields remain unchanged. No new
frame or activation buffers are allocated.

Baseline supplied by the user before this change: mean JPEG 120.48 ms,
preprocessing 180.11 ms, network 526.74 ms, total 836.42 ms across three six-frame
windows. Hardware speedup is pending. Compare `AI_TIMING`, especially `preprocess`
and `network`, and `AI_LAYERS` L2/L4/L6/L8/L10/L11 after flashing. Also compare
stream FPS and errors under similar scene and Wi-Fi conditions. Desktop numerical
checks do not predict ESP32 timing.

Validation: all 15 Python/native tests passed. The complete INT8 graph matched
the NumPy reference at every layer on four inputs. On 200 validation images,
QVGA preprocessing matched Python exactly and decoded boxes differed by at most
5.96e-8 on identical logits. These checks used a temporary export of
`autolabel-1000-3/best.pt`; the installed firmware model was not replaced.

### Stream A/B modes — 2026-10-20

- `http://ai-cam.local/`: raw MJPEG, never submits frames to inference.
- `http://ai-cam.local/inf`: detection page with boxes and diagnostics. Its image
  uses `/stream-inf`, whose handler submits frames to the inference worker.
- Port 81 continues serving metadata (with read-only cross-origin access for the
  port-80 page); the old port-81 viewer also uses the inference stream.

The mode belongs to the stream request, not a persistent global switch. Closing
an inference stream stops new submissions; an already submitted frame may finish.
Use only one viewer. Close it before switching modes because the synchronous
stream handler occupies its HTTP server until disconnect is detected. Allow one
metrics window to settle, then compare a minute per mode with the same scene and
network. The serial line `Stream started: inference=on/off` confirms the mode.
These routes supersede earlier notes that all streams trigger inference.
