"""[[checks]] (v0.6.0): colour maths, config parsing, and validate on a built demo theme."""
from pathlib import Path

import pytest

from w11cursor.colour import contrast, delta_e, delta_e_2000, relative_luminance
from w11cursor.config import ConfigError, load_theme

DEMO = Path(__file__).parents[1] / "examples" / "demo-theme" / "theme.toml"


# ── colour maths ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_wcag_contrast_and_luminance():
    assert relative_luminance((255, 255, 255)) == pytest.approx(1.0)
    assert relative_luminance((0, 0, 0)) == pytest.approx(0.0)
    assert contrast((255, 255, 255), (0, 0, 0)) == pytest.approx(21.0)
    assert contrast((0x3d, 0xae, 0xe9), (0x3d, 0xae, 0xe9)) == pytest.approx(1.0)
    # Capitaine's own numbers (Dark's Unavailable: #ed1515 sign on #fff disc)
    assert contrast((0xed, 0x15, 0x15), (255, 255, 255)) == pytest.approx(4.45, abs=0.01)


@pytest.mark.parametrize("lab1, lab2, expected", [      # Sharma, Wu & Dalal (2005) test data
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
])
def test_ciede2000_reference_pairs(lab1, lab2, expected):
    assert delta_e_2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)


def test_delta_e_same_hue_vs_different_hue():
    # Tokyo Night 3.2.0: dot == body -> 0; Rose Pine: 1.01:1 contrast but clearly different hue
    assert delta_e((0x7a, 0xa2, 0xf7), (0x7a, 0xa2, 0xf7)) == pytest.approx(0.0)
    assert contrast((0x9c, 0xcf, 0xd8), (0xeb, 0xbc, 0xba)) < 1.1
    assert delta_e((0x9c, 0xcf, 0xd8), (0xeb, 0xbc, 0xba)) > 30


# ── config ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _demo(tmp_path, checks: str):
    text = DEMO.read_text().replace('svg_dir = "svg"', f'svg_dir = "{(DEMO.parent / "svg").as_posix()}"')
    root = tmp_path / "theme"
    root.mkdir(exist_ok=True)
    (root / "LICENSE").write_text("licence text")
    (root / "theme.toml").write_text(text + "\n" + checks)
    return load_theme(root / "theme.toml")


def test_checks_parse(tmp_path):
    t = _demo(tmp_path, '[[checks]]\nname = "body vs outline"\nrole = "arrow"\na = [6, 14]\nb = [3, 12]\n'
                        'min_contrast = 3\nexempt = ["gold"]\n')
    (c,) = t.checks
    assert (c.role, c.metric, c.limit, c.a, c.b, c.size, c.frame, c.exempt) == \
        ("arrow", "min_contrast", 3.0, (6.0, 14.0), (3.0, 12.0), 64, 0, ("gold",))


@pytest.mark.parametrize("body, message", [
    ('role = "nope"\na = [1, 1]\nmin_luminance = 0.5', "unknown role"),
    ('role = "arrow"\na = [1, 1]', "exactly one of"),
    ('role = "arrow"\na = [1, 1]\nb = [2, 2]\nmin_contrast = 3\nmin_delta_e = 15', "exactly one of"),
    ('role = "arrow"\na = [1, 1]\nmin_contrast = 3', "add b"),
    ('role = "arrow"\na = [1, 1]\nb = [2, 2]\nmin_luminance = 0.5', "remove b"),
    ('role = "arrow"\na = [1]\nmin_luminance = 0.5', "must be \\[x, y\\]"),
    ('role = "arrow"\na = [1, 1]\nmin_luminance = 0.5\nexempt = ["ghost"]', "unknown variant"),
    ('role = "arrow"\na = [1, 1]\nmin_luminance = 0.5\nsize = 0', "size must be"),
    ('role = "arrow"\na = [1, 1]\nmin_luminance = 0.5\ncolour = "x"', "unknown key"),
])
def test_bad_checks_are_config_errors(tmp_path, body, message):
    with pytest.raises(ConfigError, match=message):
        _demo(tmp_path, f'[[checks]]\nname = "x"\n{body}\n')


# ── validate on built files (needs a renderer, like the other e2e tests) ─────────────────────────────────────────
def _build(t, tmp_path):
    from w11cursor.render.cairo_backend import ensure_windows_cairo_path

    ensure_windows_cairo_path()
    try:
        import cairosvg  # noqa: F401
    except (ImportError, OSError) as exc:  # pragma: no cover
        pytest.skip(f"native cairo not available: {exc}")
    from w11cursor.build import build_theme

    dist = tmp_path / "dist"
    build_theme(t, dist, log=lambda *_: None)
    return dist


def test_checks_pass_fail_exempt_and_off_shape(tmp_path):
    from w11cursor.validate import validate_theme

    # demo arrow (32 units): body interior (6, 14) is white (gold variant #F3D58A), stroke on x = 3 is #1E1E1E
    t = _demo(tmp_path, """
[[checks]]
name = "body vs outline"
role = "arrow"
a = [6, 14]
b = [3, 12]
min_contrast = 3

[[checks]]
name = "body is light"
role = "arrow"
a = [6, 14]
min_luminance = 0.9

[[checks]]
name = "two body points differ"
role = "arrow"
a = [6, 14]
b = [7, 16]
min_delta_e = 15
exempt = ["gold"]

[[checks]]
name = "off the shape"
role = "arrow"
a = [28, 4]
max_luminance = 0.5
exempt = ["gold"]
""")
    dist = _build(t, tmp_path)
    errs = validate_theme(t, dist).errors
    # passes: contrast for both variants; luminance for light (white = 1.0)
    assert not any("'body vs outline'" in e for e in errs), errs
    assert not any(e.startswith("light/") and "'body is light'" in e for e in errs), errs
    # fails: gold body #F3D58A has luminance 0.68 < 0.9
    assert any(e.startswith("gold/pointer.cur: check 'body is light': 0.68 < 0.9 (#f3d58a)") for e in errs), errs
    # fails for light only (gold exempt): same colour twice -> dE 0 < 15
    assert any(e.startswith("light/pointer.cur: check 'two body points differ': 0.00 dE00 < 15 dE00") for e in errs)
    assert not any(e.startswith("gold/") and "'two body points differ'" in e for e in errs), errs
    # a point on the transparent background is an error of its own, not a silent pass
    assert any(e.startswith("light/pointer.cur: check 'off the shape': point a") and "not opaque" in e for e in errs)
