import pytest
from PIL import Image

from w11cursor.pack import CursorImage, pack_ani, pack_cur, parse_ani, parse_cur


def frame(n_sizes=(32, 64)):
    return pack_cur([CursorImage(Image.new("RGBA", (n, n), (255, 0, 0, 255)), (1, 1)) for n in n_sizes])


def test_uniform_delays_omit_rate_by_default():
    # Microsoft layout (aero_busy.ani): anih -> LIST:fram, the one delay lives in anih.
    blob = pack_ani([frame(), frame(), frame()], 3, title="Odd Title!")  # odd-length INFO string
    info = parse_ani(blob)
    assert info.chunk_order == ["LIST:INFO", "anih", "LIST:fram"]
    assert info.n_frames == 3 and info.rates is None and info.default_rate == 3 and info.flags == 1
    assert [e.size for e in parse_cur(info.frames[0])] == [32, 64]


def test_mixed_delays_keep_rate_after_list():
    info = parse_ani(pack_ani([frame(), frame(), frame()], [4, 4, 3]))
    assert info.chunk_order == ["anih", "LIST:fram", "rate"]
    assert info.rates == [4, 4, 3] and info.default_rate == 4


def test_rate_mode_always_keeps_uniform_rate():
    info = parse_ani(pack_ani([frame(), frame(), frame()], 3, rate_mode="always"))
    assert info.chunk_order == ["anih", "LIST:fram", "rate"] and info.rates == [3, 3, 3]


def test_order_without_rate_rejects_mixed_delays():
    # Would otherwise silently play [4, 4] - Windows uses anih's delay for every step.
    with pytest.raises(ValueError, match="need a 'rate' chunk"):
        pack_ani([frame(), frame()], [4, 3], order=("anih", "LIST"))


def test_alternative_order_without_rate():
    info = parse_ani(pack_ani([frame()], 2, order=("anih", "LIST")))
    assert info.chunk_order == ["anih", "LIST:fram"] and info.rates is None


def test_riff_size_is_consistent_and_even():
    blob = pack_ani([frame(), frame()], [2, 5], title="abc")
    assert int.from_bytes(blob[4:8], "little") + 8 == len(blob)
    assert len(blob) % 2 == 0
