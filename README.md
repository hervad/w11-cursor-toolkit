# w11-cursor-toolkit (`w11cursor`)

Shared build toolchain for my Windows 11 HiDPI cursor ports. One package; every
theme repo is just a `theme.toml` + a 10-line workflow that calls this repo.

```
theme.toml ──► config ──► render (SVG → RGBA, every size natively)
                       ──► pack (.cur multi-layer / .ani RIFF)
                       ──► install.inf (17 roles incl. Pin + Person) + uninstall.cmd
                       ──► validate (re-parse bytes, assert sizes/hotspots/chunk order/budget)
                       ──► zip per variant ──► GitHub Release
```

## Install (dev)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

`cairosvg` needs the native **cairo** library (`inspect` and `probe` don't):

| Where | How |
|---|---|
| Fedora | `sudo dnf install cairo` (usually already there) |
| WSL (Ubuntu) | `sudo apt install libcairo2` |
| **Windows native** | 1. `winget install MSYS2.MSYS2` 2. open *MSYS2 UCRT64* and run `pacman -S mingw-w64-ucrt-x86_64-cairo` 3. done — the toolkit preloads `C:\msys64\ucrt64\bin\libcairo-2.dll` by full path (other location: set `CAIROCFFI_DLL_DIRECTORIES`; no PATH/setx needed) |

Use 64-bit Python on Windows (matches the 64-bit UCRT DLLs). Verify with
`python -c "from w11cursor.render.cairo_backend import ensure_windows_cairo_path as e; print(e()); import cairosvg; print('cairo OK')"`.
CI builds on Linux; a local Windows build may differ by a few antialiasing pixels if its cairo version
differs — **releases are always the CI build**.

## Commands

| Command | What it does |
|---|---|
| `w11cursor build theme.toml --out dist` | Render + pack all variants, write INF, zip |
| `w11cursor validate theme.toml --dist dist` | Re-read built bytes; fail on wrong sizes/hotspots/order/budget |
| `w11cursor inspect FILE...` | Dump any `.cur`/`.ani`: layers, formats, hotspots, image offsets, `.ani` chunk layout (also `C:\Windows\Cursors\aero_*`) |
| `w11cursor preview theme.toml --dist dist` | Draw `docs/preview.png` for the theme README from the built files (exact layers; light + dark panel, or one row per variant when the variants differ in most cursors) |
| `w11cursor inspect --lenient FILE...` | Same for files whose directory sizes disagree with their images: reports claimed vs real size instead of failing |
| `w11cursor probe` | Write the size-probe cursor (each layer shows its own px size) |
| `w11cursor unpack theme.toml` | Tarball upstreams: check the vendored archive's SHA-256, extract only `[upstream] extract` into a git-ignored folder (also the CI `pre-build`) |

Windows-only helpers in `scripts/`: `Test-LoadCursors.ps1` (loads every layer through the
real user32 loader — used by CI), `Get-AniFrameTiming.ps1` (per-step `.ani` delays as user32 parsed
them, checked against a Microsoft control file — CI, non-blocking for now), `Run-SizeProbe.ps1` (interactive size
probe: shows which layer Windows picks per pointer size and display scale; restores all pointer settings) and
`Set-CursorSize.ps1` (changes pointer size live).

Why the defaults are what they are - measured layer choice, size lists, `.ani` limits - is in [`docs/`](docs/):
[SIZE_POLICY](docs/SIZE_POLICY.md), [DECISIONS](docs/DECISIONS.md) (ADRs), [ARCHITECTURE](docs/ARCHITECTURE.md),
[LAYER_SPLITTING_DESIGN](docs/LAYER_SPLITTING_DESIGN.md), [LEGAL](docs/LEGAL.md). Raw probe readings:
[docs/probe-results.csv](docs/probe-results.csv).

## Using it from a theme repo

Start from [`theme-template/`](theme-template/) (theme.toml with every option commented, README, CREDITS,
workflow). The theme's workflow calls the reusable build:

```yaml
# .github/workflows/release.yml
jobs:
  build:
    uses: hervad/w11-cursor-toolkit/.github/workflows/build-theme.yml@v0.1.0
    with:
      toolkit-ref: v0.1.0
      # pre-build: w11cursor unpack theme.toml   # if upstream is a vendored tarball ([upstream] archive/sha256)
    permissions:
      contents: write
```

## License

MIT (code only). Cursor artwork in theme repos keeps its upstream license.
