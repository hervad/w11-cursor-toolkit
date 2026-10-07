"""Validator: re-parses the BUILT files and checks them against theme.toml.

It never trusts the builder - it reads bytes back and recomputes expectations.
Checks: all 17 roles present, exact layer sizes, per-layer hotspots, .ani chunk
order / frame count / per-step delays / byte budget, INF lists 17 roles in canonical order,
licence text + theme-root notice files present in every variant folder and release zip.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import sizes as S
from .config import LICENSE_TEXT_FILES, NOTICE_FILES, Theme, Variant
from .hotspot import scale_hotspot
from .pack import parse_ani, parse_cur
from .roles import ROLES


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _check_cur(blob: bytes, sizes, spec, canvas, mode, where, rep: Report, layer_format: str | None = None):
    try:
        entries = parse_cur(blob)
    except ValueError as e:
        rep.errors.append(f"{where}: unreadable .cur ({e})")
        return
    fmts = sorted({e.fmt for e in entries})
    if len(fmts) > 1:
        rep.errors.append(f"{where}: mixes {' and '.join(fmts)} layers - Windows ignores the PNG layers in such files "
                          "(ADR-4); every layer must use one format")
    elif layer_format and fmts and fmts[0] != layer_format:
        rep.errors.append(f"{where}: layers are {fmts[0]}, theme says layer_format = {layer_format!r}")
    got = sorted(e.size for e in entries)
    if got != sorted(sizes):
        rep.errors.append(f"{where}: layers {got} != expected {sorted(sizes)}")
    for e in entries:
        want = scale_hotspot(spec.hotspot, canvas, e.size, mode)
        if e.hotspot != want:
            rep.errors.append(f"{where}@{e.size}: hotspot {e.hotspot} != expected {want}")


def _check_ani_offsets(info, where: str, rep: Report):
    """Windows' .ani loader rejects a frame if any image starts past byte 65,535 of that frame (measured)."""
    worst, frame = 0, 0
    for i, fr in enumerate(info.frames):
        try:
            m = max(e.offset for e in parse_cur(fr))
        except ValueError:
            continue  # reported by _check_cur
        if m > worst:
            worst, frame = m, i
    if worst > S.ANI_MAX_IMAGE_OFFSET:
        rep.errors.append(f"{where}#frame{frame}: an image starts at byte {worst:,} > {S.ANI_MAX_IMAGE_OFFSET:,} - "
                          "Windows refuses such frames; drop or shrink layers below the largest")
    elif worst > S.ANI_OFFSET_WARN_FRACTION * S.ANI_MAX_IMAGE_OFFSET:
        rep.warnings.append(f"{where}#frame{frame}: largest image offset {worst:,} is "
                            f"{worst / S.ANI_MAX_IMAGE_OFFSET:.0%} of the {S.ANI_MAX_IMAGE_OFFSET:,} loader limit")


def _check_notices(theme: Theme, v: Variant, folder: Path, rep: Report):
    """Licence text + every notice file from the theme root must ship in the folder AND the zip."""
    expected = [n for n in NOTICE_FILES if (theme.root / n).is_file()]
    places = {f"{v.id}/": {p.name for p in folder.iterdir() if p.is_file()}}
    zpath = folder.parent / theme.zip_name(v)
    if not zpath.exists():
        rep.errors.append(f"{v.id}: release zip {zpath.name} missing")
    else:
        with zipfile.ZipFile(zpath) as z:
            # build.py writes "<scheme name>/<file>"; only that top level counts
            places[zpath.name] = {n.split("/")[1] for n in z.namelist() if n.count("/") == 1 and not n.endswith("/")}
    for where, names in places.items():
        if not names & set(LICENSE_TEXT_FILES):
            rep.errors.append(f"{where}: neither {' nor '.join(LICENSE_TEXT_FILES)} - recipients must get the licence text")
        for n in expected:
            if n not in names:
                rep.errors.append(f"{where}: {n} exists in the theme root but is missing here")


def validate_theme(theme: Theme, dist: Path, only: list[str] | None = None) -> Report:
    rep = Report()
    expected_order = [("LIST:fram" if c == "LIST" else c) for c in theme.ani_order]
    for v in theme.variants:
        if only and v.id not in only:
            continue
        folder = dist / v.id
        if not folder.is_dir():
            rep.errors.append(f"{v.id}: missing build folder {folder}")
            continue
        for r in ROLES:
            spec = theme.resolve(r.key)
            canvas = theme.canvas_for(spec)
            ext = "ani" if spec.animated else "cur"
            f = folder / f"{r.filename}.{ext}"
            where = f"{v.id}/{f.name}"
            if not f.exists():
                rep.errors.append(f"{where}: missing")
                continue
            blob = f.read_bytes()
            if not spec.animated:
                _check_cur(blob, theme.static_sizes, spec, canvas, theme.hotspot_mode, where, rep, theme.layer_format)
                continue
            try:
                info = parse_ani(blob)
            except ValueError as e:
                rep.errors.append(f"{where}: unreadable .ani ({e})")
                continue
            want_delays = spec.delay if isinstance(spec.delay, list) else [spec.delay] * spec.frame_count
            uniform = len(set(want_delays)) == 1
            want_order = [c for c in expected_order
                          if not (c == "rate" and uniform and theme.ani_rate_mode == "auto")]
            order = [c for c in info.chunk_order if c != "LIST:INFO"]
            if order != want_order:
                rep.errors.append(f"{where}: chunk order {order} != {want_order}")
            if info.n_frames != spec.frame_count:
                rep.errors.append(f"{where}: {info.n_frames} frames != {spec.frame_count}")
            # What Windows will play: the rate chunk if present, else anih's default for every step.
            got_delays = info.rates if info.rates is not None else [info.default_rate] * info.n_steps
            if got_delays != want_delays:
                rep.errors.append(f"{where}: delays {got_delays} != {want_delays} (jiffies)")
            if info.default_rate != want_delays[0]:
                rep.errors.append(f"{where}: anih default rate {info.default_rate} != {want_delays[0]}")
            if len(blob) > theme.ani_budget:
                rep.errors.append(f"{where}: {len(blob):,} B exceeds .ani download budget {theme.ani_budget:,} B")
            _check_ani_offsets(info, where, rep)
            for i, fr in enumerate(info.frames):
                _check_cur(fr, theme.animated_sizes, spec, canvas, theme.hotspot_mode, f"{where}#frame{i}", rep,
                           theme.layer_format)
        _check_notices(theme, v, folder, rep)
        inf = folder / "install.inf"
        if not inf.exists():
            rep.errors.append(f"{v.id}: install.inf missing")
        else:
            text = inf.read_text(encoding="utf-8")
            positions = [text.find(f'Cursors",{r.reg_value},') for r in ROLES]
            if any(p < 0 for p in positions):
                rep.errors.append(f"{v.id}: install.inf does not set all 17 roles")
            elif positions != sorted(positions):
                rep.warnings.append(f"{v.id}: install.inf role lines not in canonical order")
    return rep


def describe(path: Path) -> str:
    """Human-readable dump of any .cur/.ani - use it on other people's ports too."""
    blob = path.read_bytes()
    lines = [f"{path}  ({len(blob):,} bytes)"]
    if blob[:4] == b"RIFF":
        info = parse_ani(blob)
        lines.append(f"  type: .ani  chunk order: {' -> '.join(info.chunk_order)}")
        lines.append(f"  frames: {info.n_frames}  steps: {info.n_steps}  default rate: {info.default_rate} jiffies  flags: {info.flags:#x}")
        if info.rates:
            lines.append(f"  rate: {info.rates[:12]}{' ...' if len(info.rates) > 12 else ''}")
        if info.seq:
            lines.append(f"  seq: {info.seq[:12]}{' ...' if len(info.seq) > 12 else ''}")
        if info.frames:
            first = parse_cur(info.frames[0])
            lines.append("  frame 0 layers: " + ", ".join(f"{e.size}px({e.fmt}) hs{e.hotspot}" for e in first))
            lines.append("  frame 0 image offsets (directory order): " + ", ".join(f"#{i} {e.size}px @{e.offset:,}" for i, e in enumerate(first)))
            worst = max(max(x.offset for x in parse_cur(fr)) for fr in info.frames)
            lines.append(f"  largest image offset in any frame: {worst:,} (loader limit 65,535)")
    else:
        lines.append("   #  size   fmt  hotspot      bytes      starts at")
        for i, e in enumerate(parse_cur(blob)):
            lines.append(f"  {i:>2}  {e.size:>3}px  {e.fmt}  {str(e.hotspot):<10} {e.nbytes:>8,} B  @{e.offset:>9,}")
    return "\n".join(lines)
