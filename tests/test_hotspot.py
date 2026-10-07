import pytest

from w11cursor.hotspot import scale_hotspot


def test_point_mode_matches_validated_capitaine_build():
    # capitaine arrow: design (4,2) on a 24 canvas -> values shipped in capitaine-cursors-w11-hidpi
    got = [scale_hotspot((4, 2), 24, n) for n in (32, 40, 48, 64, 80, 96, 128)]
    assert got == [(5, 3), (7, 3), (8, 4), (11, 5), (13, 7), (16, 8), (21, 11)]


def test_point_mode_keeps_tip_exact_at_256():
    assert scale_hotspot((3, 2), 32, 256) == (24, 16)


def test_center_mode():
    assert scale_hotspot((16, 16), 32, 64, "center") == (32, 32)


def test_clamped_inside_image():
    assert scale_hotspot((32, 32), 32, 48) == (47, 47)


def test_bad_mode():
    with pytest.raises(ValueError):
        scale_hotspot((0, 0), 32, 32, "nope")
