# Full lighthouse circuit - revision 0.2

**Current assembly drawing:** [one continuous schematic](continuous-schematic.md)
has every connection drawn on one sheet. The older three-sheet files below are
retained as history. The electrical circuit and the staged checks are unchanged.

2026-10-29. **Design proposal, not a completed hardware test.** The user reported
that the attached manual-button CD4017 circuit with five LEDs works. Supply
voltage, LED current and exact part manufacturers were not reported. That result
does not validate the oscillator, light detector, motion trigger or timeout.

## Files and EasyEDA

- [Three-sheet review PDF](../output/pdf/full-circuit-v02.pdf).
- [Editable EasyEDA Standard project](../hardware/easyeda/lighthouse-v02-project.json).
- [Exact pin table](full-v02-pin-table.md).
- [Canonical netlist](full-v02-netlist.json).

The web editor successfully opened the custom schematic symbols and all three
sheets. These are electrically connectable symbols, not a bitmap placed in CAD.
No footprints or routed PCB are supplied. Desktop EasyEDA Pro import has not
been verified: native automation was denied computer-use permissions. Standard
and Pro use different native project formats; this JSON is for **EasyEDA
Standard**, available at <https://easyeda.com/editor>.

In Standard, use **File > Open > EasyEDA** and choose the project JSON. An
alternative is **File > File Source**, replace the entire text with that JSON,
then choose **Create New Document**. Do not paste it onto the drawing canvas.
The project contains three sheets: light/power, motion/timer, oscillator/LEDs.

All matching blue net names are direct wire connections, also across sheets.
For example every RUN label connects to U1 pin 3. All GND labels connect to the
same supply negative. Symbol layout is functional; use printed pin numbers to
identify DIP terminals. NC pins are intentionally left open.

## Changes from the working manual test

1. Remove the button and its clock pulldown/capacitor. U4 pin 14 now receives
   CLOCK from Q5. C12 is a different capacitor, on U4 reset pin 15.
2. Remove the **direct** U4 pin 1 to pin 15 link. Q5 output (pin 1, net STEP5)
   goes to D3 anode. D3 cathode goes to COUNT_RESET / pin 15. D2 cathode joins
   that same reset node; D2 anode connects to IDLE. R25 and C12 connect that
   reset node to GND.
3. Keep the five LED anodes connected to U4 pins 3, 2, 4, 7 and 10 respectively.
   Join their cathodes to LED_RETURN. The shared 1k resistor R28 now goes from
   LED_RETURN to Q6 collector, **not directly to GND**. Q6 emitter goes to GND;
   RUN drives its base through R26 (10k).
4. Add both TLC555 timers, the TLC372CP comparator, the LDR5516 and PIR trigger
   circuits as shown. All grounds join.

Revision 0.2 replaces the earlier five individual LED driver transistors and
emitter-follower supply with one common low-side switch. CD4017 still supplies
the LED current. References retained from revision 0.1 have gaps; do not combine
the old pin table with this circuit.

## Operation and adjustments

- In darkness U3A pulls DAY low, Q12 turns off and ARM rises, enabling U1.
  R1/R2 limit LUX to at most half the supply, within TLC372 input common-mode
  limits. P1 adjusts the threshold; R3 adds positive feedback to reduce chatter.
- A new PIR rising edge passes through Q1/Q2 and C11 to pulse Q3. Q3 pulls U1
  TRIG low briefly. A held PIR HIGH is not a held timer trigger.
- U1 starts RUN. U2 oscillates, Q5 inverts the clock and U4 cycles Q0 to Q4.
  Q4 blocks trigger pulses while RUN is high. C15 delays that lockout slightly
  and holds it briefly at timeout.
- U3B raises IDLE while RUN is low, resetting the counter through D2. Q6 opens
  the common LED return, so Q0 being selected while idle does not light LED1.
- Daylight forces U1 reset low and stops an active run. The next run requires
  darkness and a fresh PIR rising edge; an already-held HIGH does not start it.

| Adjustment | Part | Nominal range / initial setting |
| --- | --- | --- |
| Darkness threshold | P1, 100k | Tune at the intended dusk light level |
| LED step time | P2, 100k | Approx. 0.21-1.59 s per step |
| Run duration | P3, 1M | Approx. 24-134 s; about 325k for 60 s |

P2/P3 wipers W are strapped to terminal B. P1 uses all three terminals. A/B/W are
functional terminal names; identify the actual pot wiper with a meter or the
exact part drawing. Trim tolerances and electrolytic leakage affect timing.

## Power and physical pin checks

- **Regulated 5V only** at J1, positive VIN_5V and negative GND. S1 switches the
  positive lead. The 5-9V annotation on the user's manual test is not the supply
  specification for this complete design.
- Start with verified 5V USB/bench power. Battery protection, charging, boost
  wiring and load-sharing are external and are not validated by this drawing.
- The SB00312A-1 drawing identifies VCC, OUT and GND by signal name. It does
  **not** specify their left-to-right order. Verify actual PCB labels/revision
  before applying power. Confirm LOW idle / HIGH motion before connecting Q1.
- Use the purchased LDR5516 **photoresistor**, not an unspecified photodiode.
  It has no polarity. Keep it out of the lighthouse LED beam.
- BC547B C/B/E are shown functionally. Confirm the exact manufacturer's package
  drawing; for the previously referenced Semtech default pinout, leads are
  C-B-E with the flat face toward the viewer and leads pointing downward.
- Electrolytic capacitor '+' terminals connect to the named positive node;
  '-' terminals connect to GND. Observe the 1N4148 cathode stripe (K).
- Put 100nF bypasses close to each IC's supply pins. The shared 1k LED resistor
  is valid here because only one decoded output selects an LED. Do not bypass
  it. Actual LED current and brightness must be measured, not assumed from 5V.

## Staged verification

Disconnect power before every wiring change. Keep the original tested circuit
available as a reference. These are bench gates, not claims of completed tests.

1. **Power:** with ICs removed, verify +5V/GND polarity at every socket. Inspect
   for shorts, then fit correctly oriented ICs. Verify the PIR pad identities.
2. **LED section:** build sheet 3, temporarily tie RUN to +5V and IDLE to GND
   **only while U1/U3 are disconnected**. Check all five LED steps. Ground RUN:
   all LEDs must turn off. Restore RUN and IDLE to their final sources afterward.
3. **Light comparator:** before attaching U1, test sheet 1. Cover/uncover LDR,
   adjust P1 and measure ARM: near 0V in daylight, rises toward 5V in darkness.
   Check LUX remains between 0V and 2.5V. Check IDLE is high at RUN=0V and low
   at RUN=5V; do not drive RUN externally once U1 is connected.
4. **One-shot:** fit sheet 2 timer with the PIR input stage disconnected. In
   darkness pulse TRIG to GND through a temporary 1k resistor, then release it.
   RUN must go high and return low automatically. Start P3 near minimum. Adjust
   to 60 seconds with a stopwatch only after repeated timeout success.
5. **Timing-capacitor gate:** TIME should rise from near 0V toward 3.33V during
   RUN and drop near 0V at timeout. If it stalls below the threshold, check C7
   polarity/leakage and wiring; do not simply increase P3. At a 60-second setting
   the available charging current near threshold is only about 3 microamps.
   This design cannot promise a minute with an arbitrary leaky capacitor.
6. **PIR:** verify PIR output separately, then connect its trigger stage. Check
   darkness + new motion starts a run; extra motion during RUN does not restart
   it; timeout extinguishes **every** LED; a new edge can start the next run.
7. **Daylight / optics:** light on LDR must prevent/cancel a run. Confirm the
   running LEDs do not illuminate the LDR enough to cancel themselves.
8. **Final power:** only after all earlier gates pass, test the verified boost
   supply, its low-load standby behaviour and the selected protected cell.

Record supply, LED current, measured step/run times, idle current, actual module
revision, and any substitutions in [the experiment log](experiment-log.md).

## Validation and limitations

`tools/check_full_easyeda.py` reconstructs connectivity from the serialized CAD
wire, label and pin coordinates and compares every pin against the canonical
netlist. It checks both missing connections and unintended geometric shorts.
The final file passed: **71 parts, 185 pins, 48 nets**. This does not check analog
waveforms, component tolerances, supply integrity or actual hardware.

No SPICE/electrical simulation or full-circuit hardware test has been performed.
PIR warmup pulses can cause one startup run; no full warmup inhibit is included.
The one-minute RC timing is approximate, and the first LED dwell differs from
steady-state steps. This is a schematic for staged breadboard assembly, not a
finished PCB or an assurance of battery runtime.

## Sources checked for this revision

- [TI TLC555 datasheet, SLFS043K](https://www.ti.com/lit/ds/symlink/tlc555.pdf):
  DIP8 pin functions, reset/trigger behaviour, monostable and astable circuits.
- [TI TLC372 datasheet, SLCS114F](https://www.ti.com/lit/ds/symlink/tlc372.pdf):
  DIP8 pin functions, open-drain outputs and input common-mode limits.
- [TI CD4017B datasheet, SCHS027C](https://www.ti.com/lit/ds/symlink/cd4017b.pdf):
  decoded outputs, reset, clock inhibit and DIP16 pin assignments.
- [Semtech BC547B datasheet mirror](https://datasheet.datasheetarchive.com/originals/library/Datasheet-024/DSA00417422.pdf):
  previously recorded default C/B/E package; received variant still needs checking.
- [SB00312A-1 supplied product](https://www.gme.cz/v/1508403/sb00312a-1-pir-modul)
  and [LDR5516 supplied product](https://www.gme.cz/v/1495847/ldr5516-fotorezistor):
  exact user-selected module/model identities. Retailer page alone does not
  establish actual physical PIR pad order.
- [EasyEDA Standard source format](https://docs.easyeda.com/en/DocumentFormat/2-EasyEDA-Schematic-File-Format/)
  and [opening source files](https://docs.easyeda.com/en/Export/Export-EasyEDA-Source-File/).
