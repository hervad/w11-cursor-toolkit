"""End-to-end: build the demo theme and validate it. Skips if native cairo is missing."""
from pathlib import Path

import pytest

# importorskip only catches ImportError, but a missing libcairo-2.dll on Windows raises
# OSError from cairocffi - so probe it ourselves and skip cleanly in both cases.
from w11cursor.render.cairo_backend import ensure_windows_cairo_path  # noqa: E402

ensure_windows_cairo_path()  # same MSYS2 auto-detection the real build uses
try:
    import cairosvg  # noqa: F401
except (ImportError, OSError) as exc:  # pragma: no cover - depends on host
    pytest.skip(f"native cairo not available: {exc}", allow_module_level=True)

from w11cursor.build import build_theme  # noqa: E402
from w11cursor.config import load_theme  # noqa: E402
from w11cursor.validate import validate_theme  # noqa: E402

DEMO = Path(__file__).parents[1] / "examples" / "demo-theme" / "theme.toml"


def test_demo_builds_and_validates(tmp_path):
    theme = load_theme(DEMO)
    zips = build_theme(theme, tmp_path, only=["light"], log=lambda *_: None)
    assert len(zips) == 1 and zips[0].stat().st_size > 0
    rep = validate_theme(theme, tmp_path, only=["light"])
    assert rep.ok, rep.errors


def test_validator_catches_tampering(tmp_path):
    theme = load_theme(DEMO)
    build_theme(theme, tmp_path, only=["light"], log=lambda *_: None)
    (tmp_path / "light" / "pin.cur").unlink()
    rep = validate_theme(theme, tmp_path, only=["light"])
    assert any("pin.cur: missing" in e for e in rep.errors)


def test_validator_catches_delay_mismatch(tmp_path):
    from w11cursor.pack import pack_ani, parse_ani

    theme = load_theme(DEMO)  # busy: 8 frames, delay 4
    build_theme(theme, tmp_path, only=["light"], log=lambda *_: None)
    busy = tmp_path / "light" / "busy.ani"
    info = parse_ani(busy.read_bytes())
    busy.write_bytes(pack_ani(info.frames, 5, theme.ani_order))  # same frames, wrong uniform delay
    rep = validate_theme(theme, tmp_path, only=["light"])
    assert any("busy.ani: delays [5, 5, 5, 5, 5, 5, 5, 5] != [4, 4, 4, 4, 4, 4, 4, 4]" in e for e in rep.errors)
    assert any("busy.ani: anih default rate 5 != 4" in e for e in rep.errors)


def _theme_copy(tmp_path, notices: dict[str, str]):
    """Demo theme in a temp root (SVGs still read from the demo) with the given notice files."""
    root = tmp_path / "theme"
    root.mkdir()
    svg = (DEMO.parent / "svg").as_posix()
    (root / "theme.toml").write_text(DEMO.read_text().replace('svg_dir = "svg"', f'svg_dir = "{svg}"'))
    for name, text in notices.items():
        (root / name).write_text(text)
    return load_theme(root / "theme.toml"), tmp_path / "dist"


def test_notice_files_ship_in_folder_and_zip(tmp_path):
    import zipfile

    theme, dist = _theme_copy(tmp_path, {"LICENSE": "gpl text", "COPYRIGHT": "notice", "AUTHORS": "a"})
    (zp,) = build_theme(theme, dist, only=["light"], log=lambda *_: None)
    assert validate_theme(theme, dist, only=["light"]).ok
    names = {n.split("/")[-1] for n in zipfile.ZipFile(zp).namelist()}
    assert {"LICENSE", "COPYRIGHT", "AUTHORS"} <= names

    # COPYRIGHT exists in the theme root -> a zip without it must fail
    with zipfile.ZipFile(zp) as z:
        keep = [(i, z.read(i)) for i in z.infolist() if not i.filename.endswith("/COPYRIGHT")]
    with zipfile.ZipFile(zp, "w") as z:
        for info, data in keep:
            z.writestr(info, data)
    rep = validate_theme(theme, dist, only=["light"])
    assert any(e == f"{zp.name}: COPYRIGHT exists in the theme root but is missing here" for e in rep.errors)
    assert not any(e.startswith("light/:") for e in rep.errors)  # folder still complete


def test_missing_licence_text_fails(tmp_path):
    theme, dist = _theme_copy(tmp_path, {"CREDITS.md": "credits only"})
    (zp,) = build_theme(theme, dist, only=["light"], log=lambda *_: None)
    rep = validate_theme(theme, dist, only=["light"])
    assert any(e.startswith("light/: neither LICENSE nor COPYING") for e in rep.errors)
    assert any(e.startswith(f"{zp.name}: neither LICENSE nor COPYING") for e in rep.errors)
