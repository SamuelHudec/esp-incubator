# LED lighthouse wiring reference

Revision 0.1, 2026-10-21. **Untested hardware prototype.**

The PDF is the assembly guide. Matching net names are electrically connected. This is not a PCB layout.

## Pin-to-net connections

| Part | Value | Pin / terminal connections | Purpose |
| --- | --- | --- | --- |
| U1 | TLC555IP | 1=GND; 2=TRIG; 3=RUN; 4=ARM; 5=CTRL1; 6=TIME; 7=DISCH1; 8=+5V | One-shot timer |
| U2 | TLC555IP | 1=GND; 2=OSC; 3=OSC_OUT; 4=RUN; 5=CTRL2; 6=OSC; 7=DISCH2; 8=+5V | LED step oscillator |
| U3 | TLC372CP | 1=DAY; 2=LUX; 3=DARK_TH; 4=GND; 5=FIX_REF; 6=RUN_HALF; 7=IDLE; 8=+5V | Darkness comparator and RUN inverter |
| U4 | CD4017BE | 1=STEP5; 2=STEP1; 3=STEP0; 4=STEP2; 5=NC_5; 6=NC_6; 7=STEP3; 8=GND; 9=NC_9; 10=STEP4; 11=NC_11; 12=NC_12; 13=GND; 14=CLOCK; 15=COUNT_RESET; 16=+5V | Modulo-five LED sequencer |
| R1 | 100k | 1=+5V; 2=LUX | LDR divider top |
| R2 | 100k | 1=LUX; 2=GND | Limit LUX to safe comparator input range |
| R3 | 1M | 1=DAY; 2=DARK_TH | Darkness hysteresis |
| R4 | 47k | 1=+5V; 2=REF_TOP | Threshold range divider top |
| R5 | 47k | 1=REF_TOP; 2=GND | Threshold range divider bottom |
| P1 | 100k | A=REF_TOP; W=DARK_TH; B=GND | Darkness sensitivity (three terminals) |
| R6 | 10k | 1=+5V; 2=ARM | Reset pull-up / startup delay |
| R7 | 100k | 1=RUN; 2=RUN_HALF | RUN divider top |
| R8 | 100k | 1=RUN_HALF; 2=GND | RUN divider bottom |
| R9 | 47k | 1=+5V; 2=FIX_REF | IDLE reference top |
| R10 | 15k | 1=FIX_REF; 2=GND | IDLE reference bottom |
| R11 | 10k | 1=+5V; 2=IDLE | Open-drain pull-up |
| R12 | 47k | 1=PIR_OUT; 2=QB1 | PIR input current limit |
| R13 | 47k | 1=+5V; 2=INV | First inverter pull-up |
| R14 | 47k | 1=INV; 2=QB2 | Buffer base resistor |
| R15 | 47k | 1=+5V; 2=MOTION_BUF | Second inverter pull-up |
| R16 | 10k | 1=EDGE; 2=QB3 | Pulse base current limit |
| R17 | 100k | 1=QB3; 2=GND | Pulse reset / discharge |
| R18 | 10k | 1=+5V; 2=TRIG | Timer trigger pull-up |
| R19 | 47k | 1=RUN; 2=QB4 | Lockout base resistor |
| R20 | 220k | 1=+5V; 2=P3_A | Minimum timer resistance |
| P3 | 1M | A=P3_A; W=TIME; B=TIME | Duration rheostat; strap W to B |
| R21 | 10k | 1=+5V; 2=DISCH2 | Astable RA |
| R22 | 10k | 1=DISCH2; 2=P2_A | Minimum astable RB |
| P2 | 100k | A=P2_A; W=OSC; B=OSC | Step-speed rheostat; strap W to B |
| R23 | 47k | 1=OSC_OUT; 2=QB5 | Clock inverter base resistor |
| R24 | 10k | 1=+5V; 2=CLOCK | Clock pull-up |
| R25 | 100k | 1=COUNT_RESET; 2=GND | Counter reset pull-down |
| R26 | 1k | 1=RUN; 2=QB6 | LED supply buffer base resistor |
| R27 | 100k | 1=LED_POWER; 2=GND | Discharge switched LED rail |
| R28 | 1k | 1=LED_POWER; 2=LED_A1 | LED 1 current limit |
| R33 | 22k | 1=STEP0; 2=QB7 | LED 1 base resistor |
| LED1 | White LED | A=LED_A1; K=LED_K1 | Lighthouse position 1 |
| Q7 | BC547B | C=LED_K1; B=QB7; E=GND | LED 1 sink |
| R29 | 1k | 1=LED_POWER; 2=LED_A2 | LED 2 current limit |
| R34 | 22k | 1=STEP1; 2=QB8 | LED 2 base resistor |
| LED2 | White LED | A=LED_A2; K=LED_K2 | Lighthouse position 2 |
| Q8 | BC547B | C=LED_K2; B=QB8; E=GND | LED 2 sink |
| R30 | 1k | 1=LED_POWER; 2=LED_A3 | LED 3 current limit |
| R35 | 22k | 1=STEP2; 2=QB9 | LED 3 base resistor |
| LED3 | White LED | A=LED_A3; K=LED_K3 | Lighthouse position 3 |
| Q9 | BC547B | C=LED_K3; B=QB9; E=GND | LED 3 sink |
| R31 | 1k | 1=LED_POWER; 2=LED_A4 | LED 4 current limit |
| R36 | 22k | 1=STEP3; 2=QB10 | LED 4 base resistor |
| LED4 | White LED | A=LED_A4; K=LED_K4 | Lighthouse position 4 |
| Q10 | BC547B | C=LED_K4; B=QB10; E=GND | LED 4 sink |
| R32 | 1k | 1=LED_POWER; 2=LED_A5 | LED 5 current limit |
| R37 | 22k | 1=STEP4; 2=QB11 | LED 5 base resistor |
| LED5 | White LED | A=LED_A5; K=LED_K5 | Lighthouse position 5 |
| Q11 | BC547B | C=LED_K5; B=QB11; E=GND | LED 5 sink |
| R38 | 100k | 1=+5V; 2=DAY | Day comparator pull-up |
| R39 | 47k | 1=DAY; 2=QB12 | Reset transistor base current limit |
| R40 | 100 | 1=TIME; 2=DISCH1 | Limit timing-capacitor discharge current |
| Q1 | BC547B | C=INV; B=QB1; E=GND | PIR input inverter |
| Q2 | BC547B | C=MOTION_BUF; B=QB2; E=GND | Restore positive motion edge |
| Q3 | BC547B | C=TRIG; B=QB3; E=GND | Short active-low trigger pulse |
| Q4 | BC547B | C=QB3; B=QB4; E=GND | Ignore motion edges while RUN is high |
| Q5 | BC547B | C=CLOCK; B=QB5; E=GND | Clock inversion: first step starts at LED1 |
| Q6 | BC547B | C=+5V; B=QB6; E=LED_POWER | NPN emitter follower: LED rail on only during RUN |
| Q12 | BC547B | C=ARM; B=QB12; E=GND | Daylight resets timer; safely discharges C6 |
| D1 | 1N4148 | A=GND; K=QB3 | Clamp reverse base voltage on falling motion edge |
| D2 | 1N4148 | A=IDLE; K=COUNT_RESET | Reset counter while idle |
| D3 | 1N4148 | A=STEP5; K=COUNT_RESET | Return to LED1 after LED5 |
| C1 | 100n | 1=+5V; 2=GND | Local bypass at U1 |
| C2 | 100n | 1=+5V; 2=GND | Local bypass at U2 |
| C3 | 100n | 1=+5V; 2=GND | Local bypass at U3 |
| C4 | 100n | 1=+5V; 2=GND | Local bypass at U4 |
| C5 | 100u / 16V | +=+5V; -=GND | Bulk supply capacitor |
| C6 | 100u / 16V | +=ARM; -=GND | Startup reset delay |
| C7 | 100u / 16V | +=TIME; -=GND | One-shot timing capacitor; leakage must be checked |
| C8 | 10n | 1=CTRL1; 2=GND | U1 control bypass |
| C9 | 10n | 1=CTRL2; 2=GND | U2 control bypass |
| C10 | 10u / 16V | +=OSC; -=GND | Step oscillator timing |
| C11 | 100n | 1=MOTION_BUF; 2=EDGE | Motion edge coupling |
| C12 | 10n | 1=COUNT_RESET; 2=GND | Stretch self-reset pulse |
| C13 | 100n | 1=+5V; 2=GND | Bypass near PIR supply |
| C14 | 100n | 1=LUX; 2=GND | Filter light sensor noise |
| C15 | 10u / 16V | +=QB4; -=GND | Hold busy lockout briefly after RUN falls |
| LDR1 | LDR5516 | 1=LUX; 2=GND | Keep out of LED beam; no polarity |
| J1 | 5V input | +=+5V; -=GND | From verified boost output through S1 |
| J2 | SB00312A-1 | VCC=+5V; OUT=PIR_OUT; GND=GND | Signal names only; physical pad order not assumed |

## Wire groups

Join all endpoints in each row. NC pins are intentionally open.

| Net | Endpoints |
| --- | --- |
| +5V | U1.8, U2.8, U3.8, U4.16, R1.1, R4.1, R6.1, R9.1, R11.1, R13.1, R15.1, R18.1, R20.1, R21.1, R24.1, R38.1, Q6.C, C1.1, C2.1, C3.1, C4.1, C5.+, C13.1, J1.+, J2.VCC |
| ARM | U1.4, R6.2, Q12.C, C6.+ |
| CLOCK | U4.14, R24.2, Q5.C |
| COUNT_RESET | U4.15, R25.1, D2.K, D3.K, C12.1 |
| CTRL1 | U1.5, C8.1 |
| CTRL2 | U2.5, C9.1 |
| DARK_TH | U3.3, R3.2, P1.W |
| DAY | U3.1, R3.1, R38.2, R39.1 |
| DISCH1 | U1.7, R40.2 |
| DISCH2 | U2.7, R21.2, R22.1 |
| EDGE | R16.1, C11.2 |
| FIX_REF | U3.5, R9.2, R10.1 |
| GND | U1.1, U2.1, U3.4, U4.8, U4.13, R2.2, R5.2, P1.B, R8.2, R10.2, R17.2, R25.2, R27.2, Q7.E, Q8.E, Q9.E, Q10.E, Q11.E, Q1.E, Q2.E, Q3.E, Q4.E, Q5.E, Q12.E, D1.A, C1.2, C2.2, C3.2, C4.2, C5.-, C6.-, C7.-, C8.2, C9.2, C10.-, C12.2, C13.2, C14.2, C15.-, LDR1.2, J1.-, J2.GND |
| IDLE | U3.7, R11.2, D2.A |
| INV | R13.2, R14.1, Q1.C |
| LED_A1 | R28.2, LED1.A |
| LED_A2 | R29.2, LED2.A |
| LED_A3 | R30.2, LED3.A |
| LED_A4 | R31.2, LED4.A |
| LED_A5 | R32.2, LED5.A |
| LED_K1 | LED1.K, Q7.C |
| LED_K2 | LED2.K, Q8.C |
| LED_K3 | LED3.K, Q9.C |
| LED_K4 | LED4.K, Q10.C |
| LED_K5 | LED5.K, Q11.C |
| LED_POWER | R27.1, R28.1, R29.1, R30.1, R31.1, R32.1, Q6.E |
| LUX | U3.2, R1.2, R2.1, C14.1, LDR1.1 |
| MOTION_BUF | R15.2, Q2.C, C11.1 |
| NC_11 | U4.11 |
| NC_12 | U4.12 |
| NC_5 | U4.5 |
| NC_6 | U4.6 |
| NC_9 | U4.9 |
| OSC | U2.2, U2.6, P2.W, P2.B, C10.+ |
| OSC_OUT | U2.3, R23.1 |
| P2_A | R22.2, P2.A |
| P3_A | R20.2, P3.A |
| PIR_OUT | R12.1, J2.OUT |
| QB1 | R12.2, Q1.B |
| QB10 | R36.2, Q10.B |
| QB11 | R37.2, Q11.B |
| QB12 | R39.2, Q12.B |
| QB2 | R14.2, Q2.B |
| QB3 | R16.2, R17.1, Q3.B, Q4.C, D1.K |
| QB4 | R19.2, Q4.B, C15.+ |
| QB5 | R23.2, Q5.B |
| QB6 | R26.2, Q6.B |
| QB7 | R33.2, Q7.B |
| QB8 | R34.2, Q8.B |
| QB9 | R35.2, Q9.B |
| REF_TOP | R4.2, R5.1, P1.A |
| RUN | U1.3, U2.4, R7.1, R19.1, R26.1 |
| RUN_HALF | U3.6, R7.2, R8.1 |
| STEP0 | U4.3, R33.1 |
| STEP1 | U4.2, R34.1 |
| STEP2 | U4.4, R35.1 |
| STEP3 | U4.7, R36.1 |
| STEP4 | U4.10, R37.1 |
| STEP5 | U4.1, D3.A |
| TIME | U1.6, P3.W, P3.B, R40.1, C7.+ |
| TRIG | U1.2, R18.2, Q3.C |

## Power and module assumptions

- J1: verified regulated 5V, after S1; common GND.
- Use LaskaKit LA122076 with a known protected single Li-ion/Li-pol cell of 4.2V-charge chemistry and a compatible charge-current rating.
- Module physical pad order is not inferred: match actual labels or obtain the correct revision pinout before applying power.
- J2.OUT must be LOW at rest, HIGH on motion. Verify it before connecting to the trigger stage.
- Default Semtech BC547 package is C-B-E with flat face toward the viewer and leads downward. Confirm actual received variant; the manufacturer notes custom pinouts can exist.
- White LEDs have individual 1k current limiters; brightness/current must be measured.
- C7 is a long-duration RC timing capacitor. Excess leakage can prevent timeout; this is an explicit bench-test gate.

## Behaviour

- Darkness + a new PIR rising edge starts one run.
- Q4 disables new triggers during RUN. The next run requires a fresh PIR edge after timeout.
- Daylight resets U1 and cancels a running sequence. Shield the LDR from the LEDs.
- Counter is reset to LED1 while idle; clock inversion preserves the first LED at startup.
- PIR warmup pulses may start a run; this design does not add a full warmup inhibit.

## Sources

- [S1: TI TLC555, SLFS043K, Jan 2026, pin functions / mono- and astable operation](https://www.ti.com/lit/ds/symlink/tlc555.pdf)
- [S2: TI TLC372, SLCS114F, Jun 2025, p3 pinout / p4 common-mode range](https://www.ti.com/lit/ds/symlink/tlc372.pdf)
- [S3: TI CD4017B, SCHS027C, p1 pinout / 5V operation / reset](https://www.ti.com/lit/ds/symlink/cd4017b.pdf)
- [S4: Semtech BC547B, GME 210-062, manufacturer datasheets linked by retailer](https://www.gme.cz/v/1489324/semtech-bc547b-ammo-bipolarni-tranzistor)
- [S5: Semtech manufacturer datasheet mirror: default C-B-E; special pinouts can exist](https://datasheet.datasheetarchive.com/originals/library/Datasheet-024/DSA00417422.pdf)
- [S6: GME SB00312A-1, 775-183: 2.7-12V, <0.1mA, 2s; pad order not verified](https://www.gme.cz/v/1508403/sb00312a-1-pir-modul)
- [S7: GME LDR5516, 520-084: light 5-10k, dark 0.5M](https://www.gme.cz/v/1495847/ldr5516-fotorezistor)
- [S8: LaskaKit LA122076 charger + 5V boost; protected battery recommended](https://www.laskakit.cz/mikro-nabijecka-boost-pro-usb-powerbank-5v--usb-c/)
