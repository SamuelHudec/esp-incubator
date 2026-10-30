# FANET receiver for FlySkyHy

## Purpose

Receive nearby FANET pilots offline and display traffic in FlySkyHy on iOS.
No display, vario, Wi-Fi, internet gateway or own-position RF transmission.

## Status

**Planning / BLE probe prepared — 2026-10-26.** Documentation and source review
only. No sketch compilation, iPhone interoperability or RF hardware test has
been performed. The BLE sketch is a bench experiment, not receiver firmware.
See [feasibility](docs/feasibility.md) for evidence and unresolved decisions.

## Hardware

Recommended first architecture: one integrated ESP32 + 868 MHz LoRa board,
matching antenna, USB power for initial tests. Prefer an SX1276 board for the
first receiver because the reviewed FANET implementations provide references.
An SX1262 alternative is reasonable after verifying its exact board support.

Two purchasing paths remain:

- Lowest component count if GPS-free operation is verified: LILYGO T3/LoRa32
  SX1276 868 MHz. Exact revision must be selected before wiring or RF code.
- More straightforward moving receiver with its own position: LILYGO T-Beam
  ESP32 + SX1276 + GNSS, 868 MHz variant. Larger, but avoids a separate GNSS
  module and its wiring. Verify the exact revision and GNSS variant first.

These are candidate families, not interchangeable pin-compatible boards.
A display already included on a cheap board can remain unused. No current
price, dimensions or battery endurance is claimed; compare delivered prices
for exact variants after the own-position decision.

## Wiring

See [wiring and power](docs/wiring.md). No external radio wiring is approved yet.
The BLE probe uses only the selected board's USB connection and onboard BLE.

## Power and safety

Use the board's documented USB power input for the first bench test. Battery
operation is deferred until connector polarity, chemistry, charging current
and protection have been checked against the exact board revision and cell.
The finished receiver must disable FANET forwarding, acknowledgements,
beacons and tracking transmission, not just periodic position messages.

## Build and flash

1. Use Arduino IDE and install Espressif's **esp32 2.0.17** board package.
2. Open [ble_probe.ino](firmware/ble_probe/ble_probe.ino).
3. Select the actual BLE-capable ESP32 board and USB port. Do not select a
   board profile from a visually similar board. No external libraries required;
   the sketch uses the core's bundled BLE library.
4. Compile and upload using the selected board's documented procedure.
5. Open Serial Monitor at 115200 baud with newline line endings.

The version is a deliberate probe baseline, not a claim of latest support.
RF settings and pin mappings are intentionally absent from this BLE-only sketch.

## Verification

Perform on the ground, outside a flight recording session:

1. Confirm BLE advertising name `FANET-Bench`, service FFE0, characteristic
   FFE1, notifications and CCCD using a BLE inspector if needed.
2. In FlySkyHy: Settings → Vario → Bluetooth device → Model → Other Device;
   select `FANET-Bench`. Keep the iPhone as the own GPS source.
3. Obtain a valid phone position. Enter `TEST` in Serial Monitor. For 60 seconds
   the probe emits one synthetic PFLAA target per second and a PFLAU heartbeat.
   Target: 200 m north, 100 m east, 50 m above the app reference position.
4. Record whether it appears, whether GPS=0/TX=0 status prevents display, and
   whether relative vertical position follows the expected altitude reference.
   A missing marker is an unresolved result; do not fake a valid GPS status.
5. Enter `STOP`, confirm PFLAA output ends, and record when the app expires
   the marker. Disconnect/reconnect and confirm notifications resume.
6. Repeat offline with maps preloaded, mobile data and Wi-Fi off, Bluetooth
   and location available. Record iOS/app/core versions and exact board.

`TEST` is opt-in and expires after 60 seconds. A displayed synthetic marker
proves BLE parsing only; it does not establish correct absolute target placement
for a moving GNSS-free receiver. No actual FANET packets are received.

## Known limitations

PFLAA reports relative offsets. The bridge needs its own current latitude,
longitude and altitude to convert absolute FANET positions. A supported reverse
GPS feed from FlySkyHy or an absolute-position traffic sentence has not been
established. A fixed bench reference is unsuitable while flying. FANET reception
does not imply reception of FLARM-only transmitters; FLARM-formatted BLE text
is an output format, not a FLARM radio decoder. This prototype has no collision
prediction or certified warning function.

## Next steps

1. Verify the BLE probe on an available ESP32 and iPhone before buying a radio.
2. Resolve own-position input; use integrated GNSS if no documented phone feed
   or supported absolute-target format can be demonstrated.
3. Select exact board/revision; verify schematic, pins and power notes.
4. Implement radio RX only, separate FANET parser and traffic formatter; add
   meaningful malformed-frame and reference-vector tests before hardware trials.
5. Test against an owned FANET source, then measure current and choose a cell.
