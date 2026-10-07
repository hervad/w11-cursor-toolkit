"""cairosvg backend.

Rule #1 for crispness: render EVERY size natively from the vector source.
Never downscale a 256px bitmap or upscale a 32px one - that is exactly the blur
we're fixing. cairosvg's default antialiasing tested best for Capitaine
(vs resvg, supersampling, CAIRO_ANTIALIAS_BEST).
"""
from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image

# Default MSYS2 UCRT64 location of libcairo-2.dll (installed via
# `pacman -S mingw-w64-ucrt-x86_64-cairo` in the MSYS2 UCRT64 shell).
MSYS2_UCRT64_BIN = Path(r"C:\msys64\ucrt64\bin")
CAIRO_DLL = "libcairo-2.dll"

_preloaded = None  # keep a reference so the DLL stays loaded for the process lifetime


def _ctypes_load(path: str):
    import ctypes

    return ctypes.CDLL(path)


def ensure_windows_cairo_path(env: dict = os.environ, is_windows: bool = os.name == "nt",
                              default_dir: Path = MSYS2_UCRT64_BIN, loader=_ctypes_load) -> str | None:
    """On Windows, preload libcairo-2.dll by FULL PATH before cairocffi imports.

    Why: cairocffi asks cffi to open the bare name "libcairo-2.dll". For bare names cffi 2.x
    calls LoadLibraryExA(name, NULL, 0) - the legacy search order (app dir, System32, PATH...),
    which ignores folders added with os.add_dll_directory. So CAIROCFFI_DLL_DIRECTORIES alone
    doesn't help. Loading by full path uses LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR, so the DLL's
    dependencies are found next to it; afterwards Windows returns the already-loaded module
    when cairocffi asks for the bare name.

    Search order: folders in CAIROCFFI_DLL_DIRECTORIES (';'-separated), then MSYS2 default.
    Returns the loaded DLL path, or None. PATH is never modified (MSYS2's bin has python.exe).
    """
    global _preloaded
    if not is_windows:
        return None
    candidates = [Path(p) for p in env.get("CAIROCFFI_DLL_DIRECTORIES", "").split(";") if p.strip()]
    candidates.append(default_dir)
    for folder in candidates:
        dll = folder / CAIRO_DLL
        if dll.exists():
            _preloaded = loader(str(dll))
            env.setdefault("CAIROCFFI_DLL_DIRECTORIES", str(folder))
            return str(dll)
    return None


def render(svg: str, size: int) -> Image.Image:
    ensure_windows_cairo_path()
    try:
        import cairosvg  # needs the native cairo library
    except OSError as exc:  # cairocffi could not load libcairo
        raise RuntimeError(
            "cairosvg could not load the native cairo library.\n"
            "  Fedora/WSL: sudo dnf install cairo  |  sudo apt install libcairo2\n"
            "  Windows:    install MSYS2, run `pacman -S mingw-w64-ucrt-x86_64-cairo` in the MSYS2 UCRT64 shell,\n"
            "              (auto-detected at C:\\msys64\\ucrt64\\bin; for another location set\n"
            "              CAIROCFFI_DLL_DIRECTORIES to the folder containing libcairo-2.dll)\n"
            f"  original error: {exc}"
        ) from exc

    # svg already passed guard.check_svg() in render_svg(); cairosvg's own safe mode (default since 2.7)
    # is a second line of defence - never pass unsafe=True.
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")
