# 2.4 GHz Signal Lab

An iterative learning gadget built around a LaskaKit microESP-C3 and an
nRF24L01+ PA/LNA module. The long-term idea is to expose observations on a local
web page reachable from a phone.

## Status

**Phase 0 — wiring planned, not yet verified on hardware.**

The first milestone is deliberately small: power the nRF24 safely and confirm
that the ESP32-C3 can read its registers over SPI. Transmission stays disabled
until that test succeeds.

## Hardware

- LaskaKit microESP-C3 v3.2 (ESP32-C3)
- nRF24L01+ compatible 2.4 GHz PA/LNA module with antenna
- 47–100 µF electrolytic capacitor (at least 6.3 V)
- 100 nF ceramic capacitor, recommended
- short jumper wires or a suitable adapter PCB

## Documentation

- [`wiring.md`](wiring.md) — proposed SPI wiring and power precautions
- [`secrets.example.h`](secrets.example.h) — sanitized local
  Wi-Fi configuration template for a later web-interface phase

## Intended learning stages

1. Verify power and SPI communication with the nRF24.
2. Scan nRF24 channels using its Received Power Detector (RPD).
3. Compare observed activity while generating known Wi-Fi/BLE traffic.
4. Scan Wi-Fi and Bluetooth LE using the ESP32-C3's own radio.
5. Serve a small local dashboard to a phone.
6. Record limitations and distinguish energy detection from protocol decoding.

## Important limitation

The nRF24L01+ is not a general-purpose spectrum analyzer and cannot decode
Wi-Fi or Bluetooth packets. Its RPD can provide a coarse indication that energy
above its threshold was present on a selected channel. Wi-Fi and BLE discovery
will use the ESP32-C3 radio separately.

## Build and flash

The first firmware is [`2g4-signal-lab.ino`](2g4-signal-lab.ino).
It only checks SPI communication and does not transmit radio packets.

Arduino IDE setup:

1. Install the `esp32` board package by Espressif Systems in Boards Manager.
2. Install `RF24` by TMRh20 in Library Manager.
3. Open the `.ino` file and select `ESP32C3 Dev Module`.
4. Enable `USB CDC On Boot` if that option is available.
5. Upload the sketch and open Serial Monitor at `115200` baud.

If upload does not start automatically, enter the bootloader manually: hold
`FLASH`, press and release `RESET`, then release `FLASH`.

## Verification

No hardware test has been performed yet. A successful first test prints
`nRF24: detected` and continues without reporting a lost connection. If it
prints `nRF24: NOT DETECTED`, disconnect power before checking the wiring.
