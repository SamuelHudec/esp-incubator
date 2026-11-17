# 2.4 GHz Signal Lab

Explore 2.4 GHz activity using an ESP32-C3 and nRF24L01+ PA/LNA.

**Status:** wiring planned; SPI probe prepared. No hardware test yet.
The current firmware checks radio registers without transmitting.

## Hardware and wiring

- LaskaKit microESP-C3 v3.2 and nRF24L01+ PA/LNA with antenna.
- 47–100 µF capacitor (at least 6.3 V); 100 nF ceramic recommended.
- Short wires or an adapter PCB.

Follow the [proposed pin table and power checks](wiring.md). Power the radio
from **3.3 V**, never 5 V; verify module labels and capacitor polarity before
powering it. Disconnect power before changing connections.

## Build and flash

1. In Arduino IDE, install Espressif's `esp32` board package and `RF24` by TMRh20.
   Versions are not yet pinned.
2. Open [2g4-signal-lab.ino](2g4-signal-lab.ino), select **ESP32C3 Dev Module**
   and enable **USB CDC On Boot**, if available.
3. Upload and open Serial Monitor at **115200 baud**. For manual bootloader
   entry, hold FLASH, press/release RESET, then release FLASH.

## Verification and next step

Expect `nRF24: detected` with no subsequent lost-connection report.
If detection fails, disconnect power before checking wiring.

After SPI works, test channel activity using the radio's Received Power Detector.
RPD is coarse energy detection: it cannot decode Wi-Fi/BLE packets or replace
a spectrum analyzer. ESP32 discovery and a local dashboard are later work.
