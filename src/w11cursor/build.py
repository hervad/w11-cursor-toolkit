"""Build orchestration: theme.toml -> dist/<variant>/ (+ zip per variant)."""
from __future__ import annotations

import shutil
import zipfile
from functools import lru_cache
from pathlib import Path

from .config import NOTICE_FILES, CursorSpec, Theme, Variant
from .hotspot import scale_hotspot
from .inf import make_inf, make_uninstall_cmd
from .pack import CursorImage, pack_ani, pack_cur
from .render import render_svg_text
from .roles import ROLES
from .split import extract


@lru_cache(maxsize=8)
def _read_master(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"master SVG not found: {path} (is the upstream source unpacked?)")
    return path.read_text(encoding="utf-8")


def _svg_source(theme: Theme, variant: Variant, spec: CursorSpec, frame: int | None) -> tuple[str, str]:
    """(name for messages, SVG text) of one cursor or one animation frame, before recolour."""
    if spec.layers is None:
        file = spec.svg if frame is None else spec.frames.format(n=spec.frame_start + frame)
        path = theme.find_svg(variant, file)
        if not path.exists():
            raise FileNotFoundError(f"SVG not found: {path}")
        return path.name, path.read_text(encoding="utf-8")
    if frame is None:  # a static cursor cut from the master can still be replaced by a hand-made override
        for folder in (variant.id, "_all"):
            override = theme.root / "overrides" / folder / f"{spec.role}.svg"
            if override.is_file():
                return override.name, override.read_text(encoding="utf-8")
    master = theme.master_for(spec)
    rotate = None
    if spec.rotate is not None:
        r = spec.rotate
        rotate = (r["id"], tuple(r["center"]), r["step_deg"] * frame)
    name = f"{master.name}:{spec.role}" + ("" if frame is None else f"#frame{frame}")
    return name, extract(_read_master(master), spec.layers, spec.transform, rotate,
                         expect_size=theme.canvas_for(spec), name=name)


def _layers(theme: Theme, variant: Variant, spec: CursorSpec, frame: int | None, sizes) -> list[CursorImage]:
    name, svg = _svg_source(theme, variant, spec, frame)
    canvas = theme.canvas_for(spec)
    return [
        CursorImage(
            render_svg_text(svg, name, n, variant.recolor, theme.renderer),
            scale_hotspot(spec.hotspot, canvas, n, theme.hotspot_mode),
        )
        for n in sizes
    ]


def build_cursor(theme: Theme, variant: Variant, key: str) -> tuple[bytes, bool]:
    spec = theme.resolve(key)
    if not spec.animated:
        return pack_cur(_layers(theme, variant, spec, None, theme.static_sizes), theme.png_min_size), False
    frames = []
    for i in range(spec.frame_count):
        frames.append(pack_cur(_layers(theme, variant, spec, i, theme.animated_sizes), theme.png_min_size))
    blob = pack_ani(frames, spec.delay, theme.ani_order, title=variant.scheme_name, artist=theme.porter or None,
                    rate_mode=theme.ani_rate_mode)
    return blob, True


def build_variant(theme: Theme, variant: Variant, out_root: Path, log=print) -> Path:
    out = out_root / variant.id
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    animated: dict[str, bool] = {}
    for r in ROLES:
        blob, is_ani = build_cursor(theme, variant, r.key)
        animated[r.key] = is_ani
        name = f"{r.filename}.{'ani' if is_ani else 'cur'}"
        (out / name).write_bytes(blob)
        log(f"  {variant.id}/{name:<18} {len(blob):>9,} B")
    (out / "install.inf").write_text(make_inf(variant.scheme_name, animated), encoding="utf-8", newline="")
    (out / "uninstall.cmd").write_text(make_uninstall_cmd(variant.scheme_name), encoding="utf-8", newline="")
    for extra in NOTICE_FILES:
        src = theme.root / extra
        if src.exists():
            shutil.copy2(src, out / extra)
    return out


def build_theme(theme: Theme, out_root: Path, only: list[str] | None = None, log=print) -> list[Path]:
    out_root.mkdir(parents=True, exist_ok=True)
    zips = []
    for v in theme.variants:
        if only and v.id not in only:
            continue
        log(f"[{theme.slug}] building variant '{v.id}' -> {v.scheme_name}")
        folder = build_variant(theme, v, out_root, log)
        zpath = out_root / theme.zip_name(v)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(folder.iterdir()):
                z.write(f, f"{v.scheme_name}/{f.name}")
        zips.append(zpath)
        log(f"  -> {zpath.name}")
    return zips
