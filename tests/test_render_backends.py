"""Renderer backends: blur support (resvg vs cairosvg), identical recolour, resvg safety guards."""
import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from w11cursor.render import render_svg
from w11cursor.render.cairo_backend import ensure_windows_cairo_path

FIXTURES = Path(__file__).parent / "fixtures"

ensure_windows_cairo_path()
try:
    import cairosvg  # noqa: F401
    HAVE_CAIRO = True
except (ImportError, OSError):  # pragma: no cover - depends on host
    HAVE_CAIRO = False
needs_cairo = pytest.mark.skipif(not HAVE_CAIRO, reason="native cairo not available")


def alpha_levels(img: Image.Image) -> int:
    # Proxy for "soft shadow": a Gaussian falloff spreads the edge over many pixels with smoothly
    # changing alpha (many distinct levels); an unblurred pixel-aligned edge has only 0 and 255.
    return sum(1 for count in img.getchannel("A").histogram() if count)


def test_resvg_renders_gaussian_blur_softly():
    img = render_svg(FIXTURES / "blur-shadow.svg", 128, renderer="resvg")
    assert alpha_levels(img) >= 128  # measured 243 with resvg-py 0.5.0


@needs_cairo
def test_cairosvg_ignores_gaussian_blur():
    # cairosvg 2.9.1 implements only feOffset/feBlend/feFlood: the square comes out hard-edged.
    # If this ever fails, cairosvg gained blur support - revisit ADR-12.
    img = render_svg(FIXTURES / "blur-shadow.svg", 128, renderer="cairosvg")
    assert alpha_levels(img) <= 4  # measured 2 (0 and 255)


RECOLOR_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">'
               '<rect width="32" height="32" fill="#FF0000"/></svg>')


@pytest.mark.parametrize("renderer", ["resvg", pytest.param("cairosvg", marks=needs_cairo)])
def test_recolor_is_the_same_for_every_backend(tmp_path, renderer):
    p = tmp_path / "red.svg"
    p.write_text(RECOLOR_SVG)
    img = render_svg(p, 32, {"#FF0000": "#00FF00"}, renderer)
    assert img.getpixel((16, 16)) == (0, 255, 0, 255)


def _svg_with_image(href: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="8" height="8"><image width="8" height="8" xlink:href="{href}"/></svg>')


def test_resvg_rejects_external_image(tmp_path):
    # resvg would load this file by absolute path even without resources_dir (verified 2026-10-07).
    Image.new("RGBA", (8, 8), (0, 255, 0, 255)).save(tmp_path / "x.png")
    p = tmp_path / "ext.svg"
    p.write_text(_svg_with_image((tmp_path / "x.png").as_posix()))
    with pytest.raises(ValueError, match="external file"):
        render_svg(p, 8, renderer="resvg")


def test_resvg_allows_embedded_data_image(tmp_path):
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (0, 255, 0, 255)).save(buf, "PNG")
    p = tmp_path / "embedded.svg"
    p.write_text(_svg_with_image("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()))
    assert render_svg(p, 8, renderer="resvg").getpixel((4, 4)) == (0, 255, 0, 255)


def test_resvg_rejects_text(tmp_path):
    # System fonts are skipped for reproducibility, so <text> would silently vanish.
    p = tmp_path / "text.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><text y="20">A</text></svg>')
    with pytest.raises(ValueError, match="convert text to paths"):
        render_svg(p, 32, renderer="resvg")


def test_unknown_renderer_is_an_error(tmp_path):
    p = tmp_path / "red.svg"
    p.write_text(RECOLOR_SVG)
    with pytest.raises(ValueError, match="unknown renderer"):
        render_svg(p, 32, renderer="inkscape")
