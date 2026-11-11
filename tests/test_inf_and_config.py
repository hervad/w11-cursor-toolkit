from pathlib import Path

import pytest

from w11cursor.config import ConfigError, load_theme
from w11cursor.inf import make_inf
from w11cursor.roles import ROLES

DEMO = Path(__file__).parents[1] / "examples" / "demo-theme" / "theme.toml"


def test_inf_lists_17_roles_in_canonical_order():
    inf = make_inf("Test Scheme", {"busy": True, "working": True})
    assert len(ROLES) == 17
    scheme_line = next(l for l in inf.splitlines() if l.startswith('HKCU,"Control Panel\\Cursors\\Schemes"'))
    stems = [p.rsplit("%", 2)[-2] for p in scheme_line.split('",0x00020000,"')[1].rstrip('"').split(",")]
    assert stems == [r.filename for r in ROLES]
    assert '"busy.ani"' in inf and '"pointer.cur"' in inf
    assert "Pin," in inf and "Person," in inf


def test_demo_theme_loads_and_resolves():
    t = load_theme(DEMO)
    assert t.resolve("pin").svg == "arrow.svg"
    assert t.resolve("working").animated


def test_missing_role_is_an_error(tmp_path):
    text = DEMO.read_text().split("[cursors.person]")[0]
    p = tmp_path / "theme.toml"
    p.write_text(text)
    with pytest.raises(ConfigError, match="person"):
        load_theme(p)


def test_bad_ani_rate_mode_is_an_error(tmp_path):
    p = tmp_path / "theme.toml"
    p.write_text(DEMO.read_text().replace('svg_dir = "svg"', f'svg_dir = "{(DEMO.parent / "svg").as_posix()}"')
                 + '\n[sizes]\nani_rate = "sometimes"\n')
    with pytest.raises(ConfigError, match="ani_rate"):
        load_theme(p)


def test_unknown_renderer_in_theme_is_an_error(tmp_path):
    p = tmp_path / "theme.toml"
    p.write_text(DEMO.read_text().replace('renderer = "cairosvg"', 'renderer = "inkscape"'))
    with pytest.raises(ConfigError, match="renderer"):
        load_theme(p)


@pytest.mark.parametrize("sizes_table, message", [
    ("png_min_size = 256", "png_min_size was removed"),
    ('layer_format = "jpeg"', "layer_format must be one of"),
])
def test_layer_format_config_errors(tmp_path, sizes_table, message):
    p = tmp_path / "theme.toml"
    p.write_text(DEMO.read_text().replace('svg_dir = "svg"', f'svg_dir = "{(DEMO.parent / "svg").as_posix()}"')
                 + f"\n[sizes]\n{sizes_table}\n")
    with pytest.raises(ConfigError, match=message):
        load_theme(p)


def _demo_with(tmp_path, light_extra: str = "", gold_extra: str = ""):
    """Demo theme (light + gold variants) with extra lines appended to each [[variants]] table."""
    text = DEMO.read_text().replace('svg_dir = "svg"', f'svg_dir = "{(DEMO.parent / "svg").as_posix()}"')
    text = text.replace('scheme_name = "w11cursor Demo"\n', f'scheme_name = "w11cursor Demo"\n{light_extra}\n', 1)
    text = text.replace('scheme_name = "w11cursor Demo Gold"\n', f'scheme_name = "w11cursor Demo Gold"\n{gold_extra}\n', 1)
    p = tmp_path / "theme.toml"
    p.write_text(text)
    return load_theme(p)


def test_zip_name_without_package_is_per_variant(tmp_path):
    t = _demo_with(tmp_path)
    assert [t.zip_name(v) for v in t.variants] == [f"{t.slug}-light-w11-hidpi-v{t.version}.zip",
                                                   f"{t.slug}-gold-w11-hidpi-v{t.version}.zip"]


def test_variants_with_one_package_share_a_zip(tmp_path):
    t = _demo_with(tmp_path, 'package = "pair"', 'package = "pair"')
    assert {t.zip_name(v) for v in t.variants} == {f"{t.slug}-pair-w11-hidpi-v{t.version}.zip"}


def test_package_equal_to_slug_drops_the_repeat(tmp_path):
    t = _demo_with(tmp_path)
    t = _demo_with(tmp_path, f'package = "{t.slug}"', f'package = "{t.slug}"')
    assert t.zip_name(t.variants[0]) == f"{t.slug}-w11-hidpi-v{t.version}.zip"


@pytest.mark.parametrize("bad", ['"Pair"', '"pair_x"', '"-pair"', '""', "3"])
def test_bad_package_name_is_an_error(tmp_path, bad):
    with pytest.raises(ConfigError, match="package must be"):
        _demo_with(tmp_path, f"package = {bad}")


def test_package_named_like_an_unpackaged_variant_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="share one zip by accident"):
        _demo_with(tmp_path, gold_extra='package = "light"')
