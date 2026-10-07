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
