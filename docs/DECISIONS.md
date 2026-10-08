# Architecture decisions (short ADRs)

**ADR-1 One package + thin theme repos.** `w11-cursor-toolkit` (pip package `w11cursor`) holds all code;
each theme repo holds only `theme.toml`, `overrides/`, the pinned upstream, docs, and a 10-line workflow.
*Why:* a fix (e.g. hotspot math) lands once and every theme rebuilds. A common split for cursor build toolchains.

**ADR-2 Own packer, not clickgen.** clickgen's Windows output is one size per file (it ships separate
Regular/Large/XL packs) and had hotspot/INF-order bugs. We need multi-layer files. clickgen is the design
reference only.

**ADR-3 Build on Linux, verify on Windows.** cairosvg needs native cairo (trivial on Linux, painful on Windows).
CI builds on `ubuntu-latest`, then loads every file through `user32` on `windows-latest`. Locally: build in
Fedora/WSL, test on Windows.

**ADR-4 PNG layers by default.** BMP layers make a 15-layer `.cur` ~800 KB and an 8-frame `.ani` >1.3 MB.
Capitaine already ships PNG layers that load on Win11.
*Update (2026-10-08, build 26200.9457):* **one format per file, never mixed.** In `.cur` files that mixed BMP and PNG
layers, Windows never used the PNG layers (2 of 2 files, even a PNG at offset 70; all-PNG and all-BMP files used every
layer - SIZE_POLICY.md "Static .cur"). The old escape hatch `png_min_size = 256` (BMP below 256, PNG at 256) would
have produced exactly those files. It is gone: `[sizes] layer_format = "png"` (default) or `"bmp"` applies to every
layer, `pack_cur` cannot mix, a leftover `png_min_size` key is a config error, and `validate` errors on any `.cur` or
`.ani` frame that mixes formats or differs from `layer_format`.

**ADR-5 Hotspot "point" mode by default.** `round(v*N/canvas)` treats hotspots as geometric points (arrow tips).
It reproduces the validated Capitaine values exactly. The pixel-centre formula from the research report
drifts 4 px at 256 for tip-shaped cursors; it remains available as `hotspot_mode = "center"`.

**ADR-6 Validator re-reads bytes.** Never trust the builder: parse the output and recompute expectations.
Every theme CI run = validate + real Windows load test.

**ADR-7 Licensing boundary.** Toolkit MIT, artwork repos keep upstream license (GPL/LGPL). No artwork in
the toolkit except the self-drawn demo.

**ADR-8 Naming.** `<theme>-cursors-w11-hidpi` for new repos. Existing `Layan-Gold-cursors-for-Windows` keeps
its name (stars/links); optional rename later — GitHub redirects old URLs.

**ADR-9 Variants = only those on the gnome-look page.** Comix 12, Future 1, Future-cyan 1, Polar 3, Material 3.
*Amendment (2026-10-08):* one repo may combine gnome-look pages that are the same artwork from the same upstream
source. Future (p/1457141) and Future-cyan (p/1465392) ship as two variants of `future-cursors-w11-hidpi`:
same repo and commit, all 93 drawings render with identical shapes, only the accent colour differs. Still no
invented variants: each one exists on a gnome-look page.

**ADR-10 Windows cairo: preload by full path.** cffi 2.x opens bare DLL names with
`LoadLibraryExA(name, NULL, 0)` (legacy search order), which ignores `os.add_dll_directory` — so
`CAIROCFFI_DLL_DIRECTORIES` alone fails (observed on the test machine, [build 26200.9457], Oct 2026). The toolkit loads
`libcairo-2.dll` by full path via ctypes first; Windows then reuses the loaded module for the bare name.
PATH is never changed because MSYS2's bin also contains `python.exe`.

**ADR-11 `.ani`: write `rate` only when delays differ (`ani_rate = "auto"`).** A uniform delay lives in
`anih` alone, exactly like Microsoft's `aero_busy.ani`/`aero_working.ani` (`anih -> LIST:fram`, no `rate`).
Mixed delays get a `rate` chunk after `LIST`. `pack_ani` raises if delays are mixed but the chunk order has
no `rate` (it used to drop the timing silently). `validate` checks per-step delays and the anih default.
`LIST:INFO` (scheme name) stays. `"always"` restores the old layout.
*Evidence:* SIZE_POLICY.md ".ani layout experiment": both layouts load through user32 (34/34) and
`GetCursorFrameInfo` reads back `[4,4,3,4,3,4,4,3]` from a rate chunk after LIST. `scripts/Get-AniFrameTiming.ps1`
repeats that check in CI (non-blocking until it passes on the GitHub runner; control = `aero_busy.ani`).

**ADR-12 Renderer is chosen per theme (`[render] renderer`).** `cairosvg` stays the default, and
**capitaine stays on cairosvg** (its antialiasing tested best there, and its published files must not change).
**Themes whose SVGs use filters use `resvg`** (resvg-py 0.5.0, pure abi3 wheel, no native deps): cairosvg 2.9.1
implements only feOffset/feBlend/feFlood and draws `feGaussianBlur` shadows hard-edged.
*Evidence:* fixture `tests/fixtures/blur-shadow.svg` at 128 px: cairosvg 2 alpha levels, resvg 243 (the maintainer's own
test: 8 vs 161). Obsidian A/B (local comparison, not published): hard offset shadows with cairosvg,
soft shadows with resvg at 32/64/128. Recolour is the same text replacement for both backends.
*Safety:* resvg loads `<image>` files by absolute path even without `resources_dir` (verified), so every SVG
passes one shared guard before ANY backend (`render/guard.py`, see LEGAL.md): only `#id` and `data:` references,
no `@import`, no `<text>`. resvg also skips system fonts, so builds don't depend on the machine's fonts.

**ADR-13 Cursors from one Inkscape master (`[source] master` + `layers` / `transform` / `rotate`).**
Polar (and Obsidian) ship one `Cursors.svg` with a layer per drawing; some Windows cursors are composites
(Help = Arrow + Info), rotated copies (dgn1/dgn2 = NS ∓45°) or rotation animations (spinner bar +10°/frame).
`split.py` keeps the named top-level layers and **removes** the rest (hidden content would still reach the guard),
keeps `<defs>`, drops metadata/namedview, errors on drawables outside layers, and **always writes
`viewBox="0 0 W H"`**; a master whose viewBox differs from width/height is an **error** (no silent rescale).
`rotate.center` is in the rotated element's **parent** coordinates and the rotation is composed **in front of**
its existing transform (tested with a pre-transformed group). Static overrides in `overrides/` still win.
*Evidence:* LAYER_SPLITTING_DESIGN.md (IoU 1.00 for diagonals, +10°/frame fits the upstream frames).

**ADR-14 No baked-in drop shadow; Windows draws its own.** Polar's upstream PNGs have a soft shadow that is not
in the SVG (fit: offset 2,2, blur 1.5, 50 %). Windows 11 draws a pointer shadow under custom cursors itself.
*Evidence (maintainer, test machine [build 26200.9457], 2026-10-07):* Polar installed (its files contain no shadow); Settings > Accessibility >
Mouse pointer and touch > "Enable mouse pointer shadow" ON → a small shadow appears under the pointer; OFF → it
disappears. A shadow baked into the artwork would therefore be doubled for everyone with the toggle on.
*Decision:* no shadow in the artwork (option C). The raster post-process design (LAYER_SPLITTING_DESIGN.md §12)
is kept as designed-not-implemented; revisit only as an opt-in variant. Themes document the toggle in their README.
*Addendum (2026-10-08) - shadows baked into the SVG:* `[render] strip_filtered = true` removes every element drawn
through an SVG filter (`filter:url(#…)` in style or a `filter` attribute) and then every `<filter>` left unused;
a file with nothing to remove passes through unchanged. Opt-in per theme, because a filter is not always a shadow.
*Evidence (Material Cursors @2a5f302):* all 600 SVGs checked - 1,158 filtered elements, every one a top-level black
fill at opacity 0.3 without stroke, and nothing else uses a filter, so the option removes exactly the shadow. Tests:
`tests/test_strip_filtered.py`. A toolkit older than this ignores the key and would bake the shadow in, so theme
workflows using it must pin a tag that has it.
