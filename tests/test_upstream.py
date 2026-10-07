"""`w11cursor unpack`: sha256 pin, member allow-list, no symlinks / traversal, never writes into upstream/."""
import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from w11cursor.cli import main
from w11cursor.config import load_theme
from w11cursor.upstream import UnpackError, unpack

DEMO = Path(__file__).parents[1] / "examples" / "demo-theme" / "theme.toml"


def _tarball(path: Path) -> str:
    with tarfile.open(path, "w:bz2") as tf:
        def add(name, data=b"", **kw):
            info = tarfile.TarInfo(name)
            for k, v in kw.items():
                setattr(info, k, v)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data) if data else None)
        add("Theme/Source/Cursors.svg", b"<svg/>")
        add("Theme/Source/other.txt", b"not needed")
        add("Theme/link", type=tarfile.SYMTYPE, linkname="Source/Cursors.svg")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _theme(tmp_path, **upstream):
    (tmp_path / "upstream").mkdir()
    sha = _tarball(tmp_path / "upstream" / "src.tar.bz2")
    up = {"kind": "tarball", "archive": "upstream/src.tar.bz2", "sha256": sha,
          "extract": ["Theme/Source/Cursors.svg"], "into": "build/upstream", **upstream}
    lines = [f"{k} = {v!r}".replace("'", '"') for k, v in up.items() if v is not None]
    svg = (DEMO.parent / "svg").as_posix()
    text = DEMO.read_text().replace('svg_dir = "svg"', f'svg_dir = "{svg}"') + "\n[upstream]\n" + "\n".join(lines) + "\n"
    (tmp_path / "theme.toml").write_text(text)
    return load_theme(tmp_path / "theme.toml")


def test_extracts_only_listed_members(tmp_path):
    theme = _theme(tmp_path)
    (tmp_path / "build" / "upstream" / "stale.txt").parent.mkdir(parents=True)
    (tmp_path / "build" / "upstream" / "stale.txt").write_text("old")       # folder is wiped first
    written = unpack(theme, log=lambda *_: None)
    out = tmp_path / "build" / "upstream"
    assert written == [out / "Theme" / "Source" / "Cursors.svg"]
    assert (out / "Theme" / "Source" / "Cursors.svg").read_bytes() == b"<svg/>"
    assert sorted(p.name for p in out.rglob("*") if p.is_file()) == ["Cursors.svg"]


def test_cli_unpack(tmp_path):
    _theme(tmp_path)
    assert main(["unpack", str(tmp_path / "theme.toml")]) == 0


@pytest.mark.parametrize("override, message", [
    ({"sha256": "0" * 64}, "refusing to use it"),
    ({"sha256": "abc"}, "64 hex digits"),
    ({"extract": ["Theme/missing.svg"]}, "is not in"),
    ({"extract": ["Theme/link"]}, "not a regular file"),
    ({"extract": ["../escape.svg"]}, "unsafe member name"),
    ({"into": "upstream/x"}, "must not be inside upstream/"),
    ({"into": "."}, "sub-folder of the theme"),
    ({"into": "../outside"}, "sub-folder of the theme"),
    ({"kind": "git"}, "only handles"),
    ({"archive": "upstream/nope.tar.bz2"}, "archive not found"),
])
def test_refuses(tmp_path, override, message):
    theme = _theme(tmp_path, **override)
    with pytest.raises(UnpackError, match=message):
        unpack(theme, log=lambda *_: None)
