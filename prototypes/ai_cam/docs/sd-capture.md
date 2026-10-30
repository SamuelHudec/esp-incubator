# SD photo capture — 2026-10-30

## Hardware assumptions

This applies to the existing AI Thinker ESP32-CAM with its onboard microSD socket,
not an external SD module. No supply or external wiring changes are made. The
board revision was not physically re-inspected for this change; different boards
must be checked against their own schematic before use.

| SDMMC slot 1 signal | ESP32 GPIO |
|---|---:|
| CLK | 14 |
| CMD | 15 |
| DAT0 | 2 |
| DAT3 (initialization bias only) | 13 |

Use one-bit mode so SD traffic does not use DAT1/flash-LED GPIO4, DAT2 GPIO12 or
DAT3 GPIO13. GPIO4 is not configured or driven by this feature.
Sources: [AI Thinker schematic](https://docs.ai-thinker.com/_media/esp32/docs/esp32_cam_sch.pdf)
(manufacturer URL now redirects; schematic mirrored in
[Seeed's archive](https://github.com/SeeedDocument/forum_doc/blob/master/reg/ESP32_CAM_V1.6.pdf)),
and [Espressif SD_MMC example](https://github.com/espressif/arduino-esp32/blob/3.3.12/libraries/SD_MMC/examples/SDMMC_Test/SDMMC_Test.ino).
The locally installed Arduino core 3.3.12 SD_MMC implementation confirms slot 1,
one-bit mode and the explicit format-if-mount-failed parameter.

Use an already FAT32-formatted card. Mount uses `SD_MMC.begin("/sdcard", true,
false)`: failed mount never triggers formatting. Insert/remove the card with
power off; wait for a save confirmation first. No hot-remount is implemented.
SD writes add power consumption; existing board power arrangements still apply.

## Operation

`/camera` shows the non-inference stream. **Save photo to SD** posts a request to
port 81 `/capture`; GET on that endpoint reports pending/saving/saved/error.
The existing stream handler saves the next frame it owns, then returns the camera
buffer normally. The frame can differ from the displayed preview due to network
latency. JPEG bytes are original camera bytes at the configured resolution.
No second camera-buffer owner or full-frame copy is introduced. Each on-demand
SD write briefly pauses the stream; do not include capture windows in FPS tests.

Files live under `/photos/cam_<random>_<random>_<request-id>.jpg`. Names do not
represent calendar time; no clock synchronization is required. Existing names
are checked before creation, including temporary `.part` files. A short or failed
write is not reported as saved; successful writes are flushed, closed, size-checked
and renamed from `.part`. A sudden power loss can still leave partial files or
filesystem damage. There is no automatic deletion of old photos or formatting.
A timeout in the browser is an unknown outcome: check the `PHOTO saved` log before
retrying, rather than assuming nothing was written.

## Verification

Desktop/compile verification is recorded in the experiment log. Physical SD
operation remains unverified until a board test:

1. Boot with a FAT32 card; confirm `SD ready`. Open only `/camera`.
2. Capture twice and confirm distinct `Saved to SD` paths and `PHOTO saved` logs.
3. Power off, read the card on a computer, and open both JPEGs at 320x240.
4. Reboot with the same card and capture again; confirm previous files survive.
5. Boot without a card: stream should remain usable and capture should report SD
   unavailable. Do not remove the card during writes to test error behavior.

## Diagnosing startup failures

Startup now distinguishes mount failure, no detected card, an inaccessible or
non-directory `/photos` entry, and directory creation failure. Successful mount
prints card type, capacity and filesystem usage. A mount error does not by itself
prove the card format is wrong. For the underlying driver error, select Arduino
**Tools > Core Debug Level > Error**, rebuild/upload and capture the SD startup
lines. Do not enable format-if-mount-failed to diagnose an existing card. Check
the filesystem on a computer before considering any formatting; preserve data.

### DAT3 initialization bias experiment

GPIO13 is SD DAT3 on the documented onboard socket. It is not a one-bit transfer
line, but its pull state still matters during initialization. Before SD_MMC.begin,
configure GPIO13 as INPUT_PULLUP to avoid leaving DAT3 floating or biased low.
This enables a weak internal pull-up after boot, not an actively driven output;
it is not a replacement for the hardware pull-ups specified by Espressif. No
GPIO12 boot-strap or GPIO4 LED changes are made. This requires GPIO13 to have no
external peripheral attached. Hardware success is pending: power-cycle after
flashing so the card also resets, then compare startup logs.

Basis: [Espressif SD pull-up requirements](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/sd_pullup_requirements.html)
and a matching [AI Thinker timeout report](https://github.com/espressif/arduino-esp32/issues/4680)
where INPUT_PULLUP on GPIO13 resolved initialization. A user report is evidence
for a diagnostic experiment, not confirmation of our fault or a universal fix.

## Upload with the SD card removed

A user observed upload failure `Wrong boot mode detected (0xb)` after SD testing.
GPIO2 is both the SD DAT0 line and a boot strapping pin: serial download requires
it low or floating, along with GPIO0 low at reset. A card/socket pull state can
interfere with entering download mode; this is a hypothesis until a card-removed
upload test succeeds. Remove the card with power off, use the established GPIO0
programming procedure, upload, then power off and remove the programming jumper
before reinserting the card and booting normally.

Source: [Espressif boot-mode selection](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html).
The new GPIO13 input pull-up runs only in the application after boot, so it does
not run inside the ROM serial downloader. A newly bright LED during a failed
connection is an additional symptom, not a diagnosed cause; GPIO4 is shared with
SD DAT1 but remains unconfigured by our one-bit capture code.

## Hardware observation — 2026-10-30

User confirmed photo saving works and flashing succeeds after removing the card.
Use powered-off card removal for uploading on this setup, then power off before
reinserting it for normal operation. This confirms the tested workflow, not the
independent cause of the earlier card-init timeout.
