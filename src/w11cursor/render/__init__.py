"""SVG -> RGBA renderers. Imported lazily so `w11cursor inspect` works on a
Windows box that has no native cairo installed.

Every render goes through ONE pipeline: read -> recolour -> guard.check_svg -> backend.
Backends only ever receive SVG text that passed the guard."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .guard import check_svg

RENDERERS = ("cairosvg", "resvg")


def apply_recolor(svg: str, recolor: dict[str, str]) -> str:
    """Variant recolour = plain text replacement in the SVG source (same for every backend)."""
    for old, new in recolor.items():
        svg = svg.replace(old, new)
    return svg


def render_svg_text(svg: str, name: str, size: int, recolor: dict[str, str] | None = None,
                    renderer: str = "cairosvg") -> Image.Image:
    """SVG text (e.g. a cursor cut from a master by split.py) -> RGBA. `name` is only for messages."""
    if renderer == "cairosvg":
        from .cairo_backend import render
    elif renderer == "resvg":
        from .resvg_backend import render
    else:
        raise ValueError(f"unknown renderer '{renderer}'; valid: {', '.join(RENDERERS)}")
    svg = apply_recolor(svg, recolor or {})
    check_svg(svg, name)
    img = render(svg, size)
    if img.size != (size, size):
        raise ValueError(f"{name}: rendered {img.size}, expected {size}x{size} - is the viewBox square?")
    return img


def render_svg(path: Path, size: int, recolor: dict[str, str] | None = None, renderer: str = "cairosvg") -> Image.Image:
    if renderer not in RENDERERS:
        raise ValueError(f"unknown renderer '{renderer}'; valid: {', '.join(RENDERERS)}")
    if not path.exists():
        raise FileNotFoundError(f"SVG not found: {path}")
    return render_svg_text(path.read_text(encoding="utf-8"), path.name, size, recolor, renderer)
