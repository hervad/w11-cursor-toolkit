"""`inspect --lenient` reports directory/image mismatches in third-party files; strict parsing stays strict."""
import struct

import pytest
from PIL import Image

from w11cursor.cli import main
from w11cursor.pack import CursorImage, pack_cur, parse_cur, parse_cur_lenient
from w11cursor.pack.cur import _png_payload
from w11cursor.validate import describe


def _cur(entries) -> bytes:
    """[(claimed_size, real_size)] -> .cur whose directory may claim a size the image doesn't have."""
    pays = [_png_payload(Image.new("RGBA", (real, real), (255, 0, 0, 255))) for _, real in entries]
    off, dirs = 6 + 16 * len(entries), b""
    for (claimed, _), p in zip(entries, pays):
        dirs += struct.pack("<BBBBHHII", claimed % 256, claimed % 256, 0, 0, 1, 1, len(p), off)
        off += len(p)
    return struct.pack("<HHH", 0, 2, len(entries)) + dirs + b"".join(pays)


def _ani(frames, anih_rate, rates) -> bytes:
    def chunk(cid, data):
        return cid + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")
    n = len(frames)
    body = b"ACON" + chunk(b"anih", struct.pack("<9I", 36, n, n, 0, 0, 0, 0, anih_rate, 1))
    body += chunk(b"LIST", b"fram" + b"".join(chunk(b"icon", f) for f in frames))
    body += chunk(b"rate", struct.pack(f"<{n}I", *rates))
    return b"RIFF" + struct.pack("<I", len(body)) + body


@pytest.fixture
def mislabelled(tmp_path):
    """An entry labelled 80 holds a 96 px image; .ani whose anih rate (1) disagrees with its rate chunk (2)."""
    cur = _cur([(32, 32), (80, 96), (128, 128)])
    (tmp_path / "mislabelled.cur").write_bytes(cur)
    (tmp_path / "mislabelled.ani").write_bytes(_ani([cur, cur], 1, [2, 2]))
    return tmp_path


def test_strict_parser_still_rejects_it(mislabelled):
    with pytest.raises(ValueError, match="directory says 80x80, image is 96x96"):
        parse_cur((mislabelled / "mislabelled.cur").read_bytes())


def test_lenient_parser_reports_claimed_and_real(mislabelled):
    entries = parse_cur_lenient((mislabelled / "mislabelled.cur").read_bytes())
    assert [(e.claimed, e.real, e.mismatch) for e in entries] == [
        (32, (32, 32), False), (80, (96, 96), True), (128, (128, 128), False)]


def test_lenient_inspect_cur(mislabelled):
    text = describe(mislabelled / "mislabelled.cur", lenient=True)
    assert "MISMATCH: directory says 80, image is 96x96" in text
    assert "1 of 3 entries claim a size their image doesn't have" in text


def test_lenient_inspect_ani(mislabelled):
    text = describe(mislabelled / "mislabelled.ani", lenient=True)
    assert "NOTE: anih default rate 1 differs from the rate chunk (2)" in text
    assert "all frames: 2 of 6 entries mismatched; distinct real image sizes: [32, 96, 128]" in text


def test_lenient_inspect_clean_file(tmp_path):
    p = tmp_path / "clean.cur"
    p.write_bytes(pack_cur([CursorImage(Image.new("RGBA", (n, n), (0, 0, 0, 255)), (0, 0)) for n in (32, 48)]))
    assert "directory matches every image" in describe(p, lenient=True)


def test_cli_strict_fails_with_hint_lenient_succeeds(mislabelled, capsys):
    f = str(mislabelled / "mislabelled.cur")
    assert main(["inspect", f]) == 1
    assert "try: w11cursor inspect --lenient" in capsys.readouterr().out
    assert main(["inspect", "--lenient", f]) == 0
    assert "MISMATCH" in capsys.readouterr().out
