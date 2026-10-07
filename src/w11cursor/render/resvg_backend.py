"""resvg backend (pure wheel via resvg-py, no native deps).

Use it for themes whose SVGs need filters: cairosvg 2.9.1 implements only feOffset/feBlend/feFlood,
so feGaussianBlur shadows come out hard-edged (measured: 8 alpha levels vs resvg's 161 at 128 px).
Choice is per theme ([render] renderer = "resvg"); see docs/DECISIONS.md ADR-12.

Two guards keep it as safe and reproducible as cairosvg's safe mode:
* resvg loads <image> files by absolute path even without resources_dir -> any <image> that is not an
  embedded data: URI is rejected (SVG input must never read other files).
* System fonts are skipped (CI and local machines have different fonts), which would make <text>
  silently disappear -> <text> is rejected; convert text to paths in the SVG.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image

from . import apply_recolor

_IMAGE_TAG = re.compile(r"<image\b[^>]*>", re.S)
_HREF = re.compile(r"""(?:xlink:)?href\s*=\s*["']\s*([^"']*)["']""")


def _check_svg(svg: str, name: str) -> None:
    for tag in _IMAGE_TAG.findall(svg):
        href = _HREF.search(tag)
        if not href or not href.group(1).startswith("data:"):
            raise ValueError(f"{name}: <image> referencing an external file is not allowed: {tag[:120]}")
    if re.search(r"<text\b", svg):
        raise ValueError(f"{name}: contains <text>; convert text to paths (system fonts are not used)")


def render(path: Path, size: int, recolor: dict[str, str]) -> Image.Image:
    import resvg_py

    if not path.exists():
        raise FileNotFoundError(f"SVG not found: {path}")
    svg = apply_recolor(path.read_text(encoding="utf-8"), recolor)
    _check_svg(svg, path.name)
    png = resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size, skip_system_fonts=True)
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    if img.size != (size, size):
        raise ValueError(f"{path.name}: rendered {img.size}, expected {size}x{size} - is the viewBox square?")
    return img
