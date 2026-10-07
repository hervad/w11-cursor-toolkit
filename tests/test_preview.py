"""`w11cursor preview`: picks the right files and draws the exact built layers (no cairo needed)."""
import pytest
from PIL import Image

from w11cursor.pack import CursorImage, pack_ani, pack_cur
from w11cursor.preview import layer, layout_for, make_preview, pick
from w11cursor.roles import ROLES

SIZES = (32, 48, 96)


def _cur(rgb, fmt="png", sizes=SIZES) -> bytes:
    return pack_cur([CursorImage(Image.new("RGBA", (n, n), (*rgb, 255)), (0, 0)) for n in sizes], fmt)


def _variant(root, name, spinner_rgb, fmt="png"):
    """Every role gets its own colour; pin/person are byte-identical to link; busy/working are .ani."""
    d = root / name
    d.mkdir()
    for i, r in enumerate(ROLES):
        if r.filename in ("busy", "working"):
            second = (0, 0, 0) if r.filename == "busy" else (50, 50, 50)    # busy and working differ
            frames = [_cur(spinner_rgb, fmt), _cur(second, fmt)]
            (d / f"{r.filename}.ani").write_bytes(pack_ani(frames, [3, 3], rate_mode="auto"))
        else:
            rgb = (10, 20, 30) if r.filename in ("link", "pin", "person") else (i * 10, 100, 200)
            (d / f"{r.filename}.cur").write_bytes(_cur(rgb, fmt))
    return d


@pytest.fixture
def dist(tmp_path):
    return [_variant(tmp_path, "orange", (255, 94, 19)), _variant(tmp_path, "blue", (19, 179, 255))]


def test_pick_dedupes_and_appends_only_differing_variant_files(dist):
    main, extra = pick(dist)
    assert len(main) == 15                               # 17 roles minus pin/person (same bytes as link)
    assert [p.name for p in main if p.name in ("pin.cur", "person.cur")] == []
    assert [(p.parent.name, p.name) for p in extra] == [("blue", "working.ani"), ("blue", "busy.ani")]


def test_layer_png_bmp_and_ani_frame0(tmp_path):
    assert layer(_cur((1, 2, 3)), 48).getpixel((5, 5)) == (1, 2, 3, 255)
    assert layer(_cur((1, 2, 3), "bmp"), 32).getpixel((0, 31)) == (1, 2, 3, 255)
    ani = pack_ani([_cur((9, 9, 9)), _cur((7, 7, 7))], [3, 3], rate_mode="auto")
    assert layer(ani, 96).getpixel((50, 50)) == (9, 9, 9, 255)


def test_missing_layer_is_an_error_not_a_resample():
    with pytest.raises(ValueError, match="no 64 px layer"):
        layer(_cur((1, 2, 3)), 64)


def test_make_preview_size_and_pixels(dist, tmp_path):
    out = make_preview(dist, tmp_path / "docs" / "preview.png")
    img = Image.open(out)
    n, px, gap, pad = 17, 96, 40, 56                       # 15 + 2 extras, at scale 2
    assert img.size == (2 * pad + n * px + (n - 1) * gap + 2 * gap, 2 * (px + 2 * pad))
    assert img.getpixel((pad + 10, pad + 10)) == (0, 100, 200, 255)          # first icon = pointer, exact colour
    assert img.getpixel((5, img.height // 4))[:3] == (243, 243, 243)         # light panel
    assert img.getpixel((5, 3 * img.height // 4))[:3] == (32, 32, 32)        # dark panel
    assert img.getpixel((0, 0))[3] == 0                                       # rounded corner


def test_cli_preview(dist, tmp_path, monkeypatch):
    from w11cursor import cli

    toml = tmp_path / "theme.toml"
    toml.write_text("")
    calls = {}
    monkeypatch.setattr(cli, "_variant_dirs", lambda theme_path, dist_dir: dist)
    monkeypatch.setattr("w11cursor.preview.make_preview",
                        lambda dirs, out, size, scale: calls.update(dirs=dirs, size=size) or out)
    assert cli.main(["preview", str(toml), "--out", str(tmp_path / "p.png")]) == 0
    assert calls == {"dirs": dist, "size": 48}


def _shaded(root, name, grey):
    """A variant whose every cursor differs from the others (all one grey level), pin/person = link."""
    d = root / name
    d.mkdir()
    for i, r in enumerate(ROLES):
        g = grey + (17 if r.filename in ("pin", "person", "link") else i)   # 17: no clash with any role index
        if r.filename in ("busy", "working"):
            frames = [_cur((g, g, g)), _cur((g, g, 0 if r.filename == "busy" else 9))]
            (d / f"{r.filename}.ani").write_bytes(pack_ani(frames, [3, 3], rate_mode="auto"))
        else:
            (d / f"{r.filename}.cur").write_bytes(_cur((g, g, g)))
    return d


def test_mostly_different_variants_get_one_row_each_on_a_contrasting_background(tmp_path):
    dirs = [_shaded(tmp_path, "dark", 20), _shaded(tmp_path, "light", 220)]
    assert layout_for(dirs) == "rows"
    img = Image.open(make_preview(dirs, tmp_path / "p.png"))
    px, gap, pad = 96, 40, 56
    assert img.size == (2 * pad + 15 * px + 14 * gap, 2 * (px + 2 * pad))
    assert img.getpixel((5, img.height // 4))[:3] == (243, 243, 243)        # dark cursors -> light row
    assert img.getpixel((5, 3 * img.height // 4))[:3] == (32, 32, 32)       # light cursors -> dark row
    assert img.getpixel((pad + 10, 3 * img.height // 4))[:3] == (220, 220, 220)


def test_recoloured_spinner_only_keeps_panels(dist):
    assert layout_for(dist) == "panels"
