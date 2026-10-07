"""Layer splitting + frames from rotation (split.py, ADR-13), on tests/fixtures/layers.svg (16x16, no viewBox).

Fixture layers: A red square 0..8 (via <defs> gradient) | B hidden blue square 4..12 | T hidden <text>
| S grey disc r=7 at (8,8) + green bar "bar" x7..9 y2..14 | U green bar in group "moved" that already has
transform="translate(4 0)" (own coords x3..5 -> parent coords x7..9, y2..8).
"""
import io
import struct
from pathlib import Path

import pytest
from PIL import Image

from w11cursor.config import ConfigError, load_theme
from w11cursor.render import render_svg_text
from w11cursor.render.cairo_backend import ensure_windows_cairo_path
from w11cursor.split import SplitError, extract, layer_labels

FIXTURE = Path(__file__).parent / "fixtures" / "layers.svg"
MASTER = FIXTURE.read_text(encoding="utf-8")

ensure_windows_cairo_path()
try:
    import cairosvg  # noqa: F401
    HAVE_CAIRO = True
except (ImportError, OSError):  # pragma: no cover - depends on host
    HAVE_CAIRO = False
BOTH = ["resvg", pytest.param("cairosvg", marks=pytest.mark.skipif(not HAVE_CAIRO, reason="no native cairo"))]

RED, BLUE, GREEN, GREY, CLEAR = (255, 0, 0, 255), (0, 0, 255, 255), (0, 255, 0, 255), (128, 128, 128, 255), None


def px(img, x, y):
    p = img.getpixel((x, y))
    return CLEAR if p[3] == 0 else p


def render(svg, renderer, recolor=None):
    return render_svg_text(svg, "fixture", 16, recolor, renderer)


# --- what the splitter writes ------------------------------------------------------------------------

def test_removes_other_layers_and_writes_viewbox():
    out = extract(MASTER, ["A"])
    for gone in ("layerB", "layerT", "layerS", "layerU", "namedview", "metadata", "<text"):
        assert gone not in out, gone
    assert 'viewBox="0 0 16 16"' in out and "display:inline" in out and 'id="gA"' in out  # <defs> kept


@pytest.mark.parametrize("renderer", BOTH)
def test_single_layer_renders_only_that_layer(renderer):
    img = render(extract(MASTER, ["A"]), renderer)  # the guard passes: T's <text> was removed, not hidden
    assert px(img, 2, 2) == RED and px(img, 10, 10) is CLEAR


@pytest.mark.parametrize("renderer", BOTH)
def test_composite_stacks_in_master_order_not_list_order(renderer):
    img = render(extract(MASTER, ["B", "A"]), renderer)
    assert px(img, 2, 2) == RED and px(img, 10, 10) == BLUE
    assert px(img, 6, 6) == BLUE  # overlap: B comes after A in the master, so B is on top


@pytest.mark.parametrize("renderer", BOTH)
def test_transform_wraps_kept_layers(renderer):
    img = render(extract(MASTER, ["A"], transform="rotate(90 8 8)"), renderer)
    assert px(img, 12, 2) == RED and px(img, 2, 2) is CLEAR  # (x, y) -> (16 - y, x)


@pytest.mark.parametrize("renderer", BOTH)
def test_rotation_frames_turn_only_the_bar(renderer):
    f0 = render(extract(MASTER, ["S"], rotate=("bar", (8, 8), 0)), renderer)
    f90 = render(extract(MASTER, ["S"], rotate=("bar", (8, 8), 90)), renderer)
    assert px(f0, 8, 3) == GREEN and px(f0, 3, 8) == GREY       # vertical bar
    assert px(f90, 3, 8) == GREEN and px(f90, 8, 3) == GREY     # horizontal bar (clockwise on screen)
    assert px(f0, 4, 4) == px(f90, 4, 4) == GREY                 # the disc does not move


@pytest.mark.parametrize("renderer", BOTH)
def test_rotation_is_composed_in_front_of_an_existing_transform(renderer):
    out = extract(MASTER, ["U"], rotate=("moved", (8, 8), 90))
    assert 'transform="rotate(90 8 8) translate(4 0)"' in out   # kept, not replaced
    img = render(out, renderer)
    # correct: translate first (bar at x7..9, y2..8 above the centre), then rotate about (8,8) -> x8..14, y7..9
    assert px(img, 12, 8) == GREEN
    # replacing the transform would put the bar elsewhere; composing it AFTER would put it at x12..18, y3..5
    assert px(img, 8, 4) is CLEAR and px(img, 13, 4) is CLEAR


@pytest.mark.parametrize("renderer", BOTH)
def test_recolor_applies_after_split(renderer):
    img = render(extract(MASTER, ["A"]), renderer, {"#FF0000": "#00FF00"})  # stop colour inside <defs>
    assert px(img, 2, 2) == GREEN


def test_layer_labels():
    assert layer_labels(MASTER) == ["A", "B", "T", "S", "U"]


# --- errors ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("master, kwargs, message", [
    (MASTER, {"layers": ["Nope"]}, r"unknown layer\(s\) \['Nope'\]; available: \['A', 'B', 'T', 'S', 'U'\]"),
    (MASTER.replace('inkscape:label="B"', 'inkscape:label="A"'), {"layers": ["A"]}, "duplicate layer label"),
    (MASTER, {"layers": ["A", "A"]}, "listed twice"),
    (MASTER, {"layers": ["A"], "rotate": ("bar", (8, 8), 90)}, "outside the kept layers"),
    (MASTER, {"layers": ["S"], "rotate": ("nope", (8, 8), 90)}, "not in the master"),
    (MASTER.replace('width="16"', 'width="16mm"'), {"layers": ["A"]}, "plain number or px"),
    (MASTER.replace('height="16"', 'height="20"'), {"layers": ["A"]}, "square"),
    (MASTER.replace('height="16">', 'height="16" viewBox="0 0 32 32">'), {"layers": ["A"]}, "differs from '0 0 16 16'"),
    (MASTER.replace("</svg>", '<rect id="stray" width="1" height="1"/></svg>'), {"layers": ["A"]}, "outside every layer"),
    (MASTER, {"layers": ["A"], "expect_size": 32}, "design_canvas is 32"),
])
def test_errors(master, kwargs, message):
    with pytest.raises(SplitError, match=message):
        extract(master, **kwargs)


def test_old_inkscape_sodipodi_namespace_is_dropped_too():
    # Polar (Inkscape 0.4x) uses http://inkscape.sourceforge.net/DTD/sodipodi-0.dtd for sodipodi:namedview
    old = MASTER.replace("http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
                         "http://inkscape.sourceforge.net/DTD/sodipodi-0.dtd")
    assert "namedview" not in extract(old, ["A"])


def test_matching_viewbox_and_px_units_are_accepted():
    m = MASTER.replace('width="16"', 'width="16px"').replace('height="16">', 'height="16" viewBox="0 0 16 16">')
    assert 'viewBox="0 0 16 16"' in extract(m, ["A"])


# --- theme.toml + build ------------------------------------------------------------------------------

def _theme(tmp_path, cursors: str, extra: str = "") -> Path:
    others = "\n".join(f'[cursors.{k}]\nsame_as = "arrow"' for k in
                       ("help", "precision", "text", "handwriting", "unavailable", "vert", "dgn1", "dgn2",
                        "move", "alternate", "link", "pin", "person"))
    (tmp_path / "LICENSE").write_text("MIT")
    p = tmp_path / "theme.toml"
    p.write_text(f"""schema = 1
[theme]
slug = "layers"
name = "Layers test"
version = "0.0.1"
license = "MIT"
[render]
renderer = "resvg"
design_canvas = 16
[source]
master = "{FIXTURE.as_posix()}"
[sizes]
static = [16, 32]
animated = [16, 32]
[[variants]]
id = "default"
scheme_name = "Layers Test"
{extra}
{cursors}
{others}
""")
    return p


CURSORS = """[cursors.arrow]
layers = ["A"]
hotspot = [0, 0]
[cursors.busy]
layers = ["S"]
rotate = { id = "bar", center = [8, 8], step_deg = 45 }
frame_count = 4
delay = [4, 3, 4, 3]
hotspot = [8, 8]
[cursors.working]
same_as = "busy"
[cursors.horz]
layers = ["U"]
transform = "rotate(90 8 8)"
hotspot = [8, 8]
"""


def _cur_images(blob: bytes) -> dict[int, Image.Image]:
    """PNG layers of a .cur (ICONDIR + 16-byte entries), keyed by size."""
    n = struct.unpack_from("<H", blob, 4)[0]
    out = {}
    for i in range(n):
        w, _h, _c, _r, _hx, _hy, size, off = struct.unpack_from("<BBBBHHII", blob, 6 + 16 * i)
        out[w or 256] = Image.open(io.BytesIO(blob[off:off + size])).convert("RGBA")
    return out


def test_master_theme_builds_and_validates(tmp_path):
    from w11cursor.build import build_theme
    from w11cursor.pack import parse_ani
    from w11cursor.validate import validate_theme

    theme = load_theme(_theme(tmp_path, CURSORS))
    # regression: validating `rotate` once reused the variable holding [render] -> renderer/canvas fell to defaults
    assert (theme.renderer, theme.design_canvas) == ("resvg", 16)
    build_theme(theme, tmp_path / "dist", log=lambda *_: None)
    rep = validate_theme(theme, tmp_path / "dist")
    assert rep.ok, rep.errors
    info = parse_ani((tmp_path / "dist" / "default" / "busy.ani").read_bytes())
    assert info.n_frames == 4 and info.rates == [4, 3, 4, 3]
    f0, f2 = (_cur_images(info.frames[i])[16] for i in (0, 2))   # 0 deg vs 90 deg
    assert px(f0, 8, 3) == GREEN and px(f2, 3, 8) == GREEN


def test_static_override_wins_over_master_layers(tmp_path):
    from w11cursor.build import build_cursor

    theme = load_theme(_theme(tmp_path, CURSORS))
    (tmp_path / "overrides" / "_all").mkdir(parents=True)
    (tmp_path / "overrides" / "_all" / "arrow.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
        '<rect width="16" height="16" fill="#0000FF"/></svg>')
    blob, _ = build_cursor(theme, theme.variants[0], "arrow")
    assert px(_cur_images(blob)[16], 2, 2) == BLUE


FILLER = """[cursors.busy]
same_as = "arrow"
[cursors.working]
same_as = "arrow"
[cursors.horz]
same_as = "arrow"
"""


@pytest.mark.parametrize("cursors, message", [
    ('[cursors.arrow]\nlayers = ["A"]\nrotate = { id = "bar", center = [8, 8], step_deg = 45 }\nhotspot = [0, 0]',
     "rotate needs frame_count"),
    ('[cursors.arrow]\nsvg = "a.svg"\ntransform = "rotate(90)"\nhotspot = [0, 0]', "only work together with layers"),
    ('[cursors.arrow]\nlayers = ["A"]\nsvg = "a.svg"\nhotspot = [0, 0]', "exactly one of"),
    ('[cursors.arrow]\nlayers = []\nhotspot = [0, 0]', "non-empty list"),
    ('[cursors.arrow]\nlayers = ["A"]\nrotate = { id = "bar", centre = [8, 8], step_deg = 45 }\nframe_count = 2\n'
     'hotspot = [0, 0]', r"rotate = \{ id"),
])
def test_config_errors(tmp_path, cursors, message):
    with pytest.raises(ConfigError, match=message):
        load_theme(_theme(tmp_path, cursors + "\n" + FILLER))


def test_layers_need_a_master(tmp_path):
    p = _theme(tmp_path, CURSORS)
    text = (p.read_text().replace("[source]\n", "").replace(f'master = "{FIXTURE.as_posix()}"\n', "")
            .replace('scheme_name = "Layers Test"', 'scheme_name = "Layers Test"\nsvg_dir = "."'))
    p.write_text(text)
    with pytest.raises(ConfigError, match=r"needs \[source\] master"):
        load_theme(p)
