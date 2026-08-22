# -*- coding: utf-8 -*-
"""assets/GifBox.ico 를 만든다. (아이콘을 바꾸고 싶으면 이 파일을 고치고 다시 실행)

작은 크기(16px)에서도 알아볼 수 있도록, 큰 재생 삼각형을 주 형태로 쓰고
'GIF' 글자는 큰 크기에서만 읽히는 보조 요소로 둡니다.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "assets" / "GifBox.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

BG_TOP = (88, 101, 242)      # 보라빛 파랑
BG_BOTTOM = (56, 66, 180)
MARK = (255, 255, 255)
ACCENT = (255, 138, 60)


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1],
                                        radius=radius, fill=255)
    return m


def gradient(size):
    g = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        g.putpixel((0, y), tuple(round(a + (b - a) * t)
                                 for a, b in zip(BG_TOP, BG_BOTTOM)))
    return g.resize((size, size))


def load_font(px):
    for name in ("arialbd.ttf", "seguibl.ttf", "malgunbd.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg = gradient(size).convert("RGBA")
    img.paste(bg, (0, 0), rounded_mask(size, max(2, round(size * 0.22))))

    d = ImageDraw.Draw(img)
    s = size / 256.0

    # 재생 삼각형 — 작은 크기에서도 형태가 남는 주 요소
    cx, cy = size * 0.47, size * 0.42
    r = size * 0.20
    d.polygon([(cx - r * 0.75, cy - r), (cx - r * 0.75, cy + r), (cx + r, cy)],
              fill=MARK)

    # 아래 'GIF' 띠 — 큰 크기에서만 읽힘
    if size >= 48:
        band_h = size * 0.26
        top = size * 0.66
        d.rounded_rectangle([size * 0.14, top, size * 0.86, top + band_h],
                            radius=band_h / 2, fill=ACCENT)
        font = load_font(max(8, round(band_h * 0.72)))
        text = "GIF"
        box = d.textbbox((0, 0), text, font=font)
        d.text((size / 2 - (box[2] - box[0]) / 2 - box[0],
                top + band_h / 2 - (box[3] - box[1]) / 2 - box[1]),
               text, font=font, fill=(40, 26, 10))
    else:
        # 작은 크기에서는 띠 대신 점 하나로 색만 남긴다
        d.ellipse([size * 0.36, size * 0.72, size * 0.64, size * 0.90], fill=ACCENT)
    return img


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    master = draw_icon(256)
    master.save(OUT, format="ICO",
                sizes=[(s, s) for s in SIZES],
                append_images=[draw_icon(s) for s in SIZES if s != 256])
    print("만들었습니다: %s (%d바이트)" % (OUT, OUT.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
