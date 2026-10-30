# Complete circuit v0.2 - pin table

2026-10-29. Schematic-only design. Entire circuit not hardware-tested.
References are inherited from v0.1; retired references are not reused.

| Part | Value | Connections | Function |
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
| R26 | 10k | 1=RUN; 2=QB6 | Common LED switch base resistor |
| R28 | 1k | 1=LED_RETURN; 2=LED_SINK | Shared LED current limiter; one LED selected at a time |
| LED1 | White LED | A=STEP0; K=LED_RETURN | Lighthouse position 1 |
| LED2 | White LED | A=STEP1; K=LED_RETURN | Lighthouse position 2 |
| LED3 | White LED | A=STEP2; K=LED_RETURN | Lighthouse position 3 |
| LED4 | White LED | A=STEP3; K=LED_RETURN | Lighthouse position 4 |
| LED5 | White LED | A=STEP4; K=LED_RETURN | Lighthouse position 5 |
| R38 | 100k | 1=+5V; 2=DAY | Day comparator pull-up |
| R39 | 47k | 1=DAY; 2=QB12 | Reset transistor base current limit |
| R40 | 100 | 1=TIME; 2=DISCH1 | Limit timing-capacitor discharge current |
| Q1 | BC547B | C=INV; B=QB1; E=GND | PIR input inverter |
| Q2 | BC547B | C=MOTION_BUF; B=QB2; E=GND | Restore positive motion edge |
| Q3 | BC547B | C=TRIG; B=QB3; E=GND | Short active-low trigger pulse |
| Q4 | BC547B | C=QB3; B=QB4; E=GND | Ignore motion edges while RUN is high |
| Q5 | BC547B | C=CLOCK; B=QB5; E=GND | Clock inversion: first step starts at LED1 |
| Q6 | BC547B | C=LED_SINK; B=QB6; E=GND | Common LED return switch; all LEDs off while idle |
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
| J1 | 5V input | +=VIN_5V; -=GND | Verified regulated 5V input; no raw battery connection |
| J2 | SB00312A-1 | VCC=+5V; OUT=PIR_OUT; GND=GND | Signal names only; physical pad order not assumed |
| S1 | Power switch | 1=VIN_5V; 2=+5V | User-supplied power switch |
