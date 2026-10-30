# Stage 1: five running LEDs, direct drive

2026-10-22, v0.1. **Not yet hardware-tested.** This is a separate, minimal
experiment. Its reference numbers are independent of the earlier full guide.

- [Complete one-sheet schematic (PDF)](../output/pdf/stage1-five-leds.pdf)
- [Scalable schematic (SVG)](stage1-five-leds.svg)
- [Image preview](stage1-five-leds.png)

## Parts

- U1: TLC555IP, DIP8.
- U2: CD4017BE, DIP16.
- R1-R7: 10k, 0.25W, seven resistors total.
- P1: 100k trim pot. Strap wiper W to outer terminal B; A is the other end.
- C1, C2: 100n ceramic, one directly at each IC supply pair.
- C3: 10u electrolytic, positive to timing node, negative to GND.
- C4: 10n ceramic.
- LED1-LED5: white LEDs. Anodes face their resistors; cathodes go to GND.
- Verified regulated 5V DC supply and shared ground.

## Pin table

| IC pin | Connection |
| --- | --- |
| U1 TLC555 pin 1 | GND |
| U1 pin 2 | Pin 6 and C3 positive |
| U1 pin 3 | U2 pin 14 |
| U1 pin 4 | +5V |
| U1 pin 5 | C4 to GND |
| U1 pin 6 | Pin 2 and C3 positive |
| U1 pin 7 | R1 bottom and R2 top |
| U1 pin 8 | +5V |
| U2 CD4017 pin 1 (Q5) | U2 pin 15 (RESET) |
| U2 pin 2 (Q1) | R4 -> LED2 anode |
| U2 pin 3 (Q0) | R3 -> LED1 anode |
| U2 pin 4 (Q2) | R5 -> LED3 anode |
| U2 pin 7 (Q3) | R6 -> LED4 anode |
| U2 pin 8 | GND |
| U2 pin 10 (Q4) | R7 -> LED5 anode |
| U2 pin 13 | GND |
| U2 pin 14 | U1 pin 3 |
| U2 pin 15 | U2 pin 1 |
| U2 pin 16 | +5V |
| U2 pins 5, 6, 9, 11, 12 | Leave open |

R1 is from +5V to U1 pin 7. R2 is from U1 pin 7 to P1.A.
P1.W and P1.B are joined and connect to U1 pins 2/6 and C3 positive.
C1 is between U1 pins 8/1; C2 is between U2 pins 16/8.
All LED cathodes and C3 negative connect to GND.

## Timing and power assumptions

The nominal step period is 0.693 * (R1 + 2 * (R2 + P1)) * C3, approximately
0.21-1.59 seconds. The clock starts immediately when power is applied; the first
visible step is not guaranteed to be LED1, but the counter settles into the
five-step cycle. No power-on reset, PIR, darkness detection, timeout or drivers
are included in this experiment.

Each LED has a conservative 10k resistor. With 5V and a white LED around 3V,
the output current is about 0.2mA before output-voltage losses. This is below
the CD4017 datasheet's 0.36mA source-current test point at VOH=4.6V, 5V supply,
25C. The LED may look dim; do not lower the resistor without checking actual
current, output voltage and the received LED specifications. Use 5V DC only.

## First check

1. Assemble unpowered. Check DIP orientation and every numbered connection.
2. Identify the trim-pot wiper with a meter; set it near mid travel.
3. Verify supply polarity and about 5V before connecting the circuit.
4. Power on: expect LED1 -> LED2 -> LED3 -> LED4 -> LED5, repeating after startup.
5. Adjust P1. If no LED lights, check polarity and supply first; do not replace
   the current-limiting resistors with wires.

## Sources

- [TI TLC555, SLFS043K: pins and astable timing](https://www.ti.com/lit/ds/symlink/tlc555.pdf)
- [TI CD4017B, SCHS027C: pins, reset and output drive](https://www.ti.com/lit/ds/symlink/cd4017b.pdf)
