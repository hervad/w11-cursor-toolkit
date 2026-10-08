"""Cursors from ONE Inkscape master SVG: keep some layers, optionally transform them, optionally rotate
one element per animation frame. See docs/LAYER_SPLITTING_DESIGN.md and ADR-13.

    extract(master_text, ["Arrow", "Info"])                       # composite of two layers
    extract(master_text, ["NS"], transform="matrix(0 1 1 0 0 0)") # transposed copy
    extract(master_text, ["Spinner"], rotate=("g12727", (16.422, 16.421), 30.0))   # one frame

Rules (each violation raises SplitError with a clear message):
* Layers = DIRECT children of <svg> with inkscape:groupmode="layer", matched by exact inkscape:label.
* Every other layer is REMOVED, not hidden: hidden content would still reach the guard and the renderer.
* <defs> is kept; <metadata> and sodipodi:namedview are dropped; any other drawable element outside the
  layers is an error (it would show up in every cursor).
* The output always has an explicit viewBox="0 0 W H" (W/H from width/height, unitless or px, square).
  A master with a DIFFERENT viewBox is an error - overwriting it would silently rescale the art.
* rotate = (element id, (cx, cy) in the element's PARENT coordinates, angle in degrees, clockwise on screen):
  "rotate(a cx cy)" is composed IN FRONT of the element's existing transform, never replacing it.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
INK_NS = "http://www.inkscape.org/namespaces/inkscape"
SODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
_PREFIXES = {
    "": SVG_NS, "xlink": "http://www.w3.org/1999/xlink", "inkscape": INK_NS, "sodipodi": SODI_NS,
    "dc": "http://purl.org/dc/elements/1.1/", "cc": "http://web.resource.org/cc/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}
for _p, _u in _PREFIXES.items():
    ET.register_namespace(_p, _u)  # keep familiar prefixes in the output (ElementTree registry is global)

_LAYER = f"{{{INK_NS}}}groupmode"
_LABEL = f"{{{INK_NS}}}label"
# Inkscape 0.4x files (e.g. Polar, 2006) use an older URI for the sodipodi namespace than later ones (Obsidian).
SODI_NS_OLD = "http://inkscape.sourceforge.net/DTD/sodipodi-0.dtd"
_DROP = {f"{{{SVG_NS}}}metadata", f"{{{SODI_NS}}}namedview", f"{{{SODI_NS_OLD}}}namedview"}
_KEEP_NON_DRAWABLE = {f"{{{SVG_NS}}}{t}" for t in ("defs", "style", "title", "desc")}
_LENGTH = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*(px)?\s*$")


class SplitError(ValueError):
    pass


_FILTER_REF = re.compile(r"url\(\s*#([^)\s]+)\s*\)")


def _filter_ref(el: ET.Element) -> str | None:
    style = el.get("style", "")
    m = re.search(r"(?:^|;)\s*filter\s*:\s*(url\([^)]*\))", style)
    return m.group(1) if m else el.get("filter")


def strip_filtered(svg_text: str) -> tuple[str, int]:
    """Remove every element drawn through an SVG filter (`filter:url(#...)` in style, or a filter attribute), then
    every <filter> no longer referenced. For upstreams that bake their drop shadow in as blurred copies (ADR-14:
    Windows draws its own). Returns (svg, elements removed); with nothing to remove the text is returned unchanged."""
    root = ET.fromstring(svg_text)
    parent = {c: p for p in root.iter() for c in p}
    hits = [el for el in root.iter() if el.tag != f"{{{SVG_NS}}}filter" and _filter_ref(el)]
    if not hits:
        return svg_text, 0
    for el in hits:
        if el in parent:          # an ancestor removed earlier takes its children with it
            try:
                parent[el].remove(el)
            except ValueError:
                pass
    used = {m.group(1) for el in root.iter() for v in el.attrib.values() for m in _FILTER_REF.finditer(v)}
    parent = {c: p for p in root.iter() for c in p}
    for f in [el for el in root.iter(f"{{{SVG_NS}}}filter") if el.get("id") not in used]:
        parent[f].remove(f)
    return ET.tostring(root, encoding="unicode"), len(hits)


def _length(value: str | None, what: str) -> float:
    m = _LENGTH.match(value or "")
    if not m:
        raise SplitError(f"master {what}={value!r}: need a plain number or px (other units would change the scale)")
    return float(m.group(1))


def master_size(root: ET.Element) -> float:
    """Square canvas size in user units; checks width/height/viewBox consistency."""
    w, h = _length(root.get("width"), "width"), _length(root.get("height"), "height")
    if w != h:
        raise SplitError(f"master canvas must be square, got {w:g}x{h:g}")
    vb = root.get("viewBox")
    if vb is not None:
        nums = [float(x) for x in re.split(r"[\s,]+", vb.strip()) if x]
        if nums != [0.0, 0.0, w, h]:
            raise SplitError(f"master viewBox={vb!r} differs from '0 0 {w:g} {h:g}' (width/height) - "
                             "refusing to guess which scale is meant")
    return w


def _set_display_inline(el: ET.Element) -> None:
    parts = [p for p in (el.get("style") or "").split(";") if p.strip() and not p.strip().startswith("display")]
    el.set("style", ";".join(parts + ["display:inline"]))


_OWN_ROTATE = re.compile(r"^\s*rotate\(\s*([-+0-9.eE]+)[\s,]+([-+0-9.eE]+)[\s,]+([-+0-9.eE]+)\s*\)")


def _rotate(target: ET.Element, center: tuple[float, float] | None, angle: float, name: str) -> None:
    """Rotate `target` by `angle` degrees, composed IN FRONT of its existing transform. center=None: about the centre
    of the element's own leading rotate(a, cx, cy) - how ComixCursors animates (sed rotate(0, -> rotate(angle,)."""
    existing = target.get("transform")
    if center is None:
        m = _OWN_ROTATE.match(existing or "")
        if not m:
            raise SplitError(f"{name}: rotate without center needs id {target.get('id')!r} to start its transform "
                             f"with rotate(a, cx, cy); it has {existing!r}")
        center = (float(m.group(2)), float(m.group(3)))
    cx, cy = center
    rot = f"rotate({angle:g} {cx:g} {cy:g})"
    target.set("transform", f"{rot} {existing}" if existing else rot)


def rotate_element(svg_text: str, rid: str, center: tuple[float, float] | None, angle: float, name: str = "svg") -> str:
    """One animation frame of a single-file cursor: rotate the element with id `rid` (see _rotate)."""
    root = ET.fromstring(svg_text)
    target = next((e for e in root.iter() if e.get("id") == rid), None)
    if target is None:
        raise SplitError(f"{name}: rotate id {rid!r} not found")
    _rotate(target, center, angle, name)
    return ET.tostring(root, encoding="unicode")


def layer_labels(master_text: str) -> list[str]:
    root = ET.fromstring(master_text)
    return [g.get(_LABEL) for g in root if g.get(_LAYER) == "layer"]


def extract(master_text: str, layers: list[str], transform: str | None = None,
            rotate: tuple[str, tuple[float, float], float] | None = None, expect_size: float | None = None,
            name: str = "master") -> str:
    root = ET.fromstring(master_text)
    if root.tag != f"{{{SVG_NS}}}svg":
        raise SplitError(f"{name}: root element is not <svg>")
    size = master_size(root)
    if expect_size is not None and size != expect_size:
        raise SplitError(f"{name}: master canvas is {size:g}, but design_canvas is {expect_size:g}")

    top = [c for c in root if c.get(_LAYER) == "layer"]
    labels = [g.get(_LABEL) for g in top]
    dupes = sorted({l for l in labels if labels.count(l) > 1})
    if dupes:
        raise SplitError(f"{name}: duplicate layer label(s) {dupes} - layer names must be unique")
    if len(set(layers)) != len(layers):
        raise SplitError(f"{name}: a layer is listed twice in {layers}")
    missing = [l for l in layers if l not in labels]
    if missing:
        raise SplitError(f"{name}: unknown layer(s) {missing}; available: {labels}")

    ids_in_master = {e.get("id") for e in root.iter() if e.get("id")}
    for child in list(root):
        if child.get(_LAYER) == "layer":
            if child.get(_LABEL) not in layers:
                root.remove(child)                      # REMOVE, not hide
            continue
        if child.tag in _DROP:
            root.remove(child)
        elif child.tag not in _KEEP_NON_DRAWABLE:
            raise SplitError(f"{name}: <{child.tag.split('}')[-1]} id={child.get('id')!r}> is outside every layer "
                             "and would appear in every cursor")
    kept = [g for g in root if g.get(_LAYER) == "layer"]   # master document order = stacking order
    for g in kept:
        _set_display_inline(g)

    if rotate is not None:
        rid, center, angle = rotate
        target = next((e for g in kept for e in g.iter() if e.get("id") == rid), None)
        if target is None:
            where = "not in the master" if rid not in ids_in_master else f"outside the kept layers {layers}"
            raise SplitError(f"{name}: rotate id {rid!r} is {where}")
        _rotate(target, center, angle, name)

    if transform:
        wrapper = ET.Element(f"{{{SVG_NS}}}g", {"transform": transform})
        at = list(root).index(kept[0])
        for g in kept:
            root.remove(g)
            wrapper.append(g)
        root.insert(at, wrapper)

    root.set("viewBox", f"0 0 {size:g} {size:g}")
    return ET.tostring(root, encoding="unicode")
