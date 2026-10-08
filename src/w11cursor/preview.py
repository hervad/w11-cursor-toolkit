"""README preview image, drawn from the BUILT cursor files - the exact layers Windows gets, never re-rendered.

Every row shows a variant's distinct cursors in Windows role order (byte-identical files such as Pin = Link once;
animated cursors show their first frame that is at least 95 % as full as the fullest one: frame 0 for spinners,
the complete shape for build-up animations that start nearly empty). Two layouts, chosen automatically:
  - "panels" (variants differ in at most half the cursors, e.g. a recoloured spinner): the first variant on a light
    and on a dark panel, then - after a thin divider - the other variants' files that differ from the first.
  - "rows" (variants differ in most cursors, e.g. dark/light themes): one row per variant, each on the background
    that contrasts with it (dark cursors on light, light cursors on dark), like the capitaine preview.
Icons are the `size * scale` px layer (default 48 px at 2x = the 96 px layer), so the image stays sharp on HiDPI
screens. A missing layer is an error: a preview must not show a resampled image Windows never draws.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat

from .pack import parse_ani, parse_cur
from .roles import ROLES

PANELS = ((243, 243, 243), (32, 32, 32))      # light, dark background (RGB)
DIVIDER = ((200, 200, 200), (80, 80, 80))     # divider colour per panel


def _visible(img: Image.Image) -> int:
    return sum(img.getchannel("A").histogram()[26:])


def layer(blob: bytes, px: int) -> Image.Image:
    """The px x px image of a .cur, or of an .ani's representative frame (see module docstring), as RGBA."""
    if blob[:4] == b"RIFF":
        frames = [_cur_layer(f, px) for f in parse_ani(blob).frames]
        full = max(_visible(f) for f in frames)
        return next(f for f in frames if _visible(f) >= 0.95 * full)
    return _cur_layer(blob, px)


def _cur_layer(blob: bytes, px: int) -> Image.Image:
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


def _distinct(folder: Path) -> list[Path]:
    seen: set[bytes] = set()
    out = []
    for p in _cursor_files(folder):
        data = p.read_bytes()
        if data not in seen:
            seen.add(data)
            out.append(p)
    return out


def _background(icons: list[Image.Image]) -> int:
    """Index into PANELS that contrasts with the icons: their mean opaque luminance < 128 -> light panel."""
    total = count = 0
    for icon in icons:
        lum, alpha = icon.convert("LA").split()
        mask = alpha.point(lambda v: 255 if v > 127 else 0)
        n = ImageStat.Stat(mask).sum[0] / 255
        if n:
            total += ImageStat.Stat(lum, mask).mean[0] * n
            count += n
    return 0 if count == 0 or total / count < 128 else 1


def layout_for(variant_dirs: list[Path]) -> str:
    main, extra = pick(variant_dirs)
    return "rows" if len(extra) > len(main) // 2 else "panels"


def make_preview(variant_dirs: list[Path], out: Path, size: int = 48, scale: int = 2) -> Path:
    if layout_for(variant_dirs) == "rows":
        return _make_rows(variant_dirs, out, size, scale)
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


def _make_rows(variant_dirs: list[Path], out: Path, size: int, scale: int) -> Path:
    px, gap, pad, radius = size * scale, 20 * scale, 28 * scale, 16 * scale
    rows = [[layer(p.read_bytes(), px) for p in _distinct(d)] for d in variant_dirs]
    n = max(len(r) for r in rows)
    width = 2 * pad + n * px + (n - 1) * gap
    row_h = px + 2 * pad
    canvas = Image.new("RGBA", (width, row_h * len(rows)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for row, icons in enumerate(rows):
        top = row * row_h
        last = row == len(rows) - 1
        draw.rounded_rectangle((0, top, width - 1, top + row_h - 1), radius=radius, fill=PANELS[_background(icons)],
                               corners=(row == 0, row == 0, last, last))
        for i, icon in enumerate(icons):
            canvas.alpha_composite(icon, (pad + i * (px + gap), top + pad))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    return out
