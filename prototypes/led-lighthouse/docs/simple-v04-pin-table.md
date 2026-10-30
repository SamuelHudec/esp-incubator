# Revision 0.4 connection reference

Functional terminal names are not a physical module or transistor lead order.

| Part | Value | Terminal to wire / net | Purpose |
| --- | --- | --- | --- |
| J1 | Regulated 5V | +: VIN_5V; -: GND | External verified 5V input |
| S1 | Power switch | 1: VIN_5V; 2: +5V | Main switch |
| J2 | SB00312A-1 PIR | VCC: +5V; OUT: PIR_OUT; GND: GND | Match module labels; physical order unverified |
| LDR1 | LDR5516 | 1: LDR_SUPPLY; 2: LIGHT | Upper leg of light-sensing divider |
| R12 | 10k | 1: +5V; 2: LDR_SUPPLY | Limits LDR current even with P1 at zero resistance |
| P1 | 100k / LIGHT | A: LIGHT; B: GND; W: GND | Lower divider leg; start at about 50k; wiper tied to B |
| R1 | 10k | 1: LIGHT; 2: LIGHT_BASE | Light transistor base current limiter |
| Q1 | BC547B | B: LIGHT_BASE; C: ARM; E: GND | On in light: cancels and inhibits U1 via RESET |
| R2 | 10k | 1: +5V; 2: ARM | Enables U1 in darkness |
| C1 | 10u / 16V | +: ARM; -: GND | Short power-on reset delay, not full PIR warmup suppression |
| C2 | 100n | 1: PIR_OUT; 2: PIR_EDGE | AC coupling: responds to rising motion edge, blocks held HIGH |
| R3 | 47k | 1: PIR_EDGE; 2: TRIG_BASE | Limits PIR transient load and base clamp current |
| R4 | 100k | 1: TRIG_BASE; 2: GND | Returns trigger base to ground |
| D1 | 1N4148 | A: GND; K: TRIG_BASE | Clamps negative base transient on PIR falling edge |
| Q2 | BC547B | B: TRIG_BASE; C: TRIG; E: GND | Generates a short active-low trigger at U1 pin 2 |
| R5 | 10k | 1: +5V; 2: TRIG | Trigger pull-up |
| U1 | TLC555IP | 1: GND; 2: TRIG; 3: RUN; 4: ARM; 5: CTRL1; 6: TIME; 7: DISCH1; 8: +5V | Monostable run timer |
| R6 | 220k | 1: +5V; 2: TIME_TOP | Minimum timing resistance |
| P3 | 1M / TIME | A: TIME_TOP; B: TIME; W: TIME | Run-time adjustment; wiper tied to B |
| R7 | 100R | 1: TIME; 2: DISCH1 | Limits timing capacitor discharge current |
| C3 | 100u / 16V | +: TIME; -: GND | Timing capacitor: leakage and actual duration must be tested |
| C4 | 10n | 1: CTRL1; 2: GND | Control voltage bypass |
| U2 | TLC555IP | 1: GND; 2: OSC_TIME; 3: CLOCK; 4: RUN; 5: CTRL2; 6: OSC_TIME; 7: DISCH2; 8: +5V | Astable LED step clock; stopped by U1 while idle |
| R8 | 10k | 1: +5V; 2: DISCH2 | Astable charging resistor |
| R9 | 10k | 1: DISCH2; 2: OSC_TOP | Minimum astable variable resistance |
| P2 | 100k / SPEED | A: OSC_TOP; B: OSC_TIME; W: OSC_TIME | LED speed adjustment; wiper tied to B |
| C5 | 10u / 16V | +: OSC_TIME; -: GND | Astable timing capacitor |
| C6 | 10n | 1: CTRL2; 2: GND | Control voltage bypass |
| U3 | CD4017BE | 1: RESET5; 2: STEP1; 3: STEP0; 4: STEP2; 5: NC_Q6; 6: NC_Q7; 7: STEP3; 8: GND; 9: NC_Q8; 10: STEP4; 11: NC_Q9; 12: NC_CARRY; 13: GND; 14: CLOCK; 15: RESET5; 16: +5V | Five-step sequence; preserve direct pin 1 to 15 reset wire |
| LED1 | White LED | A: STEP0; K: LED_RETURN | Direct drive as in user-tested manual circuit |
| LED2 | White LED | A: STEP1; K: LED_RETURN | Direct drive as in user-tested manual circuit |
| LED3 | White LED | A: STEP2; K: LED_RETURN | Direct drive as in user-tested manual circuit |
| LED4 | White LED | A: STEP3; K: LED_RETURN | Direct drive as in user-tested manual circuit |
| LED5 | White LED | A: STEP4; K: LED_RETURN | Direct drive as in user-tested manual circuit |
| R10 | 1k | 1: LED_RETURN; 2: LED_SINK | Shared LED current limiter; keep at least 1k during initial test |
| R11 | 10k | 1: RUN; 2: LED_BASE | Common LED switch base resistor |
| Q3 | BC547B | B: LED_BASE; C: LED_SINK; E: GND | Switches all LEDs off at timeout |
| C7 | 100n | 1: +5V; 2: GND | Close to U1 supply pins |
| C8 | 100n | 1: +5V; 2: GND | Close to U2 supply pins |
| C9 | 100n | 1: +5V; 2: GND | Close to U3 supply pins |
| C10 | 100u / 16V | +: +5V; -: GND | Supply bulk capacitor |
| C11 | 100n | 1: +5V; 2: GND | Close to PIR supply pads |
