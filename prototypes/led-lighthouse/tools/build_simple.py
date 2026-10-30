"""Build revision 0.4: three transistors, two timers, one complete drawing.

Reuses this prototype's verified drawing primitives and continuous-wire router.
The independent CAD checker validates serialized connectivity separately.
"""
import ast
import heapq
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A0, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT=Path(__file__).resolve().parents[1]
INK,WIRE,BLUE,RED='#171717','#171717','#176597','#b52b2b'
counter=200000
parts={}
def add(ref,value,kind,pins,purpose):
    parts[ref]=dict(ref=ref,value=value,kind=kind,pins=pins,purpose=purpose)
def r(ref,value,a,b,purpose):add(ref,value,'R',{'1':a,'2':b},purpose)
def cap(ref,value,a,b,polar=False,purpose='Supply bypass'):
    add(ref,value,'C',({'+':a,'-':b} if polar else {'1':a,'2':b}),purpose)
add('J1','Regulated 5V','J',{'+':'VIN_5V','-':'GND'},'External verified 5V input')
add('S1','Power switch','SW',{'1':'VIN_5V','2':'+5V'},'Main switch')
add('J2','SB00312A-1 PIR','J',{'VCC':'+5V','OUT':'PIR_OUT','GND':'GND'},'Match module labels; physical order unverified')
add('LDR1','LDR5516','LDR',{'1':'LDR_SUPPLY','2':'LIGHT'},'Upper leg of light-sensing divider')
r('R12','10k','+5V','LDR_SUPPLY','Limits LDR current even with P1 at zero resistance')
add('P1','100k / LIGHT','P',{'A':'LIGHT','B':'GND','W':'GND'},'Lower divider leg; start at about 50k; wiper tied to B')
r('R1','10k','LIGHT','LIGHT_BASE','Light transistor base current limiter')
add('Q1','BC547B','Q',{'B':'LIGHT_BASE','C':'ARM','E':'GND'},'On in light: cancels and inhibits U1 via RESET')
r('R2','10k','+5V','ARM','Enables U1 in darkness')
cap('C1','10u / 16V','ARM','GND',True,'Short power-on reset delay, not full PIR warmup suppression')
cap('C2','100n','PIR_OUT','PIR_EDGE',purpose='AC coupling: responds to rising motion edge, blocks held HIGH')
r('R3','47k','PIR_EDGE','TRIG_BASE','Limits PIR transient load and base clamp current')
r('R4','100k','TRIG_BASE','GND','Returns trigger base to ground')
add('D1','1N4148','D',{'A':'GND','K':'TRIG_BASE'},'Clamps negative base transient on PIR falling edge')
add('Q2','BC547B','Q',{'B':'TRIG_BASE','C':'TRIG','E':'GND'},'Generates a short active-low trigger at U1 pin 2')
r('R5','10k','+5V','TRIG','Trigger pull-up')
add('U1','TLC555IP','U',{'1':'GND','2':'TRIG','3':'RUN','4':'ARM','5':'CTRL1','6':'TIME','7':'DISCH1','8':'+5V'},'Monostable run timer')
r('R6','220k','+5V','TIME_TOP','Minimum timing resistance')
add('P3','1M / TIME','P',{'A':'TIME_TOP','B':'TIME','W':'TIME'},'Run-time adjustment; wiper tied to B')
r('R7','100R','TIME','DISCH1','Limits timing capacitor discharge current')
cap('C3','100u / 16V','TIME','GND',True,'Timing capacitor: leakage and actual duration must be tested')
cap('C4','10n','CTRL1','GND',purpose='Control voltage bypass')
add('U2','TLC555IP','U',{'1':'GND','2':'OSC_TIME','3':'CLOCK','4':'RUN','5':'CTRL2','6':'OSC_TIME','7':'DISCH2','8':'+5V'},'Astable LED step clock; stopped by U1 while idle')
r('R8','10k','+5V','DISCH2','Astable charging resistor')
r('R9','10k','DISCH2','OSC_TOP','Minimum astable variable resistance')
add('P2','100k / SPEED','P',{'A':'OSC_TOP','B':'OSC_TIME','W':'OSC_TIME'},'LED speed adjustment; wiper tied to B')
cap('C5','10u / 16V','OSC_TIME','GND',True,'Astable timing capacitor')
cap('C6','10n','CTRL2','GND',purpose='Control voltage bypass')
add('U3','CD4017BE','U',{'1':'RESET5','2':'STEP1','3':'STEP0','4':'STEP2','5':'NC_Q6','6':'NC_Q7','7':'STEP3','8':'GND','9':'NC_Q8','10':'STEP4','11':'NC_Q9','12':'NC_CARRY','13':'GND','14':'CLOCK','15':'RESET5','16':'+5V'},'Five-step sequence; preserve direct pin 1 to 15 reset wire')
for i in range(1,6):add(f'LED{i}','White LED','LED',{'A':f'STEP{i-1}','K':'LED_RETURN'},'Direct drive as in user-tested manual circuit')
r('R10','1k','LED_RETURN','LED_SINK','Shared LED current limiter; keep at least 1k during initial test')
r('R11','10k','RUN','LED_BASE','Common LED switch base resistor')
add('Q3','BC547B','Q',{'B':'LED_BASE','C':'LED_SINK','E':'GND'},'Switches all LEDs off at timeout')
for i,ic in [(7,'U1'),(8,'U2'),(9,'U3')]:cap(f'C{i}','100n','+5V','GND',purpose=f'Close to {ic} supply pins')
cap('C10','100u / 16V','+5V','GND',True,'Supply bulk capacitor')
cap('C11','100n','+5V','GND',purpose='Close to PIR supply pads')
rev=dict(revision='0.4',date='2026-10-30',status='design and CAD connectivity reviewed; complete assembly NOT hardware-tested',supply='regulated 5V only',parts=list(parts.values()))
(ROOT/'docs/simple-v04-netlist.json').write_text(json.dumps(rev,indent=2)+'\n')
lines=['# Revision 0.4 connection reference','','Functional terminal names are not a physical module or transistor lead order.','','| Part | Value | Terminal to wire / net | Purpose |','| --- | --- | --- | --- |']
for p in parts.values():lines.append('| '+p['ref']+' | '+p['value']+' | '+'; '.join(f'{k}: {v}' for k,v in p['pins'].items())+' | '+p['purpose']+' |')
(ROOT/'docs/simple-v04-pin-table.md').write_text('\n'.join(lines)+'\n')
# Load definitions only, so archived designs are not regenerated or modified.
for filename in ('build_full_easyeda.py','build_continuous.py'):
    tree=ast.parse((ROOT/'tools'/filename).read_text())
    keep=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and (filename=='build_full_easyeda.py' or isinstance(n,ast.ClassDef))]
    exec(compile(ast.Module(body=keep,type_ignores=[]),filename,'exec'))
W,H,G=4200,2240,10
NW,NH=W//G+1,H//G+1
s=Continuous();s.shape=[];s.ops=[]
s.text(110,65,'LED lighthouse - SIMPLE complete circuit / revision 0.4',33,True)
s.text(110,105,'Regulated 5V / 5 white LEDs / motion in darkness / adjustable duration and speed / no TLC372',20)
s.text(110,2175,'2026-10-30 / Complete combined circuit NOT hardware-tested. Follow the staged checks before permanent assembly.',18,color=RED)
s.text(110,2205,'Dot = connection. Bridge = crossing WITHOUT connection. All wires are drawn. Use printed pin numbers; symbol layout is functional.',17)
s.text(3000,155,'RED: +5V    BLUE: GND',19,True)
s.component('J1',110,230,w=150,h=120,pinpos={'+':(280,280,'right'),'-':(280,320,'right')},names={'+':'+ IN','-':'GND'})
s.horizontal('S1',410,280)
s.note(150,430,'PIR rising edge -> short start pulse')
s.component('J2',150,500,w=160,h=190,pinpos={'VCC':(330,550,'right'),'OUT':(330,600,'right'),'GND':(330,650,'right')})
s.horizontal('C2',460,600)
s.horizontal('R3',660,600)
s.component('Q2',880,600)
s.component('R5',900,380)
s.component('R4',690,830)
s.component('D1',490,830)
s.text(150,990,'D1 band (K) faces the transistor BASE net.',17)
s.text(150,1020,'A held-HIGH PIR output cannot hold U1 TRIG low.',17)
# Duration timer.
s.note(1510,370,'U1 - duration')
s.component('U1',1500,500,w=220,h=360,pinpos={'1':(1580,880,'down'),'2':(1480,600,'left'),'3':(1740,600,'right'),'4':(1480,670,'left'),'5':(1680,880,'down'),'6':(1480,770,'left'),'7':(1480,710,'left'),'8':(1580,480,'up')},names={'1':'GND','2':'TRIG','3':'RUN','4':'RESET','5':'CTRL','6':'THRES','7':'DISCH','8':'VDD'})
s.component('R6',1260,350)
s.component('P3',1260,520)
s.horizontal('R7',1370,710)
s.component('C3',1260,1020)
s.component('C4',1680,1020)
s.component('C7',1440,400)
s.text(1170,1120,'P3: about 325k for 60 s; measure and adjust.',17)
# Astable.
s.note(2290,370,'U2 - LED speed')
s.component('U2',2280,500,w=220,h=360,pinpos={'1':(2360,880,'down'),'2':(2260,790,'left'),'3':(2520,600,'right'),'4':(2260,600,'left'),'5':(2460,880,'down'),'6':(2260,740,'left'),'7':(2260,670,'left'),'8':(2360,480,'up')},names={'1':'GND','2':'TRIG','3':'OUT','4':'RESET','5':'CTRL','6':'THRES','7':'DISCH','8':'VDD'})
s.component('R8',2010,340)
s.component('R9',2010,540)
s.component('P2',2010,740)
s.component('C5',2010,1020)
s.component('C6',2460,1020)
s.component('C8',2200,400)
s.text(1930,1120,'P2: about 0.21-1.59 s per LED step.',17)
# Counter and the familiar direct reset wire.
s.note(2950,310,'U3 - five steps')
s.component('U3',2950,400,w=260,h=900,pinpos={'1':(3230,1140,'right'),'2':(3230,660,'right'),'3':(3230,540,'right'),'4':(3230,780,'right'),'5':(2930,900,'left'),'6':(2930,960,'left'),'7':(3230,900,'right'),'8':(3080,1320,'down'),'9':(2930,1020,'left'),'10':(3230,1020,'right'),'11':(2930,1080,'left'),'12':(2930,1140,'left'),'13':(2930,600,'left'),'14':(2930,500,'left'),'15':(2930,700,'left'),'16':(3080,380,'up')},names={'1':'Q5 / RESET','2':'Q1','3':'Q0','4':'Q2','5':'Q6 NC','6':'Q7 NC','7':'Q3','8':'GND','9':'Q8 NC','10':'Q4','11':'Q9 NC','12':'CARRY NC','13':'INHIBIT','14':'CLOCK','15':'RESET','16':'VDD'})
for i,y in enumerate((540,660,780,900,1020),1):s.component(f'LED{i}',3590,y)
s.component('R10',3990,1320)
s.component('Q3',3970,1510)
s.horizontal('R11',3670,1510)
s.component('C9',3270,350)
s.text(3360,1670,'Q3: all LEDs OFF after timeout.',18,True)
s.text(3360,1700,'Keep the shared 1k resistor.',17)
s.text(2830,1460,'U3 pin 1 -> pin 15: direct wire, as tested.',17)
# One-transistor light detector.
s.note(180,1300,'Daylight inhibit - one transistor')
s.component('R12',300,1390)
s.component('LDR1',300,1510)
s.component('P1',300,1760)
s.horizontal('R1',570,1630)
s.component('Q1',800,1630)
s.component('R2',1000,1430)
s.component('C1',1000,1770)
s.text(180,1890,'P1: start at about 50k, then adjust at dusk.',17)
s.text(180,1920,'Light: Q1 ON -> U1 RESET low -> LEDs OFF.',17)
s.text(180,1950,'Dark: Q1 OFF -> a new motion edge can start U1.',17)
s.text(180,1980,'Keep the LDR outside the LED beam.',17)
s.note(1500,1790,'Supply capacitors - place close to the corresponding device')
s.component('C10',1640,1930)
s.component('C11',1980,1930)
s.text(2250,1900,'C7: U1   C8: U2   C9: U3   C11: PIR',17)
s.text(2250,1930,'C3, C5, C1, C10: electrolytic, + shown.',17)
s.text(2250,1960,'Pots: W = wiper; W is wired to B.',17)
assert Counter(s.used)==Counter(parts.keys())
assert len(s.pins)==sum(len(p['pins']) for p in parts.values())

# Reuse the route/export pipeline; substitute the hand-planned rails below.
text=(ROOT/'tools/build_continuous.py').read_text()
router=text[text.index('def grid(p):'):]
start=router.index('# Continuous, drawn supply rails.')
end=router.index('\ndef allowed(',start)
seeds='''# Hand-planned rails and the five visible LED wires.
seed('+5V',[(40,180),(4100,180)])
seed('+5V',[(40,180),(40,1250),(1100,1250)])
seed('GND',[(90,320),(90,2090),(4100,2090)])
seed('GND',[(90,1210),(2600,1210)])
seed('VIN_5V',[(280,280),(370,280)])
seed('+5V',[(450,280),(460,280),(460,180)])
seed('GND',[(280,320),(90,320)])
for i,y in enumerate((540,660,780,900,1020)):
    seed(f'STEP{i}',[(3230,y),(3560,y)])
    seed('LED_RETURN',[(3620,y),(3990,y)])
seed('LED_RETURN',[(3990,540),(3990,1290)])
seed('LED_SINK',[(3990,1350),(3990,1470)])
seed('GND',[(3990,1550),(3990,2090)])
'''
router=router[:start]+seeds+router[end:]
router=router.replace('lighthouse-continuous','lighthouse-simple-continuous')
router=router.replace('Lighthouse / one continuous drawing','Lighthouse / simple revision 0.4')
router=router.replace('LED lighthouse - one continuous fully wired schematic','LED lighthouse - simple complete circuit, revision 0.4')
exec(compile(router,'<continuous route/export>','exec'))
