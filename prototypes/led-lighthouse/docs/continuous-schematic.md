# One continuous lighthouse schematic

2026-10-30. Layout revision 0.3; **electrical connections unchanged from v0.2**.

- [One-page vector PDF](../output/pdf/lighthouse-continuous.pdf).
- [Editable EasyEDA Standard sheet](../hardware/easyeda/lighthouse-continuous.json).
- [Exact component pin table](full-v02-pin-table.md).
- [Circuit behaviour, power assumptions and staged verification](full-v02.md).

This replaces the three-sheet presentation as the primary assembly drawing.
Every connection is an actual visible wire, including the complete 5V and ground
rails. There are no hidden connections through net labels or power flags.

## Read the drawing

- Red wires are regulated +5V; blue wires are GND; black wires are signals or
  switched LED returns. Wire colours are optional when physically assembling.
- A filled dot means connected wires. An arched bridge crosses another wire
  **without** connecting. Follow the continuous line through the bridge.
- All 71 components are on this single sheet. Zoom in to read values and pin
  numbers; the PDF is a wide poster, not a page intended to shrink onto A4.
- IC symbol positions are functional. Use the printed DIP pin numbers, not the
  left/right position of a terminal on the drawing, to identify physical pins.
- J2 uses the PIR's VCC/OUT/GND signal names, not an assumed physical pad order.
- P2 and P3 have their wipers visibly wired to an outer terminal. P1 uses all
  three terminals. Identify actual trimmer terminals from its datasheet/meter.
- The shared LED resistor returns through Q6. D3 replaces the manual test's
  direct CD4017 pin 1-to-15 reset wire; do not retain that direct wire here.

## Open in EasyEDA

Use EasyEDA **Standard** (<https://easyeda.com/editor>), then **File > Open >
EasyEDA** and select the JSON. Alternatively open **File > File Source**, replace
the entire field with the file contents and choose **Create New Document**.
The single-sheet file was opened and visually inspected in the web editor.
Native EasyEDA Pro format/PCB footprints are not supplied.

## Verification status

The independent connectivity checker reconstructs actual wire geometry and
compares all 185 physical pin endpoints against the original 48-net v0.2
connection table. For this drawing it additionally rejects hidden net labels
and power flags. The final drawing passes, including the actual crossings and
junctions. Cosmetic bridge arcs do not replace or interrupt electrical wires.

The user-confirmed hardware result remains the manual-button five-LED CD4017
test. The complete sensor/timer circuit is still not hardware-tested or
electrically simulated. Regulated 5V, C7 leakage/time calibration, physical PIR
pad identities and the original staged checks still apply.

To regenerate, run `tools/build_continuous.py`, then
`tools/check_full_easyeda.py hardware/easyeda/lighthouse-continuous.json` with
the JSON path relative to the prototype directory (or use its absolute path).
