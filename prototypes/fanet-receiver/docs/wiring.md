# Wiring and power gate

Status: 2026-10-26, exact board/revision not selected. Do not wire an external
radio or battery from a generic ESP32/LoRa tutorial.

| Connection | Current decision | Required verification |
| --- | --- | --- |
| USB | Bench power and programming via onboard port | Selected board manual |
| SPI SCK/MISO/MOSI/NSS | Not assigned | Exact schematic and board definitions |
| Radio RESET/IRQ | Not assigned | SX1276 DIO mapping or SX1262 DIO1/BUSY mapping |
| Radio power/logic | Not assigned | Exact module voltage and supply requirements |
| Antenna | Matching 868 MHz antenna required | Board connector and RF variant |
| GNSS | Architecture pending | Integrated model, UART, enable and power pins |
| Battery | Not connected | Polarity, chemistry, full-charge voltage, charger current, protection |

Primary manufacturer references:

- [LILYGO LoRa series](https://github.com/Xinyuan-LilyGO/LilyGo-LoRa-Series)
- [T3 V1.6.1 schematic candidate](https://github.com/Xinyuan-LilyGO/LilyGo-LoRa-Series/blob/master/schematic/T3_V1.6.1.pdf)
- [T-Beam V1.2 schematic candidate](https://github.com/Xinyuan-LilyGO/LilyGo-LoRa-Series/blob/master/schematic/LilyGo_TBeam_V1.2.pdf)

These links identify documents to match to the purchased board; electrical
values have not yet been extracted or approved. Do not infer battery polarity
from connector shape or wire colour. Measure whole-device current in continuous
receive with BLE connected before estimating endurance; a radio-only RX current
is insufficient.
