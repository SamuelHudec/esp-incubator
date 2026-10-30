# LED lighthouse

A souvenir lighthouse with five white LEDs that run in sequence for about one
minute after motion is detected in darkness. The circuit uses analog timers and
CMOS logic; no microcontroller or firmware is required.

## Status

**Partial hardware test confirmed by user**, 2026-10-29. The manual-button
CD4017 five-LED test works; its supply and current measurements were not reported.
The current simple revision 0.4 remains an untested design: 42 parts,
three transistors, no TLC372. Its 117 CAD pin connections on 35 nets were
independently checked. No electrical simulation or combined hardware test has
been performed; received module revisions and battery remain unverified.

## Hardware

- 2 x TI TLC555IP, DIP8; 1 x CD4017BE, DIP16.
- Revision 0.4: 3 x BC547B, 1 x 1N4148, 5 white LEDs with a shared 1k current
  limiter and switched common return. No TLC372 is required.
- SB00312A-1 PIR module and LDR5516 photoresistor.
- Two 100k trim pots (light threshold and speed), one 1M trim pot (duration).
- LaskaKit LA122076 USB-C charger / 5V boost module.
- Known protected 1S Li-ion/Li-pol battery with 4.2V charge chemistry and a
  compatible charge-current rating; battery selection still needs verification.
- Resistors and capacitors are listed in the PDF and connection reference.

## Wiring

**Use revision 0.4:** [simple circuit, sources and staged checks](docs/simple-v04.md),
[one-page PDF with every wire drawn](output/pdf/lighthouse-simple-continuous.pdf),
[editable EasyEDA Standard sheet](hardware/easyeda/lighthouse-simple-continuous.json),
and [complete pin table](docs/simple-v04-pin-table.md).

Revision 0.4 removes the comparator and several interface stages. It retains
the user-tested CD4017 direct pin 1-15 reset link. Reference numbers restart in
this revision; do not mix component identifiers across drawings.

For the first oscillator trial, [stage 1](docs/stage1-simple.md) remains useful.
The [older continuous drawing](docs/continuous-schematic.md),
[revision 0.2](docs/full-v02.md) and [original guide](docs/wiring.md) are history,
not the current build instructions.

Module pads are identified by their verified PCB labels, never by an assumed
physical order. The current drawing is a connection schematic, not a PCB or
numbered breadboard layout. Every power and signal wire is drawn explicitly.

## Power and safety notes

Use regulated 5V, with all circuit grounds connected. First power-up should use
a current-limited bench supply or verified 5V USB source. Confirm module pad
labels, supply polarity, actual transistor variant and capacitor polarity before
inserting ICs. An unidentified salvaged cell is not an approved power source.

The boost board's behaviour at the final low standby load must be measured.
Charging and simultaneous operation have not been validated; use S1 off for the
first charging tests. Keep the LDR out of the lighthouse LEDs' light path.

## Build / flash

No flashing is required. Follow the [revision 0.4 staged verification](docs/simple-v04.md#staged-verification).
Use sockets for the three DIP ICs. Regenerate using `tools/build_simple.py` with
Python and ReportLab. Validate using `tools/check_full_easyeda.py` with the
revision 0.4 schematic and canonical netlist as its two arguments.

The EasyEDA Standard symbols are schematic-only, without PCB footprints.
PDFs are intended user artifacts, not firmware build products.

## Verification

Follow the current staged checks: polarity and resistance; 5V rails; one-transistor
light inhibit; manual timer trigger; held-HIGH edge input test; automatic
five-step sequence; actual PIR; final battery/boost supply.

Record the supply, duration, LED current, idle current, component substitutions
and module revisions in `docs/experiment-log.md` after an actual hardware test.

## Known limitations

- RC timing is approximate. Excess leakage of C3 may prevent the one-minute
  timeout. Check its voltage rise; a verified low-leakage capacitor or a timebase
  redesign may be needed if the purchased sample fails this test.
- Daylight cancels an ongoing run. PIR warmup pulses can cause a startup run.
- No forced LED1 restart or light-threshold hysteresis. First dwell can differ.
- Held-HIGH PIR needs a LOW transition and a new rising edge to start again.
- No fading or optical overlap; no measured battery life or finished PCB layout.
- No physical pad order is claimed for the actual boost/PIR modules until their
  labels/revisions are inspected.

## Next steps

Keep the user-tested manual sequencer as a reference. Verify the 5V supply and
automatic oscillator next, then add darkness detection, timeout and the PIR
trigger in small steps. Record measured results before a permanent assembly.
