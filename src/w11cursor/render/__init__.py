"""SVG -> RGBA renderers. Imported lazily so `w11cursor inspect` works on a
Windows box that has no native cairo installed."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

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
    return render(path, size, recolor or {})
