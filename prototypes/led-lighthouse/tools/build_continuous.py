"""One continuous, fully wired drawing of the unchanged v0.2 circuit.

The router connects real component pins; it never substitutes net-name labels
for wires. Crossings have no junction and get visible bridge decoration.
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
canonical=json.loads((ROOT/'docs/full-v02-netlist.json').read_text())
parts={p['ref']:p for p in canonical['parts']}
INK, WIRE, BLUE, RED='#171717','#171717','#176597','#b52b2b'
counter=100000
# Reuse only drawing definitions, without running the old multi-sheet builder.
tree=ast.parse((ROOT/'tools/build_full_easyeda.py').read_text())
defs=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
exec(compile(ast.Module(body=defs,type_ignores=[]),'<drawing primitives>','exec'))
W,H,G=5400,2940,10
NW,NH=W//G+1,H//G+1

class Continuous(Sheet):
    def __init__(self):
        self.title='Complete lighthouse / all wires visible'
        self.n=1
        self.shape=[];self.ops=[];self.used=[]
        self.pins={};self.directions={};self.component_ops=[]
        self.text(110,65,'LED lighthouse - complete circuit on ONE sheet',36,True)
        self.text(110,105,'5V regulated / five white LEDs / motion in darkness / approximately one minute',22)
        self.text(110,2895,'Layout revision 0.3 / 2026-10-30. Electrical circuit unchanged from v0.2. Complete circuit NOT hardware-tested.',19,color=RED)
        self.text(110,2925,'Filled dot = connection. Arched bridge = crossing WITHOUT connection. All power and ground wires are drawn. Functional symbol positions; follow printed pin numbers.',17)
        self.text(3700,105,'RED: +5V   BLUE: GND   BLACK: signals',20,True)

    def component(self,ref,x,y,**kw):
        start=len(self.ops)
        points=super().component(ref,x,y,**kw)
        self.component_ops.extend(self.ops[start:])
        kind=kw.get('kind',parts[ref]['kind'])
        if kw.get('pinpos'):
            directions={k:v[2] for k,v in kw['pinpos'].items()}
        elif kind=='Q':directions={'B':'left','C':'up','E':'down'}
        elif kind=='P':directions={'A':'up','B':'down','W':'right'}
        elif kind=='LED':directions={'A':'left','K':'right'}
        else:directions=dict(zip(parts[ref]['pins'],('up','down')))
        for k,point in points.items():
            self.pins[ref,k]=point;self.directions[ref,k]=directions[k]
        return points

    def horizontal(self,ref,x,y):
        start=len(self.ops);p=parts[ref];kind=p['kind'];sub=[]
        if kind=='R':
            self.rect(x-18,y-8,36,16,shapes=sub)
            self.line([(x-40,y),(x-18,y)],shapes=sub)
            self.line([(x+18,y),(x+40,y)],shapes=sub)
        elif kind=='C':
            self.line([(x-40,y),(x-5,y)],shapes=sub)
            self.line([(x+5,y),(x+40,y)],shapes=sub)
            for xx in (x-5,x+5):self.line([(xx,y-14),(xx,y+14)],shapes=sub)
        elif kind=='D':
            self.line([(x-40,y),(x-12,y)],shapes=sub)
            self.line([(x-12,y-12),(x-12,y+12),(x+12,y),(x-12,y-12)],shapes=sub)
            self.line([(x+12,y-13),(x+12,y+13)],shapes=sub)
            self.line([(x+12,y),(x+40,y)],shapes=sub)
            self.text(x+15,y+26,'K',11,shapes=sub)
        elif kind=='SW':
            self.line([(x-40,y),(x-15,y),(x+10,y-18)],shapes=sub)
            self.line([(x+15,y),(x+40,y)],shapes=sub)
        else:raise ValueError(kind)
        self.text(x,y-36,ref,16,True,anchor='middle',shapes=sub)
        self.text(x,y-17,p['value'],14,anchor='middle',shapes=sub)
        keys=list(p['pins'])
        for k,px in zip(keys,(x-40,x+40)):
            sub.append(f'P~show~0~{k}~{px}~{y}~0~{uid()}~0^^{px}~{y}^^M {px} {y} h 0~#880000^^0~{px}~{y}~0~{k}~start~~7pt^^0~{px}~{y}~0~{k}~start~~7pt^^0~{px}~{y}^^0~M {px} {y}')
            self.pins[ref,k]=(px,y);self.directions[ref,k]='left' if px<x else 'right'
        sub.append(f'T~P~{x}~{y-50}~0~#000080~Arial~9pt~~~~comment~{ref}~0~start~{uid()}~0~')
        sub.append(f'T~N~{x}~{y-40}~0~#000080~Arial~9pt~~~~comment~{p["value"]}~0~start~{uid()}~0~')
        self.shape.append(f'LIB~{x}~{y}~package``nameAlias`Value`Value`{p["value"]}`~~0~{uid()}~~~0~~yes~yes#@$'+'#@$'.join(sub))
        self.used.append(ref);self.component_ops.extend(self.ops[start:])

    def note(self,x,y,txt):self.text(x,y,txt,20,True,color=BLUE)

s=Continuous()
# Power connector and switch.
s.component('J1',100,220,w=150,h=130,
    pinpos={'+':(280,280,'right'),'-':(280,320,'right')},
    value='Regulated 5V',names={'+':'+ IN','-':'- / GND'})
s.horizontal('S1',400,280)
s.note(110,440,'PIR motion input')
s.component('J2',100,500,w=160,h=190,
    pinpos={'VCC':(280,560,'right'),'OUT':(280,610,'right'),'GND':(280,660,'right')})
s.horizontal('R12',420,610)
s.component('Q1',580,610)
s.component('R13',600,440)
s.horizontal('R14',820,530)
s.component('Q2',1000,530)
s.component('R15',1020,360)
s.horizontal('C11',1200,490)
s.horizontal('R16',1380,490)
s.component('Q3',1580,490)
s.component('R17',1450,660)
s.component('D1',1310,660)
s.component('R18',1600,310)
s.component('Q4',1760,870)
s.horizontal('R19',1570,870)
s.component('C15',1690,1020)
s.note(1160,400,'Motion edge / short trigger')
s.note(1480,780,'Ignore motion while running')

# One-shot. Physical pin 6 and 7 are intentionally on the same side.
s.note(2110,370,'U1 - run duration')
s.component('U1',2160,500,w=220,h=360,
    pinpos={'1':(2240,880,'down'),'2':(2140,600,'left'),
            '3':(2400,600,'right'),'4':(2140,670,'left'),
            '5':(2360,880,'down'),'6':(2140,770,'left'),
            '7':(2140,710,'left'),'8':(2240,480,'up')},
    names={'1':'GND','2':'TRIG','3':'RUN','4':'RESET','5':'CTRL','6':'THRES','7':'DISCH','8':'VDD'})
s.component('R20',1950,340)
s.component('P3',1950,500)
s.horizontal('R40',1990,710)
s.component('C7',1950,940)
s.component('C8',2360,1020)
s.component('C1',2100,400)
s.text(1860,1080,'P3: duration; about 325k for 60 seconds. Calibrate on the bench.',16)

# Astable and clock inversion.
s.note(3090,370,'U2 - LED step speed')
s.component('U2',3150,500,w=220,h=360,
    pinpos={'1':(3240,880,'down'),'2':(3130,790,'left'),
            '3':(3390,600,'right'),'4':(3130,600,'left'),
            '5':(3310,880,'down'),'6':(3130,740,'left'),
            '7':(3130,670,'left'),'8':(3240,480,'up')},
    names={'1':'GND','2':'TRIG','3':'OUT','4':'RESET','5':'CTRL','6':'THRES','7':'DISCH','8':'VDD'})
s.component('R21',2840,340)
s.component('R22',2840,570)
s.component('P2',2840,740)
s.component('C10',2840,1000)
s.component('C9',3310,1020)
s.component('C2',3050,400)
s.horizontal('R23',3470,600)
s.component('Q5',3590,600)
s.component('R24',3610,380)
s.text(2760,1260,'P2: speed (about 0.21-1.59 seconds per step).',16)

# Counter, five direct-drive LEDs, reset OR and one common return switch.
s.note(3920,290,'CD4017 - five steps')
s.component('U4',3920,400,w=260,h=900,
    pinpos={'1':(4200,1140,'right'),'2':(4200,660,'right'),
            '3':(4200,540,'right'),'4':(4200,780,'right'),
            '5':(3900,900,'left'),'6':(3900,960,'left'),
            '7':(4200,900,'right'),'8':(4050,1320,'down'),
            '9':(3900,1020,'left'),'10':(4200,1020,'right'),
            '11':(3900,1080,'left'),'12':(3900,1140,'left'),
            '13':(3900,600,'left'),'14':(3900,500,'left'),
            '15':(3900,700,'left'),'16':(4050,380,'up')},
    names={'1':'Q5 (reset after 5)','2':'Q1','3':'Q0','4':'Q2','5':'Q6 NC','6':'Q7 NC',
           '7':'Q3','8':'GND','9':'Q8 NC','10':'Q4','11':'Q9 NC','12':'CARRY NC',
           '13':'INHIBIT','14':'CLOCK','15':'RESET','16':'VDD'})
for i,y in enumerate((540,660,780,900,1020),1):s.component(f'LED{i}',4600,y)
s.component('R28',5100,1600)
s.component('Q6',5080,1750)
s.horizontal('R26',4820,1750)
s.horizontal('D3',4350,1250)
s.horizontal('D2',3650,1400)
s.component('R25',3800,1580)
s.component('C12',4050,1580)
s.component('C4',4230,350)
s.text(4490,1860,'Q6 switches OFF every LED after timeout.',18,True)
s.text(4310,1320,'D3 replaces the direct pin 1 to pin 15 wire.',16,color=RED)

# Light detector and the second comparator (same physical DIP8 package).
s.note(160,1630,'LDR5516 - darkness detector')
s.component('R1',200,1740)
s.component('R2',200,1990)
s.component('LDR1',430,1990)
s.component('C14',660,1990)
s.component('R4',840,1690)
s.component('R5',840,1910)
s.component('P1',1000,1720)
s.horizontal('R3',1320,1720)
s.component('U3',1150,1840,w=250,h=330,
    pinpos={'1':(1420,1890,'right'),'2':(1130,1940,'left'),
            '3':(1130,1890,'left'),'4':(1270,2190,'down'),
            '5':(1130,2040,'left'),'6':(1130,2120,'left'),
            '7':(1420,2040,'right'),'8':(1270,1820,'up')},
    names={'1':'OUT A / DAY','2':'IN A -','3':'IN A +','4':'GND',
           '5':'IN B +','6':'IN B -','7':'OUT B / IDLE','8':'VDD'})
s.component('R38',1590,1740)
s.horizontal('R39',1740,1890)
s.component('Q12',1900,1890)
s.component('R6',1920,1690)
s.component('C6',2080,2000)
s.component('R7',960,2280)
s.component('R8',960,2460)
s.component('R9',430,2280)
s.component('R10',430,2460)
s.component('R11',1550,2170)
s.text(950,1610,'P1: darkness sensitivity',18,True)
s.text(160,2120,'Keep the LDR outside the LED beam.',18)
s.text(1660,2140,'Q12 inhibits U1 in daylight.',18)
s.text(1660,2170,'C6 provides a short startup reset delay.',16)
s.note(1810,2480,'Supply decoupling (place close to the corresponding IC/module)')
s.component('C5',2020,2620)
s.component('C13',2350,2620)
s.text(2500,2610,'C1: U1   C2: U2   C3: U3   C4: U4   C13: PIR',18)
s.component('C3',1620,2620)
assert Counter(s.used)==Counter(parts.keys()), (set(parts)-set(s.used))
assert len(s.pins)==185

def grid(p):
    # Pot wiper points are 5 units off a 10-unit grid. Extend their terminal
    # by 5 units before routing, without moving or renumbering the CAD pin.
    return round(p[0]/G),round(p[1]/G)

DIRS=((1,0),(-1,0),(0,1),(0,-1))
dirvec={'left':(-1,0),'right':(1,0),'up':(0,-1),'down':(0,1)}
blocked=bytearray(NW*NH)
def blockrect(x1,y1,x2,y2):
    for yy in range(max(0,int(y1//G)),min(NH-1,int(math.ceil(y2/G)))+1):
        for xx in range(max(0,int(x1//G)),min(NW-1,int(math.ceil(x2/G)))+1):blocked[yy*NW+xx]=1
for op in s.component_ops:
    if op[0]=='rect':
        _,x,y,w,h,_,_=op;blockrect(x-8,y-8,x+w+8,y+h+8)
    elif op[0]=='line':
        _,pts,_,_=op
        for a,b in zip(pts,pts[1:]):blockrect(min(a[0],b[0])-4,min(a[1],b[1])-4,max(a[0],b[0])+4,max(a[1],b[1])+4)
    elif op[0]=='text':
        _,x,y,txt,size,bold,_,anchor=op
        width=stringWidth(txt,'Helvetica-Bold' if bold else 'Helvetica',size)
        x1=x if anchor=='start' else x-width if anchor=='end' else x-width/2
        blockrect(x1-3,y-size-3,x1+width+3,y+3)
# Notes must not acquire wires through their text either.
for op in s.ops:
    if op[0]=='text' and op not in s.component_ops:
        _,x,y,txt,size,bold,_,anchor=op
        width=stringWidth(txt,'Helvetica-Bold' if bold else 'Helvetica',size)
        blockrect(x-5,y-size-5,x+width+5,y+5)

netpins=defaultdict(list);reserved=defaultdict(set);escape=defaultdict(set)
for key,p in s.pins.items():
    net=parts[key[0]]['pins'][key[1]];gp=grid(p)
    netpins[net].append(gp)
    dx,dy=dirvec[s.directions[key]]
    for t in range(5):
        q=(gp[0]+dx*t,gp[1]+dy*t)
        reserved[q].add(net);escape[net].add(q)

edges={};nodes=defaultdict(lambda:defaultdict(set));graphs=defaultdict(lambda:defaultdict(set))
def ek(a,b):return (a,b) if a<b else (b,a)
def install(net,path):
    for a,b in zip(path,path[1:]):
        e=ek(a,b)
        assert e not in edges or edges[e]==net,(net,edges.get(e),e)
        edges[e]=net;axis=0 if a[1]==b[1] else 1
        nodes[a][net].add(axis);nodes[b][net].add(axis)
        graphs[net][a].add(b);graphs[net][b].add(a)

def seed(net,physical):
    out=[]
    for aa,bb in zip(physical,physical[1:]):
        a,b=grid(aa),grid(bb);assert a[0]==b[0] or a[1]==b[1]
        dx=(b[0]>a[0])-(b[0]<a[0]);dy=(b[1]>a[1])-(b[1]<a[1])
        p=a
        while p!=b:out.append(p);p=(p[0]+dx,p[1]+dy)
    out.append(grid(physical[-1]));install(net,out)

# Continuous, drawn supply rails. No hidden power symbols or global labels.
seed('+5V',[(40,180),(5300,180)])
seed('+5V',[(40,180),(40,2550)])
seed('+5V',[(40,1550),(3180,1550)])
seed('+5V',[(40,2550),(2640,2550)])
seed('GND',[(90,320),(90,2780),(5300,2780)])
seed('GND',[(90,1180),(3690,1180)])
seed('GND',[(90,2520),(2100,2520)])
seed('VIN_5V',[(280,280),(360,280)])
seed('+5V',[(440,280),(450,280),(450,180)])
seed('GND',[(280,320),(90,320)])
# Explicit straight, easy-to-follow LED and return wires.
for i,y in enumerate((540,660,780,900,1020)):
    seed(f'STEP{i}',[(4200,y),(4570,y)])
    seed('LED_RETURN',[(4630,y),(5100,y)])
seed('LED_RETURN',[(5100,540),(5100,1570)])
seed('LED_SINK',[(5100,1630),(5100,1710)])
seed('GND',[(5100,1790),(5100,2780)])
# Short clock line and existing series parts.
seed('OSC_OUT',[(3390,600),(3430,600)])
seed('QB5',[(3510,600),(3550,600)])
seed('QB6',[(4860,1750),(5040,1750)])

def allowed(net,a,b,lastaxis):
    if not (2<=b[0]<NW-2 and 14<=b[1]<NH-9):return False
    if blocked[b[1]*NW+b[0]] and b not in escape[net]:return False
    if reserved.get(b,set())-{net}:return False
    if ek(a,b) in edges and edges[ek(a,b)]!=net:return False
    axis=0 if a[1]==b[1] else 1
    # Never bend, branch or stop on a foreign wire. Only perpendicular,
    # straight crossings through a degree-two foreign wire are permitted.
    for q in (a,b):
        for other,axes in nodes.get(q,{}).items():
            if other==net:continue
            if len(axes)!=1 or axis in axes or len(graphs[other][q])!=2:return False
            if q==a and lastaxis!=axis:return False
    return True

def route(net,start,goal):
    if start==goal:return [start]
    queue=[];serial=0;cost={(start,-1):0};parent={}
    heapq.heappush(queue,(abs(start[0]-goal[0])+abs(start[1]-goal[1]),0,serial,start,-1))
    seen=0
    while queue:
        _,g,_,p,axis=heapq.heappop(queue)
        if g!=cost.get((p,axis)):continue
        if p==goal:
            out=[p];state=(p,axis)
            while state in parent:
                state=parent[state];out.append(state[0])
            return out[::-1]
        seen+=1
        if seen>900000:break
        for dx,dy in DIRS:
            q=(p[0]+dx,p[1]+dy);naxis=0 if dx else 1
            if not allowed(net,p,q,axis):continue
            cross=bool(set(nodes.get(q,{}))-{net})
            step=1+(3 if axis not in (-1,naxis) else 0)+(14 if cross else 0)
            # Keep some white space alongside existing foreign wires.
            near=0
            for xx,yy in ((q[0]+1,q[1]),(q[0]-1,q[1]),(q[0],q[1]+1),(q[0],q[1]-1)):
                if set(nodes.get((xx,yy),{}))-{net}:near+=1
            ng=g+step+near*.35
            state=(q,naxis)
            if ng>=cost.get(state,1e30):continue
            cost[state]=ng;parent[state]=(p,axis);serial+=1
            h=abs(q[0]-goal[0])+abs(q[1]-goal[1])
            heapq.heappush(queue,(ng+h,ng,serial,q,naxis))
    raise RuntimeError(f'Cannot route {net}: {start} -> {goal} ({seen} states)')

def targets(net):
    return [p for p in graphs[net] if not (set(nodes[p])-{net}) and
            (not blocked[p[1]*NW+p[0]] or p in escape[net])]

priority=[n for n in netpins if n not in ('+5V','GND') and not n.startswith('NC_')]
priority.sort(key=lambda n:max(p[0] for p in netpins[n])-min(p[0] for p in netpins[n])+max(p[1] for p in netpins[n])-min(p[1] for p in netpins[n]))
priority+=['+5V','GND']
for net in priority:
    pending=set(netpins[net])-set(graphs[net])
    if not graphs[net] and pending:
        first=min(pending);pending.remove(first);graphs[net][first]
    while pending:
        ts=targets(net)
        candidates=sorted((abs(p[0]-t[0])+abs(p[1]-t[1]),p,t) for p in pending for t in ts)
        error=None
        # A blocked closest approach can be bypassed by joining another point.
        attempted=set()
        for _,p,t in candidates:
            if p in attempted:continue
            try:
                path=route(net,p,t);install(net,path);pending.remove(p)
                break
            except RuntimeError as exc:
                attempted.add(p);error=exc
        else:raise error
    print(f'Routed {net}: {len(netpins[net])} pins',flush=True)

wire_shapes=[];segments=[]
netcolor=lambda net:RED if net=='+5V' else BLUE if net=='GND' else INK
for net,graph in graphs.items():
    visited=set()
    for p,neighbours in graph.items():
        for q in neighbours:
            if ek(p,q) in visited:continue
            axis=0 if p[1]==q[1] else 1
            # Grow the maximal straight run in both directions, through a
            # same-net junction as well; dots are added independently below.
            run={p,q};todo=[p,q]
            while todo:
                a=todo.pop()
                for b in graph[a]:
                    if (a[1]==b[1])!=(axis==0):continue
                    visited.add(ek(a,b))
                    if b not in run:run.add(b);todo.append(b)
            a=min(run);b=max(run)
            pa=(a[0]*G,a[1]*G);pb=(b[0]*G,b[1]*G)
            wire_shapes.append(f'W~{pa[0]} {pa[1]} {pb[0]} {pb[1]}~{netcolor(net)}~2~0~none~{uid()}~0')
            segments.append((net,pa,pb))

# Wires behind the symbols. Junctions are explicit and never at a crossing.
component_shapes=s.shape[:]
s.shape=wire_shapes+component_shapes
wire_ops=[('line',[a,b],netcolor(net),2) for net,a,b in segments]
component_ops=s.ops[:];s.ops=wire_ops+component_ops
junctions=0;crossings=0
for net,graph in graphs.items():
    for p,neighbours in graph.items():
        if len(neighbours)>=3:
            assert not (set(nodes[p])-{net}),('junction on crossing',p)
            x,y=p[0]*G,p[1]*G
            s.shape.append(f'J~{x}~{y}~3~{netcolor(net)}~{uid()}~0')
            s.ops.append(('dotcolor',x,y,netcolor(net)));junctions+=1
for p,owners in nodes.items():
    if len(owners)!=2:continue
    horizontal=[net for net,axes in owners.items() if axes=={0}]
    vertical=[net for net,axes in owners.items() if axes=={1}]
    assert len(horizontal)==len(vertical)==1,(p,owners)
    x,y=p[0]*G,p[1]*G
    # Cosmetic bridge: underlying continuous W primitives preserve actual CAD
    # connectivity. The white gap + restored vertical + arc make it readable.
    s.rect(x-7,y-3,14,6,color='#FFFFFF',fill='#FFFFFF')
    s.line([(x,y-5),(x,y+5)],color=netcolor(vertical[0]),width=2)
    path=f'M {x-8} {y} C {x-8} {y-12} {x+8} {y-12} {x+8} {y}'
    s.shape.append(f'PT~{path}~#FFFFFF~6~0~none~{uid()}~0')
    s.shape.append(f'PT~{path}~{netcolor(horizontal[0])}~2~0~none~{uid()}~0')
    s.ops.append(('bridge',x,y,netcolor(horizontal[0])));crossings+=1

for ref,k in s.pins:
    if parts[ref]['pins'][k].startswith('NC_'):
        x,y=s.pins[ref,k]
        s.shape.append(f'O~{x}~{y}~{uid()}~M{x-4},{y-4} L{x+4},{y+4} M{x-4},{y+4} L{x+4},{y-4}~#777777~0')
        s.line([(x-4,y-4),(x+4,y+4)],'#777777');s.line([(x-4,y+4),(x+4,y-4)],'#777777')

# Wiper coordinates are the only non-grid pins. Their short extension belongs
# to the same electrical net and is drawn explicitly (not a label).
for key,p in s.pins.items():
    gp=grid(p);snapped=(gp[0]*G,gp[1]*G)
    if p!=snapped:
        net=parts[key[0]]['pins'][key[1]]
        s.shape.append(f'W~{p[0]} {p[1]} {snapped[0]} {snapped[1]}~{netcolor(net)}~2~0~none~{uid()}~0')
        s.ops.append(('line',[p,snapped],netcolor(net),2))

data={'head':{'docType':'1','editorVersion':'6.5.61','newgId':True,
              'c_para':{'Title':'Lighthouse / one continuous drawing','Prefix Start':'1'}},
      'canvas':f'CA~{W}~{H}~#FFFFFF~yes~#EEEEEE~10~{W}~{H}~dot~10~pixel~5~0~0',
      'shape':s.shape,'BBox':{'x':0,'y':0,'width':W,'height':H},'colors':{}}
out=ROOT/'hardware/easyeda/lighthouse-continuous.json'
out.write_text(json.dumps(data,indent=2)+'\n')

pw=landscape(A0)[0]
ph=(pw-24)*H/W+24  # Wide single-sheet poster; no unused presentation margin.
c=canvas.Canvas(str(ROOT/'output/pdf/lighthouse-continuous.pdf'),pagesize=(pw,ph))
c.setTitle('LED lighthouse - one continuous fully wired schematic')
c.saveState();c.translate(12,ph-12);scale=min((pw-24)/W,(ph-24)/H);c.scale(scale,-scale)
def color(h):return colors.HexColor(h)
for op in s.ops:
    typ=op[0]
    if typ=='line':
        _,pts,co,width=op;c.setStrokeColor(color(co));c.setLineWidth(width)
        p=c.beginPath();p.moveTo(*pts[0])
        for point in pts[1:]:p.lineTo(*point)
        c.drawPath(p)
    elif typ=='rect':
        _,x,y,w,h,co,fill=op;c.setStrokeColor(color(co));c.setLineWidth(1.2)
        if fill!='none':c.setFillColor(color(fill))
        c.rect(x,y,w,h,stroke=1,fill=int(fill!='none'))
    elif typ=='dotcolor':
        _,x,y,co=op;c.setFillColor(color(co));c.circle(x,y,3,fill=1,stroke=0)
    elif typ=='text':
        _,x,y,txt,size,bold,co,anchor=op
        c.saveState();c.translate(x,y);c.scale(1,-1);c.setFillColor(color(co));c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
        {'start':c.drawString,'end':c.drawRightString,'middle':c.drawCentredString}[anchor](0,0,txt);c.restoreState()
    elif typ=='bridge':
        _,x,y,co=op;p=c.beginPath();p.moveTo(x-8,y);p.curveTo(x-8,y-12,x+8,y-12,x+8,y)
        c.setStrokeColor(colors.white);c.setLineWidth(6);c.drawPath(p)
        c.setStrokeColor(color(co));c.setLineWidth(2);c.drawPath(p)
c.restoreState();c.showPage();c.save()
print(f'Created one-sheet CAD/PDF: {len(parts)} parts, {len(s.pins)} pins, {junctions} junctions, {crossings} bridged crossings.')
