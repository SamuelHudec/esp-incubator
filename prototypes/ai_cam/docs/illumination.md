# Onboard illumination — 2026-10-30

## Hardware and configuration

Target: existing AI Thinker ESP32-CAM / OV2640 with its onboard white LED on GPIO4.
GPIO4 also connects to SD DAT1. Keep SDMMC in one-bit mode (CLK14/CMD15/DAT0=2).
No additional wiring, voltage or external load is introduced. Simultaneous LED/SD
operation is still a hardware test item, not a completed verification.

Sources: [Espressif AI Thinker pin definition](https://github.com/espressif/arduino-esp32/blob/3.3.12/libraries/ESP32/examples/Camera/CameraWebServer/camera_pins.h),
[Espressif PWM example](https://github.com/espressif/arduino-esp32/blob/3.3.12/libraries/ESP32/examples/Camera/CameraWebServer/app_httpd.cpp)
and [research notes](illumination-research.md).

Edit the constants near the top of `firmware/firmware.ino`:

| Setting | Initial value | Meaning |
|---|---:|---|
| `LIGHT_ENABLED` | `true` | Master switch; `false` overrides all modes and holds LED off |
| `LIGHT_MAX_PERCENT` | `25` | Cap for manual/auto PWM duty, not a thermal or power rating |
| `LIGHT_AUTO_STEP` | `8` | PWM counts per automatic adjustment, out of 255 |
| `LIGHT_SETTLE_MS` | `2000` | Minimum settling time after a change |
| `LIGHT_DARK_PERCENT` | `20` | Raise duty below this smoothed image intensity |
| `LIGHT_BRIGHT_PERCENT` | `35` | Lower duty above this smoothed image intensity |

PWM: 5 kHz, 8-bit, low-speed LEDC timer 1 / channel 2, independent of camera timer
0 / channel 0. Only Arduino loop writes PWM. The duty cap and feedback thresholds
are initial project choices to tune on the actual scene, not published universal
values. Increasing duty increases board power and LED heating; preserve the
existing documented supply arrangement and validate it on this board.

## Modes and lifecycle

- `/`: Off, for comparable raw-stream measurements.
- `/camera`: Manual. Slider values are PWM duty percentages, limited by the cap.
  Each new stream starts at zero; settings are not persisted to flash/SD.
- `/inf` (including the old port-81 viewer): Auto. Begins at zero and uses mean
  image intensity from the existing 128x96 grayscale INT8 input, before inference
  overwrites it. This reuses preprocessing, without an additional JPEG decoder.

The stream request owns the mode. Its guard returns to Off on all handler exits.
A four-second heartbeat timeout also turns off a stalled stream. The main loop
applies changes on its roughly 100 ms cadence. Mode changes and the master switch
are rechecked before output. An in-flight worker result is ignored for lighting
if its stream is no longer in Auto.

Auto uses a 0.25-weight exponential filter, a 20–35% deadband, and duty steps of
8 up to the cap. Samples captured before the last change has settled are ignored;
a new duty requires another two-second settling period. Light measurement is an
image intensity percentage, not lux or model confidence. Camera exposure/gain can
compensate for darkness; this first controller cannot guarantee improvement in
face recognition or optimal illumination for every background/distance.

## Capture and control

Port 81 `/light` supports GET status and POST `?value=<percent>` from this camera's
pages. Updates require the active Manual stream, enabled hardware and a valid
value within the configured cap. It reports initialization/master-disable state.
The `/camera` slider briefly disables photo capture while illumination/exposure
settles. The stream's SD-save path also checks settling before using a frame.
The original five-second pending-photo deadline still applies. Wait for **Saved**
before powering off/removing the SD card. No additional image buffer is allocated.

## Verification

Desktop checks cover controller settling, stale samples, deadband, duty saturation,
reset, manual UI requests, master-disabled UI and SD-capture flow. Firmware was
compiled for AI Thinker core 3.3.12. Actual illumination/SD/FPS effects are pending.

After flashing (remove SD while powered off for upload on this setup):

1. Boot normally with SD. Open only `/camera`; LED should begin off. Try low manual
   brightness, confirm visible changes, and capture a readable JPEG on SD.
2. Close the viewer; LED should turn off after disconnect detection, with a
   four-second heartbeat fallback for blocked streams.
3. Open `/inf`, darken/brighten the scene, and observe slow bounded steps without
   immediate on/off oscillation. Compare FPS/IPS and power/reset behavior.
4. Set `LIGHT_ENABLED=false`, rebuild/upload, and confirm both modes keep LED off
   and the manual slider is unavailable.

Hardware feedback: the user confirmed manual/auto operation and reported direct
LED glare with limited perceived illumination benefit. A proposed reduction to
5% duty / 2-count steps was reverted at the user's request. Keep the original
25% cap / 8-count steps while collecting further data.
