"""The size probe must contain a layer for every size either sizing model predicts, or a reading can't decide.

exact model:    layer = CursorBaseSize x scale            (capped at 256)
bucketed model: layer = CursorBaseSize x bucket(scale)    100-149 % -> 100 %, 150-199 % -> 150 %, 200 %+ -> 200 %
At 100/150/200 % both models agree; 125 % and 175 % are the discriminating scales (docs/SIZE_POLICY.md).
"""
import pytest

from w11cursor.pack import parse_cur
from w11cursor.probe import PROBE_SIZES, make_probe

SLIDERS = (1, 2, 3, 4, 5, 7, 9, 15)


def exact(scale: int) -> list[int]:
    return [min(256, round(16 * (s + 1) * scale / 100)) for s in SLIDERS]


def bucketed(scale: int) -> list[int]:
    bucket = 100 if scale < 150 else 150 if scale < 200 else 200
    return exact(bucket)


def test_predictions_match_the_task5_table():
    assert exact(125) == [40, 60, 80, 100, 120, 160, 200, 256]
    assert bucketed(125) == [32, 48, 64, 80, 96, 128, 160, 256]
    assert exact(175) == [56, 84, 112, 140, 168, 224, 256, 256]
    assert bucketed(175) == [48, 72, 96, 120, 144, 192, 240, 256]


@pytest.mark.parametrize("scale", [100, 125, 150, 175, 200])
def test_probe_file_has_every_predicted_layer(tmp_path, scale):
    layers = {e.size for e in parse_cur(make_probe(tmp_path).read_bytes())}
    assert layers == set(PROBE_SIZES)
    missing = sorted(set(exact(scale) + bucketed(scale)) - layers)
    assert not missing, f"{scale} %: probe lacks layers {missing}"
