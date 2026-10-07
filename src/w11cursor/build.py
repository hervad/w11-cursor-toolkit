"""Build orchestration: theme.toml -> dist/<variant>/ (+ zip per variant)."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from .config import NOTICE_FILES, CursorSpec, Theme, Variant
from .hotspot import scale_hotspot
from .inf import make_inf, make_uninstall_cmd
from .pack import CursorImage, pack_ani, pack_cur
from .render import render_svg
from .roles import ROLES


def _layers(theme: Theme, variant: Variant, svg_name: str, spec: CursorSpec, sizes) -> list[CursorImage]:
    svg = theme.find_svg(variant, svg_name)
    canvas = theme.canvas_for(spec)
    return [
        CursorImage(
            render_svg(svg, n, variant.recolor, theme.renderer),
            scale_hotspot(spec.hotspot, canvas, n, theme.hotspot_mode),
        )
        for n in sizes
    ]


def build_cursor(theme: Theme, variant: Variant, key: str) -> tuple[bytes, bool]:
    spec = theme.resolve(key)
    if not spec.animated:
        return pack_cur(_layers(theme, variant, spec.svg, spec, theme.static_sizes), theme.png_min_size), False
    frames = []
    for i in range(spec.frame_count):
        name = spec.frames.format(n=spec.frame_start + i)
        frames.append(pack_cur(_layers(theme, variant, name, spec, theme.animated_sizes), theme.png_min_size))
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
