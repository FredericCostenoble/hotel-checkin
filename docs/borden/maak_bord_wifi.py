from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
F="/usr/share/fonts/truetype/google-fonts/"
for n,f in [("L","Poppins-Light.ttf"),("R","Poppins-Regular.ttf"),("M","Poppins-Medium.ttf")]: pdfmetrics.registerFont(TTFont(n,F+f))
ACC=HexColor("#B4BCCC"); DARK=HexColor("#2B2F38"); MID=HexColor("#5C6478")
SSID,PWD="HotelLucca-Guest","voorbeeld2026"
LINES=["Geen bereik? Scan om te verbinden met ons wifi","Pas de réseau ? Scannez pour vous connecter au Wi-Fi",
       "No signal? Scan to connect to our Wi-Fi","Kein Empfang? Scannen und mit unserem WLAN verbinden",
       "¿Sin cobertura? Escanee para conectarse a nuestro Wi-Fi"]
def spaced(c,font,size,x,y,text,space):
    c.saveState(); w=pdfmetrics.stringWidth(text,font,size)+space*(len(text)-1)
    t=c.beginText(); t.setFont(font,size); t.setCharSpace(space); t.setTextOrigin(x-w/2,y); t.textOut(text); c.drawText(t); c.restoreState()
W=H=10*cm; c=canvas.Canvas("hotel-lucca-wifi-10x10.pdf",pagesize=(W,H))
band=1.75*cm; c.setFillColor(ACC); c.rect(0,H-band,W,band,stroke=0,fill=1)
lw=2.8*cm; lh=lw*688/1523; c.drawImage(ImageReader("site-logo.png"),W/2-lw/2,H-band/2-lh/2,lw,lh,mask="auto")
y=H-band-0.5*cm; c.setFillColor(MID)
spaced(c,"M",5.6,W/2,y,"WIFI · WI-FI · WLAN",1.4)
q=3.6*cm; qy=y-0.25*cm-q; c.drawImage(ImageReader("wifi-qr.png"),W/2-q/2,qy,q,q)
ty=qy-0.33*cm
c.setFont("R",6.4); c.setFillColor(DARK)
c.drawCentredString(W/2,ty,f"{SSID}   ·   {PWD}"); ty-=0.38*cm
for txt in LINES:
    c.setFont("L",5.8); c.setFillColor(DARK); c.drawCentredString(W/2,ty,txt); ty-=0.29*cm
c.setStrokeColor(ACC); c.setLineWidth(0.6); c.line(W/2-1*cm,0.8*cm,W/2+1*cm,0.8*cm)
c.setFillColor(MID); c.setFont("L",5.8); c.drawCentredString(W/2,0.45*cm,"Hotel Lucca · Naaldenstraat 30, Brugge · +32 478 08 30 49")
c.save()
