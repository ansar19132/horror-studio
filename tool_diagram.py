#!/usr/bin/env python3
"""Horror Studio tool flow diagram (Roman Urdu labels)."""
from PIL import Image, ImageDraw, ImageFont

W, H = 1000, 1720
BG = (11, 11, 16)
BOX = (22, 22, 30)
BORDER = (60, 60, 75)
RED = (224, 56, 59)
GREEN = (76, 195, 138)
WHITE = (245, 245, 247)
GREY = (165, 165, 175)
DIM = (110, 110, 125)

FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

f_title = ImageFont.truetype(FB, 42)
f_sub = ImageFont.truetype(FR, 24)
f_step = ImageFont.truetype(FB, 27)
f_txt = ImageFont.truetype(FR, 21)
f_num = ImageFont.truetype(FB, 30)
f_tag = ImageFont.truetype(FB, 19)
f_foot = ImageFont.truetype(FB, 26)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

def center_text(y, text, font, fill):
    bb = d.textbbox((0, 0), text, font=font)
    x = (W - (bb[2] - bb[0])) / 2
    d.text((x, y), text, font=font, fill=fill)

center_text(40, "HORROR STUDIO", f_title, WHITE)
center_text(95, "Complete Tool — Script se Final Video tak", f_sub, GREY)

steps = [
    ("1", "SCRIPT INPUT", ["Tum sirf script paste karti ho.", "Bas — iske baad sab kuch automatic."], GREEN, "TUMHARA KAAM"),
    ("2", "VOICE STUDIO ENGINE  (built-in)", ["Auto voiceover: Christopher voice, emotion", "detection, whisper, pro mastering."], RED, None),
    ("3", "AI IMAGE GENERATOR", ["Har sentence par 1 horror image,", "har image me motion (zoom / pan)."], RED, None),
    ("4", "STOCK PHOTO FALLBACK", ["Jahan AI image na ban sake wahan", "Pexels stock photo (free key)."], RED, None),
    ("5", "AUTO EDIT ENGINE", ["Clip length = voice timing, transitions,", "horror FX (grain, vignette, red flash),", "word-by-word karaoke captions."], RED, None),
    ("6", "MULTI-LANGUAGE DUB  (optional)", ["Urdu / Hindi / Spanish me dub —", "wohi images, nayi voice + captions."], RED, None),
    ("7", "FINAL VIDEO", ["6+ minute video + Shorts.", "Download karo — upload ke liye ready."], RED, None),
]

BOX_X, BOX_W, BOX_H = 80, 840, 150
STEP_GAP = 208
y0 = 175

def rounded_box(x, y, w, h, radius, outline, width):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=BOX, outline=outline, width=width)

for i, (num, title, lines, accent, tag) in enumerate(steps):
    y = y0 + i * STEP_GAP
    rounded_box(BOX_X, y, BOX_W, BOX_H, 18, accent, 3)
    # number badge
    cx, cy = BOX_X, y + BOX_H // 2
    d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=accent)
    bb = d.textbbox((0, 0), num, font=f_num)
    d.text((cx - (bb[2] - bb[0]) / 2, cy - (bb[3] - bb[1]) / 2 - 2), num, font=f_num, fill=WHITE)
    # texts
    tx = BOX_X + 55
    d.text((tx, y + 16), title, font=f_step, fill=WHITE)
    ty = y + 58
    for line in lines:
        d.text((tx, ty), line, font=f_txt, fill=GREY)
        ty += 30
    if tag:
        tb = d.textbbox((0, 0), tag, font=f_tag)
        tw = tb[2] - tb[0] + 24
        d.rounded_rectangle([BOX_X + BOX_W - tw - 18, y + 14, BOX_X + BOX_W - 18, y + 46], radius=10, fill=GREEN)
        d.text((BOX_X + BOX_W - tw - 18 + 12, y + 18), tag, font=f_tag, fill=(10, 10, 12))
    # arrow to next
    if i < len(steps) - 1:
        x1 = BOX_X + BOX_W // 2
        ya, yb = y + BOX_H + 6, y + STEP_GAP - 8
        d.line([x1, ya, x1, yb], fill=RED, width=5)
        d.polygon([(x1 - 12, yb - 14), (x1 + 12, yb - 14), (x1, yb + 2)], fill=RED)

center_text(H - 90, "1 Click  =  Mukammal Horror Video", f_foot, RED)

out = "/home/hatch/workspace/your_files/horror-tool-diagram.png"
img.save(out)
print("saved:", out)
