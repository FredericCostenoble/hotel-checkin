from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import sys
F="/usr/share/fonts/truetype/google-fonts/"
for n,f in [("L","Poppins-Light.ttf"),("R","Poppins-Regular.ttf"),("M","Poppins-Medium.ttf")]: pdfmetrics.registerFont(TTFont(n,F+f))
ACC=HexColor("#B4BCCC"); DARK=HexColor("#2B2F38"); MID=HexColor("#5C6478")
LINES=["Scan voor alle info over uw verblijf","Scannez pour toutes les infos sur votre séjour",
       "Scan for all information about your stay","Scannen für alle Infos zu Ihrem Aufenthalt",
       "Escanee para toda la información de su estancia"]
def spaced(c,font,size,x,y,text,space):
    c.saveState()
    w=pdfmetrics.stringWidth(text,font,size)+space*(len(text)-1)
    t=c.beginText(); t.setFont(font,size); t.setCharSpace(space); t.setTextOrigin(x-w/2,y); t.textOut(text); c.drawText(t)
    c.restoreState()
def sign(path,W,H,qr_cm,band_cm,logo_cm,gap,ts=7,ls=0.39,hs=6.3):
    c=canvas.Canvas(path,pagesize=(W,H))
    band=band_cm*cm
    c.setFillColor(ACC); c.rect(0,H-band,W,band,stroke=0,fill=1)
    lw=logo_cm*cm; lh=lw*688/1523
    c.drawImage(ImageReader("site-logo.png"),W/2-lw/2,H-band/2-lh/2,lw,lh,mask="auto")
    y=H-band-gap*cm
    c.setFillColor(MID)
    spaced(c,"M",hs,W/2,y,"UW VERBLIJF · VOTRE SÉJOUR · YOUR STAY",1.4)
    spaced(c,"M",hs,W/2,y-hs*0.065*cm,"IHR AUFENTHALT · SU ESTANCIA",1.4)
    q=qr_cm*cm; qy=y-hs*0.065*cm-0.25*cm-q
    c.drawImage(ImageReader("hotel-lucca-qr-logo.png"),W/2-q/2,qy,q,q)
    ty=qy-0.35*cm
    for txt in LINES:
        c.setFont("L",ts); c.setFillColor(DARK); c.drawCentredString(W/2,ty,txt); ty-=ls*cm
    c.setStrokeColor(ACC); c.setLineWidth(0.6); c.line(W/2-1*cm,0.8*cm,W/2+1*cm,0.8*cm)
    c.setFillColor(MID); c.setFont("L",5.8); c.drawCentredString(W/2,0.45*cm,"Hotel Lucca · Naaldenstraat 30, Brugge · +32 478 08 30 49")
    c.save()
sign("hotel-lucca-qr-10x15.pdf",10*cm,15*cm,5.8,3.3,4.6,1.0,ts=7.2,ls=0.42)
sign("hotel-lucca-qr-10x10.pdf",10*cm,10*cm,3.9,1.75,2.8,0.5,ts=6,ls=0.31,hs=5.6)
