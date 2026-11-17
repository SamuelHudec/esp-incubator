# Wiring and power

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
- The flash LED is controlled via a dedicated PWM timer; see
  [illumination modes and verification](illumination.md). The microSD socket uses one-bit
  SDMMC for on-demand photo capture (see [SD notes](sd-capture.md)). Brownout
  detection remains enabled; fix the power supply if brownout resets occur.
- The AI Thinker Arduino board profile uses a 4 MB flash layout. The seller currently lists
  8 MB while the older manufacturer specification lists 4 MB. Check the actual
  flash size in the boot/upload output; this application does not require 8 MB.
