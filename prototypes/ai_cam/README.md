# AI cam

Local MJPEG streaming and face detection on an AI Thinker ESP32-CAM.
A custom model is trained in Python and runs on the board through a plain C
INT8 runtime. No cloud inference.

## Status

Streaming, inference, SD photo capture and manual/automatic LED control have
been tested on hardware. Face detection quality remains experimental, especially
in dim light. Measurements and test history: [experiment log](docs/experiment-log.md).

## Hardware and setup

| Component | Project hardware / configuration |
| --- | --- |
| Board | AI Thinker ESP32-CAM, LaskaKit LA100069; physical PCB revision not recorded |
| Processor | Classic ESP32, dual-core 32-bit Xtensa LX6, running at 240 MHz; exact chip suffix/revision not recorded |
| Internal RAM | 520 KB SRAM on the chip; only part is available as application heap |
| External RAM | 4 MB PSRAM per board specification; first stream logs reported 4,156,888 bytes free |
| Flash | Firmware uses a 4 MB flash layout; physical capacity of this board has not been verified |
| Camera | OV2640; configured for 320 × 240 JPEG, quality 12, two framebuffers in PSRAM |
| Wireless | 2.4 GHz Wi-Fi 802.11 b/g/n; Bluetooth 4.2 / BLE available but unused |
| Storage | Onboard microSD socket, FAT32, one-bit SDMMC for photos |
| Illumination | Onboard white LED on GPIO4, PWM brightness control |
| Programming | External USB-to-UART programmer; tested with a CH340 USB-C ESP32-CAM programmer |
| Power / logic | 5 V board supply, 3.3 V UART logic; see wiring notes before connecting |

Memory capacities are not free-memory budgets: firmware, Wi-Fi, camera buffers
and inference consume RAM. Live metrics report internal and PSRAM heap usage
separately. Flash stores firmware/model weights; it is not working RAM.

Sources: [ESP32 datasheet](https://documentation.espressif.com/esp32_datasheet_en.pdf),
[AI Thinker board specification](https://www.laskakit.cz/user/related_files/esp32-cam_product_specification.pdf),
and the project's [measurements](docs/experiment-log.md).
See [pin table, power and programming notes](docs/wiring.md) for board-variant
caveats. Disconnect power before changing wiring or cards.

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

Optional secondary Wi-Fi in `firmware/secrets.h`:

```cpp
#define WIFI_FALLBACK_SSID "YOUR_SECOND_WIFI_NAME"
#define WIFI_FALLBACK_PASSWORD "YOUR_SECOND_WIFI_PASSWORD"
```

The camera tries primary for 15 seconds, then fallback for 15 seconds, repeating
until connected. An empty or omitted fallback SSID keeps single-network behavior.
After a disconnect it tries primary first again; a working fallback is kept until
disconnected. Both networks must support 2.4 GHz. Recompile/upload after editing.
Verify by booting with primary unavailable, checking fallback access, then dropping
that connection and checking reconnection. Hardware verification is pending.

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
