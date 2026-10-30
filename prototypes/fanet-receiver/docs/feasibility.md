# Feasibility and implementation decision

Research date: 2026-10-26. Distinguish documented capabilities from tested
interoperability: no iPhone or receiver has been tested for this prototype.

## FlySkyHy interface

The [official Bluetooth device documentation](https://flyskyhy.com/bluetooth-varios.html)
describes nearby traffic icons in the base app, with Social adding appearance
and friend features. It documents FFE0/FFE1 text notifications, newline-delimited
UTF-8, splitting long lines across notifications, PFLAU at 1 Hz and PFLAA when
traffic is available. Select Other Device for an unlisted device.

The page is inconsistently retrievable directly (some requests returned a hosting
placeholder); its indexed documentation was available during research. Recheck
against the installed app and BLE probe before treating compatibility as proven.

The [FLARM data-port ICD](https://www.flarm.com/wp-content/uploads/2024/04/FTD-012-Data-Port-Interface-Control-Document-ICD.pdf)
defines PFLAA target position as north/east/vertical offsets from own position.
Thus absolute FANET coordinates cannot simply be placed in those fields.

No documented FlySkyHy-to-peripheral GPS feed or raw FANET sentence was found
in the reviewed documentation. This is an unresolved capability, not proof that
such support is impossible. BLE hardware capability alone does not provide it.

## Architecture

FANET radio RX → validated MAC/payload decoder → target cache → relative traffic
formatter using a fresh own fix → BLE text notifications → FlySkyHy map.

For a moving receiver, prefer onboard GNSS unless a supported alternative is
verified. Maintain consistent own-position and altitude references between the
formatter and the app; evaluate sending valid own GPRMC/GPGGA and selecting
Use Device GPS in FlySkyHy so both use the same reference. Verify vertical datum
and the app's barometric/GPS treatment rather than assuming altitude equality.
Suppress traffic output on missing/stale own fix rather than fabricate offsets.

Names and weather may be decoded locally, but their display is outside the
verified PFLAA bridge scope. Start with airborne tracking (type 1). Preserve the
complete FANET manufacturer/device identity and explicitly map aircraft types;
FANET and FLARM type numbers differ (paraglider is FANET 1 versus FLARM 7).

## Open-source options

| Project | Relevant evidence | Decision |
| --- | --- | --- |
| [fanet-stm32](https://github.com/3s1d/fanet-stm32) | Original protocol reference and STM32 implementation | Use specification and decoding vectors; not a drop-in ESP32 Arduino library |
| [GXAirCom](https://github.com/gereic/GXAirCom) | ESP32 FANET implementation; source uses FFE0/FFE1 notifications | Strong source reference; full firmware includes unwanted features and TX paths |
| [SoftRF](https://github.com/lyusupov/SoftRF) | FANET/proximity system; [Card documentation](https://github.com/lyusupov/SoftRF/wiki/Card-Edition) lists FlySkyHy BLE interoperability | Useful end-to-end reference; a tested edition does not prove any ESP32 build/configuration |

GXAirCom's [published app list](https://github.com/gereic/GXAirCom/wiki/Software)
reviewed here lists Android software, so it does not independently establish
FlySkyHy support. Its [BLE implementation](https://github.com/gereic/GXAirCom/blob/master/src/ble.h)
provides a concrete transport reference, not a hardware-test result for this project.

SoftRF is GPL-3.0. Before reusing any upstream code, inspect the license notices
of the exact files and their dependencies, pin an upstream commit, and retain
required notices. No upstream firmware source has been copied into this prototype;
the small BLE probe is original code. Missing root-level licensing in a project
must not be treated as unrestricted reuse permission.

## Radio requirements

The [upstream FANET protocol](https://github.com/3s1d/fanet-stm32/blob/master/Src/fanet/radio/protocol.txt)
specifies EU operation at 868.2 MHz, 250 kHz bandwidth, spreading factor 7,
explicit headers and payload CRC. The SX127x sync word is 0xF1; the documented
SX1262 equivalent is 0xF414. Coding rates vary in the explicit header.
These are protocol settings, not a verified driver configuration for this project.
LoRaWAN, Meshtastic and default LoRa examples will not automatically receive FANET.

Before integrating a FANET stack, audit and disable every transmit path, including
ACK, forwarding, retries and service announcements. A packet-decoder-only RX path
is preferable to starting an unrestricted mesh MAC. No RF transmission is needed.

## Verification gates

1. BLE bench probe: capture notifications, confirm checksum/framing and marker
   display; record whether no-GNSS/no-TX heartbeat affects the app.
2. Own-reference decision: demonstrate correct target placement while moving,
   with consistent own position and altitude; otherwise select GNSS hardware.
3. Software parser: independent known vectors, truncated headers, optional MAC
   fields, signed coordinates/climb, altitude scaling and type conversion.
4. Radio: compare one known FANET sender's identity and position against decoded
   output. Confirm no TX calls or automatic mesh transmissions are enabled.
5. Field bench: multiple targets, duplicates, stale targets, disconnect/reconnect,
   missing fix, offline maps and measured full-device battery consumption.

Acceptance requires real RF traffic to appear at the expected map position with
the receiver moving. A successful BLE synthetic target alone is insufficient.
