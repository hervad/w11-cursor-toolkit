"""Single-file rotate animations (centre from the element's own rotate()) and per-variant mirror_hotspots."""
import re
import shutil
from pathlib import Path

import pytest

from w11cursor.config import ConfigError, load_theme
from w11cursor.split import SplitError, rotate_element

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">'
       '<path id="bar" transform="rotate(0,20,10) matrix(1,0,0,1,2,3)" d="M0 0h4v4z"/></svg>')
DEMO = Path(__file__).parents[1] / "examples" / "demo-theme"
# A busy cursor that animates by rotating one element about its own rotate() centre (the ComixCursors technique):
# an off-centre bar, so every 90-degree step puts it in a different quadrant.
SPINNER = ('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">'
           '<rect id="bar" transform="rotate(0,16,16)" x="14" y="2" width="4" height="10" fill="#000"/></svg>')


def _transform(svg, rid="bar"):
    el = re.search(rf'<[^>]*\bid="{rid}"[^>]*>', svg).group(0)
    return re.search(r'transform="([^"]*)"', el).group(1)


def test_rotate_without_center_uses_the_elements_own_rotate():
    assert _transform(rotate_element(SVG, "bar", None, 90)) == "rotate(90 20 10) rotate(0,20,10) matrix(1,0,0,1,2,3)"


def test_rotate_with_explicit_center_wins():
    assert _transform(rotate_element(SVG, "bar", (5, 6), 45)).startswith("rotate(45 5 6) rotate(0,20,10)")


def test_rotate_errors_are_clear():
    with pytest.raises(SplitError, match="rotate id 'nope' not found"):
        rotate_element(SVG, "nope", None, 10)
    plain = SVG.replace('transform="rotate(0,20,10) matrix(1,0,0,1,2,3)"', 'transform="matrix(1,0,0,1,2,3)"')
    with pytest.raises(SplitError, match=r"needs id 'bar' to start its transform with rotate\(a, cx, cy\)"):
        rotate_element(plain, "bar", None, 10)


def _theme(tmp_path, busy=None, mirror="true"):
    """Demo theme copy: busy = single-file rotate animation; extra variant 'lh' with mirror_hotspots."""
    svg = tmp_path / "svg"
    shutil.copytree(DEMO / "svg", svg)
    for notice in DEMO.iterdir():                      # LICENSE etc.: validate requires them in every variant
        if notice.is_file() and notice.name != "theme.toml":
            shutil.copy2(notice, tmp_path / notice.name)
    (svg / "spinner.svg").write_text(SPINNER, encoding="utf-8")
    text = (DEMO / "theme.toml").read_text(encoding="utf-8")
    busy = busy or 'svg = "spinner.svg"\nrotate = { id = "bar", step_deg = 90 }\nframe_count = 4\ndelay = 3'
    text = re.sub(r"\[cursors\.busy\]\n(?:(?!\[).*\n)*", f"[cursors.busy]\n{busy}\nhotspot = [16, 16]\n\n", text, count=1)
    text = text.replace('[[variants]]\nid = "gold"',
                        f'[[variants]]\nid = "lh"\nscheme_name = "Demo LH"\nsvg_dir = "svg"\nmirror_hotspots = {mirror}\n\n'
                        '[[variants]]\nid = "gold"', 1)
    t = tmp_path / "theme.toml"
    t.write_text(text, encoding="utf-8")
    return t


def test_config_accepts_single_svg_rotate_and_mirror(tmp_path):
    theme = load_theme(_theme(tmp_path))
    spec = theme.resolve("busy")
    assert spec.animated and spec.svg == "spinner.svg" and "center" not in spec.rotate
    lh = next(v for v in theme.variants if v.id == "lh")
    arrow = theme.resolve("arrow")
    assert theme.hotspot_for(lh, arrow) == (32 - arrow.hotspot[0], arrow.hotspot[1])
    assert theme.hotspot_for(theme.variants[0], arrow) == tuple(arrow.hotspot)


def test_config_rejects_rotate_on_frames(tmp_path):
    with pytest.raises(ConfigError, match="rotate needs layers or a single svg"):
        load_theme(_theme(tmp_path, busy='frames = "busy-{n:02d}.svg"\nframe_count = 8\nrotate = { id = "bar", step_deg = 45 }'))


def test_config_rejects_non_bool_mirror(tmp_path):
    with pytest.raises(ConfigError, match="mirror_hotspots must be true or false"):
        load_theme(_theme(tmp_path, mirror='"yes"'))


def test_build_rotates_frames_and_mirrors_hotspots(tmp_path):
    from w11cursor.render.cairo_backend import ensure_windows_cairo_path

    ensure_windows_cairo_path()
    pytest.importorskip("cairosvg", exc_type=(ImportError, OSError))
    from w11cursor.build import build_theme
    from w11cursor.pack import parse_ani, parse_cur
    from w11cursor.preview import layer
    from w11cursor.validate import validate_theme

    theme = load_theme(_theme(tmp_path))
    dist = tmp_path / "dist"
    build_theme(theme, dist, only=["light", "lh"], log=lambda *_: None)
    assert validate_theme(theme, dist, only=["light", "lh"]).ok

    # frames: the bar's bounding box moves to a different quadrant every 90 degrees
    ani = parse_ani((dist / "light" / "busy.ani").read_bytes())
    boxes = [layer(f, 32).getchannel("A").getbbox() for f in ani.frames]
    assert len(set(boxes)) == 4

    # mirror: lh arrow hotspot x = 32 - x at 32 px
    x, y = theme.resolve("arrow").hotspot
    light = parse_cur((dist / "light" / "pointer.cur").read_bytes())[0]
    lh = parse_cur((dist / "lh" / "pointer.cur").read_bytes())[0]
    assert light.hotspot == (round(x), round(y)) and lh.hotspot == (round(32 - x), round(y))
