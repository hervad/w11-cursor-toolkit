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


def render_svg(path: Path, size: int, recolor: dict[str, str] | None = None, renderer: str = "cairosvg") -> Image.Image:
    if renderer == "cairosvg":
        from .cairo_backend import render
    elif renderer == "resvg":
        from .resvg_backend import render
    else:
        raise ValueError(f"unknown renderer '{renderer}'; valid: {', '.join(RENDERERS)}")
    if not path.exists():
        raise FileNotFoundError(f"SVG not found: {path}")
    svg = apply_recolor(path.read_text(encoding="utf-8"), recolor or {})
    check_svg(svg, path.name)
    img = render(svg, size)
    if img.size != (size, size):
        raise ValueError(f"{path.name}: rendered {img.size}, expected {size}x{size} - is the viewBox square?")
    return img
