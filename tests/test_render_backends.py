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


BOTH = ["resvg", pytest.param("cairosvg", marks=needs_cairo)]
XLINK = 'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="8" height="8"'


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (0, 255, 0, 255)).save(buf, "PNG")
    return buf.getvalue()


def _render(tmp_path, body: str, renderer: str):
    p = tmp_path / "t.svg"
    p.write_text(f"<svg {XLINK}>{body}</svg>")
    return render_svg(p, 8, renderer=renderer)


def _external_cases(tmp_path):
    (tmp_path / "x.png").write_bytes(_png_bytes())
    ext = (tmp_path / "x.png").as_posix()  # resvg WOULD load this (verified 2026-10-07)
    return {
        "xlink:href image, absolute path": (f'<image width="8" height="8" xlink:href="{ext}"/>', "external reference"),
        "xlink:href image, file:// URI": (f'<image width="8" height="8" xlink:href="file:///{ext}"/>', "external reference"),
        "SVG2 href on <use>, other file": ('<use href="other.svg#shape"/>', "external reference"),
        "xlink:href, http URL": ('<image width="8" height="8" xlink:href="https://example.com/x.png"/>', "external reference"),
        "style attribute url()": ('<rect width="8" height="8" style="fill:url(other.svg#g)"/>', "external CSS url"),
        "presentation attribute url()": ("<rect width=\"8\" height=\"8\" fill=\"url('pattern.svg#p')\"/>", "external CSS url"),
        "<style> url()": ('<style>rect { fill: url("https://example.com/p.svg#p") }</style><rect width="8" height="8"/>',
                          "external CSS url"),
        "<style> @import": ('<style>@import "evil.css";</style><rect width="8" height="8"/>', "@import"),
        "<text>": ('<text y="8">A</text>', "convert text to paths"),
    }


CASES = ["xlink:href image, absolute path", "xlink:href image, file:// URI", "SVG2 href on <use>, other file",
         "xlink:href, http URL", "style attribute url()", "presentation attribute url()", "<style> url()",
         "<style> @import", "<text>"]


@pytest.mark.parametrize("renderer", BOTH)
@pytest.mark.parametrize("case", CASES)
def test_guard_rejects(tmp_path, renderer, case):
    body, message = _external_cases(tmp_path)[case]
    with pytest.raises(ValueError, match=message):
        _render(tmp_path, body, renderer)


@pytest.mark.parametrize("renderer", BOTH)
def test_guard_allows_same_document_and_data_references(tmp_path, renderer):
    data = "data:image/png;base64," + base64.b64encode(_png_bytes()).decode()
    body = ('<defs><linearGradient id="g"><stop offset="0" stop-color="#00FF00"/></linearGradient>'
            '<rect id="r" width="4" height="8"/></defs>'
            '<use xlink:href="#r" style="fill:url(#g)"/>'                      # internal href + internal url()
            f'<image x="4" width="4" height="8" xlink:href="{data}"/>')        # embedded image
    img = _render(tmp_path, body, renderer)
    assert img.getpixel((1, 4)) == (0, 255, 0, 255) and img.getpixel((6, 4)) == (0, 255, 0, 255)


def test_unknown_renderer_is_an_error(tmp_path):
    p = tmp_path / "red.svg"
    p.write_text(RECOLOR_SVG)
    with pytest.raises(ValueError, match="unknown renderer"):
        render_svg(p, 32, renderer="inkscape")
