import pytest
from PIL import Image

from w11cursor.pack import CursorImage, pack_cur, parse_cur


def img(n, color=(255, 255, 255, 255)):
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    im.paste(color, (0, 0, n // 2, n // 2))
    return im


@pytest.mark.parametrize("layer_format", ["png", "bmp"])
def test_roundtrip_sizes_hotspots_formats(layer_format):
    sizes = [32, 48, 64, 128, 256]
    blob = pack_cur([CursorImage(img(n), (n // 8, n // 16)) for n in sizes], layer_format=layer_format)
    entries = parse_cur(blob)
    assert [e.size for e in entries] == sizes
    assert [e.hotspot for e in entries] == [(n // 8, n // 16) for n in sizes]
    assert {e.fmt for e in entries} == {layer_format}   # one format per file, never mixed (ADR-4)


def test_unknown_layer_format_is_rejected():
    with pytest.raises(ValueError, match="layer_format"):
        pack_cur([CursorImage(img(32), (0, 0))], layer_format="jpeg")


def test_256_is_encoded_as_zero_in_directory():
    blob = pack_cur([CursorImage(img(256), (0, 0))])
    assert blob[6] == 0 and blob[7] == 0
    assert parse_cur(blob)[0].size == 256


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        pack_cur([CursorImage(img(32), (40, 0))])          # hotspot outside
    with pytest.raises(ValueError):
        pack_cur([CursorImage(img(32), (0, 0)), CursorImage(img(32), (0, 0))])  # duplicate size
    with pytest.raises(ValueError):
        parse_cur(b"\x00\x00\x01\x00\x01\x00")            # .ico, not .cur


def test_inspect_prints_directory_order_and_offsets(tmp_path):
    from PIL import Image

    from w11cursor.pack import CursorImage, pack_cur, parse_cur
    from w11cursor.validate import describe

    blob = pack_cur([CursorImage(Image.new("RGBA", (n, n), (255, 0, 0, 255)), (0, 0)) for n in (32, 64)])
    p = tmp_path / "x.cur"
    p.write_bytes(blob)
    entries = parse_cur(blob)
    assert entries[0].offset == 6 + 16 * 2 and entries[1].offset == entries[0].offset + entries[0].nbytes
    text = describe(p)
    assert "starts at" in text
    assert f"   0   32px  png  (0, 0)" in text and f"@{entries[1].offset:>9,}" in text
