# NFC Lab

An offline USB console for exploring ISO/IEC 14443-A tags. The ESP32 handles timing, PN532 normal frames, tag selection and checked page operations. Python handles presentation, capture files and the interactive copy workflow. The sketch uses Arduino Wire directly so polling requires only the existing I²C wires. The macOS console uses the Python 3 standard library. No network setup or radio services are used.

## Status and hardware

2026-11-19: the Arduino target is an ESP32-C3 Super Mini connected by USB to macOS and by I²C to a PN532 breakout. The builder confirmed SDA on GPIO8 and SCL on GPIO9. The breakout revision, switch positions and power wiring are undocumented. Physical validation is pending.

| Connection | Wiring and verification |
|---|---|
| SDA | GPIO8 (console default) |
| SCL | GPIO9 (console default) |
| GND | Verify common ground with power disconnected. |
| VCC and pull-ups | Identify both PCB revisions. Check the module manual for supply input, regulator, pull-ups and level shifting. Verify bus high level is compatible with 3.3 V GPIO and the board supply can handle the stated module load before powering. |
| USB | Use a data cable. GPIO18 and GPIO19 serve native USB on the C3. |
| Mode | Verify the breakout's I²C selector settings against its own manual before power-up. |
| IRQ and reset | The firmware polls the I²C ready byte and relies on module power-on reset. |

Record the PCB markings, manual and measured bus voltage here after the bench test. The sketch accepts GPIO0–10 only and never selects pin defaults. The PN532 uses 7-bit address 0x24 at 100 kHz. An INIT success validates a PN532 firmware response over the chosen wires.

References: [PN532 firmware manual UM0701-02](https://www.nxp.com/docs/en/user-guide/141520.pdf), [NTAG213/215/216 memory and command specification](https://www.nxp.com/docs/en/data-sheet/NTAG213_215_216.pdf), [ESP32-C3 datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-c3_datasheet_en.pdf).

## Build, flash and run on macOS

1. In Arduino IDE 2 install **esp32 by Espressif Systems 3.3.12** through Boards Manager. Wire comes with the core. Open [nfc_lab.ino](firmware/nfc_lab/nfc_lab.ino).
2. Select **ESP32C3 Dev Module**, enable **USB CDC On Boot**, select the board's USB port, Verify and Upload. If the port is missing, hold BOOT, tap RESET, release BOOT and reselect the port. Close Serial Monitor before opening the console.
3. From this prototype directory, install the terminal command with uv. An editable install picks up changes to the checkout automatically. uv manages the Python environment. No activation is needed.

~~~sh
uv tool install --editable .
nfc-lab
~~~

For development in the checkout, use `uv run nfc-lab` and `uv run python -m unittest -v`. The console has no third-party runtime dependencies. An offline installation requires a compatible local Python and a cached build dependency.

The console selects a single USB modem automatically. To choose among several, run `nfc-lab /dev/cu.usbmodemPORT` with the actual device name. The default wiring is SDA 8 and SCL 9.

In an interactive terminal, use the arrow keys to move through the action menu and Enter to select. The menu offers actions based on the current scan or loaded capture. Save and Load prompt for a file path. Copy NDEF appears for eligible NTAG213 captures with a complete supported NDEF layout. Read sector prompts for the sector number and lets you select Key A or Key B.

## Verification

1. Start the console. Expect the IC/version/revision/support response beginning with 32. If initialization fails, recheck wiring, selector and power, then power-cycle the reader.
2. Present one tag. Select **Scan**. Check UID, raw ATQA/SAK, reported version, hex pages, access registers and NDEF output. Try a tag with known text or a URL. Remove it and check that a new scan fails.
3. Select **Save** and enter `captures/source.json`, then select **Load** and enter the same path. Compare **Show** with the scan. Save refuses to overwrite an existing file. Captures may contain personal data; captures/ is ignored.
4. Use two different NTAG213 tags. Scan and save the destination first if its data matters. Load the source capture again, present only the destination, then select **Copy NDEF**. Check the destination UID and page preview. Cancel once and confirm that the original data is intact. Repeat and type the requested confirmation.
5. After verification, scan again and check the decoded records and destination UID independently with a phone. Record board revisions, GPIOs, tags and observed outcomes here.

## Coverage and limitations

| Tag or data | First-version behavior |
|---|---|
| Type A target | Shows UID, ATQA and SAK. Other RF protocols and application-specific files are unsupported. |
| NTAG213/215/216 | Matches the complete GET_VERSION response along with Type A metadata. Reports the inferred model and shows raw identification for unknown layouts. Reads individual four-byte pages through both configuration registers. The memory view displays hex page addresses, hex bytes, and printable ASCII. The read-byte count excludes unavailable pages and masked fields. Failed pages are marked unavailable; RF errors cannot establish protection by themselves. |
| Manufacturer and access | Reports the recognized version's manufacturer, static and dynamic lock bytes, capacity container (CC), AUTH0 and ACCESS. A masked password/PACK is never saved as recovered data. |
| NDEF | Walks Type 2 TLVs and ordinary unchunked NDEF records. Displays raw type, identifier, payload and TNF. Decodes Text and common URI prefixes. Remaining encodings retain their hex representation. |
| Copy | One ordinary NDEF TLV between standard NTAG213 tags. Accepts a blank destination or an existing NDEF TLV, including the standard NTAG213 lock-control prefix. Requires readable user pages and rejects locked, mirrored or password-configured destinations and unknown layouts. |
| Excluded from copy | UID, manufacturer pages, locks, CC, configuration, secrets and trailing source storage. Old bytes beyond the destination message can remain. |

Copy stages an empty message, updates changed pages and publishes the final length last. Each page receives an immediate read-back, followed by a fresh destination scan and full affected-range comparison. Keep one tag stationary. Power loss or removal can leave an empty, incomplete or uncertain destination. Inspect it again before retrying. A saved capture is required to restore an old message.

Next steps are a two-tag bench verification and additional read-only tag layouts based on observed ATQA, SAK and version responses.

## MIFARE Classic inspection

Upload the updated sketch before using authenticated reads. Refresh an existing editable uv install to register the new Classic module. Run `uv tool install --editable . --reinstall` from this directory.

1. Place one card on the reader and select **Scan**. For ATQA `0004` and SAK `08`, expect the likely Classic 1K layout with 16 sectors, 64 blocks and 1024 bytes. Classic 4K has 40 sectors, 256 blocks and 4096 bytes. Its first 32 sectors have four blocks each and the remaining eight have 16. All blocks are 16 bytes.
2. If you have an authorized sector key, select **Read sector**, enter the sector number, choose **Key A** or **Key B**, and type the 12 hexadecimal digits at the hidden prompt. Use the decimal sector number. The reader reselects the expected UID before each request. There is no default key list, discovery, or fallback to another key. Each request replaces the previous result for the selected sector and key type.
3. Use **Show** to review the complete map and captured blocks. Use **Save** to export to `captures/classic.json` and **Load** to review it later. The existing capture format now accepts an optional `classic` object keyed by decimal sector and key type. Each attempt contains authentication status and block records keyed by decimal block address. Successful manufacturer and data reads contain a 32-digit hex string. Trailer records expose only the four returned bytes at offsets 6–9 (access bits and GPB). Key fields are omitted in firmware. Failed or skipped reads have status and error fields without placeholders for raw data.

ATQA/SAK indicate a probable layout. Successful authentication confirms Classic-compatible behavior but cannot establish the manufacturer, exact chip variant, or full capacity. The PN532 performs authentication and reads through `InDataExchange`. The sketch supports the reported 4- and 7-byte UID variants for these layouts. It reads the trailer first, validates the access-bit complements in the console and reports effective read permissions where available. A failed block exchange can invalidate the PN532 session, so remaining blocks for that request are marked unknown. An error can also indicate RF or transport trouble. The next explicit sector request can proceed independently. All Classic operations are read-only. Keys travel over the local USB link to the firmware for the requested operation.

References [NXP MIFARE identification procedure](https://www.nxp.com/docs/en/application-note/AN10833.pdf), [NXP Classic EV1 4K layout and access conditions](https://www.nxp.com/docs/en/data-sheet/MF1S70YYX_V1.pdf), [PN532 application note](https://cdn-shop.adafruit.com/datasheets/PN532C106_Application%20Note_v1.2.pdf).

## Versioning and releases

For each verified rebuild that ships NFC Lab changes, increment the patch version in `pyproject.toml` unless a minor or major release is intended. Regenerate `uv.lock` with `uv lock`, run `uv run --locked python -m unittest -v`, and verify `uv run --locked nfc-lab --version`. Recompile the ESP32 sketch when firmware changes.

Commit the release as `nfc-lab X.Y.Z`, create the annotated tag `nfc-lab-vX.Y.Z` on that commit, and push the branch and tag to origin. Local rebuilds of an already released revision use its existing version.

## Type 2 page probe

For a seven-byte Type A UID with ATQA `0044`, SAK `00`, and an unsuccessful GET_VERSION, the firmware reselects the same UID and tries a standard READ at page 00. A successful response shows pages 00–03. When page 03 contains a recognized Type 2 Capability Container, the console reports its declared data-area size. The probe leaves the exact model and physical capacity unknown and offers only read-only capture actions.

Upload the current sketch to use this probe. Scan diagnostics show the raw PN532 status and the InDataExchange response length, including the status byte. When no response frame could be parsed, these values are unavailable. Saved captures can optionally include these diagnostics. Older captures and firmware scan responses remain readable.
