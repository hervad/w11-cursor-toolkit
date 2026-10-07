"""Size lists follow the MEASURED layer-choice rule (docs/SIZE_POLICY.md, docs/probe-results.csv)."""
import csv
from pathlib import Path

from w11cursor import sizes as S

PROBE_RESULTS = Path(__file__).parents[1] / "docs" / "probe-results.csv"
# Independent restatement of the rule (not via S.choosable_sizes): bases 32..256, buckets x1 x1.5 x2 x2.5 x3, cap 256.
BASES = [32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 224, 240, 256]
CHOOSABLE = sorted({min(256, round(b * f)) for b in BASES for f in (1.0, 1.5, 2.0, 2.5, 3.0)})


def bucket(scale_pct: int) -> float:
    """Verified for 100-199 %; Layan's assumption above."""
    return 1.0 if scale_pct < 150 else 1.5 if scale_pct < 200 else 2.0 if scale_pct < 250 else 2.5 if scale_pct < 300 else 3.0


def test_static_list_is_exactly_the_choosable_sizes():
    assert list(S.STATIC_SIZES) == CHOOSABLE
    assert list(S.STATIC_SIZES) == [32, 48, 64, 72, 80, 96, 112, 120, 128, 144, 160, 168, 176, 192, 200,
                                    208, 216, 224, 240, 256]


def test_every_shipped_size_can_be_chosen_and_every_choosable_size_is_shipped():
    assert set(S.STATIC_SIZES) <= set(CHOOSABLE)                    # no dead layers (e.g. old 40, 56)
    assert {s for s in CHOOSABLE if s <= 256} <= set(S.STATIC_SIZES)  # no missing layers
    assert set(S.ANIMATED_SIZES) <= set(CHOOSABLE)                  # animated is a subset of choosable


def test_verified_vs_assumed_buckets_are_marked():
    assert S.VERIFIED_BUCKETS == (1.0, 1.5) and S.ASSUMED_BUCKETS == (2.0, 2.5, 3.0)
    assert S.choosable_sizes(S.VERIFIED_BUCKETS) == tuple(x for x in CHOOSABLE if x != 200)  # 200 = assumed x2.5 only


def test_rule_matches_every_recorded_probe_reading():
    rows = list(csv.DictReader(PROBE_RESULTS.open(encoding="utf-8")))
    assert len(rows) >= 25
    for r in rows:
        scale, base, shown = int(r["scale"]), int(r["base_px"]), r["shown"].strip()
        assert r.get("os_build", "").count(".") == 1, f"reading without an OS build tag: {r}"
        assert not shown.endswith("?"), f"blurry reading recorded: {r}"
        assert int(shown) == min(S.MAX_LAYER, round(base * bucket(scale))), r
