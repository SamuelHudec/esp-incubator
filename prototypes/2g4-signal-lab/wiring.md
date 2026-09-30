# Proposed wiring: microESP-C3 to nRF24L01+ PA/LNA

> Status: proposed on 2026-09-23; verify the labels and exact board revision
> before applying power.

| nRF24L01+ pin | microESP-C3 pin | Purpose |
| --- | --- | --- |
| VCC | 3V3 | 3.3 V supply — never connect to VIN or 5 V |
| GND | GND | Common ground |
| SCK | GPIO5 | SPI clock |
| MOSI | GPIO7 | ESP32-C3 to nRF24 data |
| MISO | GPIO6 | nRF24 to ESP32-C3 data |
| CSN / CS | GPIO3 | SPI chip select |
| CE | GPIO1 | Radio RX/TX enable |
| IRQ | not connected | Optional interrupt, not needed initially |

## Power precautions

- Disconnect USB and every other power source while changing wiring.
- Power the radio from 3V3 only. The module is specified for 1.9–3.6 V.
- Place a 47–100 µF electrolytic capacitor directly across the radio's VCC and
  GND pins; connect its positive lead to VCC and negative lead to GND.
- Add a 100 nF ceramic capacitor in parallel when available.
- Keep the power, ground, and SPI wires short. PA/LNA modules have current spikes
  that make marginal wiring especially unreliable.
- Follow the printed signal labels, not a memorized connector orientation.
  Clones may differ, and swapping VCC/GND can destroy the module.

## First power-on checklist

- [ ] Board and module revisions match the documentation.
- [ ] VCC is connected to 3V3, not VIN/5V.
- [ ] Grounds are connected.
- [ ] Capacitor polarity is correct.
- [ ] Antenna is attached before any later transmission test.
- [ ] Multimeter shows approximately 3.3 V at the module.
- [ ] Initial firmware performs SPI detection only.
