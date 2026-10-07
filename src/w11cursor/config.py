"""theme.toml loader + validation.

One theme.toml describes one theme repo: where the artwork comes from, which SVG
plays which Windows role, where each hotspot is, and which variants to build.
See theme-template/theme.toml for a fully commented example.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import sizes as S
from .roles import ROLE_BY_KEY, ROLES


class ConfigError(ValueError):
    pass


# Licence / notice files copied from the theme root into every variant folder and release zip.
# GPL obliges whoever *distributes* copies to give recipients the licence text and keep the notices;
# the zip is what users download, so the notices must travel inside it.
NOTICE_FILES: tuple[str, ...] = ("LICENSE", "COPYING", "COPYRIGHT", "NOTICE", "AUTHORS", "CREDITS.md")
LICENSE_TEXT_FILES: tuple[str, ...] = ("LICENSE", "COPYING")   # at least one must ship


@dataclass
class CursorSpec:
    role: str
    svg: str | None = None
    frames: str | None = None          # format string with {n}, e.g. "wait-{n:02d}.svg"
    frame_count: int = 0
    frame_start: int = 1
    delay: int | list[int] = 2         # jiffies (1/60 s)
    hotspot: tuple[float, float] = (0.0, 0.0)
    design_canvas: int | None = None   # per-cursor override
    same_as: str | None = None

    @property
    def animated(self) -> bool:
        return self.frames is not None


@dataclass
class Variant:
    id: str
    scheme_name: str
    svg_dir: Path
    recolor: dict[str, str] = field(default_factory=dict)


@dataclass
class Theme:
    root: Path
    slug: str
    name: str
    version: str
    license: str
    description: str
    porter: str
    upstream: dict
    renderer: str
    design_canvas: int
    hotspot_mode: str
    static_sizes: tuple[int, ...]
    animated_sizes: tuple[int, ...]
    ani_budget: int
    ani_order: tuple[str, ...]
    ani_rate_mode: str
    png_min_size: int
    variants: list[Variant]
    cursors: dict[str, CursorSpec]

    def resolve(self, key: str) -> CursorSpec:
        """Follow same_as links (pin -> link etc.)."""
        seen = []
        spec = self.cursors[key]
        while spec.same_as:
            if spec.same_as in seen:
                raise ConfigError(f"same_as loop: {seen}")
            seen.append(spec.same_as)
            spec = self.cursors[spec.same_as]
        return spec

    def find_svg(self, variant: Variant, name: str) -> Path:
        """overrides/<variant>/<name> wins over <svg_dir>/<name>."""
        override = self.root / "overrides" / variant.id / name
        if override.exists():
            return override
        common = self.root / "overrides" / "_all" / name
        if common.exists():
            return common
        return variant.svg_dir / name

    def canvas_for(self, spec: CursorSpec) -> int:
        return spec.design_canvas or self.design_canvas

    def zip_name(self, variant: Variant) -> str:
        return f"{self.slug}-{variant.id}-w11-hidpi-v{self.version}.zip"


def _req(tbl: dict, key: str, where: str):
    if key not in tbl:
        raise ConfigError(f"missing '{key}' in [{where}]")
    return tbl[key]


def load_theme(path: str | Path) -> Theme:
    path = Path(path).resolve()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    root = path.parent

    t = _req(data, "theme", "root")
    r = data.get("render", {})
    sz = data.get("sizes", {})

    variants = []
    for v in _req(data, "variants", "root"):
        variants.append(
            Variant(
                id=_req(v, "id", "variants"),
                scheme_name=_req(v, "scheme_name", "variants"),
                svg_dir=(root / _req(v, "svg_dir", "variants")).resolve(),
                recolor=dict(v.get("recolor", {})),
            )
        )
    if not variants:
        raise ConfigError("at least one [[variants]] entry is required")

    cursors: dict[str, CursorSpec] = {}
    for key, c in _req(data, "cursors", "root").items():
        if key not in ROLE_BY_KEY:
            raise ConfigError(f"unknown role [cursors.{key}]; valid: {', '.join(ROLE_BY_KEY)}")
        spec = CursorSpec(
            role=key,
            svg=c.get("svg"),
            frames=c.get("frames"),
            frame_count=int(c.get("frame_count", 0)),
            frame_start=int(c.get("frame_start", 1)),
            delay=c.get("delay", 2),
            hotspot=tuple(c.get("hotspot", (0, 0))),
            design_canvas=c.get("design_canvas"),
            same_as=c.get("same_as"),
        )
        kinds = sum(x is not None for x in (spec.svg, spec.frames, spec.same_as))
        if kinds != 1:
            raise ConfigError(f"[cursors.{key}] needs exactly one of svg / frames / same_as")
        if spec.frames and spec.frame_count < 1:
            raise ConfigError(f"[cursors.{key}] animated cursor needs frame_count >= 1")
        cursors[key] = spec

    missing = [r_.key for r_ in ROLES if r_.key not in cursors]
    if missing:
        raise ConfigError(
            "every Windows role must be mapped (use same_as to reuse art). Missing: " + ", ".join(missing)
        )
    for key, spec in cursors.items():
        if spec.same_as and spec.same_as not in cursors:
            raise ConfigError(f"[cursors.{key}] same_as -> unknown role '{spec.same_as}'")

    theme = Theme(
        root=root,
        slug=_req(t, "slug", "theme"),
        name=_req(t, "name", "theme"),
        version=str(_req(t, "version", "theme")),
        license=_req(t, "license", "theme"),
        description=t.get("description", ""),
        porter=t.get("porter", ""),
        upstream=data.get("upstream", {}),
        renderer=r.get("renderer", "cairosvg"),
        design_canvas=int(r.get("design_canvas", 32)),
        hotspot_mode=r.get("hotspot_mode", "point"),
        static_sizes=tuple(sz.get("static", S.STATIC_SIZES)),
        animated_sizes=tuple(sz.get("animated", S.ANIMATED_SIZES)),
        ani_budget=int(sz.get("ani_budget_bytes", S.ANI_BUDGET_BYTES)),
        ani_order=tuple(sz.get("ani_chunk_order", S.ANI_CHUNK_ORDER)),
        ani_rate_mode=sz.get("ani_rate", S.ANI_RATE_MODE),
        png_min_size=int(sz.get("png_min_size", S.PNG_MIN_SIZE)),
        variants=variants,
        cursors=cursors,
    )
    for k in cursors:
        theme.resolve(k)  # detect same_as loops early
    if theme.hotspot_mode not in ("point", "center"):
        raise ConfigError("[render] hotspot_mode must be 'point' or 'center'")
    from .render import RENDERERS

    if theme.renderer not in RENDERERS:
        raise ConfigError(f"[render] renderer must be one of: {', '.join(RENDERERS)}")
    if theme.ani_rate_mode not in S.ANI_RATE_MODES:
        raise ConfigError(f"[sizes] ani_rate must be one of: {', '.join(S.ANI_RATE_MODES)}")
    for name, lst in (("static", theme.static_sizes), ("animated", theme.animated_sizes)):
        if any(not 1 <= s <= 256 for s in lst):
            raise ConfigError(f"[sizes] {name} sizes must be within 1..256")
    return theme
