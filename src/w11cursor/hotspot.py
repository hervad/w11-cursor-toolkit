"""Hotspot scaling.

A hotspot is stored ONCE per cursor in design space (the SVG's nominal canvas,
e.g. 24 or 32) and derived for every output size.

Two modes (theme.toml  [render] hotspot_mode):

* "point" (default) - the hotspot is a GEOMETRIC point in SVG coordinates, e.g. the
  vertex of the arrow tip.  out = round(v * size / canvas)
  This is what the validated capitaine-cursors-w11-hidpi build used
  (design (4,2)@24 -> (5,3)@32 ... (21,11)@128) and keeps arrow tips exact.

* "center" - the hotspot names a design PIXEL and we map that pixel's centre:
  out = round((v + 0.5) * size / canvas - 0.5)
  Use it for art whose feature sits in the middle of a pixel (1px crosshair lines).

Analogy: "point" maps a street corner between two map scales; "center" maps the
middle of a building. For an arrow tip you want the corner - the building-centre
rule drifts 4 px down-right by the 256 px layer.
"""
from __future__ import annotations

MODES = ("point", "center")


def scale_hotspot(design_xy: tuple[float, float], canvas: int, size: int, mode: str = "point") -> tuple[int, int]:
    if canvas <= 0 or size <= 0:
        raise ValueError("canvas and size must be positive")
    if mode not in MODES:
        raise ValueError(f"hotspot mode must be one of {MODES}")

    def one(v: float) -> int:
        out = round(v * size / canvas) if mode == "point" else round((v + 0.5) * size / canvas - 0.5)
        return max(0, min(size - 1, out))

    return one(design_xy[0]), one(design_xy[1])
