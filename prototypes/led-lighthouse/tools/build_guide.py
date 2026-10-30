"""Build the vector PDF and wiring reference for the LED lighthouse prototype.

Use the Codex bundled Python runtime (reportlab, pypdf, pypdfium2).
No downloaded datasheets or temporary renders are stored in this prototype.
"""
from pathlib import Path
from collections import Counter, defaultdict
import json
import math

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/lighthouse-wiring-guide.pdf"
DATE = "2026-10-21"
PARTS = []

def part(ref, value, pins, purpose, kind="R"):
    PARTS.append(dict(ref=ref, value=value, pins=pins, purpose=purpose, kind=kind))

def r(n, value, a, b, purpose):
    part(f"R{n}", value, {"1":a,"2":b}, purpose)

def cap(n, value, a, b, purpose, polarized=False):
    part(f"C{n}", value, {"+" if polarized else "1":a,"-" if polarized else "2":b}, purpose, "C")

def q(n, c, b, e, purpose):
    part(f"Q{n}", "BC547B", {"C":c,"B":b,"E":e}, purpose, "Q")

def diode(n, a, k, purpose):
    part(f"D{n}", "1N4148", {"A":a,"K":k}, purpose, "D")

part("U1", "TLC555IP", {"1":"GND","2":"TRIG","3":"RUN","4":"ARM","5":"CTRL1","6":"TIME","7":"DISCH1","8":"+5V"}, "One-shot timer", "U")
part("U2", "TLC555IP", {"1":"GND","2":"OSC","3":"OSC_OUT","4":"RUN","5":"CTRL2","6":"OSC","7":"DISCH2","8":"+5V"}, "LED step oscillator", "U")
part("U3", "TLC372CP", {"1":"DAY","2":"LUX","3":"DARK_TH","4":"GND","5":"FIX_REF","6":"RUN_HALF","7":"IDLE","8":"+5V"}, "Darkness comparator and RUN inverter", "U")
part("U4", "CD4017BE", {"1":"STEP5","2":"STEP1","3":"STEP0","4":"STEP2","5":"NC_5","6":"NC_6","7":"STEP3","8":"GND","9":"NC_9","10":"STEP4","11":"NC_11","12":"NC_12","13":"GND","14":"CLOCK","15":"COUNT_RESET","16":"+5V"}, "Modulo-five LED sequencer", "U")

r(1,"100k","+5V","LUX","LDR divider top")
r(2,"100k","LUX","GND","Limit LUX to safe comparator input range")
r(3,"1M","DAY","DARK_TH","Darkness hysteresis")
r(4,"47k","+5V","REF_TOP","Threshold range divider top")
r(5,"47k","REF_TOP","GND","Threshold range divider bottom")
part("P1","100k",{"A":"REF_TOP","W":"DARK_TH","B":"GND"},"Darkness sensitivity (three terminals)","P")
r(6,"10k","+5V","ARM","Reset pull-up / startup delay")
r(7,"100k","RUN","RUN_HALF","RUN divider top")
r(8,"100k","RUN_HALF","GND","RUN divider bottom")
r(9,"47k","+5V","FIX_REF","IDLE reference top")
r(10,"15k","FIX_REF","GND","IDLE reference bottom")
r(11,"10k","+5V","IDLE","Open-drain pull-up")
r(12,"47k","PIR_OUT","QB1","PIR input current limit")
r(13,"47k","+5V","INV","First inverter pull-up")
r(14,"47k","INV","QB2","Buffer base resistor")
r(15,"47k","+5V","MOTION_BUF","Second inverter pull-up")
r(16,"10k","EDGE","QB3","Pulse base current limit")
r(17,"100k","QB3","GND","Pulse reset / discharge")
r(18,"10k","+5V","TRIG","Timer trigger pull-up")
r(19,"47k","RUN","QB4","Lockout base resistor")
r(20,"220k","+5V","P3_A","Minimum timer resistance")
part("P3","1M",{"A":"P3_A","W":"TIME","B":"TIME"},"Duration rheostat; strap W to B","P")
r(21,"10k","+5V","DISCH2","Astable RA")
r(22,"10k","DISCH2","P2_A","Minimum astable RB")
part("P2","100k",{"A":"P2_A","W":"OSC","B":"OSC"},"Step-speed rheostat; strap W to B","P")
r(23,"47k","OSC_OUT","QB5","Clock inverter base resistor")
r(24,"10k","+5V","CLOCK","Clock pull-up")
r(25,"100k","COUNT_RESET","GND","Counter reset pull-down")
r(26,"1k","RUN","QB6","LED supply buffer base resistor")
r(27,"100k","LED_POWER","GND","Discharge switched LED rail")
for i in range(5):
    r(28+i,"1k","LED_POWER",f"LED_A{i+1}",f"LED {i+1} current limit")
    r(33+i,"22k",f"STEP{i}",f"QB{i+7}",f"LED {i+1} base resistor")
    part(f"LED{i+1}","White LED",{"A":f"LED_A{i+1}","K":f"LED_K{i+1}"},f"Lighthouse position {i+1}","LED")
    q(i+7,f"LED_K{i+1}",f"QB{i+7}","GND",f"LED {i+1} sink")
r(38,"100k","+5V","DAY","Day comparator pull-up")
r(39,"47k","DAY","QB12","Reset transistor base current limit")
r(40,"100","TIME","DISCH1","Limit timing-capacitor discharge current")
q(1,"INV","QB1","GND","PIR input inverter")
q(2,"MOTION_BUF","QB2","GND","Restore positive motion edge")
q(3,"TRIG","QB3","GND","Short active-low trigger pulse")
q(4,"QB3","QB4","GND","Ignore motion edges while RUN is high")
q(5,"CLOCK","QB5","GND","Clock inversion: first step starts at LED1")
q(6,"+5V","QB6","LED_POWER","NPN emitter follower: LED rail on only during RUN")
q(12,"ARM","QB12","GND","Daylight resets timer; safely discharges C6")
diode(1,"GND","QB3","Clamp reverse base voltage on falling motion edge")
diode(2,"IDLE","COUNT_RESET","Reset counter while idle")
diode(3,"STEP5","COUNT_RESET","Return to LED1 after LED5")
for n,u in [(1,"U1"),(2,"U2"),(3,"U3"),(4,"U4")]:
    cap(n,"100n","+5V","GND",f"Local bypass at {u}")
cap(5,"100u / 16V","+5V","GND","Bulk supply capacitor",True)
cap(6,"100u / 16V","ARM","GND","Startup reset delay",True)
cap(7,"100u / 16V","TIME","GND","One-shot timing capacitor; leakage must be checked",True)
cap(8,"10n","CTRL1","GND","U1 control bypass")
cap(9,"10n","CTRL2","GND","U2 control bypass")
cap(10,"10u / 16V","OSC","GND","Step oscillator timing",True)
cap(11,"100n","MOTION_BUF","EDGE","Motion edge coupling")
cap(12,"10n","COUNT_RESET","GND","Stretch self-reset pulse")
cap(13,"100n","+5V","GND","Bypass near PIR supply")
cap(14,"100n","LUX","GND","Filter light sensor noise")
cap(15,"10u / 16V","QB4","GND","Hold busy lockout briefly after RUN falls",True)
part("LDR1","LDR5516",{"1":"LUX","2":"GND"},"Keep out of LED beam; no polarity","LDR")
part("J1","5V input",{"+":"+5V","-":"GND"},"From verified boost output through S1","J")
part("J2","SB00312A-1",{"VCC":"+5V","OUT":"PIR_OUT","GND":"GND"},"Signal names only; physical pad order not assumed","J")

BYREF={p["ref"]:p for p in PARTS}
NETS=defaultdict(list)
for p in PARTS:
    for pin,net in p["pins"].items(): NETS[net].append(f'{p["ref"]}.{pin}')
assert len(BYREF)==len(PARTS)
assert len([p for p in PARTS if p["kind"]=="Q"])==12
assert all(len(NETS[n])>=2 for n in NETS if not n.startswith("NC_"))
assert all(len(NETS[n])==1 for n in NETS if n.startswith("NC_"))
assert BYREF["U3"]["pins"]["8"]=="+5V" and BYREF["U3"]["pins"]["4"]=="GND"
assert BYREF["U4"]["pins"]["13"]=="GND"
assert not any(p["kind"]=="LED" and "+5V" in p["pins"].values() for p in PARTS)

SOURCES=[
 ("S1","TI TLC555, SLFS043K, Jan 2026, pin functions / mono- and astable operation","https://www.ti.com/lit/ds/symlink/tlc555.pdf"),
 ("S2","TI TLC372, SLCS114F, Jun 2025, p3 pinout / p4 common-mode range","https://www.ti.com/lit/ds/symlink/tlc372.pdf"),
 ("S3","TI CD4017B, SCHS027C, p1 pinout / 5V operation / reset","https://www.ti.com/lit/ds/symlink/cd4017b.pdf"),
 ("S4","Semtech BC547B, GME 210-062, manufacturer datasheets linked by retailer","https://www.gme.cz/v/1489324/semtech-bc547b-ammo-bipolarni-tranzistor"),
 ("S5","Semtech manufacturer datasheet mirror: default C-B-E; special pinouts can exist","https://datasheet.datasheetarchive.com/originals/library/Datasheet-024/DSA00417422.pdf"),
 ("S6","GME SB00312A-1, 775-183: 2.7-12V, <0.1mA, 2s; pad order not verified","https://www.gme.cz/v/1508403/sb00312a-1-pir-modul"),
 ("S7","GME LDR5516, 520-084: light 5-10k, dark 0.5M","https://www.gme.cz/v/1495847/ldr5516-fotorezistor"),
 ("S8","LaskaKit LA122076 charger + 5V boost; protected battery recommended","https://www.laskakit.cz/mikro-nabijecka-boost-pro-usb-powerbank-5v--usb-c/"),
]

W,H=landscape(A4)
INK=colors.HexColor("#182d3b"); TEAL=colors.HexColor("#087f8c"); LIGHT=colors.HexColor("#eef5f7")
GREY=colors.HexColor("#596b77"); ORANGE=colors.HexColor("#b35f12")
c=canvas.Canvas(str(OUT), pagesize=(W,H))
c.setTitle("LED Lighthouse - Wiring and commissioning guide v0.1")
c.setAuthor("ESP Incubator")
page=0
style=ParagraphStyle("body",fontName="Helvetica",fontSize=10,leading=14,textColor=INK)

def txt(x,y,s,size=10,bold=False,color=INK):
    c.setFillColor(color); c.setFont("Helvetica-Bold" if bold else "Helvetica",size); c.drawString(x,y,s)

def para(x,y,s,width=750,size=10):
    st=ParagraphStyle("p",parent=style,fontSize=size,leading=size*1.35)
    p=Paragraph(s,st); _,h=p.wrap(width,500); p.drawOn(c,x,y-h); return y-h-9

def new(title, subtitle):
    global page
    if page: c.showPage()
    page+=1
    c.setFillColor(TEAL); c.rect(0,H-12,W,12,fill=1,stroke=0)
    txt(32,H-45,title,22,True)
    txt(32,H-65,subtitle,10,color=GREY)
    c.setStrokeColor(colors.HexColor("#d2dfe5")); c.line(32,38,W-32,38)
    txt(32,23,"LED LIGHTHOUSE  |  v0.1  |  2026-10-21  |  UNTESTED HARDWARE PROTOTYPE",8,color=GREY)
    txt(W-80,23,f"{page:02d}",9,True)

def table(x,y,rows,widths,fs=9):
    pstyle=ParagraphStyle("t",parent=style,fontSize=fs,leading=fs*1.28)
    data=[[Paragraph(str(cell),pstyle) for cell in row] for row in rows]
    t=Table(data,colWidths=widths,hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),LIGHT),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cbd9df")),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    tw,th=t.wrap(W,H); assert y-th>45,(page,y,th)
    t.drawOn(c,x,y-th); return y-th-12

def line(x1,y1,x2,y2):
    c.setStrokeColor(INK); c.setLineWidth(1); c.line(x1,y1,x2,y2)

def node(x,y):
    c.setFillColor(INK);c.circle(x,y,2,fill=1,stroke=0)

def resistor(x,y,ref,value,a,b,width=220):
    txt(x,y+12,ref+"  "+value,9,True)
    txt(x,y-15,a,9,color=TEAL);txt(x+width-65,y-15,b,9,color=TEAL)
    line(x,y,x+65,y); c.setStrokeColor(INK);c.rect(x+65,y-5,width-130,10,fill=0,stroke=1);line(x+width-65,y,x+width,y)

def block(x,y,w,h,title,body):
    c.setFillColor(LIGHT);c.setStrokeColor(colors.HexColor("#bbd1d8"));c.roundRect(x,y-h,w,h,6,fill=1,stroke=1)
    txt(x+10,y-21,title,12,True);para(x+10,y-34,body,w-20,9)

def ic(x,y,ref):
    p=BYREF[ref]; n=len(p["pins"]); h=24+n/2*24; w=150
    c.setStrokeColor(INK);c.setFillColor(colors.white);c.rect(x,y-h,w,h,stroke=1,fill=1)
    c.arc(x+w/2-9,y-9,x+w/2+9,y+9,180,180)
    txt(x+32,y-h/2+8,ref,14,True);txt(x+15,y-h/2-8,p["value"],10)
    for pin in range(1,n+1):
        left=pin<=n/2
        yy=y-24-(pin-1 if left else n-pin)*24
        xx=x if left else x+w
        line(xx,yy,xx+(-18 if left else 18),yy)
        txt(x+5 if left else x+w-18,yy+4,str(pin),8)
        net=p["pins"][str(pin)]
        if net.startswith("NC_"):net="NC"
        label=f"{net}"
        if left:
            c.setFont("Helvetica",9);c.setFillColor(TEAL);c.drawRightString(x-22,yy-3,label)
        else:txt(x+w+22,yy-3,label,9,color=TEAL)
    return y-h

def bjt(x,y,ref):
    p=BYREF[ref]
    line(x-20,y,x,y);line(x,y-13,x,y+13)
    line(x,y+8,x+20,y+22);line(x+20,y+22,x+20,y+32)
    line(x,y-8,x+20,y-22);line(x+20,y-22,x+20,y-32)
    # NPN arrow points out of the base toward emitter.
    line(x+13,y-17,x+20,y-22);line(x+20,y-22,x+13,y-22);line(x+20,y-22,x+17,y-15)
    txt(x+30,y+8,ref+"  BC547B",10,True)
    txt(x-85,y-4,"B: "+p["pins"]["B"],8,color=TEAL)
    txt(x+4,y+40,"C: "+p["pins"]["C"],8,color=TEAL)
    txt(x+4,y-47,"E: "+p["pins"]["E"],8,color=TEAL)

def vres(x,y,ref,value):
    line(x,y+20,x,y+8);c.setStrokeColor(INK);c.rect(x-5,y-8,10,16);line(x,y-8,x,y-20)
    txt(x+10,y+3,ref+" "+value,9,True)

def vcap(x,y,ref,value):
    line(x,y+20,x,y+3);line(x-10,y+3,x+10,y+3);line(x-10,y-3,x+10,y-3);line(x,y-3,x,y-20)
    txt(x+14,y+1,ref+" "+value,9);txt(x-17,y+9,"+",9)

def ground(x,y):
    line(x,y+10,x,y);line(x-10,y,x+10,y);line(x-6,y-4,x+6,y-4);line(x-2,y-8,x+2,y-8)

def timing_networks():
    new("03A / Timing network schematics", "These drawings expand the TIME, DISCH1, DISCH2 and OSC nets from sheet 03")
    txt(40,480,"U1 / about one minute",16,True)
    txt(440,480,"U2 / LED stepping speed",16,True)
    txt(45,442,"+5V",10,True,color=TEAL)
    line(60,432,60,410);line(60,410,90,410)
    c.setStrokeColor(INK);c.rect(90,405,70,10);line(160,410,200,410)
    txt(85,428,"R20 220k",10)
    c.rect(200,405,70,10);line(270,410,315,410);node(315,410)
    txt(200,444,"P3 1M",10,True);txt(190,386,"W strapped to B",9)
    line(235,435,235,415);line(235,415,230,420);line(235,415,240,420)
    txt(302,430,"TIME / U1.6",10,True,color=TEAL)
    line(315,410,315,355);vcap(315,335,"C7","100u");ground(315,305)
    line(315,410,385,410);line(385,410,385,385);vres(385,365,"R40","100")
    line(385,345,385,320);txt(350,300,"DISCH1 / U1.7",9,color=TEAL)
    txt(445,442,"+5V",10,True,color=TEAL)
    line(460,432,460,420);vres(460,400,"R21","10k")
    line(460,380,460,355);node(460,355);txt(432,338,"DISCH2",9,color=TEAL)
    txt(440,323,"U2.7",9,color=TEAL)
    line(460,355,525,355);c.rect(525,350,65,10);line(590,355,635,355)
    txt(525,375,"R22 10k",10)
    c.rect(635,350,65,10);line(700,355,750,355);node(750,355)
    txt(630,394,"P2 100k",10,True);txt(615,330,"W strapped to B",9)
    line(668,382,668,360);line(668,360,663,365);line(668,360,673,365)
    txt(728,378,"OSC",10,True,color=TEAL);txt(710,314,"U2.2 + U2.6",9,color=TEAL)
    line(750,355,750,295);vcap(750,275,"C10","10u");ground(750,245)
    para(40,220,"<b>How to wire the trim pots:</b> choose one outer terminal as A. Connect the wiper W to the other outer terminal B. The resistance from A to W+B is adjustable from nearly zero to the pot's rated resistance. Verify with a meter while unpowered.",width=750)
    para(40,150,"<b>Capacitor polarity:</b> C7 positive to TIME, C10 positive to OSC; both negative leads to GND. R40 prevents a large current surge when U1 discharges C7. Do not join DISCH1 directly to TIME.",width=750)

def led_networks():
    new("05A / Five LED branches", "All five LED anodes use the switched LED_POWER rail from Q6, not the permanent +5V rail")
    txt(40,512,"LED_POWER from Q6.E",11,True,color=TEAL)
    line(40,490,797,490);line(40,240,797,240);txt(40,217,"GND",11,True,color=TEAL)
    for i in range(5):
        x=108+i*150
        node(x+10,490);line(x+10,490,x+10,480);vres(x+10,460,f"R{28+i}","1k")
        line(x+10,440,x+10,425)
        path=c.beginPath();path.moveTo(x+2,425);path.lineTo(x+18,425);path.lineTo(x+10,412);path.close()
        c.setStrokeColor(INK);c.setFillColor(colors.white);c.drawPath(path,stroke=1,fill=0)
        line(x,409,x+20,409);line(x+10,409,x+10,393)
        txt(x+28,400,f"LED{i+1}",10,True)
        for dx,dy in [(25,0),(33,-7)]:
            line(x+dx,426+dy,x+dx+10,436+dy);line(x+dx+10,436+dy,x+dx+4,434+dy);line(x+dx+10,436+dy,x+dx+8,430+dy)
        line(x-15,357,x-15,383);line(x-15,378,x+10,393)
        line(x-15,362,x+10,345);line(x+10,345,x+10,240);node(x+10,240)
        line(x+2,350,x+10,345);line(x+10,345,x+3,345);line(x+10,345,x+7,352)
        line(x-72,370,x-62,370);c.rect(x-62,365,32,10);line(x-30,370,x-15,370)
        txt(x-73,388,f"R{33+i} 22k",9);txt(x-75,349,f"STEP{i}",9,color=TEAL)
        txt(x+23,373,f"Q{i+7}",11,True);txt(x+23,357,"BC547B",8)
    y=185
    y=para(40,y,"<b>Counter outputs:</b> STEP0=U4 pin 3; STEP1=pin 2; STEP2=pin 4; STEP3=pin 7; STEP4=pin 10. Wire each output to its own 22k base resistor. All five emitters join GND.",width=750)
    para(40,y,"<b>LED polarity:</b> A (anode) is above the LED symbol, connected through 1k to LED_POWER. K (cathode, bar in the symbol) connects to the transistor collector. Identify the actual LED polarity before soldering; do not rely only on lead length for used LEDs.",width=750)

def refs_table(refs,x=32,y=245,width=778,fs=9):
    rows=[["Part","Value","Connect terminals to these named nets"]]
    for ref in refs:
        p=BYREF[ref]
        pins="; ".join(f"{k} = {v}" for k,v in p["pins"].items())
        rows.append([ref,p["value"],pins])
    return table(x,y,rows,[70,125,width-195],fs)

new("LED lighthouse", "Motion + darkness -> about 60 seconds of five sequential white LEDs -> all LEDs off")
y=H-95
y=para(32,y,"<b>Build status:</b> datasheet-based prototype, not electrically simulated or tested on hardware. Use this guide to assemble and measure one stage at a time. This is a connection schematic, not a PCB or breadboard hole layout.")
for x,title,body in [(32,"1  DETECT","PIR senses a new motion edge.<br/>LDR permits operation only in darkness."),(297,"2  RUN","U1 enables the LED supply for about one minute.<br/>Extra motion does not restart the timer."),(562,"3  SEQUENCE","U2 + U4 select LED1 to LED5 repeatedly.<br/>Idle resets the sequence to LED1.")]:
    block(x,430,248,90,title,body)
txt(32,310,"Power arrangement",15,True)
block(32,292,220,75,"Protected 1S battery","3.7V nominal, 4.2V charge chemistry.<br/>Known charge-current rating required.")
block(297,292,248,75,"LaskaKit LA122076","Battery terminals verified on actual board.<br/>USB-C for charging; 5V boost output.")
block(590,292,220,75,"S1 -> J1 -> circuit","Switch the verified +5V output.<br/>GND is common across all stages.")
line(252,254,297,254);line(545,254,590,254)
y=195
for s in ["<b>Power first:</b> use a current-limited regulated 5V supply for initial checks, or a verified USB 5V source. Do not connect an unidentified recycled cell.","<b>Board terminals:</b> J1 and J2 use signal names, not an assumed physical pin order. Match the actual PCB labels. If a module is unlabelled, obtain its pinout before connecting it.","<b>Behaviour:</b> daylight during a run cancels it. A PIR startup pulse can activate the lighthouse while the sensor settles; allow at least 60 seconds after power-on before testing.","<b>Reading:</b> matching teal net names on different sheets are the same wire. NC means leave open. Component pin numbers are top view, notch upward."]:
    y=para(32,y,s)

new("01 / Darkness and reset", "U3A permits night operation; U3B resets the LED sequence whenever RUN is low")
ic(190,465,"U3")
resistor(480,450,"R1","100k","+5V","LUX")
resistor(480,390,"R2","100k","LUX","GND")
resistor(480,330,"R3","1M","DAY","DARK_TH")
txt(32,298,"LDR1: LUX to GND. C14: LUX to GND. Neither has polarity.",10)
y=table(32,275,[["Network","Exact connections"],["Darkness setting","R4: +5V to REF_TOP, 47k. R5: REF_TOP to GND, 47k. P1 A=REF_TOP, W=DARK_TH, B=GND (100k)."],["Daylight output","R38: +5V to DAY, 100k. R39: DAY to Q12 base, 47k. Q12 C=ARM, E=GND. R6: +5V to ARM, 10k. C6: ARM (+) to GND (-), 100u."],["Idle detection","R7: RUN to RUN_HALF, 100k. R8: RUN_HALF to GND, 100k. R9: +5V to FIX_REF, 47k. R10: FIX_REF to GND, 15k. R11: +5V to IDLE, 10k."]],[130,648])
para(32,y,"Inputs remain below 3.5V at a 5V supply. DAY is high in light, low in darkness. Q12 pulls ARM low in light. In darkness C6 charges and releases U1 RESET. P1 clockwise direction depends on which outer terminal is A; start at mid travel.")

new("02 / Motion pulse and lockout", "Buffered edge trigger: no capacitive signal is applied directly to a TLC555 input")
for x,ref in [(110,"Q1"),(305,"Q2"),(500,"Q3"),(695,"Q4")]:bjt(x,423,ref)
txt(32,340,"Signal path",13,True)
para(32,320,"PIR_OUT -> R12 -> Q1 -> INV -> R14 -> Q2 -> MOTION_BUF -> C11 -> EDGE -> R16 -> Q3 base. A rising PIR output produces a short LOW pulse at TRIG.")
y=table(32,272,[["Part / network","Connection"],["Q1 input inverter","R12=47k from PIR_OUT to Q1.B; Q1.E=GND; Q1.C=INV; R13=47k from +5V to INV."],["Q2 motion buffer","R14=47k from INV to Q2.B; Q2.E=GND; Q2.C=MOTION_BUF; R15=47k from +5V to MOTION_BUF."],["Q3 pulse switch","C11=100n between MOTION_BUF and EDGE. R16=10k from EDGE to Q3.B. R17=100k from Q3.B to GND. Q3.E=GND; Q3.C=TRIG; R18=10k from +5V to TRIG."],["D1 base clamp","D1 anode=GND; cathode (band)=Q3.B. It limits reverse base voltage on the falling edge."],["Q4 busy lockout","R19=47k from RUN to Q4.B; Q4.E=GND; Q4.C=Q3.B. C15=10u, (+)=Q4.B, (-)=GND. RUN disables Q3; C15 holds lockout briefly after timeout to reject an overlapping edge."]],[150,628],9)
para(32,y,"The PIR can stay high during continued movement. C11 responds to edges, so a held-high PIR output does not hold TRIG low. After timeout and a short lockout tail, the next LOW-to-HIGH PIR transition can start a new run.",size=9)

new("03 / Duration and LED speed", "Both ICs are TLC555IP, DIP8; use the numbered pins, not the text position on the package")
ic(160,468,"U1");ic(555,468,"U2")
y=table(32,300,[["Circuit","Timing network and settings"],["U1 minute timer","+5V -> R20 220k -> P3 A. Strap P3 W and B together at TIME. C7 100u: (+)=TIME, (-)=GND. U1 pin 6=TIME. TIME -> R40 100 ohm -> U1 pin 7 (DISCH1). C8 10n from pin 5 to GND."],["U2 LED oscillator","+5V -> R21 10k -> DISCH2 (pin 7) -> R22 10k -> P2 A. Strap P2 W and B at OSC. U2 pins 2 and 6=OSC. C10 10u: (+)=OSC, (-)=GND. C9 10n from pin 5 to GND."],["Local supply bypass","C1 100n directly between U1 pins 8 and 1. C2 100n directly between U2 pins 8 and 1."]],[130,648])
y=para(32,y,"<b>Duration:</b> t approximately 1.1 x (220k + P3) x 100u: nominally 24 to 134 seconds. Start P3 near 330k for about 60 seconds. Measure and adjust; capacitor tolerance and leakage can substantially change the result.")
para(32,y,"<b>Step interval:</b> T approximately 0.693 x [10k + 2 x (10k + P2)] x 10u: about 0.21 to 1.59 seconds per LED. Start P2 near 35k for about 0.69 seconds per step. The first LED dwell after starting is different from steady-state timing.")

timing_networks()

new("04 / Five-step counter", "Clock inversion preserves LED1 at the start; diode OR combines idle reset and modulo-five reset")
ic(180,470,"U4");bjt(590,425,"Q5")
resistor(490,335,"R23","47k","OSC_OUT","QB5")
resistor(490,280,"R24","10k","+5V","CLOCK")
y=table(32,222,[["Connection","Details"],["Clock","U2.3=OSC_OUT -> R23 -> Q5.B; Q5.E=GND; Q5.C=CLOCK. R24 pulls CLOCK up to +5V. CLOCK -> U4.14."],["Reset OR","D2 A=IDLE, K=COUNT_RESET. D3 A=STEP5 (U4.1), K=COUNT_RESET. R25=100k and C12=10n each from COUNT_RESET to GND. COUNT_RESET -> U4.15."],["Always connected","U4.16=+5V; U4.8=GND; U4.13=GND. C4=100n between pins 16 and 8. Pins 5, 6, 9, 11 and 12 stay unconnected."]],[130,648],9)
para(32,y,"Sequence: U4.3 -> U4.2 -> U4.4 -> U4.7 -> U4.10 -> repeat. STEP5 at pin 1 is a reset signal, not a sixth LED.",size=9)

new("05 / Switched LED supply", "Q6 is an emitter follower, not a grounded-emitter switch; connect its three terminals exactly as shown")
bjt(165,425,"Q6")
resistor(445,450,"R26","1k","RUN","QB6")
resistor(445,390,"R27","100k","LED_POWER","GND")
para(32,330,"Q6 collector goes to +5V; its emitter provides LED_POWER (typically about 4V during RUN, near 0V when idle). This deliberate voltage drop leaves ample headroom for low-current white LEDs while ensuring that they all turn off.")
txt(32,265,"Repeat this branch five times",14,True)
y=table(32,245,[["LED position","Counter output -> base resistor -> transistor","Light-current path"],*[ [f"LED{i+1}",f"U4.{[3,2,4,7,10][i]} (STEP{i}) -> R{33+i} 22k -> Q{i+7}.B",f"LED_POWER -> R{28+i} 1k -> LED{i+1}.A; LED{i+1}.K -> Q{i+7}.C; Q{i+7}.E -> GND"] for i in range(5)]],[95,310,373],9)
para(32,y,"Each LED has its own 1k resistor. Start with these values; expect roughly 0.5-1.5mA for typical white LEDs. Actual LED forward voltage and brightness must be measured. Do not connect LEDs directly to CD4017 outputs or directly to the battery.",size=9)

led_networks()

new("06 / Pin orientation and assembly", "All DIP diagrams are TOP VIEW: notch upward, pin 1 at top left; numbering runs counterclockwise")
for x,ref in [(155,"U1"),(515,"U3")]:ic(x,470,ref)
y=table(32,295,[["Item","How to identify and connect it"],["BC547B Q1-Q12","Manufacturer default TO-92 drawing: flat face toward you, leads downward, C-B-E from left to right. Verify the received manufacturer / package against its datasheet; special pinouts and substitutions exist. The circuit netlist names C, B, E rather than assuming generic TO-92 numbering."],["1N4148 D1-D3","The painted band marks K (cathode). A is the unbanded end. D1 band to Q3.B; D2 and D3 bands to COUNT_RESET."],["Electrolytic capacitors","C5, C6, C7, C10 and C15 are polarized. The body stripe normally marks the negative lead: all negative leads here go to GND. Follow the + / - entries in the parts table."],["P1, P2, P3 trim pots","Identify the wiper W from the pot drawing or a resistance measurement. Do not infer pin order from how a pot is drawn here. P1 uses all three terminals; P2/P3 strap W to outer terminal B."],["PIR and boost module","Connect by verified PCB signal labels only. No physical pad order has been inferred. PIR OUT must be measured LOW at rest and HIGH on motion. If labels or output polarity differ, resolve that before connecting J2."]],[155,623],9)
para(32,y,"Fit sockets first, then resistors/diodes, then capacitors. Insert ICs only after confirming supply polarity. Keep bypass capacitors close to the supply pins and the long TIME wire short and clean.",size=9)

new("07 / Parts actually used", "Counts below are derived from the complete connection netlist, replacing the earlier shopping estimates")
groups=defaultdict(list)
for p in PARTS:
    if p["kind"] in ["R","C"]:groups[(p["kind"],p["value"])].append(p["ref"])
rows=[["Type / value","Used","References"]]
for (kind,value),refs in groups.items(): rows.append([f"{kind}: {value}",len(refs),", ".join(refs)])
y=table(32,490,rows,[145,55,578],8.4)
y=para(32,y,"Also used: 2 x TLC555IP, 1 x TLC372CP, 1 x CD4017BE, <b>12 x BC547B</b>, 3 x 1N4148, 2 x 100k trim pots, 1 x 1M trim pot, 5 white LEDs and 1 LDR5516. Sockets: 3 x DIP8 and 1 x DIP16. The transistor design uses all 12 ordered pieces.",size=9)
para(32,y,"Resistors are standard 0.25W parts. Check your resistor assortment against the value/count table before assembly. Series combinations are possible where necessary; record any substitutions in the wiring notes.<br/><b>Supply capacitors:</b> C3=100n between U3 pins 8 and 4; C5=100u (+ to +5V, - to GND); C13=100n between +5V and GND near the PIR. C1-C4 belong directly at their IC supply pins.",size=9)

new("08 / First power-up and adjustment", "Complete each stage before moving on; the battery is the last power source to connect")
rows=[["Step","Check / expected result"],
["1. Unpowered","No short between +5V and GND. Verify DIP notch orientation, diode bands, transistor C/B/E, capacitor polarity and all pot wipers. Leave PIR unplugged."],
["2. Supply","Apply regulated 5V with current limit initially 20mA. Confirm about 4.75-5.25V at every IC. If current limit is reached or a component heats, switch off and inspect. Do not increase the limit to mask a wiring fault."],
["3. Darkness","Cover LDR1. Adjust P1: ARM should rise near 5V. Illuminate LDR: ARM should go below 0.2V. DAY does not need to reach 5V; it drives a transistor. Check LUX / DARK_TH remain below 3.5V."],
["4. Manual start","With ARM high and LEDs disconnected, briefly connect TRIG to GND through 1k. RUN should go high, then low once. Disconnect the test resistor. This manual test bypasses the motion lockout; do not hold it low."],
["5. Timer","Start P3 near 330k (measured with power off). TIME should rise smoothly to about 3.3V, then discharge and RUN must fall. Time the interval and adjust P3 to about 60s."],
["6. Oscillator / LEDs","Connect LED branches. P2 about 35k gives about 0.7s per step. Confirm LED1 -> LED2 -> LED3 -> LED4 -> LED5, repeat. At timeout LED_POWER and all LED light must fall to zero."],
["7. PIR","Before connecting OUT, verify the module pad labels and output voltage / polarity. Connect J2, allow at least 60s to settle, then test motion in dark and light. Motion during RUN must not restart the minute."],
["8. Final source","Check the actual charger board terminal labels and battery charge-current specification. Use a known protected 1S, 4.2V-charge Li-ion/Li-pol cell. Confirm 5V persists for at least 10 minutes while the lighthouse is idle, then test motion. First charging tests: S1 off."]]
table(32,490,rows,[115,663],9)

new("09 / Troubleshooting and limits", "The one-minute RC timer and the exact module revisions require bench verification")
y=table(32,490,[["Symptom","What to inspect"],["RUN stays high / timer too long","C7 leakage can prevent TIME reaching the threshold. Check polarity, clean flux, reduce P3 and retest. Measure the TIME rise. If it stalls below about 3.3V, use a verified low-leakage 100u timing capacitor or redesign the timebase; do not assume this is a pot adjustment problem."],["All LEDs off while RUN high","Check Q6: collector=+5V, base through R26 to RUN, emitter=LED_POWER. LED_POWER should be around 4V. Check LED polarity and transistor pinouts."],["LEDs stay on after timeout","LED anodes must be powered from LED_POWER, not +5V. Check Q6 pinout, RUN low, R27 and accidental solder bridges."],["Only one LED / wrong order","Check inverted CLOCK at U4.14, U4.13 at GND, the five numbered output pins, and D2/D3 cathodes at COUNT_RESET."],["Stops immediately when LEDs light","The LEDs may illuminate LDR1, causing daylight reset. Shield / reposition the LDR; adjust P1. Feedback is not fixed by simply extending the timer."],["Works on USB, fails on battery","Verify 5V boost output at idle and during a run. Check battery protection and actual board revision. Auto-off at low load is not guaranteed by the retailer specification."],["Turns on after power-up","PIR warmup can create a motion signal. Allow settling. The brief reset delay is not a full 60-second PIR warmup inhibit."]],[180,598],9)
y=para(32,y,"<b>Limits:</b> low-current white LEDs, indoor use, no brightness fading, no firmware, no PCB layout. No measured battery life is claimed. Simultaneous charging and operating has not been verified. The design must pass the commissioning checks before permanent installation.",size=9)

new("10 / Sources and design checks", "Component pinouts checked from manufacturer documentation; module pad order remains a physical inspection step")
y=490
for sid,title,url in SOURCES:
    y=para(32,y,f"<b>{sid}</b> {title}<br/><font color='#087f8c'><link href='{url}'>{url}</link></font>",size=8.5)
y=para(32,y,"<b>Checks performed:</b> unique component references; all non-NC nets have at least two endpoints; every DIP pin is assigned or explicitly NC; safe comparator input-divider ranges; current-limiting resistors for all LEDs and transistor bases; separate switched LED supply; nominal timing and initial-stage loading calculations.",size=9)
para(32,y,"<b>Not performed:</b> SPICE simulation, measurements on the ordered components, verification of unlabelled module pad order, confirmation of received transistor variants, or testing with the selected battery. Update status only after recording real measurements.",size=9)
c.save()

(ROOT/"docs/netlist.json").write_text(json.dumps({"revision":"0.1","date":DATE,"status":"untested","parts":PARTS},indent=2)+"\n")
md=["# LED lighthouse wiring reference", "", "Revision 0.1, 2026-10-21. **Untested hardware prototype.**", "", "The PDF is the assembly guide. Matching net names are electrically connected. This is not a PCB layout.", "", "## Pin-to-net connections", "", "| Part | Value | Pin / terminal connections | Purpose |", "| --- | --- | --- | --- |"]
for p in PARTS:
    md.append(f'| {p["ref"]} | {p["value"]} | '+"; ".join(f'{pin}={net}' for pin,net in p["pins"].items())+f' | {p["purpose"]} |')
md += ["", "## Wire groups", "", "Join all endpoints in each row. NC pins are intentionally open.", "", "| Net | Endpoints |", "| --- | --- |"]
for net,ends in sorted(NETS.items()):md.append(f'| {net} | '+", ".join(ends)+" |")
md += ["", "## Power and module assumptions", "", "- J1: verified regulated 5V, after S1; common GND.", "- Use LaskaKit LA122076 with a known protected single Li-ion/Li-pol cell of 4.2V-charge chemistry and a compatible charge-current rating.", "- Module physical pad order is not inferred: match actual labels or obtain the correct revision pinout before applying power.", "- J2.OUT must be LOW at rest, HIGH on motion. Verify it before connecting to the trigger stage.", "- Default Semtech BC547 package is C-B-E with flat face toward the viewer and leads downward. Confirm actual received variant; the manufacturer notes custom pinouts can exist.", "- White LEDs have individual 1k current limiters; brightness/current must be measured.", "- C7 is a long-duration RC timing capacitor. Excess leakage can prevent timeout; this is an explicit bench-test gate.", "", "## Behaviour", "", "- Darkness + a new PIR rising edge starts one run.", "- Q4 disables new triggers during RUN. The next run requires a fresh PIR edge after timeout.", "- Daylight resets U1 and cancels a running sequence. Shield the LDR from the LEDs.", "- Counter is reset to LED1 while idle; clock inversion preserves the first LED at startup.", "- PIR warmup pulses may start a run; this design does not add a full warmup inhibit.", "", "## Sources", ""]
for sid,title,url in SOURCES:md.append(f'- [{sid}: {title}]({url})')
(ROOT/"docs/wiring.md").write_text("\n".join(md)+"\n")
print(f"Created {OUT} ({page} pages); {len(PARTS)} parts; {len(NETS)} nets.")
print("Resistor counts:",dict(Counter(p["value"] for p in PARTS if p["kind"]=="R")))
