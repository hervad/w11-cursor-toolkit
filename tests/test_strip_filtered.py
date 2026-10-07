"""[render] strip_filtered: drop the elements drawn through a filter (a baked drop shadow, ADR-14), nothing else."""
from pathlib import Path

import pytest

from w11cursor.render import render_svg_text
from w11cursor.split import strip_filtered

FIXTURES = Path(__file__).parent / "fixtures"

SHADOWED = """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">
 <defs>
  <filter id="blur1"><feGaussianBlur stdDeviation=".3"/></filter>
  <filter id="blur2"><feGaussianBlur stdDeviation=".3"/></filter>
  <filter id="kept"><feGaussianBlur stdDeviation="1"/></filter>
 </defs>
 <path id="shadow" style="opacity:0.3;fill:#000000;filter:url(#blur1)" d="M1 2 L10 2 L10 12 Z"/>
 <g id="grp"><circle id="nested-shadow" cx="5" cy="5" r="2" filter="url(#blur2)"/><rect id="art2" width="2" height="2"/></g>
 <path id="art" style="fill:#526d78;opacity:0.25" d="M1 1 L10 1 L10 11 Z"/>
 <rect id="mask-user" width="1" height="1" mask="url(#kept)"/>
</svg>"""


def test_removes_filtered_elements_and_their_unused_filters():
    out, n = strip_filtered(SHADOWED)
    assert n == 2
    for gone in ('id="shadow"', 'id="nested-shadow"', 'id="blur1"', 'id="blur2"'):
        assert gone not in out
    for kept in ('id="art"', 'id="art2"', 'id="grp"', 'id="kept"'):  # 'kept' is still referenced (by mask=)
        assert kept in out


def test_no_filter_returns_the_text_unchanged():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8"/></svg>'
    assert strip_filtered(svg) == (svg, 0)


def test_style_without_filter_url_is_not_a_hit():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8">'
           '<rect style="color-interpolation-filters:sRGB;fill:#000" width="8" height="8"/></svg>')
    assert strip_filtered(svg)[1] == 0


@pytest.mark.parametrize("renderer", ["cairosvg", "resvg"])
def test_rendered_shadow_fixture_is_empty_after_stripping(renderer):
    if renderer == "cairosvg":
        pytest.importorskip("cairosvg", exc_type=(ImportError, OSError))
    svg, n = strip_filtered((FIXTURES / "blur-shadow.svg").read_text(encoding="utf-8"))
    assert n == 1
    img = render_svg_text(svg, "blur-shadow.svg", 64, {}, renderer)
    assert img.getextrema()[3] == (0, 0)          # nothing left to draw: the only shape was the filtered one


def test_config_rejects_non_bool(tmp_path):
    from w11cursor.config import ConfigError, load_theme

    demo = (Path(__file__).parents[1] / "examples" / "demo-theme" / "theme.toml").read_text(encoding="utf-8")
    t = tmp_path / "theme.toml"
    t.write_text(demo.replace("[render]\n", '[render]\nstrip_filtered = "yes"\n', 1), encoding="utf-8")
    with pytest.raises(ConfigError, match="strip_filtered must be true or false"):
        load_theme(t)
