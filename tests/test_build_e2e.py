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
    assert any(e.startswith("light/: neither LICENSE nor LICENSE.GPL nor COPYING") for e in rep.errors)
    assert any(e.startswith(f"{zp.name}: neither LICENSE nor LICENSE.GPL nor COPYING") for e in rep.errors)


def test_license_gpl_name_is_kept_and_accepted(tmp_path):
    """ComixCursors ships COPYING (a notice pointing to 'LICENSE.GPL') + LICENSE.GPL (full text): both keep their names."""
    import zipfile

    theme, dist = _theme_copy(tmp_path, {"COPYING": "see LICENSE.GPL", "LICENSE.GPL": "GPL v3 text"})
    (zp,) = build_theme(theme, dist, only=["light"], log=lambda *_: None)
    assert validate_theme(theme, dist, only=["light"]).ok
    with zipfile.ZipFile(zp) as z:
        names = {Path(n).name for n in z.namelist()}
    assert {"COPYING", "LICENSE.GPL"} <= names


def _pad_first_image(frame: bytes, extra: int) -> bytes:
    """Same .cur, but the first PNG grows by `extra` bytes (private 'prVt' chunk), pushing later images back."""
    import struct
    import zlib

    n = struct.unpack_from("<H", frame, 4)[0]
    dirs = [list(struct.unpack_from("<BBBBHHII", frame, 6 + 16 * i)) for i in range(n)]
    datas = [frame[d[7]:d[7] + d[6]] for d in dirs]
    first = datas[0]
    iend = first.rindex(b"IEND") - 4
    body = b"\0" * (extra - 12)
    chunk = struct.pack(">I", len(body)) + b"prVt" + body + struct.pack(">I", zlib.crc32(b"prVt" + body) & 0xFFFFFFFF)
    datas[0] = first[:iend] + chunk + first[iend:]
    off, out = 6 + 16 * n, b""
    for d, data in zip(dirs, datas):
        d[6], d[7] = len(data), off
        out += struct.pack("<BBBBHHII", *d)
        off += len(data)
    return frame[:6] + out + b"".join(datas)


def test_validator_enforces_ani_image_offset_limit(tmp_path):
    from w11cursor.pack import pack_ani, parse_ani, parse_cur

    theme = load_theme(DEMO)
    build_theme(theme, tmp_path, only=["light"], log=lambda *_: None)
    busy = tmp_path / "light" / "busy.ani"
    frames = parse_ani(busy.read_bytes()).frames
    now = max(e.offset for e in parse_cur(frames[0]))                  # bytes before the last image today

    near = [_pad_first_image(frames[0], 61_000 - now)] + frames[1:]     # 93 % of the limit -> warning only
    assert 0.9 * 65_535 < max(e.offset for e in parse_cur(near[0])) <= 65_535
    busy.write_bytes(pack_ani(near, 4, theme.ani_order))
    rep = validate_theme(theme, tmp_path, only=["light"])
    assert rep.ok, rep.errors
    assert any("busy.ani#frame0: largest image offset" in w for w in rep.warnings)

    over = [_pad_first_image(frames[0], 66_000 - now)] + frames[1:]    # past 65,535 -> Windows refuses it
    assert max(e.offset for e in parse_cur(over[0])) > 65_535
    busy.write_bytes(pack_ani(over, 4, theme.ani_order))
    rep = validate_theme(theme, tmp_path, only=["light"])
    assert any(e.startswith("light/busy.ani#frame0: an image starts at byte 66,000") for e in rep.errors), rep.errors


def _mixed_cur(images) -> bytes:
    """A .cur whose layers alternate BMP/PNG - what the removed png_min_size=256 escape hatch produced."""
    import struct

    from w11cursor.pack.cur import _bmp_payload, _png_payload

    images = sorted(images, key=lambda c: c.image.width)
    pays = [(_bmp_payload if i % 2 else _png_payload)(c.image) for i, c in enumerate(images)]
    off, dirs = 6 + 16 * len(images), b""
    for c, p in zip(images, pays):
        w = c.image.width
        dirs += struct.pack("<BBBBHHII", w % 256, w % 256, 0, 0, *c.hotspot, len(p), off)
        off += len(p)
    return struct.pack("<HHH", 0, 2, len(images)) + dirs + b"".join(pays)


def test_validator_rejects_mixed_layer_formats(tmp_path):
    from w11cursor.build import _layers
    from w11cursor.pack import pack_ani, parse_ani, parse_cur

    theme = load_theme(DEMO)
    v = theme.variants[0]
    build_theme(theme, tmp_path, only=["light"], log=lambda *_: None)
    # static: same sizes and hotspots as the real pointer.cur, only the encoding is mixed
    mixed = _mixed_cur(_layers(theme, v, theme.resolve("arrow"), None, theme.static_sizes))
    assert {e.fmt for e in parse_cur(mixed)} == {"bmp", "png"}
    (tmp_path / "light" / "pointer.cur").write_bytes(mixed)
    # animated: frame 0 of busy.ani mixed, the rest untouched
    busy = tmp_path / "light" / "busy.ani"
    frames = parse_ani(busy.read_bytes()).frames
    spec = theme.resolve("busy")
    frames[0] = _mixed_cur(_layers(theme, v, spec, 0, theme.animated_sizes))
    busy.write_bytes(pack_ani(frames, spec.delay, theme.ani_order))
    rep = validate_theme(theme, tmp_path, only=["light"])
    assert any(e.startswith("light/pointer.cur: mixes bmp and png layers") for e in rep.errors), rep.errors
    assert any(e.startswith("light/busy.ani#frame0: mixes bmp and png layers") for e in rep.errors), rep.errors
    assert not any("#frame1:" in e for e in rep.errors)


def test_layer_format_bmp_builds_all_bmp(tmp_path):
    from w11cursor.pack import parse_ani, parse_cur

    root = tmp_path / "theme"
    root.mkdir()
    (root / "LICENSE").write_text("MIT")
    svg = (DEMO.parent / "svg").as_posix()
    # small animated sizes: uncompressed BMP frames with option C's sizes would break the .ani offset limit
    (root / "theme.toml").write_text(DEMO.read_text().replace('svg_dir = "svg"', f'svg_dir = "{svg}"')
                                     + '\n[sizes]\nlayer_format = "bmp"\nanimated = [32, 48, 64]\n')
    theme = load_theme(root / "theme.toml")
    build_theme(theme, tmp_path / "dist", only=["light"], log=lambda *_: None)
    assert validate_theme(theme, tmp_path / "dist", only=["light"]).ok
    assert {e.fmt for e in parse_cur((tmp_path / "dist" / "light" / "pointer.cur").read_bytes())} == {"bmp"}
    fr = parse_ani((tmp_path / "dist" / "light" / "busy.ani").read_bytes()).frames[0]
    assert {e.fmt for e in parse_cur(fr)} == {"bmp"}
