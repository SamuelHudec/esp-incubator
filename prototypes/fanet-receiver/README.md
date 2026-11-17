# FANET receiver for FlySkyHy

Receive FANET traffic offline and display nearby pilots in FlySkyHy on iOS.

**Status — 2026-10-26:** feasibility study and BLE bench probe only. Compilation,
iPhone interoperability and RF reception have not been tested.

## Hardware, wiring and power

The BLE probe needs a BLE-capable ESP32 and USB power; no external radio wiring.
Radio candidates are LILYGO T3/LoRa32 SX1276 868 MHz, or T-Beam with GNSS.
Exact board/revision is undecided; consult [wiring and power](docs/wiring.md)
before selecting pins or connecting hardware. Battery setup is deferred until
polarity, charging and protection are verified for the actual board and cell.

## Build and flash

1. Install Espressif **esp32 2.0.17** in Arduino IDE.
2. Open [ble_probe.ino](firmware/ble_probe/ble_probe.ino), select your actual
   BLE-capable ESP32 board and port. No extra libraries required.
3. Upload using that board's procedure. Open Serial Monitor at **115200 baud**
   with newline line endings.

## Verify the BLE probe

Test on the ground, outside a flight recording session:

1. In FlySkyHy, select Settings → Vario → Bluetooth device → Model → Other
   Device → **FANET-Bench**. Keep the iPhone as the GPS source.
2. Obtain a valid phone position; enter `TEST` in Serial Monitor. For 60 seconds,
   the probe sends a synthetic target 200 m north, 100 m east and 50 m above
   the app reference position, plus a heartbeat.
3. Check target visibility and altitude. Enter `STOP`; check target expiry and
   disconnect/reconnect behavior. If diagnosing BLE, service is FFE0 and
   characteristic FFE1 with notifications/CCCD.
4. Repeat offline with maps preloaded and Bluetooth/location enabled. Record
   board, core, iOS/app versions and results.

This checks BLE parsing only, not FANET reception or moving-receiver positioning.

## Limitations and next steps

PFLAA uses relative offsets, so the receiver needs its own position to convert
absolute FANET coordinates. A supported phone-to-receiver GPS feed has not been
established; integrated GNSS may be necessary. FANET reception does not decode
FLARM-only radio traffic. This is not a collision-warning system.

First verify BLE and resolve the position source, then select exact radio hardware
and implement receive-only firmware. Disable RF forwarding, acknowledgements,
beacons and tracking transmissions. See [feasibility notes](docs/feasibility.md)
for protocol evidence and open decisions.
