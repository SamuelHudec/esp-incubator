"""Build a schematic-only EasyEDA Standard project and matching review PDF.

No footprint assignments are made. Symbols carry verified physical DIP pin
numbers; module terminals are signal names, not guessed physical pad positions.
Reference numbers inherited from revision 0.1 are intentionally not renumbered.
"""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'hardware/easyeda'
DOC = ROOT / 'docs'
PDF = ROOT / 'output/pdf/full-circuit-v02.pdf'
W, H = 1600, 1100
INK, WIRE, BLUE, RED = '#273643', '#008800', '#245f8a', '#a23232'

old = json.loads((DOC / 'netlist.json').read_text())
drop = {f'Q{i}' for i in range(7, 12)} | {f'R{i}' for i in range(29, 38)} | {'R27'}
parts = {p['ref']: p for p in old['parts'] if p['ref'] not in drop}
parts['Q6']['pins'] = {'C': 'LED_SINK', 'B': 'QB6', 'E': 'GND'}
parts['Q6']['purpose'] = 'Common LED return switch; all LEDs off while idle'
parts['R26']['value'] = '10k'
parts['R26']['purpose'] = 'Common LED switch base resistor'
parts['R28']['pins'] = {'1': 'LED_RETURN', '2': 'LED_SINK'}
parts['R28']['purpose'] = 'Shared LED current limiter; one LED selected at a time'
for i in range(1, 6):
    parts[f'LED{i}']['pins'] = {'A': f'STEP{i-1}', 'K': 'LED_RETURN'}
parts['J1']['pins'] = {'+': 'VIN_5V', '-': 'GND'}
parts['J1']['purpose'] = 'Verified regulated 5V input; no raw battery connection'
parts['S1'] = dict(ref='S1', value='Power switch', kind='SW',
                   pins={'1': 'VIN_5V', '2': '+5V'}, purpose='User-supplied power switch')
rev = dict(revision='0.2', date='2026-10-29',
           status='design reviewed; only manual CD4017 five-LED test user-confirmed',
           supply='regulated 5V only', parts=list(parts.values()))
OUT.mkdir(parents=True, exist_ok=True)
(DOC / 'full-v02-netlist.json').write_text(json.dumps(rev, indent=2) + '\n')

counter = 0
def uid():
    global counter
    counter += 1
    return f'gge{counter}'

class Sheet:
    def __init__(self, title, subtitle, n):
        self.title, self.n = title, n
        self.shape, self.ops, self.used = [], [], []
        self.text(35, 42, f'LED lighthouse / {title}', 25, True)
        self.text(35, 70, subtitle, 13)
        self.line([(30, 90), (1570, 90)], color=BLUE, width=2)
        self.text(35, 1058, 'Rev 0.2 / 2026-10-29 / Regulated 5V only / Complete circuit NOT hardware-tested', 12, color=RED)
        self.text(35, 1080, 'Same net name = direct electrical connection, including between sheets. Pin positions are functional, not a DIP top view.', 11)
        self.text(1510, 1080, f'{n} / 3', 12)

    def text(self, x, y, value, size=12, bold=False, color=INK, anchor='start', shapes=None):
        s = f'T~L~{x}~{y}~0~{color}~Arial~{size}pt~{"bold" if bold else ""}~~~comment~{value}~1~{anchor}~{uid()}~0~'
        (self.shape if shapes is None else shapes).append(s)
        self.ops.append(('text', x, y, value, size, bold, color, anchor))

    def line(self, pts, color=INK, width=1.4, electrical=False, shapes=None):
        cmd = 'W' if electrical else 'PL'
        flat = ' '.join(str(v) for p in pts for v in p)
        s = f'{cmd}~{flat}~{color}~{width}~0~none~{uid()}~0'
        (self.shape if shapes is None else shapes).append(s)
        self.ops.append(('line', pts, color, width))

    def rect(self, x, y, w, h, color=INK, fill='none', shapes=None):
        s = f'R~{x}~{y}~~~{w}~{h}~{color}~1.2~0~{fill}~{uid()}~0'
        (self.shape if shapes is None else shapes).append(s)
        self.ops.append(('rect', x, y, w, h, color, fill))

    def dot(self, x, y):
        self.shape.append(f'J~{x}~{y}~2.5~{WIRE}~{uid()}~0')
        self.ops.append(('dot', x, y))

    def wire(self, *pts): self.line(pts, WIRE, 1.6, True)

    def label(self, p, net, direction='right'):
        x, y = p
        dx, dy = {'right': (35, 0), 'left': (-35, 0), 'up': (0, -25), 'down': (0, 25)}[direction]
        ex, ey = x + dx, y + dy
        self.wire((x,y), (ex,ey))
        tx, ty = ex + (3 if dx >= 0 else -3), ey - 5
        anchor = 'end' if dx < 0 else 'start'
        self.shape.append(f'N~{ex}~{ey}~0~{BLUE}~{net}~{uid()}~{anchor}~{tx}~{ty}~Arial~10pt~0')
        self.ops.append(('text', tx, ty, net, 10, False, BLUE, anchor))

    def panel(self, x, y, w, h, title):
        self.rect(x,y,w,h,color='#b9c9d3')
        self.text(x+15,y+25,title,16,True,color=BLUE)

    def component(self, ref, x, y, kind=None, pinpos=None, value=None, names=None, w=130, h=160):
        p = parts[ref]
        value = value or p['value']
        kind = kind or p['kind']
        sub = []
        if kind in ('R','C','D','LED','LDR','SW'):
            keys = list(p['pins'])
            pinpos = pinpos or {keys[0]:(x,y-30,'up'),keys[1]:(x,y+30,'down')}
            if kind in ('R','LDR'):
                self.rect(x-7,y-15,14,30,shapes=sub)
                self.line([(x,y-30),(x,y-15)],shapes=sub)
                self.line([(x,y+15),(x,y+30)],shapes=sub)
                if kind=='LDR':
                    for yy in (y-14,y):
                        self.line([(x-28,yy-9),(x-12,yy+1),(x-16,yy-7)],shapes=sub)
            elif kind=='C':
                self.line([(x,y-30),(x,y-5)],shapes=sub)
                self.line([(x-12,y-5),(x+12,y-5)],shapes=sub)
                self.line([(x-12,y+5),(x+12,y+5)],shapes=sub)
                self.line([(x,y+5),(x,y+30)],shapes=sub)
                if '+' in p['pins']: self.text(x-20,y-10,'+',12,shapes=sub)
            elif kind=='LED':
                pinpos={'A':(x-30,y,'left'),'K':(x+30,y,'right')}
                self.line([(x-30,y),(x-10,y)],shapes=sub)
                self.line([(x-10,y-10),(x-10,y+10),(x+10,y),(x-10,y-10)],shapes=sub)
                self.line([(x+10,y-11),(x+10,y+11)],shapes=sub)
                self.line([(x+10,y),(x+30,y)],shapes=sub)
                for xx in (x-8,x+4):
                    self.line([(xx,y-16),(xx+12,y-29),(xx+11,y-23)],shapes=sub)
            elif kind=='D':
                self.line([(x,y-30),(x,y-10)],shapes=sub)
                self.line([(x-10,y-10),(x+10,y-10),(x,y+10),(x-10,y-10)],shapes=sub)
                self.line([(x-11,y+10),(x+11,y+10)],shapes=sub)
                self.line([(x,y+10),(x,y+30)],shapes=sub)
                self.text(x-22,y+17,'K',9,shapes=sub)
            elif kind=='SW':
                self.line([(x,y-30),(x,y-10),(x+14,y+7)],shapes=sub)
                self.line([(x,y+10),(x,y+30)],shapes=sub)
            if kind=='LED':
                self.text(x+35,y-7,ref,12,True,shapes=sub)
            else:
                self.text(x+20,y-4,ref,12,True,shapes=sub)
                self.text(x+20,y+13,value,12,shapes=sub)
        elif kind=='P':
            pinpos={'A':(x,y-40,'up'),'B':(x,y+40,'down'),'W':(x+45,y,'right')}
            self.rect(x-7,y-22,14,44,shapes=sub)
            self.line([(x,y-40),(x,y-22)],shapes=sub)
            self.line([(x,y+22),(x,y+40)],shapes=sub)
            self.line([(x+45,y),(x+8,y),(x+16,y-5)],shapes=sub)
            self.line([(x+8,y),(x+16,y+5)],shapes=sub)
            self.text(x-15,y-7,ref,12,True,anchor='end',shapes=sub)
            self.text(x-15,y+10,value,12,anchor='end',shapes=sub)
            self.text(x-16,y-30,'A',9,shapes=sub)
            self.text(x-16,y+34,'B',9,shapes=sub)
            self.text(x+31,y-7,'W',9,shapes=sub)
        elif kind=='Q':
            pinpos={'B':(x-40,y,'left'),'C':(x+20,y-40,'up'),'E':(x+20,y+40,'down')}
            self.line([(x-40,y),(x-8,y)],shapes=sub)
            self.line([(x-8,y-20),(x-8,y+20)],shapes=sub)
            self.line([(x-8,y-10),(x+20,y-27),(x+20,y-40)],shapes=sub)
            self.line([(x-8,y+10),(x+20,y+27),(x+20,y+40)],shapes=sub)
            self.line([(x+20,y+27),(x+10,y+15),(x+7,y+23),(x+20,y+27)],shapes=sub)
            self.text(x+40,y-5,ref,12,True,shapes=sub)
            self.text(x+40,y+13,value,12,shapes=sub)
            self.text(x-32,y-6,'B',9,shapes=sub)
            self.text(x+6,y-34,'C',9,shapes=sub)
            self.text(x+6,y+36,'E',9,shapes=sub)
        else:
            assert pinpos
            self.rect(x,y,w,h,fill='#f4f8fa',shapes=sub)
            self.text(x+w/2,y+24,ref,15,True,anchor='middle',shapes=sub)
            self.text(x+w/2,y+43,value,12,anchor='middle',shapes=sub)
            for k,(px,py,direction) in pinpos.items():
                name=(names or {}).get(k,k)
                if direction=='left':
                    self.line([(px,py),(x,py)],shapes=sub)
                    self.text(x+8,py+4,name,11,shapes=sub)
                    self.text(px+5,py-6,k,9,shapes=sub)
                elif direction=='right':
                    self.line([(x+w,py),(px,py)],shapes=sub)
                    self.text(x+w-8,py+4,name,11,anchor='end',shapes=sub)
                    self.text(px-5,py-6,k,9,anchor='end',shapes=sub)
                elif direction=='up':
                    self.line([(px,py),(px,y)],shapes=sub)
                    self.text(px+5,py+12,k,9,shapes=sub)
                else:
                    self.line([(px,y+h),(px,py)],shapes=sub)
                    self.text(px+5,py-4,k,9,shapes=sub)
        assert set(pinpos)==set(p['pins']), (ref,pinpos,p['pins'])
        for k,(px,py,direction) in pinpos.items():
            # Component graphics include the lead. Hidden pin path still has a
            # real connectable dot and a physical pin number for EDA netlists.
            sub.append(f'P~show~0~{k}~{px}~{py}~0~{uid()}~0^^{px}~{py}^^M {px} {py} h 0~#880000^^0~{px}~{py}~0~{k}~start~~7pt^^0~{px}~{py}~0~{k}~start~~7pt^^0~{px}~{py}^^0~M {px} {py}')
        # Explicit prefix/value text makes these usable schematic components.
        # No footprint is assigned: this is NOT ready to order as a PCB.
        sub.append(f'T~P~{x}~{y-50}~0~#000080~Arial~9pt~~~~comment~{ref}~0~start~{uid()}~0~')
        sub.append(f'T~N~{x}~{y-40}~0~#000080~Arial~9pt~~~~comment~{value}~0~start~{uid()}~0~')
        attr=f'package``nameAlias`Value`Value`{value}`spicePre`{ref[0]}`Contributor`Local verified-pin symbol'
        self.shape.append(f'LIB~{x}~{y}~{attr}~~0~{uid()}~~~0~~yes~yes#@$'+'#@$'.join(sub))
        self.used.append(ref)
        return {k:(px,py) for k,(px,py,_) in pinpos.items()}

    def passive(self,ref,x,y,top=True,bottom=True):
        pp=self.component(ref,x,y)
        keys=list(parts[ref]['pins'])
        if top: self.label(pp[keys[0]],parts[ref]['pins'][keys[0]],'up')
        if bottom: self.label(pp[keys[1]],parts[ref]['pins'][keys[1]],'down')
        return pp

    def data(self):
        return dict(head={'docType':'1','editorVersion':'6.5.55','newgId':True,
                          'c_para':{'Prefix Start':'1','Title':self.title}},
                    canvas=f'CA~{W}~{H}~#FFFFFF~yes~#EEEEEE~10~{W}~{H}~dot~10~pixel~5~0~0',
                    shape=self.shape, BBox={'x':0,'y':0,'width':W,'height':H},colors={})

s1=Sheet('01 Light sensor and power','LDR5516 photoresistor, TLC372CP dual comparator, daylight inhibit and common 5V power.',1)
s1.panel(30,110,670,280,'A / Power input and local bypass')
p=s1.component('J1',65,160,w=130,h=110,
    pinpos={'+':(215,210,'right'),'-':(215,245,'right')},value='5V input',names={'+':'+5V IN','-':'GND'})
s1.label(p['+'],'VIN_5V');s1.label(p['-'],'GND')
s1.passive('S1',350,220)
s1.passive('C5',525,220)
s1.passive('C3',65,330)
s1.passive('C13',300,330)
s1.text(470,335,'C3: close to U3 pins 8 / 4',11)
s1.text(470,355,'C13: close to PIR power',11)
s1.panel(730,110,840,280,'B / Supply notes and behaviour')
for i,t in enumerate([
    'Use regulated +5V from USB or a verified boost output.',
    'Do not connect a 3.7V cell to VIN_5V. All GND nodes join.',
    'Battery, charger and boost are external to this schematic.',
    'PIR connector: match VCC / OUT / GND labels on your board.',
    'Dark + a NEW motion edge starts one run; daylight cancels it.',
    'Shield the LDR from LED light. Adjust P1 at the desired dusk level.',
    'Only the manual five-LED CD4017 test is user-confirmed.',
    'New sensor / timer stages need the staged bench checks.'
]):s1.text(750,160+i*27,t,13)
s1.panel(30,410,960,620,'C / Darkness detector + RUN-to-IDLE comparator')
# LUX divider: two resistors cap the maximum input at half supply.
a=s1.passive('R1',100,520,bottom=False)
b=s1.passive('R2',100,690,top=False)
s1.wire(a['2'],(100,605),b['1']);s1.dot(100,605);s1.label((100,605),'LUX')
s1.passive('LDR1',285,690)
s1.passive('C14',480,690)
# Reference network and three-terminal threshold pot.
a=s1.passive('R4',310,520,bottom=False)
b=s1.passive('R5',520,520)
p=s1.component('P1',700,520)
s1.wire(a['2'],(310,585),(620,585),(620,450),(700,450),p['A'])
s1.label((620,450),'REF_TOP');s1.label(p['B'],'GND','down');s1.label(p['W'],'DARK_TH')
s1.passive('R3',700,690)
# Comparator functional symbol with exact DIP8 numbers.
up=s1.component('U3',750,780,w=170,h=210,
    pinpos={'1':(940,840,'right'),'2':(730,850,'left'),'3':(730,815,'left'),
            '4':(805,1010,'down'),'5':(730,920,'left'),'6':(730,955,'left'),
            '7':(940,930,'right'),'8':(850,760,'up')},
    names={'1':'OUT A','2':'IN A -','3':'IN A +','4':'GND','5':'IN B +','6':'IN B -','7':'OUT B','8':'VDD'})
for k in up:s1.label(up[k],parts['U3']['pins'][k], 'left' if k in ('2','3','5','6') else ('up' if k=='8' else ('down' if k=='4' else 'right')))
for ref,x,y in [('R7',100,840),('R8',300,840),('R9',100,970),('R10',300,970)]:s1.passive(ref,x,y)
s1.text(450,900,'LUX increases in darkness.',11)
s1.text(450,925,'A: DAY releases high in light.',11)
s1.text(450,950,'B: IDLE high when RUN is low.',11)
s1.panel(1020,410,550,620,'D / Daylight reset and startup delay')
s1.passive('R38',1100,510)
s1.passive('R39',1380,510)
p=s1.component('Q12',1280,720)
s1.label(p['B'],'QB12','left');s1.label(p['C'],'ARM','up');s1.label(p['E'],'GND','down')
s1.passive('R6',1100,720)
s1.passive('C6',1100,910)
s1.passive('R11',1380,910)
s1.text(1190,835,'Q12 pulls ARM low in daylight.',12)
s1.text(1190,860,'R6 + C6 delay arming at power-up.',12)
s1.text(1190,995,'R11 pulls comparator OUT B high.',11)

s2=Sheet('02 Motion pulse and timeout','A buffered PIR edge triggers a TLC555 one-shot. Busy lockout ignores new edges during RUN.',2)
s2.panel(30,110,1540,430,'E / PIR input and edge pulse (SB00312A-1 signal names; no physical pad order assumed)')
p=s2.component('J2',60,165,w=160,h=145,
    pinpos={'VCC':(240,225,'right'),'OUT':(240,260,'right'),'GND':(240,295,'right')})
for k in p:s2.label(p[k],parts['J2']['pins'][k])
for ref,x in [('R12',415),('R13',690),('R14',980),('R15',1250)]:s2.passive(ref,x,220)
q=s2.component('Q1',525,390)
for k,d in [('B','left'),('C','up'),('E','down')]:s2.label(q[k],parts['Q1']['pins'][k],d)
q=s2.component('Q2',1080,390)
for k,d in [('B','left'),('C','up'),('E','down')]:s2.label(q[k],parts['Q2']['pins'][k],d)
s2.text(70,480,'Q1 inverts PIR_OUT; Q2 restores a positive 5V edge. C11 couples only the change, not a held PIR HIGH.',13)
s2.text(70,510,'Confirm LOW at rest / HIGH on motion on the actual PIR. Startup/warmup motion pulses may start one run.',12)
s2.panel(30,565,750,465,'F / Short trigger + busy lockout')
for ref,x,y in [('C11',105,675),('R16',310,675),('R17',555,675),('D1',105,850),('R19',310,850),('C15',555,850)]:s2.passive(ref,x,y)
q=s2.component('Q3',180,955)
for k,d in [('B','left'),('C','up'),('E','down')]:s2.label(q[k],parts['Q3']['pins'][k],d)
q=s2.component('Q4',565,955)
for k,d in [('B','left'),('C','up'),('E','down')]:s2.label(q[k],parts['Q4']['pins'][k],d)
s2.panel(810,565,760,465,'G / Approximately one minute (TLC555IP)')
u=s2.component('U1',1130,735,w=175,h=220,
    pinpos={'1':(1190,975,'down'),'2':(1110,805,'left'),'3':(1325,805,'right'),
            '4':(1110,850,'left'),'5':(1325,900,'right'),'6':(1110,900,'left'),
            '7':(1325,850,'right'),'8':(1240,715,'up')},
    names={'1':'GND','2':'TRIG','3':'RUN','4':'RESET','5':'CTRL','6':'THRES','7':'DISCH','8':'VDD'})
for k in u:s2.label(u[k],parts['U1']['pins'][k], 'left' if k in ('2','4','6') else ('up' if k=='8' else ('down' if k=='1' else 'right')))
s2.passive('R18',875,680)
s2.passive('R20',1060,680)
p=s2.component('P3',1420,690)
s2.label(p['A'],'P3_A','up')
s2.wire(p['W'],(1480,690),(1480,750),(1420,750),p['B']);s2.dot(1420,750);s2.label((1420,750),'TIME','left')
s2.passive('R40',875,830)
s2.passive('C7',1010,970)
s2.passive('C8',1400,970)
s2.passive('C1',875,970)
s2.text(1130,620,'t = 1.1 x (220k + P3) x 100uF (nominal)',12,True)
s2.text(1130,645,'24-134 s nominal; P3 about 325k for 60 s.',12)
s2.text(1130,670,'Calibrate by stopwatch; capacitor leakage matters.',11)

s3=Sheet('03 Running LEDs and complete blanking','One TLC555 oscillator + CD4017 modulo-five sequencer. Q6 switches the common LED return.',3)
s3.panel(30,110,720,710,'H / Adjustable oscillator and inverted clock')
u=s3.component('U2',415,320,w=170,h=240,
    pinpos={'1':(480,580,'down'),'2':(395,400,'left'),'3':(605,400,'right'),
            '4':(395,360,'left'),'5':(605,510,'right'),'6':(395,450,'left'),
            '7':(395,510,'left'),'8':(530,300,'up')},
    names={'1':'GND','2':'TRIG','3':'OUT','4':'RESET','5':'CTRL','6':'THRES','7':'DISCH','8':'VDD'})
for k in u:s3.label(u[k],parts['U2']['pins'][k], 'left' if k in ('2','4','6','7') else ('up' if k=='8' else ('down' if k=='1' else 'right')))
s3.passive('R21',105,220)
s3.passive('R22',320,220)
p=s3.component('P2',600,220)
s3.label(p['A'],'P2_A','up')
s3.wire(p['W'],(670,220),(670,280),(600,280),p['B']);s3.dot(600,280);s3.label((600,280),'OSC','right')
s3.passive('C10',105,400)
s3.passive('C9',105,610)
s3.passive('C2',320,610)
s3.passive('R23',105,750)
s3.passive('R24',320,750)
q=s3.component('Q5',550,725)
for k,d in [('B','left'),('C','up'),('E','down')]:s3.label(q[k],parts['Q5']['pins'][k],d)
s3.panel(780,110,790,710,'I / CD4017 and five direct-drive white LEDs')
u=s3.component('U4',1010,270,w=190,h=430,
    pinpos={'1':(1220,590,'right'),'2':(1220,380,'right'),'3':(1220,330,'right'),
            '4':(1220,430,'right'),'5':(990,520,'left'),'6':(990,550,'left'),
            '7':(1220,480,'right'),'8':(1080,720,'down'),'9':(990,580,'left'),
            '10':(1220,530,'right'),'11':(990,610,'left'),'12':(990,640,'left'),
            '13':(990,430,'left'),'14':(990,330,'left'),'15':(990,380,'left'),
            '16':(1120,250,'up')},
    names={'1':'Q5 / RESET','2':'Q1','3':'Q0','4':'Q2','5':'Q6 NC','6':'Q7 NC','7':'Q3',
           '8':'GND','9':'Q8 NC','10':'Q4','11':'Q9 NC','12':'CARRY NC','13':'INHIBIT','14':'CLOCK','15':'RESET','16':'VDD'})
for k in ('13','14','15','16','8'):
    s3.label(u[k],parts['U4']['pins'][k], 'left' if k in ('13','14','15') else ('up' if k=='16' else 'down'))
for k in ('5','6','9','11','12'):
    x,y=u[k]
    s3.shape.append(f'O~{x}~{y}~{uid()}~M{x-4},{y-4} L{x+4},{y+4} M{x-4},{y+4} L{x+4},{y-4}~#999999~0')
    s3.line([(x-4,y-4),(x+4,y+4)],'#999999');s3.line([(x-4,y+4),(x+4,y-4)],'#999999')
# Horizontal LEDs keep each output line separate from the common cathode bus.
for i,k in enumerate(('3','2','4','7','10')):
    y=330+i*50
    led=s3.component(f'LED{i+1}',1390,y)
    s3.wire(u[k],led['A'])
    s3.wire(led['K'],(1510,y))
    s3.dot(1510,y)
s3.wire((1510,330),(1510,700));s3.label((1510,700),'LED_RETURN','down')
s3.label(u['1'],'STEP5')
for ref,x,y in [('R25',880,750),('C12',1250,750),('C4',1370,750)]:s3.passive(ref,x,y)
s3.panel(30,845,720,185,'J / Counter reset: idle OR sixth step')
s3.passive('D2',120,945)
s3.passive('D3',400,945)
s3.text(530,920,'D2: holds Q0 while idle.',12)
s3.text(530,950,'D3: Q5 returns to Q0.',12)
s3.text(530,980,'Do NOT retain direct pin 1-15 link.',11,True,color=RED)
s3.panel(780,845,790,185,'K / All LEDs off when RUN = LOW')
s3.passive('R28',880,945)
s3.passive('R26',1080,945)
q=s3.component('Q6',1320,945)
for k,d in [('B','left'),('C','up'),('E','down')]:s3.label(q[k],parts['Q6']['pins'][k],d)

sheets=[s1,s2,s3]
# Every component and every physical pin must exist exactly once in the CAD.
used=Counter(ref for s in sheets for ref in s.used)
assert set(used)==set(parts),(set(parts)-set(used),set(used)-set(parts))
assert all(n==1 for n in used.values()),used
project={'editorVersion':'6.5.55','docType':'5','title':'LED lighthouse v0.2',
         'description':'5V; motion in darkness; about one minute; schematic only, no PCB footprints',
         'schematics':[{'docType':'1','title':s.title,'description':'',
                        'dataStr':json.dumps(s.data(),separators=(',',':'))} for s in sheets]}
(OUT/'lighthouse-v02-project.json').write_text(json.dumps(project,indent=2)+'\n')
for i,s in enumerate(sheets,1):
    (OUT/f'lighthouse-v02-sheet-{i}.json').write_text(json.dumps(s.data(),indent=2)+'\n')

pw,ph=landscape(A3)
c=canvas.Canvas(str(PDF),pagesize=(pw,ph))
c.setTitle('LED lighthouse - complete circuit revision 0.2')
def col(hexcode):return colors.HexColor(hexcode)
for s in sheets:
    c.saveState();c.translate(10,ph-10);scale=min((pw-20)/W,(ph-20)/H);c.scale(scale,-scale)
    for op in s.ops:
        typ=op[0]
        if typ=='line':
            _,pts,color,width=op;c.setStrokeColor(col(color));c.setLineWidth(width)
            path=c.beginPath();path.moveTo(*pts[0])
            for p in pts[1:]:path.lineTo(*p)
            c.drawPath(path)
        elif typ=='rect':
            _,x,y,w,h,color,fill=op;c.setStrokeColor(col(color));c.setLineWidth(1.2)
            if fill!='none':c.setFillColor(col(fill))
            c.rect(x,y,w,h,stroke=1,fill=int(fill!='none'))
        elif typ=='dot':
            _,x,y=op;c.setFillColor(col(WIRE));c.circle(x,y,2.5,stroke=0,fill=1)
        elif typ=='text':
            _,x,y,txt,size,bold,color,anchor=op
            c.saveState();c.translate(x,y);c.scale(1,-1);c.setFillColor(col(color))
            c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
            {'start':c.drawString,'middle':c.drawCentredString,'end':c.drawRightString}[anchor](0,0,txt)
            c.restoreState()
    c.restoreState();c.showPage()
c.save()
# Human-readable pin table is generated from the exact same canonical nets.
lines=['# Complete circuit v0.2 - pin table','',
       '2026-10-29. Schematic-only design. Entire circuit not hardware-tested.',
       'References are inherited from v0.1; retired references are not reused.','',
       '| Part | Value | Connections | Function |','| --- | --- | --- | --- |']
for p in parts.values():
    lines.append('| '+ ' | '.join([p['ref'],p['value'], '; '.join(f'{k}={v}' for k,v in p['pins'].items()),p['purpose']])+' |')
(DOC/'full-v02-pin-table.md').write_text('\n'.join(lines)+'\n')
print(f'Created 3-sheet EasyEDA project and PDF; {len(parts)} components / {sum(len(p["pins"]) for p in parts.values())} pins.')
