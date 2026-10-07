"""README preview image, drawn from the BUILT cursor files - the exact layers Windows gets, never re-rendered.

Two rounded panels (light and dark background), one row each:
  - every distinct cursor of the first variant, in Windows role order (byte-identical files such as Pin = Link
    are shown once; animated cursors show frame 0);
  - after a thin divider: the files of the other variants that differ from the first variant (for themes whose
    variants only recolour a few cursors, that is exactly what tells them apart).
Icons are the `size * scale` px layer (default 48 px at 2x = the 96 px layer), so the image stays sharp on HiDPI
screens. A missing layer is an error: a preview must not show a resampled image Windows never draws.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw

from .pack import parse_ani, parse_cur
from .roles import ROLES

PANELS = ((243, 243, 243), (32, 32, 32))      # light, dark background (RGB)
DIVIDER = ((200, 200, 200), (80, 80, 80))     # divider colour per panel


def layer(blob: bytes, px: int) -> Image.Image:
    """The px x px image of a .cur, or of frame 0 of an .ani, decoded as RGBA."""
    if blob[:4] == b"RIFF":
        blob = parse_ani(blob).frames[0]
    for e in parse_cur(blob):
        if e.size != px:
            continue
        payload = blob[e.offset : e.offset + e.nbytes]
        if e.fmt == "png":
            return Image.open(io.BytesIO(payload)).convert("RGBA")
        # BMP layer: BITMAPINFOHEADER + 32-bit BGRA rows, bottom-up (the AND mask after it is ignored).
        hdr = struct.unpack_from("<I", payload, 0)[0]
        img = Image.frombytes("RGBA", (px, px), payload[hdr : hdr + px * px * 4], "raw", "BGRA", 0, -1)
        return img
    raise ValueError(f"no {px} px layer")


def _cursor_files(folder: Path) -> list[Path]:
    out = []
    for r in ROLES:
        for ext in ("cur", "ani"):
            p = folder / f"{r.filename}.{ext}"
            if p.exists():
                out.append(p)
                break
        else:
            raise FileNotFoundError(f"{folder}: no {r.filename}.cur/.ani")
    return out


def pick(variant_dirs: list[Path]) -> tuple[list[Path], list[Path]]:
    """(distinct files of the first variant, files of the other variants that differ from the first)."""
    seen: set[bytes] = set()
    main = []
    for p in _cursor_files(variant_dirs[0]):
        data = p.read_bytes()
        if data not in seen:
            seen.add(data)
            main.append(p)
    first = {p.name: p.read_bytes() for p in _cursor_files(variant_dirs[0])}
    extra = []
    for d in variant_dirs[1:]:
        for p in _cursor_files(d):
            data = p.read_bytes()
            if data != first[p.name] and data not in seen:
                seen.add(data)
                extra.append(p)
    return main, extra


def make_preview(variant_dirs: list[Path], out: Path, size: int = 48, scale: int = 2) -> Path:
    main, extra = pick(variant_dirs)
    px, gap, pad, radius = size * scale, 20 * scale, 28 * scale, 16 * scale
    split = 2 * gap if extra else 0                      # extra room around the divider
    icons = [layer(p.read_bytes(), px) for p in main + extra]
    n = len(icons)
    width = 2 * pad + n * px + (n - 1) * gap + split
    row_h = px + 2 * pad
    canvas = Image.new("RGBA", (width, row_h * len(PANELS)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for row, bg in enumerate(PANELS):
        top = row * row_h
        last = row == len(PANELS) - 1
        draw.rounded_rectangle((0, top, width - 1, top + row_h - 1), radius=radius, fill=bg,
                               corners=(row == 0, row == 0, last, last))
        x = pad
        for i, icon in enumerate(icons):
            if extra and i == len(main):
                line_x = x - gap + (gap + split) // 2
                draw.line((line_x, top + pad, line_x, top + pad + px), fill=DIVIDER[row], width=scale)
                x += split
            canvas.alpha_composite(icon, (x, top + pad))
            x += px + gap
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    return out
