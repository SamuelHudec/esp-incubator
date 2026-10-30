# ESP32-CAM illumination research — 2026-10-30

Status: research only; automatic LED control is not implemented or hardware-tested.
Target: existing AI Thinker ESP32-CAM / OV2640 with one-bit SDMMC.

## Findings from primary sources

| Project | Actual behavior / parameters | Relevance |
|---|---|---|
| Espressif CameraWebServer, Arduino core 3.3.12 | GPIO4 for AI Thinker, PWM 5 kHz / 8 bits, duty 0–255; capture handler waits 150 ms after enabling LED | Proven example settings for PWM and a capture lead time; not a brightness-feedback controller |
| s60sc ESP32-CAM_Motion | Computes mean sampled RGB intensity as percent of 255; example night threshold 10%; NIGHT_SEQUENCE=10 and `nightCnt > NIGHT_SEQUENCE` (11 qualifying checks) | Concrete image-based darkness detector; not calibrated lux or a universal face-visibility threshold |
| easytarget esp32-cam-webserver | 50 kHz / 9-bit PWM, nonlinear lamp slider; `autoLamp` means on while streaming | Shows an alternative PWM setup, but its auto mode does not measure scene darkness |
| jomjol AI-on-the-edge-device sample config | LEDIntensity=50 and WaitBeforeTakingPicture=2 seconds | Practical exposure-settling approach for meter snapshots; not a prescription for continuous face-detection lighting |

Sources inspected:

- [Espressif PWM and capture code](https://github.com/espressif/arduino-esp32/blob/3.3.12/libraries/ESP32/examples/Camera/CameraWebServer/app_httpd.cpp)
- [Espressif AI Thinker pin mapping](https://github.com/espressif/arduino-esp32/blob/3.3.12/libraries/ESP32/examples/Camera/CameraWebServer/camera_pins.h)
- [s60sc light-level and night-sequence implementation](https://github.com/s60sc/ESP32-CAM_Motion/blob/master/motionDetect.cpp)
- [s60sc example threshold](https://github.com/s60sc/ESP32-CAM_Motion/blob/master/ESP32-CAM_Motion.ino)
- [easytarget PWM and autoLamp implementation](https://github.com/easytarget/esp32-cam-webserver/blob/master/esp32-cam-webserver.ino)
- [AI-on-the-edge-device sample config](https://github.com/jomjol/AI-on-the-edge-device/blob/main/sd-card/config/config.ini)

The s60sc sample confirms darkness over multiple checks but uses the same threshold
for return to day; do not describe it as implementing separate on/off thresholds.
Enabling its lamp changes the image being measured, so its exact controller should
not be copied without accounting for that feedback. Source paths on moving branches
can change; the Espressif example is pinned to our installed core version.

## Proposed adaptation, not externally validated tuning

- Start from Espressif's 5 kHz / 8-bit PWM. Allocate a timer/channel independent of
  the camera's LEDC timer 0/channel 0; verify this against the installed core.
- Reuse the decoded/preprocessed image in the inference worker, without another
  JPEG decode. That makes this first auto mode dependent on inference activity.
  Automatic lighting in raw-stream/capture modes needs a separate measurement path.
- Measure brightness separately from detection confidence. Mean image intensity
  is affected by auto exposure, gain, scene reflectance and lamp illumination.
- Adjust slowly, initially no more frequently than every two seconds after a
  change, to allow exposure to settle. Use smoothing/deadband and gradual PWM
  changes rather than immediate on/off based on a single frame.
- Try low duty values such as 32–64 out of 255 initially; these are our trial
  values, not a published continuous-current or thermal safety rating. Verify
  illumination, face detail, power stability and SD operation on this board.
- Do not copy the sample 10% night threshold as a face-visibility threshold.
  Record image brightness/quality with LED off and at trial duty levels at the
  actual face distance; choose target/deadband from those observations.
- Keep automatic gain/exposure behavior unchanged for the first LED test so we
  can attribute changes. Snapshot lead-time examples do not guarantee settling
  under all continuous-stream conditions.

GPIO4 also connects to SD DAT1; our one-bit transfer uses CLK14/CMD15/DAT0=2.
Simultaneous PWM/card writes require a board test, with photos and stream checked.
