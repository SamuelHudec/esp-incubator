# AI cam

Local MJPEG streaming and face detection on an AI Thinker ESP32-CAM.
A custom model is trained in Python and runs on the board through a plain C
INT8 runtime. No cloud inference.

## Status

Streaming, inference, SD photo capture and manual/automatic LED control have
been tested on hardware. Face detection quality remains experimental, especially
in dim light. Measurements and test history: [experiment log](docs/experiment-log.md).

## Hardware and setup

- AI Thinker ESP32-CAM with OV2640 and PSRAM; classic ESP32 at 240 MHz.
- USB programmer; FAT32 microSD optional for photo capture.
- [Pin table, power and programming notes](docs/wiring.md).
  Use 3.3 V UART logic; disconnect power before changing wiring or cards.

1. Install **esp32 by Espressif Systems 3.3.12** in Arduino IDE.
2. Open [firmware/firmware.ino](firmware/firmware.ino), select
   **AI Thinker ESP32-CAM** and the serial port. No extra libraries required.
3. Copy `firmware/secrets.example.h` to `firmware/secrets.h` and enter your
   2.4 GHz Wi-Fi credentials. The local file is ignored by Git.
4. Upload following your programmer's boot/reset procedure. On this setup,
   remove the SD card with power off before uploading; reinsert with power off.
   Release GPIO0 from ground before normal boot.
5. Open Serial Monitor at **115200 baud** and use the printed address.
   If `ai-cam.local` does not resolve, use the printed IP.

## Use

Keep only one stream viewer open.

| Address | Function | Light |
| --- | --- | --- |
| `http://ai-cam.local/` | Raw stream, no inference | Off |
| `http://ai-cam.local/inf` | Stream, detection boxes and live metrics | Auto |
| `http://ai-cam.local/camera` | Stream and **Save photo to SD** | Manual slider |

Photos are original 320×240 JPEGs stored in `/photos` on the card. Wait for
**Saved to SD** before powering off. The firmware never formats the card.
See [SD capture](docs/sd-capture.md) for troubleshooting.

Light settings are at the top of `firmware.ino`. `LIGHT_ENABLED=false` overrides
all modes. The current PWM cap is 25%; automatic adjustments settle for two
seconds. See [illumination](docs/illumination.md) for configuration and behavior.

## Model and diagnostics

Follow the [training workflow](neuralnet-training/README.md) to annotate, train
and quantize. Successful quantization installs `firmware/neuralnet/nn_model.h`;
then compile and upload to use it. Without the generated header, streaming works
with detection disabled. Model files and training data are not committed.

Inference runs on CPU1 while `/inf` is active. It accepts a new frame when the
worker is free, skipping frames rather than queuing them. Boxes show the latest
result; they are not frame-synchronized tracking. Firmware score threshold: 0.30.

The browser shows stream FPS, completed inferences per second (IPS), score,
CPU0/CPU1 and internal/PSRAM heap usage. RAM percentages refer to allocator heaps,
not all physical memory. Serial logging is controlled by `LOG_PROFILE` in
`firmware/logging_config.h`:

- `0`: compact stream/AI rows every five seconds, memory once per minute.
- `1`: adds JPEG, preprocessing, network and per-layer timings.

Recorded observations: roughly 25 FPS without inference and 23 FPS with
~2.5 IPS after optimization. These are scene/network-dependent observations,
not throughput guarantees; see the experiment log for conditions and tables.

## Verification and next steps

After flashing, check raw video, `/inf` metrics and boxes, an SD photo, and
reconnection after closing the viewer and power cycling. Check Serial Monitor
for errors and sustained memory loss. Test manual light on `/camera` and automatic
light on `/inf`; direct LED glare may limit its usefulness.

Next: collect and review real camera data, then compare model changes using the
[architecture experiment plan](docs/architecture-experiment-plan.md).
The [technical reference](docs/architecture-reference.md) describes the current graph.
