"""One-sheet, fully wired five-LED experiment. References are local to stage 1."""
from pathlib import Path
from reportlab.graphics.shapes import Drawing, Group, Line, Rect, Circle, String, Polygon
from reportlab.graphics import renderPDF, renderSVG
from reportlab.lib import colors

ROOT=Path(__file__).resolve().parents[1]
PDF=ROOT/'output/pdf/stage1-five-leds.pdf'
SVG=ROOT/'docs/stage1-five-leds.svg'
PNG=ROOT/'docs/stage1-five-leds.png'
W,H=1190,842
d=Drawing(W,H)
INK=colors.HexColor('#173142')
POWER=colors.HexColor('#ad3232')
GROUND=colors.HexColor('#176d8b')
LIGHT=colors.HexColor('#f0f6f8')

def text(x,y,s,size=13,bold=False,color=INK,anchor='start',angle=0):
    item=String(0 if angle else x,0 if angle else y,s,fontName='Helvetica-Bold' if bold else 'Helvetica',fontSize=size,fillColor=color,textAnchor=anchor)
    if angle:
        import math
        a=math.radians(angle)
        g=Group(item);g.transform=(math.cos(a),math.sin(a),-math.sin(a),math.cos(a),x,y);d.add(g)
    else:d.add(item)

def wire(*points,color=INK):
    for a,b in zip(points,points[1:]):d.add(Line(*a,*b,strokeColor=color,strokeWidth=1.7))

def dot(x,y,color=INK):d.add(Circle(x,y,3,fillColor=color,strokeColor=color))

def vr(x,y,ref,value):
    wire((x,y+25),(x,y+11));d.add(Rect(x-7,y-11,14,22,strokeColor=INK,strokeWidth=1.5,fillColor=colors.white));wire((x,y-11),(x,y-25))
    text(x+17,y+3,ref+' '+value,13,True)

def hr(x,y,ref,value):
    wire((x-40,y),(x-20,y));d.add(Rect(x-20,y-6,40,12,strokeColor=INK,strokeWidth=1.5,fillColor=colors.white));wire((x+20,y),(x+40,y))
    text(x,y+15,ref+' '+value,12,True,anchor='middle')

def capacitor(x,y,ref,value,polarized=False,rotate_label=False):
    wire((x,y+20),(x,y+4));wire((x-10,y+4),(x+10,y+4));wire((x-10,y-4),(x+10,y-4));wire((x,y-4),(x,y-20))
    if polarized:text(x-18,y+12,'+',14,True)
    if rotate_label:text(x-18 if x<500 else x+25,y-42,ref+' '+value,12,angle=90)
    else:text(x+15,y+2,ref+' '+value,12)

def pin_left(x,y,n,name):
    wire((x-15,y),(x,y));text(x-7,y+7,str(n),12,True,anchor='end');text(x+10,y-4,name,12)

def pin_right(x,y,n,name):
    wire((x,y),(x+15,y));text(x+7,y+7,str(n),12,True);text(x-10,y-4,name,12,anchor='end')

def pin_top(x,y,n,name):
    wire((x,y),(x,y+15));text(x-6,y+6,str(n),12,True,anchor='end');text(x,y-18,name,11,anchor='middle')

def pin_bottom(x,y,n,name):
    wire((x,y),(x,y-15));text(x-7,y-13,str(n),12,True,anchor='end');text(x,y+13,name,11,anchor='middle')

d.add(Rect(0,832,W,10,fillColor=GROUND,strokeColor=GROUND))
text(50,793,'Stage 1 / Five running LEDs',28,True)
text(50,766,'Complete circuit on one sheet: TLC555 + speed trim pot + CD4017 + five LEDs. No sensors or transistors.',14)

# Common supply rails. The two bypass capacitors have separate uninterrupted
# routes to the ground bus, avoiding signal/ground crossings in this drawing.
wire((50,720),(1135,720),color=POWER)
wire((50,210),(1135,210),color=GROUND)
text(500,735,'+5V DC  (regulated USB / verified 5V boost output)',15,True,POWER)
text(500,190,'GND / supply negative - all blue ground connections are common',13,True,GROUND)
for x,ref in [(50,'C1'),(1135,'C2')]:
    wire((x,720),(x,670),color=POWER)
    capacitor(x,650,ref,'100n',rotate_label=True)
    wire((x,630),(x,210),color=GROUND)
    dot(x,720,POWER);dot(x,210,GROUND)

# TLC555 functional symbol. Pin numbers, rather than symbol position, identify
# the physical DIP terminals.
d.add(Rect(290,325,150,275,fillColor=LIGHT,strokeColor=INK,strokeWidth=1.8))
text(385,500,'U1',20,True,anchor='middle')
text(365,477,'TLC555IP',16,True,anchor='middle')
for y,n,name in [(520,7,'DISCH'),(460,6,'THRES'),(420,2,'TRIG'),(360,5,'CTRL')]:pin_left(290,y,n,name)
pin_right(440,540,3,'OUT')
pin_top(330,600,8,'VDD');pin_top(390,600,4,'RESET')
pin_bottom(350,325,1,'GND')
for x in [330,390]:
    wire((x,615),(x,720),color=POWER);dot(x,720,POWER)
wire((350,310),(350,210),color=GROUND);dot(350,210,GROUND)

# Conventional astable: RA=10k; RB=10k+P1; C3=10u.
wire((120,720),(120,675),color=POWER);dot(120,720,POWER)
vr(120,650,'R1','10k')
wire((120,625),(120,520),(275,520));dot(120,520)
wire((120,520),(120,495));vr(120,470,'R2','10k')
wire((120,445),(120,425))
d.add(Rect(113,385,14,40,fillColor=colors.white,strokeColor=INK,strokeWidth=1.5))
text(145,439,'P1 100k',13,True)
wire((120,385),(120,340),(120,300));dot(120,350);dot(120,340)
# Wiper is visibly strapped to the lower outer terminal.
wire((160,400),(127,400));wire((127,400),(135,404));wire((127,400),(135,396))
wire((160,400),(160,350),(120,350))
text(171,395,'W',12,True);text(83,419,'A',11);text(83,378,'B',11)
wire((120,340),(210,340),(210,460),(275,460));dot(210,420)
wire((210,420),(275,420))
capacitor(120,280,'C3','10u',True)
wire((120,260),(120,210),color=GROUND);dot(120,210,GROUND)
wire((275,360),(255,360),(255,300));capacitor(255,280,'C4','10n')
wire((255,260),(255,210),color=GROUND);dot(255,210,GROUND)

# Clock wire joins the two ICs directly.
wire((455,540),(575,540))
text(510,556,'CLOCK',12,True,anchor='middle')

# CD4017 functional symbol, with reset brought out at the bottom to make the
# modulo-five feedback route completely crossing-free.
d.add(Rect(590,330,200,270,fillColor=LIGHT,strokeColor=INK,strokeWidth=1.8))
text(665,505,'U2',20,True,anchor='middle');text(675,475,'CD4017BE',16,True,anchor='middle')
pin_left(590,540,14,'CLOCK');pin_left(590,390,13,'INHIBIT')
pin_top(700,600,16,'VDD');pin_bottom(640,330,8,'GND');pin_bottom(740,330,15,'RESET')
wire((700,615),(700,720),color=POWER);dot(700,720,POWER)
wire((640,315),(640,210),color=GROUND);dot(640,210,GROUND)
wire((575,390),(550,390),(550,210),color=GROUND);dot(550,210,GROUND)

# Individual LED current limiters keep the direct-drive experiment well below
# the CD4017 5V output-current test point (0.36mA at VOH=4.6V, 25C).
for i,(pin,y) in enumerate([(3,570),(2,530),(4,490),(7,450),(10,410)],1):
    pin_right(790,y,pin,f'Q{i-1}')
    wire((805,y),(830,y));hr(870,y,f'R{i+2}','10k');wire((910,y),(980,y))
    d.add(Polygon([980,y+8,980,y-8,995,y],fillColor=colors.white,strokeColor=INK,strokeWidth=1.5))
    wire((999,y-11),(999,y+11));wire((999,y),(1115,y));dot(1115,y)
    text(1034,y+12,f'LED{i}',12,True)
    # Small outward arrows identify a light-emitting diode.
    for dx,dy in [(0,0),(9,-5)]:
        wire((989+dx,y+13+dy),(1000+dx,y+24+dy));wire((1000+dx,y+24+dy),(994+dx,y+22+dy));wire((1000+dx,y+24+dy),(998+dx,y+18+dy))
    if i==1:text(962,y-18,'A',10);text(1004,y-18,'K',10)
wire((1115,570),(1115,210),color=GROUND);dot(1115,210,GROUND)
pin_right(790,370,1,'Q5')
wire((805,370),(825,370),(825,265),(740,265),(740,315))
text(845,290,'Q5 -> RESET',12,True)
text(845,271,'After LED5, return to LED1.',11)

# Short, large-print assembly notes on the same page.
text(50,156,'P1 sets the LED step interval: approximately 0.2-1.6 seconds. This first test runs continuously.',14,True)
text(50,131,'All five LED resistors are 10k: deliberately low current and low brightness. C3 positive is at the top.',13)
text(50,107,'Dots mean joined wires. Pin positions are functional: use the pin NUMBERS on the actual DIP packages.',13)
text(50,83,'Leave CD4017 pins 5, 6, 9, 11 and 12 open. Startup may begin mid-sequence; then it settles into five steps.',13)
text(50,49,'Stage 1 v0.1 | 2026-10-22 | Datasheet-checked design; not yet hardware-tested.',10)
text(50,31,'Sources: TI TLC555 SLFS043K and TI CD4017B SCHS027C. Place C1 and C2 next to their respective ICs.',10)

PDF.parent.mkdir(parents=True,exist_ok=True)
renderPDF.drawToFile(d,str(PDF))
renderSVG.drawToFile(d,str(SVG))
# PDF rasterization is used for a matching inline preview and visual QA.
import pypdfium2 as pdfium
pdfium.PdfDocument(str(PDF))[0].render(scale=1.8).to_pil().save(PNG)
print(PDF)
print(SVG)
print(PNG)
