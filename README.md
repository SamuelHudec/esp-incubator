# ESP Incubator

Independent ESP hardware experiments. Each prototype contains its own firmware,
setup instructions and notes.

| Project | Purpose | Status |
| --- | --- | --- |
| [AI cam](prototypes/ai_cam/) | Camera stream, on-device face detection and SD capture | Working prototype; model quality in development |
| [2.4 GHz Signal Lab](prototypes/2g4-signal-lab/) | ESP32-C3 and nRF24L01+ radio experiments | Wiring planned; SPI probe prepared |
| [FANET Receiver](prototypes/fanet-receiver/) | FANET traffic bridge to FlySkyHy | Feasibility / BLE probe |

Start a new experiment by copying [templates/prototype](templates/prototype/)
into `prototypes/<name>/`. Use Arduino IDE unless the prototype documents another
workflow. Repository rules are in [AGENTS.md](AGENTS.md).

Keep credentials, datasets, generated models and build outputs local and ignored.
Commit sanitized configuration examples only.
