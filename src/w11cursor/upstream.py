"""`w11cursor unpack`: verify a vendored upstream archive and extract only what the build needs.

For themes whose upstream exists only as a tarball (Polar), the ORIGINAL archive is committed unchanged under
upstream/ (GPL "corresponding source"), and the build reads files extracted from it into a git-ignored folder.
The same command runs locally and as the CI `pre-build` step, so both builds start from identical bytes.

    [upstream]
    kind    = "tarball"
    archive = "upstream/27913-PolarCursorThemes.tar.bz2"   # committed, never modified (Hard rule 1)
    sha256  = "03d77c52...e50c16f598"                       # checked BEFORE anything is read from it
    extract = ["PolarCursorTheme/Source/Cursors.svg"]      # exact member names; regular files only
    into    = "build/upstream"                              # git-ignored; wiped and re-created each run
"""
from __future__ import annotations

import hashlib
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath

from .config import Theme


class UnpackError(ValueError):
    pass


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def unpack(theme: Theme, log=print) -> list[Path]:
    up = theme.upstream
    if up.get("kind") != "tarball":
        raise UnpackError(f"[upstream] kind = {up.get('kind')!r}: unpack only handles kind = \"tarball\"")
    for key in ("archive", "sha256", "extract", "into"):
        if key not in up:
            raise UnpackError(f"[upstream] missing '{key}'")
    want = str(up["sha256"]).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", want):
        raise UnpackError(f"[upstream] sha256 must be 64 hex digits, got {up['sha256']!r}")
    members = up["extract"]
    if not members or not all(isinstance(m, str) for m in members):
        raise UnpackError("[upstream] extract must be a non-empty list of archive member names")

    root = theme.root.resolve()
    archive = (root / up["archive"]).resolve()
    into = (root / up["into"]).resolve()
    if not _inside(into, root) or into == root:
        raise UnpackError(f"[upstream] into = {up['into']!r} must be a sub-folder of the theme")
    if _inside(into, root / "upstream"):
        raise UnpackError("[upstream] into must not be inside upstream/ (pinned sources are never written to)")
    if not archive.is_file():
        raise UnpackError(f"archive not found: {archive}")

    got = hashlib.sha256(archive.read_bytes()).hexdigest()
    if got != want:
        raise UnpackError(f"{archive.name}: SHA-256 {got} != pinned {want} - refusing to use it")
    log(f"{archive.name}: SHA-256 OK ({got})")

    for name in members:
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts or "\\" in name:
            raise UnpackError(f"unsafe member name {name!r}")

    if into.exists():
        shutil.rmtree(into)
    written = []
    with tarfile.open(archive, "r:*") as tf:
        for name in members:
            try:
                m = tf.getmember(name)
            except KeyError:
                raise UnpackError(f"{name!r} is not in {archive.name}") from None
            if not m.isfile():
                raise UnpackError(f"{name!r} is not a regular file (symlinks/devices are never extracted)")
            dest = into.joinpath(*PurePosixPath(name).parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = tf.extractfile(m).read()
            dest.write_bytes(data)
            written.append(dest)
            log(f"  {name}  {len(data):,} B  sha256 {hashlib.sha256(data).hexdigest()}")
    return written
