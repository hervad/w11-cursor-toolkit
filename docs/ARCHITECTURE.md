# Architecture

```
w11-cursors/                         ← workspace folder = LOCAL-ONLY git repo (CLAUDE.md, VSCODE_PROMPTS.md, docs/)
├── docs/                            MIGRATION.md · THEME_LICENSES.md (workspace-local, never published)
├── w11-cursor-toolkit/              ← repo: hervad/w11-cursor-toolkit   (MIT, pip package `w11cursor`)
│   ├── src/w11cursor/
│   │   ├── roles.py        17 Windows roles, canonical registry order, Xcursor name hints
│   │   ├── sizes.py        size policy defaults (static/animated lists, budgets, chunk order)
│   │   ├── config.py       theme.toml → Theme dataclass, validation, same_as/overrides resolution
│   │   ├── hotspot.py      design-space → per-size hotspot ("point" | "center")
│   │   ├── render/         SVG → RGBA (cairosvg default; resvg for themes with SVG filters, ADR-12)
│   │   ├── pack/cur.py     multi-layer .cur writer + parser
│   │   ├── pack/ani.py     RIFF/ACON .ani writer + parser (configurable chunk order)
│   │   ├── inf.py          install.inf (17 roles) + uninstall.cmd
│   │   ├── build.py        orchestration → dist/<variant>/ + zip
│   │   ├── validate.py     re-parse built files, assert everything; `inspect` dumps
│   │   ├── probe.py        size-probe cursor
│   │   ├── split.py        cursors cut from one Inkscape master (layers / transform / rotate, ADR-13)
│   │   ├── upstream.py     `unpack`: verify a vendored upstream tarball (sha256), extract what the build needs
│   │   └── cli.py          w11cursor build | validate | inspect | probe | unpack
│   ├── scripts/            Test-LoadCursors.ps1 · Get-AniFrameTiming.ps1 · Run-SizeProbe.ps1 · Set-CursorSize.ps1
│   ├── examples/demo-theme self-drawn theme proving the pipeline end-to-end
│   ├── tests/              pytest (hotspots, .cur/.ani round-trips, INF order, e2e build, sizes vs probe data)
│   ├── docs/               SIZE_POLICY · DECISIONS · LAYER_SPLITTING_DESIGN · ARCHITECTURE · LEGAL · probe-results.csv
│   ├── theme-template/     copy for any future theme (versioned with the toolkit features it uses)
│   └── .github/workflows/  ci.yml (tests + Windows load) · build-theme.yml (REUSABLE, called by themes)
└── themes/                          ← one folder = one GitHub repo
    ├── material-cursors-w11-hidpi/        GPL-2.0   3 variants
    ├── future-cursors-w11-hidpi/          GPL-3.0   1 variant
    ├── future-cyan-cursors-w11-hidpi/     GPL-3.0   1 variant
    ├── comix-cursors-w11-hidpi/           GPL-3.0   12 variants
    ├── polar-cursors-w11-hidpi/           GPL-2.0-or-later   3 variants (author notice COPYRIGHT~)
    ├── capitaine-cursors-w11-hidpi/       (git clone of existing repo → migrate)
    └── Layan-Gold-cursors-for-Windows/    (git clone of existing repo → migrate)
```

Each theme repo:
```
theme.toml           all build input (upstream pin, canvas, sizes, variants, 17 role mappings + hotspots)
upstream/            git submodule pinned to a commit, or the original tarball (sha256-pinned; `w11cursor unpack`)
overrides/           SVGs that win over upstream (_all/ or <variant>/) — Pin/Person, fixes
.github/workflows/release.yml   → uses hervad/w11-cursor-toolkit/.github/workflows/build-theme.yml@vX
README.md CREDITS.md LICENSE PORT_STATUS.md
```

Data flow per variant: `theme.toml` → for each of 17 roles → resolve `same_as` → find SVG (overrides first)
→ render every size natively → scale hotspot → pack `.cur` (or N frames → `.ani`) → `install.inf` →
zip → CI validate → Windows `user32` load test → release with SHA256SUMS.
