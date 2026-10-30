# Experiment log

## 2026-10-30 - One continuous drawing requested

- User found the three-sheet layout difficult to assemble and requested one
  conventional drawing with visible connections, like the tested manual circuit.
- Added one large continuous EasyEDA Standard sheet and one-page vector PDF.
  All power/ground connections are wires; no net labels or flags join endpoints.
- Kept the v0.2 electrical circuit unchanged: 71 parts, 185 pins, 48 nets.
- Independent geometric connectivity check passed; 98 junctions and 52 bridged
  crossings are explicitly drawn. Opened and visually checked in web EasyEDA.
- Full circuit hardware and electrical-simulation status remain unverified.

## 2026-10-29 - Manual counter test confirmed by user; full CAD revision 0.2

- User reports the attached manual-button circuit works: CD4017, Q0-Q4 driving
  five LEDs through one shared 1k return resistor, Q5 pin 1 tied to reset pin 15.
  Exact supply, LED current and received part manufacturer were not reported.
- Only that manual counter test is confirmed; oscillator and sensor/timer stages
  have not been reported working.
- Added a three-sheet EasyEDA Standard schematic and matching PDF, retaining
  direct LED drive and using one common NPN return switch for complete blanking.
- Direct pin 1-15 wire is replaced by diode reset OR; old and new references
  must not be mixed. The complete design uses 7 BC547B transistors.
- Serialized CAD connectivity check passed: 71 components, 185 pins, 48 nets.
- Web editor opens the three-sheet design. Native EasyEDA Pro automation was
  denied computer-use permissions; Pro-native import remains unverified.
- Status: full circuit remains untested and not electrically simulated.
  Follow the new staged checks, especially C7 leakage and automatic timeout.

## 2026-10-22 - Simplified first experiment

- User chose incremental assembly and an initial test without LED transistors.
- Added a single-sheet, fully wired circuit with one TLC555IP, one CD4017BE,
  five white LEDs, a 100k speed pot and the required passive components.
- Direct LED drive starts with 10k per LED for low current; brightness is not
  assumed to match the earlier driver circuit.
- No sensors, timeout or guaranteed power-on starting position in Stage 1.
- Status: schematic and rendering checked; not hardware-tested.

## 2026-10-21 - Design v0.1

- Created a datasheet-based connection schematic and staged commissioning guide.
- Verified TI DIP pin assignments and comparator common-mode constraints.
- Added buffered pulse triggering, busy lockout, counter reset and a switched
  LED supply. The resulting design uses all 12 ordered BC547B transistors.
- Status: no hardware test and no electrical simulation yet.
- Pending: inspect received module labels and transistor variants; select a
  known protected battery; measure C7 leakage/timeout and idle 5V behaviour.

## 2026-10-30 - simple revision 0.4 design review

User requested a simpler circuit without TLC372 and original online examples.
Created a complete one-sheet schematic with 42 parts: two TLC555, one CD4017,
three BC547 and one 1N4148. Preserved the direct CD4017 pin 1-15 reset wire.
Independent serialized CAD check: 117 pins, 35 nets, no opens/shorts. Rendered
and visually inspected the one-page PDF. No combined hardware test or SPICE
simulation. Original tutorials support individual blocks, not this exact build.
Fresh web EasyEDA Standard import visually confirmed and screenshot saved.
Existing editors retained older content during initial File Source attempts.
Added fixed 10k R12 to limit LDR current even at zero P1 resistance. See simple-v04.md
for sources, assumptions, calculations and bench acceptance steps.
