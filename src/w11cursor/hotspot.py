"""Hotspot scaling.

A hotspot is stored ONCE per cursor in design space (the SVG's nominal canvas,
e.g. 24 or 32) and derived for every output size.

Three modes (theme.toml  [render] hotspot_mode):

* "point" (default) - the hotspot is a GEOMETRIC point in SVG coordinates, e.g. the
  vertex of the arrow tip.  out = round(v * size / canvas)
  (Polar, Material, Future and Comix use it; capitaine and Layan Gold use "pixel", as their own v2 builds did.)

* "pixel" - the hotspot is a geometric point and we take the output PIXEL THAT CONTAINS it:
  out = floor(v * size / canvas). For fractional points measured at a visible tip (Layan Gold v2:
  (4.78, 5.66) -> (4, 5) at 32 px, the pixel the tip lies in; "point" would round to (5, 6)).

* "center" - the hotspot names a design PIXEL and we map that pixel's centre:
  out = round((v + 0.5) * size / canvas - 0.5)
  Use it for art whose feature sits in the middle of a pixel (1px crosshair lines).

Analogy: "point" maps a street corner between two map scales; "center" maps the
middle of a building. For an arrow tip you want the corner - the building-centre
rule drifts 4 px down-right by the 256 px layer.
"""
from __future__ import annotations

import math

MODES = ("point", "pixel", "center")


def scale_hotspot(design_xy: tuple[float, float], canvas: int, size: int, mode: str = "point") -> tuple[int, int]:
    if canvas <= 0 or size <= 0:
        raise ValueError("canvas and size must be positive")
    if mode not in MODES:
        raise ValueError(f"hotspot mode must be one of {MODES}")

    def one(v: float) -> int:
        if mode == "point":
            out = round(v * size / canvas)
        elif mode == "pixel":
            out = math.floor(v * size / canvas)
        else:
            out = round((v + 0.5) * size / canvas - 0.5)
        return max(0, min(size - 1, out))

    return one(design_xy[0]), one(design_xy[1])
