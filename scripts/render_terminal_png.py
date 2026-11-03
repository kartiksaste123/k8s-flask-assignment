"""Render evidence/logs/*.txt as terminal-style PNG screenshots
(evidence/screenshots/NN_name.png) and add a browser URL bar to the
headless-Chrome screenshots. Uses Pillow only, no GUI."""
import glob
import os
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SIZE, PAD, WRAP, MAX_LINES = 15, 22, 165, 70
BG, FG, PROMPT, CMD, TITLE_BG = (30, 30, 36), (220, 223, 228), (80, 250, 123), (139, 233, 253), (52, 52, 60)

font, fontb = ImageFont.truetype(FONT, SIZE), ImageFont.truetype(FONT_B, SIZE)
sans = ImageFont.truetype(SANS, 14)
EMOJI = re.compile(r"[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F]")
OUT = "evidence/screenshots"


def clean(line):
    return EMOJI.sub("", line.rstrip("\n")).replace("\t", "    ")


def render(path):
    name = os.path.splitext(os.path.basename(path))[0]
    raw = [clean(l) for l in open(path, encoding="utf-8", errors="replace")]
    while raw and not raw[-1].strip():
        raw.pop()
    if len(raw) > MAX_LINES:  # long build logs: keep head and tail
        raw = raw[:25] + [f"... ({len(raw) - 60} lines omitted, full output in evidence/logs/{name}.txt) ..."] + raw[-35:]
    lines = []
    for l in raw:
        lines += textwrap.wrap(l, WRAP, replace_whitespace=False, drop_whitespace=False) or [""]
    cw = font.getbbox("M")[2]
    lh = SIZE + 6
    width = max(900, min(WRAP, max(len(l) for l in lines)) * cw + 2 * PAD)
    title_h = 34
    height = title_h + 2 * PAD + lh * len(lines)
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, title_h], fill=TITLE_BG)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([14 + i * 22, 11, 26 + i * 22, 23], fill=c)
    title = f"kartik@cloud-lab: ~/k8s-assignment  —  {name}"
    d.text(((width - d.textlength(title, font=sans)) / 2, 9), title, fill=(200, 200, 205), font=sans)
    y = title_h + PAD
    prompt = "kartik@cloud-lab:~/k8s-assignment$"
    for l in lines:
        if l.startswith(prompt):
            d.text((PAD, y), prompt, fill=PROMPT, font=fontb)
            d.text((PAD + len(prompt) * cw, y), l[len(prompt):], fill=CMD, font=fontb)
        else:
            d.text((PAD, y), l, fill=FG, font=font)
        y += lh
    out = f"{OUT}/{name}.png"
    img.save(out, optimize=True)
    return out


def add_url_bar(path, url):
    shot = Image.open(path).convert("RGB")
    bar = 48
    img = Image.new("RGB", (shot.width, shot.height + bar), (222, 225, 230))
    d = ImageDraw.Draw(img)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([16 + i * 22, 18, 28 + i * 22, 30], fill=c)
    d.rounded_rectangle([100, 9, shot.width - 20, bar - 9], radius=14, fill=(255, 255, 255))
    d.text((118, 16), url, fill=(40, 40, 40), font=ImageFont.truetype(SANS, 15))
    img.paste(shot, (0, bar))
    img.save(path, optimize=True)


if __name__ == "__main__":
    for p in sorted(glob.glob("evidence/logs/*.txt")):
        print(render(p))
