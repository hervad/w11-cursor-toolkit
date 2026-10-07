"""Size probe: a cursor whose every layer draws ITS OWN pixel size as digits.

Install it as "Normal Select", move the pointer-size slider / display scale, and
the cursor literally tells you which layer Windows picked. If the number shown is
not what you expected, or the digits look blurry, Windows resampled.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .pack import CursorImage, pack_cur
from .sizes import STATIC_SIZES

# Extra odd sizes so we can SEE when Windows asks for something we didn't expect.
# 84/100/140/168/200 make 125 % and 175 % (the scales where the exact and bucketed models DISAGREE) fully covered.
PROBE_SIZES = tuple(sorted(set(STATIC_SIZES) | {36, 44, 60, 84, 88, 100, 104, 120, 140, 168, 176, 200, 208, 240}))


def probe_layer(n: int) -> Image.Image:
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = n / 32
    arrow = [(0, 0), (0, 22 * s), (6 * s, 16 * s), (15 * s, 15 * s)]
    d.polygon(arrow, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    font = ImageFont.load_default(size=max(7, int(n * 0.34)))
    text = str(n)
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    x, y = n - tw - 1 - box[0], n - th - 1 - box[1]
    d.rectangle((x + box[0] - 1, y + box[1] - 1, n - 1, n - 1), fill=(220, 0, 90, 255))
    d.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return img


def make_probe(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    blob = pack_cur([CursorImage(probe_layer(n), (0, 0)) for n in PROBE_SIZES])
    p = out / "size-probe.cur"
    p.write_bytes(blob)
    return p
