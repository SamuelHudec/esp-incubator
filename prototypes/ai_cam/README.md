# ESP32-CAM: simple local video stream

## First run

The firmware is just **ai_cam.ino + secrets.h**. Open [ai_cam.ino](ai_cam.ino)
in Arduino IDE. The original AI experiment plan is retained below for later.

1. In Boards Manager, install **esp32 by Espressif Systems 3.3.7**.
2. Select **AI Thinker ESP32-CAM** and your programmer's serial port.
3. Edit local `secrets.h` with your 2.4 GHz Wi-Fi name and password. If missing,
   copy [secrets.example.h](secrets.example.h) to `secrets.h`. Git ignores secrets.
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
verification of this instrumentation is pending; the earlier hardware test covers
only the original stream. Compilation passed for AI Thinker ESP32-CAM with the
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

## Known limitations and next steps

JPEG video at 320 × 240, one viewer at a time. No audio, recording, face detection
or authentication. Use a trusted LAN without Internet port forwarding. Guest Wi-Fi
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
