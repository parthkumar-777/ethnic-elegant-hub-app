"""Generates premium placeholder product images (no internet needed)."""
from PIL import Image, ImageDraw, ImageFont
import os, random

OUT = os.path.join(os.path.dirname(__file__), "static", "products")
os.makedirs(OUT, exist_ok=True)

PALETTES = [
    ("#6b1626", "#8a2432", "#d4af37"),  # maroon -> gold
    ("#2c2c2c", "#3f3f3f", "#c9a227"),  # charcoal -> gold
    ("#7a2e3a", "#a5445a", "#e8c15a"),  # rose maroon -> gold
    ("#3b1f2b", "#5c2a3d", "#d4af37"),  # deep plum -> gold
    ("#1f2a2c", "#33403f", "#c9a227"),  # deep teal charcoal -> gold
]


def make_image(filename, label, seed):
    random.seed(seed)
    w, h = 800, 1000
    c1, c2, accent = random.choice(PALETTES)

    def hex2rgb(x):
        x = x.lstrip('#')
        return tuple(int(x[i:i+2], 16) for i in (0, 2, 4))

    top = hex2rgb(c1)
    bottom = hex2rgb(c2)
    gold = hex2rgb(accent)

    img = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # decorative paisley-like circles
    for i in range(6):
        rx = random.randint(60, 220)
        cx = random.randint(0, w)
        cy = random.randint(0, h)
        draw.ellipse([cx - rx, cy - rx, cx + rx, cy + rx], outline=gold, width=2)

    # border frame
    draw.rectangle([20, 20, w - 20, h - 20], outline=gold, width=4)

    # label text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 42)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
        font_small = font

    words = label.split()
    lines, cur = [], ""
    for wrd in words:
        test = (cur + " " + wrd).strip()
        if draw.textlength(test, font=font) > w - 100:
            lines.append(cur)
            cur = wrd
        else:
            cur = test
    if cur:
        lines.append(cur)

    total_h = len(lines) * 55
    y0 = h / 2 - total_h / 2
    for i, ln in enumerate(lines):
        tw = draw.textlength(ln, font=font)
        draw.text(((w - tw) / 2, y0 + i * 55), ln, font=font, fill=(245, 240, 230))

    draw.text((w / 2 - 90, h - 70), "ETHNIC ELEGANT HUB", font=font_small, fill=gold)

    img.save(os.path.join(OUT, filename), quality=90)


if __name__ == "__main__":
    import json
    with open(os.path.join(os.path.dirname(__file__), "products_data.json")) as f:
        products = json.load(f)
    for i, p in enumerate(products):
        make_image(p["image"], p["name"], i)
    print(f"Generated {len(products)} images")
