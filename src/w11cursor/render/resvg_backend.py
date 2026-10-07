"""resvg backend (pure wheel via resvg-py, no native deps).

Use it for themes whose SVGs need filters: cairosvg 2.9.1 implements only feOffset/feBlend/feFlood,
so feGaussianBlur shadows come out hard-edged (measured: 2 alpha levels vs resvg's 243 at 128 px on
tests/fixtures/blur-shadow.svg). Choice is per theme ([render] renderer = "resvg"); see ADR-12.

resvg has no "safe mode": it loads <image> files by absolute path even without resources_dir.
That is why render_svg() runs guard.check_svg() on the text before it gets here.
System fonts are skipped so builds don't depend on the machine's fonts (the guard rejects <text>).
"""
from __future__ import annotations

import io

from PIL import Image


def render(svg: str, size: int) -> Image.Image:
    import resvg_py

    png = resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size, skip_system_fonts=True)
    return Image.open(io.BytesIO(png)).convert("RGBA")
