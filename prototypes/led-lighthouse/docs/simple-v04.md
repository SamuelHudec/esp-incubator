# Simple complete lighthouse circuit - revision 0.4

## Purpose and status

Five white LEDs run in sequence after a new motion event in darkness. An
adjustable analog timer turns every LED off after approximately one minute.
Daylight inhibits starting and cancels a running cycle.

2026-10-30: proposed simpler replacement for revisions 0.1-0.3. Only the user's
manual-button CD4017 five-LED circuit has been physically confirmed. This
combined circuit has **not** been built or electrically simulated. CAD
connectivity checking is not evidence of correct hardware operation.

## Complete drawing

- [One-page PDF, every wire visible](../output/pdf/lighthouse-simple-continuous.pdf)
- [Full-resolution image](lighthouse-simple-continuous.png)
- [Editable EasyEDA Standard schematic](../hardware/easyeda/lighthouse-simple-continuous.json)
- [Every component and pin connection](simple-v04-pin-table.md)
- [Canonical connection data](simple-v04-netlist.json)

This is one connected electrical schematic, not a presentation. Filled dots
join wires; bridges cross without connecting. Use the printed DIP pin numbers,
not the drawn position of each pin. Module terminals are named signals, not an
assertion of their physical pad order. Reference numbers were restarted for
this revision; do not mix them with older PDFs.

## Why this is simpler

There are 42 parts: 2 TLC555IP, 1 CD4017BE, 3 BC547B, 1 signal diode, 5 LEDs,
3 trim pots, 12 resistors, 11 capacitors, 1 LDR, 2 connectors and 1 switch.
There is no TLC372 comparator, clock inverter, idle-reset gate, or separate
transistor for each LED. The familiar direct CD4017 pin 1 to pin 15 wire remains.

Q1 senses light and pulls U1 RESET low in daylight. Q2 turns a rising PIR edge
into a short low trigger pulse. Q3 opens the common LED return when U1 times
out. U1 controls duration; U2 supplies the clock; U3 selects each LED.

The deliberate compromises are: no sharp light threshold with hysteresis, no
forced restart at LED1, and no explicit busy-lockout circuit. The first step
may differ in length and the first run can need several clocks to reach the
five-state sequence from an unspecified CD4017 power-up state. Subsequent runs
continue from the stopped counter state. Additional short motion edges normally
do not restart the RC charging interval; an edge overlapping the actual timeout
can affect it for the short trigger interval. This is not a precision event
controller.

## Internet evidence and its limits

These are original tutorials, manufacturer data, and a supplier's own module
document. They support the individual building blocks; none demonstrates this
exact combined 5V circuit with this PIR, five LEDs, and a 60-second setting.
No source waveform or photograph is presented as a test of our drawing.

1. [Elonics: light/dark sensor using LDR and one BC547](https://elonics.org/light-sensor-and-darkness-detector-circuit-using-ldr-transistor/).
   Includes a breadboard tutorial and schematics. Its light-sensing divider is
   adapted here: instead of lighting an indicator, the collector inhibits U1
   during daylight. The LDR5516 is a **photoresistor**, not a photodiode.
2. [Electronut Labs: built PIR + 555 lamp](https://electronut.in/night-lamp/).
   Author supplies a schematic, PCB photos and video and reports that the unit
   still worked two years later. Its schematic has **no LDR**. It is a reference
   for PIR inversion and monostable timing, not a complete darkness detector.
   Its DC-coupled PIR trigger is not copied unchanged: a held HIGH could keep
   the 555 trigger low beyond the intended timeout.
3. [Electronics Club: monostable and edge triggering](https://electronicsclub.info/555monostable.htm).
   Explains RESET, 1.1RC, electrolytic leakage, and why a sensor must not hold
   TRIG low past timeout. Our positive-edge capacitor is placed before Q2;
   the transistor isolates TLC555 input pins from capacitive overshoot.
4. [TechStudyCell: built 555 + CD4017 LED chaser](https://easyelectronicsproject.com/mini-projects/led-chaser-lights/).
   PCB, circuit and tutorial at 5V. The five-step direct reset variant is also
   the circuit the user has already tested manually.
5. [TI TLC555 data sheet, SLFS043K](https://www.ti.com/lit/ds/symlink/tlc555.pdf),
   sections 4, 5.1, 5.6, 6.3.1 and 6.3.2: exact DIP8 pinout, voltage limits,
   reset behaviour, monostable and astable equations. TRIG must return HIGH at
   least 1us before timeout; any input must stay between -0.3V and VDD.
6. [TI CD4017B data sheet](https://www.ti.com/lit/ds/symlink/cd4017b.pdf),
   pages 1-5: exact DIP16 pinout, operation and limited output-drive strength.
7. [Semtech BC546-BC549 manufacturer data, archived PDF](https://datasheet.datasheetarchive.com/originals/library/Datasheet-024/DSA00417422.pdf):
   BC547 ratings and saturation characteristics. B/C/E symbols here are
   functional terminals; confirm the actual supplier's lead arrangement.
8. [HADEX SB00312A-1 declaration](https://www.hadex.cz/prohl/m356.pdf):
   module supply 2.7-12V and listed output 3.3V. The same model name does not
   verify the actual GME board revision, pad order, or its output load capacity.
   [HADEX module description](https://www.hadex.cz/p/m356-detektor-pohybu-modul-pir-sb00312a-1)
   explicitly says continuing motion can hold its output HIGH continuously.
9. [LaskaKit LA122076 module](https://www.laskakit.cz/mikro-nabijecka-boost-pro-usb-powerbank-5v--usb-c/):
   nominal 5V output, 4.2V charge termination, charge current up to 1A; supplier
   recommends a battery with integrated protection. Actual low-load behaviour
   and compatibility with the user's cell must be checked.

## Engineering checks

These calculations use nominal values and a transistor approximation; they
are not a SPICE simulation or a guarantee across all component tolerances.

- U1: `t = ln(3) * (220k + P3) * 100u`, approximately 24-134 seconds.
  A 60-second starting point is P3 about 326k (325k rounded in the drawing).
  Electrolytic capacitance and leakage can lengthen the measured time.
- At P3 = 325k, charging current near the nominal 3.33V threshold is only
  `(5 - 3.33) / 545k = 3.06uA`. Excess timing-capacitor leakage can prevent
  timeout. At the data sheet's higher threshold limit, less current remains.
  Verify C3 actually charges far enough and that every cycle ends; replace a
  leaky capacitor before adjusting the design.
- R7 limits nominal initial discharge of C3 at 3.33V to below about 34mA;
  U1 pin 6 observes TIME directly, while pin 7 connects through R7.
- U2: `T = ln(2) * [10k + 2*(10k + P2)] * 10u`, approximately
  0.208-1.594 seconds per step. This is one LED step, not the whole revolution.
- Q2: assuming a measured 0-to-3.3V PIR transition and VBE about 0.7V,
  initial R3 current is about 55uA, of which R4 takes 7uA, leaving about
  48uA base drive. The TRIG pull-up load is about 0.5mA. This gives a nominal
  forced current gain near 10. Capacitive base drive decays in a few
  milliseconds, much shorter than one minute. Confirm TRIG returns HIGH even
  while PIR OUT stays HIGH; verify output voltage under this transient load.
- Q2's collector, with its 5V pull-up, drives U1 TRIG; the coupling capacitor
  is **not** directly connected to the TLC555 input. D1 anode is GND and
  cathode (band) is TRIG_BASE, clamping the negative base transient.
- Q3 base current is roughly `(5 - 0.7)/10k = 0.43mA`. The shared 1k LED
  resistor caps the branch current below 5mA even before LED voltage and
  CD4017 output voltage drop are included. Actual brightness and CD4017
  loading must be measured; keep the resistor at least 1k for this trial.
- For Q1, start P1 near 50k. Illustratively, LDR = 500k gives an unloaded
  sense voltage of 0.446V; LDR = 10k gives 3.57V before base loading.
  R12 adds a fixed 10k in series with the LDR, limiting current to at most
  0.5mA even if P1 is turned to zero resistance.
  These resistance examples are **not** a measurement of the user's LDR.
  Adjust for the real ambient light and verify RESET at the IC pin.

## Power and terminal notes

Use verified regulated 5V from USB or the boost **output**, never the raw
3.7V cell. All blue ground wires connect. First tests use a verified USB source
or a current-limited bench supply. Do not connect USB 5V to a battery pad.
The battery/charger wiring is intentionally external until the actual board
labels, battery chemistry and charge-current compatibility are verified.

| Device | Supply | Other essential terminals |
| --- | --- | --- |
| U1 TLC555IP | 8 = +5V; 1 = GND | 2 = TRIG; 3 = RUN; 4 = ARM/RESET; 5 = CTRL1; 6 = TIME; 7 = DISCH1 |
| U2 TLC555IP | 8 = +5V; 1 = GND | 2 and 6 = OSC_TIME; 3 = CLOCK; 4 = RUN/RESET; 5 = CTRL2; 7 = DISCH2 |
| U3 CD4017BE | 16 = +5V; 8 = GND | 14 = CLOCK; 13 = GND; 1 wired directly to 15 |
| Five LEDs | Anodes to U3 pins 3, 2, 4, 7, 10 in order | Cathodes share R10 then Q3 collector; observe LED polarity |
| PIR | VCC = +5V; GND = common GND | OUT = C2; follow actual PCB labels, not drawn order |
| BC547B Q1-Q3 | E = GND | B and C per drawing; physical lead order needs actual part verification |
| C1, C3, C5, C10 | Electrolytic, 16V or higher | Positive terminal marked + in drawing; negative terminal to GND |
| P1, P2, P3 | A/B are track ends, W is wiper | W is explicitly tied to B; confirm pot terminals with a meter |

Place C7, C8 and C9 at the supply pins of U1, U2 and U3 respectively; C11
at the PIR. The drawing places components for readability, not PCB routing.
CD4017 pins 5, 6, 9, 11 and 12 are unused outputs and stay unconnected.
There are no unused floating inputs.

## Staged verification

1. Preserve a photo of the working manual-button circuit. Power off before
   changing wires. Verify resistor values, capacitor polarity, module labels,
   actual transistor lead order and continuous breadboard supply rails.
2. Verify 5V on the empty IC sockets. Add bypass capacitors.
3. Check the light detector independently: P1 near 50k; measure ARM at the
   future U1 pin 4. Aim for below 0.3V in light and above 4V in darkness.
   Sweep slowly through dusk. No hysteresis is provided: do not leave it at
   an unstable threshold or expose the LDR to the lighthouse LEDs.
4. Test U1 with its RESET enabled in darkness and Q2 temporarily omitted.
   Its pin 2 already has R5 pull-up: momentarily connect pin 2 to GND with a
   jumper and remove it. Measure RUN at pin 3. Set P3 initially low, check a
   short cycle, then set about 325k and calibrate to approximately 60 seconds.
   Confirm C3 voltage rises and every cycle finishes.
5. Add Q2/C2/R3/R4/D1. Before connecting PIR OUT, produce a test edge by
   changing C2 input from GND to +5V and leave it HIGH beyond the timeout.
   Verify RUN still ends. This checks the edge circuit without depending on
   undocumented PIR drive capability. The actual PIR test follows below.
6. Add U2 and U3, retaining direct U3 pin 1 to 15 and CE pin 13 to GND.
   Replace the manual clock button and its 100n/10k debounce parts with U2
   pin 3 directly into U3 pin 14. **Remove** those old debounce parts from
   the clock node. Add Q3 and R11: R10 now goes to Q3 collector instead of
   directly to ground. Verify five-step rotation only during RUN, every LED
   dark afterwards, and acceptable LED current measured from R10 voltage.
7. Verify PIR supply/pad labels and standalone output first. After warmup,
   measure OUT HIGH and LOW, then connect C2. Check a new motion edge in
   darkness starts a cycle. Continue moving for longer than the minute:
   RUN must still end, even if OUT stays HIGH. To rearm a continuously HIGH
   PIR, stop moving until OUT goes LOW, then cause a new motion edge.
8. Repeat in light: motion must not start LEDs; lighting the LDR during a
   run cancels it. Check repeated runs, the real dusk setting and startup.
9. Only then test the battery/boost supply, idle voltage/current and whether
   its output remains on under the small standby load. Do not infer battery
   life from nominal component currents. Record actual results in the log.

## Build and limitations

No firmware or flashing. Regenerate with `python3 tools/build_simple.py` using
ReportLab, then check with:

```text
python3 tools/check_full_easyeda.py hardware/easyeda/lighthouse-simple-continuous.json docs/simple-v04-netlist.json
```

The checker independently reconstructs the serialized wire geometry and checks
117 pins on 35 nets for unintended opens/shorts. There are no hidden net labels.
The PDF was rendered and visually inspected. This does not validate transistor
models, temperature behaviour, capacitor leakage or the received module revision.

EasyEDA file is for Standard, with schematic-only symbols and no PCB footprints.
Import through File > Open > EasyEDA; alternatively File > File Source can
accept the JSON when starting from a fresh editor. Import was confirmed in a fresh web Standard editor. An already-open editor
retained an older document during earlier File Source attempts; use a fresh
editor and verify the visible revision 0.4 heading.

A PIR warmup event can cause a startup run. C1 only gives a brief reset delay.
A light change from day to night alone does not start a cycle, nor does a PIR
already held HIGH when darkness begins: a new rising edge is required.
The circuit keeps the PIR and control ICs powered while the LEDs are off.

## Next steps

Bench-test the light transistor and short timer separately, then the edge input
with a held HIGH, before connecting the complete sequencer. Record the actual
module markings, supply voltages, timeout and LED current before soldering.
