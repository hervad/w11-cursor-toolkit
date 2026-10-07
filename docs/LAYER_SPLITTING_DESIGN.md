# Design: cursors from one Inkscape master (layer splitting + frames from rotation)

Status: **layer splitting + rotation IMPLEMENTED (ADR-13); drop shadow (§12) designed, rejected (ADR-14).** Evidence gathered 2026-10-07 [build 26200.9457] with local scratch scripts
(outside every repo). Numbers are measured unless marked *inferred*.

Polar (and Obsidian) ship ONE `Cursors.svg` with one Inkscape layer per drawing.
The toolkit today expects one SVG file per cursor. This design adds a second way to name a cursor's art:
"these layers of the master", plus an optional transform and an optional rotation animation.

---

## 1. What Polar actually needs (evidence)

Measured by rendering candidate layer sets with the toolkit's renderer (cairosvg, 32 px) and comparing with
upstream's 32 px PNG exports (IoU of alpha masks; 1.00 = identical shape).

| Upstream PNG | Built from | IoU | Notes |
|---|---|---|---|
| Arrow | layer `Arrow` | 0.98 | |
| Help | layers `Arrow` + `Info` | 0.95 | composite (Arrow alone: 0.63) |
| Link (X11 chain badge) | `Arrow` + `Link` | 0.95 | composite; not the Windows "link" role |
| Copy / Move | `Arrow` + `Copy` / `Arrow` + `move` | 0.95 / 0.98 | composites |
| AppStarting (working) | `Arrow` + `AppSpinner`, bar rotated | 0.95 | `AppSpinner` alone is only the small disc (0.35) |
| Wait (busy) | `Spinner`, bar rotated | see §4 | |
| SizeNS | `NS` | 1.00 | |
| SizeWE | `NS` transposed, `matrix(0 1 1 0 0 0)` | 1.00 | plain rotate(90) about centre: 0.90 |
| **SizeNWSE** | `NS` rotated −45° about its centre (5.65, 12.65), centre moved to (9.5, 9) | **1.00** | no layer matches without rotation (best 0.66) |
| **SizeNESW** | `NS` rotated +45°, centre moved to (9, 9.5) | **1.00** | |
| SizeAll | `Fleur` | 1.00 | |
| IBeam | `Caret` | 1.00 | |
| UpArrow | `ArrowUP` | 1.00 | |
| HandPointer | `Hand Pointer` | 0.96 | |
| Crosshair / NO / Handwriting | `Crosshair` / `Circle` / `Pencil` | 0.84 / 0.82 / 0.82 | best match by far; visual check before building |

So the feature needs: **(a)** several layers per cursor, **(b)** an optional SVG transform per cursor,
**(c)** frames made by rotating one element.

---

## 2. theme.toml syntax

```toml
[render]
renderer      = "cairosvg"            # "resvg" if the drop-shadow option (§8) is chosen
design_canvas = 32                    # must equal the master's width/height (checked)

[source]                              # NEW - optional; themes with one SVG per cursor don't use it
master = "upstream/PolarCursorTheme/Source/Cursors.svg"   # relative to the theme root

[cursors.arrow]
layers  = ["Arrow"]                   # inkscape:label of top-level layers in the master
hotspot = [0, 0]                      # design space = master canvas, AFTER any transform

[cursors.help]
layers  = ["Arrow", "Info"]           # composite; stacked in the MASTER's document order, not list order
hotspot = [0, 0]

[cursors.horz]
layers    = ["NS"]
transform = "matrix(0 1 1 0 0 0)"     # SVG transform on a wrapper <g> around the kept layers
hotspot   = [12, 5]

[cursors.dgn1]                        # Windows "Diagonal Resize 1" = NW-SE
layers    = ["NS"]
transform = "translate(9 9) rotate(-45) translate(-5.65 -12.65)"
hotspot   = [9, 9]

[cursors.busy]
layers      = ["Spinner"]
rotate      = { id = "g12727", center = [16.422, 16.421], step_deg = 10 }
frame_count = 18
delay       = [4, 3, 4, 3, 4, 4, 3, 4, 3, 4, 4, 3, 4, 3, 4, 4, 3, 4]   # see §5 - maintainer chooses
hotspot     = [10, 10]
```

Rules (checked by `load_theme`, ConfigError otherwise):
- A cursor has exactly one of `svg` / `frames` / `same_as` / `layers` (today: one of the first three).
- `layers` needs `[source] master`. `rotate` needs `layers` + `frame_count >= 1`. `transform` needs `layers`.
- `rotate.center` is in the coordinate system of the rotated element's **parent**: the splitter prepends
  `rotate(step_deg*i cx cy)` to that element's `transform`. (Canvas coordinates would need the inverse of the
  whole ancestor transform chain; parent coordinates are exact and simple. §4 shows how to find them.)
- Frame `i` (0-based) is rotated by `i * step_deg`. Positive = clockwise on screen (y points down).
- Hotspots are given in master canvas units after the transform; they scale per size as today (ADR-5).
- An override `overrides/<variant>/<key>.svg` or `overrides/_all/<key>.svg` still wins (static cursors);
  a per-cursor `master = "..."` key may replace the theme master for one cursor (e.g. a fixed-up Help).

---

## 3. The splitter (REMOVES other layers, always writes a viewBox)

Pipeline per cursor/frame: **master text → split → transform → rotate → recolour → guard → backend.**
Everything after "split" already exists (`apply_recolor`, `guard.check_svg`, backends).

1. Parse the master with ElementTree (namespace prefixes registered so `xlink:`/`inkscape:` survive).
2. Layers = **direct children** of `<svg>` with `inkscape:groupmode="layer"`, matched by exact `inkscape:label`.
   Errors: unknown label (message lists all labels), duplicate label, any requested label used twice.
3. **Remove** every other top-level layer (not hide). Why: hidden content still reaches the guard and the
   renderer; Obsidian's hidden Info/DND-ask layers contain `<text>` and tripped the guard while splitting
   Arrow. Removal makes "what's in the file" == "what's drawn".
4. Drop `sodipodi:namedview` and `<metadata>` (no visual effect). Keep `<defs>` whole (gradients, filters).
   **Error** if the master has drawable elements outside any layer (they would appear in every cursor).
5. Set `display:inline` on each kept layer, preserving its other style properties. Sub-elements keep their
   own `display` (hidden objects inside a layer stay hidden).
6. `transform` (if any): wrap the kept layers in one `<g transform="...">`.
7. `rotate` (if any): find `id` **inside the kept layers** (error if absent or outside), prepend the rotation.
8. **viewBox: always explicit.** Read `width`/`height` (unitless or `px` only; other units → error; must be
   square and equal `design_canvas`). If the master has no `viewBox`, write `viewBox="0 0 W H"`. If it has
   one that equals `0 0 W H`, keep it. **If it has a different one → error** (recommended: overwriting would
   silently rescale the art; decided: error). Polar and Obsidian both have **no** viewBox (measured).
9. Serialize to text in memory. Optional CLI for inspection: `w11cursor extract theme.toml --out dir`
   (writes each cursor/frame SVG so a human can open it in Inkscape/browser).

Recolour stays a text replacement on the split result. For Polar it is safe: `#ff5e13` and `#912121` each occur
exactly once in the master, and only the `Spinner`/`AppSpinner` layers use gradients that chain to them.

---

## 4. Frames from rotation - Polar evidence

Spinner structure (layer `Spinner`): fixed disc = `path12725` (grey gradient) + `path12191` (black outline);
**bar = group `g12727`** (two rects: `rect12731` radial-gradient fill, `rect12729` gradient stroke).

How the centre was found: the bar rects' centre in `g12727`'s own coordinates is (16.422, 16.421); `g12727`'s
transform is `matrix(-1,0,0,-1, 32.844, 32.841)` (a 180° turn about 16.42,16.42), which maps that point to
itself → centre in the parent's coordinates = **(16.422, 16.421)**. Same for AppSpinner (`g13479`, near-identity
matrix → also (16.422, 16.421)).

Test: render 18 frames rotating only the bar, compare with upstream `Spinner{i}.png` (mean |diff|, 0-255):

| Hypothesis | Spinner (cairosvg) | Spinner (resvg) | AppSpinner (with Arrow, cairosvg) |
|---|---|---|---|
| bar static | 9.50 (rises to 11.1) | 9.69 | 6.15 |
| **+10°/frame (clockwise)** | **4.09, flat 3.6-4.4** | **4.21** | **4.59, flat** |
| −10°/frame | 9.35 (dips only at 0 and 9) | 9.44 | 5.94 |

The ≈4 residual is present at frame 0 too (no rotation involved): it is the drop shadow missing from the SVG
(§8) plus renderer differences vs Inkscape 0.43, not a rotation error.

---

## 5. Timing (maintainer chooses) - 18 frames, original 60 ms = 3.6 jiffies, cycle 1,080 ms

| Option | Delays (jiffies) | Cycle | vs original | Max drift inside a cycle |
|---|---|---|---|---|
| uniform 3 | 3 × 18 | 900 ms | −16.7 % | 180 ms |
| uniform 4 | 4 × 18 | 1,200 ms | +11.1 % | 120 ms |
| 11×4 + 7×3, grouped | 4×11 then 3×7 | 1,083 ms | +0.3 % | 73 ms |
| **11×4 + 7×3, spread** (error diffusion) | `4,3,4,3,4,4,3,4,3,4,4,3,4,3,4,4,3,4` | 1,083 ms | +0.3 % | **6.7 ms** |

Recommendation: the spread pattern (same total as grouped, but no visible speed-up/slow-down within a turn).
It needs a `rate` chunk (ADR-11 writes it automatically for mixed delays; user32 parsing of mixed delays is
verified). On-screen timing is not verified by any method yet.

---

## 6. Blue and Green recolours (measured from upstream PNGs)

Upstream variants differ ONLY in hue: bar pixels in all 18 frames have identical lightness (0.471) and
saturation (0.720) in all three variants; mean hue default 13.9°, Blue 194.1° (shift +180.2°, i.e. −179.9°),
Green 88.2° (+74.2°). → apply the same hue rotation to the two gradient stops (HLS, L and S unchanged):

| Variant | recolor map | Upstream bar hue / L / S | Ours (cairosvg) hue / L / S |
|---|---|---|---|
| default | — | 13.9° / 0.471 / 0.720 | 13.8° / 0.455 / 0.533 |
| Blue | `#ff5e13 → #13b3ff`, `#912121 → #219191` | 194.1° / 0.471 / 0.720 | 194.0° / 0.455 / 0.533 |
| Green | `#ff5e13 → #7cff13`, `#912121 → #769121` | 88.2° / 0.471 / 0.720 | 88.1° / 0.455 / 0.533 |

Hue matches within 0.1°. The lower saturation (0.533 vs 0.720) is identical for the un-recoloured default, so it
is a renderer/export difference, not a recolour error. (Swatch comparison done locally, not published.)

README note (proposed): *"Blue and Green recolour the busy/working bar by rotating the original orange's hue
(+180° / +74°), measured from the upstream PNGs. Upstream's own recolouring script is an incomplete draft, so
these colours approximate the originals (hue within 0.1°)."*

---

## 7. Diagonals and the AngleNW/AngleSW quirk

- Windows has exactly two diagonal roles (`roles.py`): **dgn1 = SizeNWSE** ("Diagonal Resize 1", `\`) and
  **dgn2 = SizeNESW** ("Diagonal Resize 2", `/`). Both come from layer **`NS`** rotated −45° / +45° (§1).
- The `Angle` layer feeds `AngleNW/NE/SW/SE`, which Build.sh installs as X11 corner names (`ul_angle`,
  `ur_angle`, `ll_angle`, `lr_angle`). None of the 17 Windows roles is a corner cursor, so **the AngleSW.conf →
  AngleNW.png quirk does not affect the Windows port at all.**
- Hotspot: `.conf` says (9, 9) for both; the fitted centres are (9.5, 9) / (9, 9.5). Proposal: place the arrow
  centre exactly at (9, 9) via the transform and use hotspot (9, 9), so art and hotspot agree by construction.

---

## 8. Finding: upstream's PNGs have a drop shadow that is NOT in the SVG

Polar's SVG has no filters and no shadow shapes; Build.sh/Buildwand.sh run no image processing. Yet every
upstream PNG has a soft shadow (Arrow: 282 semi-transparent px vs our 72; bbox 20×29 vs 16×24).
Fitting `alpha ≈ A + opacity·blur(shift(A, dx, dy), r)·(1 − A)` at 32 px gives the SAME parameters for three
different cursors: **dx = 2, dy = 2, blur r = 1.5, opacity 0.5** (alpha error 7.0→0.44 Arrow, 8.3→0.87
HandPointer, 7.6→0.39 SizeNS). *Inferred:* one uniform effect added outside the SVG (tool unknown).

Options (maintainer chooses):
- **A. No shadow** — the port shows the SVG as drawn; looks flatter than the originals.
- **B. Synthetic shadow (recommended for fidelity):** `[render] drop_shadow = {dx=2, dy=2, blur=1.5, opacity=0.5}`
  makes the splitter add one filter (feGaussianBlur on SourceAlpha → feOffset → 50 % black → merged under the
  art) around the kept layers. In design units, so it scales to every size. Requires `renderer = "resvg"`
  (cairosvg ignores blur, ADR-12) - checked at load time. Listed in CREDITS "Changes from upstream".
- C. Rely on Windows' "pointer shadow" setting — *unverified* whether it applies to custom/alpha cursors; not
  recommended without a test.

---

## 9. Help "?" and fonts

- **Polar: no `<text>` anywhere** (0 `<text>`, 0 `<tspan>`, 0 `<flowRoot>`); the whole master passes the guard.
  The "?" in the `Info` and `DND-ask` layers is already paths (`path7210`, `path7212`, `path7183`, `path7185`,
  `text6443`, `path3402` - the id `text6443` is the usual leftover of Inkscape's "Object to Path"). Their style
  still names `font-family:Nimbus Roman No9 L`, which has no effect on paths. No conversion needed.
- Licence of those glyph outlines: they derive from URW's Nimbus Roman No9 L, which URW released under the GPL
  (the Ghostscript font set) — *from memory, not verified here*; compatible with GPL-2.0-or-later in any case,
  and the author distributed the converted outlines as part of his GPL work.
- Obsidian is different: its "?" is live `<text>` in Bitstream Vera Sans → would need an override with
  the text converted to paths; Vera's licence allows embedding outlines (*from memory; check if it ever matters*).

---

## 10. Proposed Polar role map (17 Windows roles)

| Role | Source | Hotspot | | Role | Source | Hotspot |
|---|---|---|---|---|---|---|
| arrow | `Arrow` | 0,0 | | vert | `NS` | 5,12 |
| help | `Arrow`+`Info` | 0,0 | | horz | `NS` + transpose | 12,5 |
| working | `Arrow`+`AppSpinner`, rotate `g13479` | 0,0 | | dgn1 | `NS` −45° | 9,9 |
| busy | `Spinner`, rotate `g12727` | 10,10 | | dgn2 | `NS` +45° | 9,9 |
| precision | `Crosshair` | 11,11 | | move | `Fleur` | 12,12 |
| text | `Caret` | 5,9 | | alternate | `ArrowUP` | 6,0 |
| handwriting | `Pencil` | 0,20 | | link | `Hand Pointer` | 5,0 |
| unavailable | `Circle` | 11,11 | | pin / person | **decided: `same_as = "link"`** (v1) | |

Hotspots from upstream `.conf` (design space 32). Busy hotspot (10,10) vs computed disc centre in canvas
coordinates ≈ (10.5, 10.5) - to confirm visually.

---

## 11. Tests (with a small multi-layer fixture)

`tests/fixtures/layers.svg` (self-drawn, 16×16, **no viewBox**): layer `A` (red square), layer `B`
(`display:none`, blue square elsewhere), layer `T` (contains `<text>`), layer `S` (grey disc + group `bar`,
a thin vertical rect), one gradient in `<defs>` used by `A`.

1. split `["A"]`: B, T, S removed (not present in output text); `viewBox="0 0 16 16"` written; renders red only;
   the guard passes even though the master contains `<text>` in T.
2. composite `["B", "A"]`: both drawn, stacking follows the master order (A under B), not list order.
3. errors: unknown label (message lists labels), duplicate label in master, `rotate.id` not in kept layers,
   width `16mm`, existing different viewBox, drawable element outside layers.
4. transform: `rotate(90 8 8)` on a known asymmetric shape → expected pixel moves.
5. rotation frames: `bar` at 0° vertical, 90° horizontal, disc pixels identical in every frame.
6. recolour after split hits a `<defs>` gradient stop; both backends (cairosvg skips if no cairo).
7. e2e: a tiny theme using `[source] master` builds and validates (17 roles, frame count, delays).

---

## 12. Drop shadow as a RASTER post-process - DESIGNED, NOT IMPLEMENTED

**Rejected (ADR-14) because of double shadow:** the maintainer's test [build 26200.9457] showed Windows draws its own pointer shadow under
custom cursors ("Enable mouse pointer shadow" on → shadow under Polar; off → none). A baked-in shadow would be
doubled for everyone with the toggle on. Revisit only as an opt-in variant. The design below is kept for that case.

The maintainer tested whether Windows' own "Enable pointer shadow" also draws under custom 32-bit cursors - it
does, so a baked-in shadow would double it. Whatever the answer, a shadow (if any) is NOT an SVG filter:

```toml
[render]
shadow = { dx = 2, dy = 2, blur = 1.5, opacity = 0.5 }   # design units (design_canvas space); omit = no shadow
```

- **Where:** in `build._layers`, after `render_svg_text()` and before `pack_cur()`: per output size `n`,
  `k = n / design_canvas`; shadow = `opacity × GaussianBlur(σ = blur·k)( shift(alpha, dx·k, dy·k) )`, black,
  composited UNDER the art (`out = art over shadow`). Same code for cairosvg and resvg → Polar stays on cairosvg.
- **Sub-pixel offsets:** at 40/56/72 px, `dx·k` is fractional (e.g. 2.5 px). Shift on a 4× supersampled alpha
  (or shift with bilinear resampling) so small sizes don't snap to whole pixels; blur at full resolution.
- **Canvas:** the cursor stays n×n (Windows layer size); the shadow is clipped at the edges (see below). Hotspots
  are unchanged (the shadow is not clickable art).
- **Config checks:** all four keys numeric, `opacity` 0..1, `blur` ≥ 0; applies to every role and frame.
- **Recorded in** CREDITS "Changes from upstream" for themes that use it (Polar: re-creates the upstream PNGs' shadow).

### Clipping evidence (Polar, orange, packaged 128 px layers, shadow applied on a padded canvas)
Model at 128 px: offset (8, 8) px, σ 6 px, opacity 0.5 (= 2, 2 / 1.5 design units).

| Role (frames) | Art bbox (design units) | Shadow mass outside the canvas | Max shadow alpha at right/bottom edge |
|---|---|---|---|
| arrow | 0,0 – 15.25,24.25 | 0.52 % | 0/255 |
| help | 0,0 – 27,25.25 | 0.32 % | 2/255 |
| working (18) | 0,0 – 27,25 | 0.33 % (worst frame) | 2/255 |
| busy (18) | 0,0 – 21,21 | 0.18 % | 0/255 |
| text | 0,0 – 11,19 | 0.85 % | 0/255 |
| dgn1 / dgn2 | 0,0 – 18,18 | 0.55 / 0.56 % | 0/255 |
| others (precision, handwriting, unavailable, vert, horz, move, alternate, link, pin, person) | — | 0.04 – 0.23 % | 0/255 |

**No visible clipping.** Right/bottom edges reach at most 2/255. The small lost mass is the blur's faint tail past
the **top/left** edges: every Polar cursor's art starts at (0, 0), and blur reaches ~3.3σ ≈ 5 design units while the
offset moves only 2 inward. Upstream's 32 px PNGs have the same canvas, so they clip the same way.
Build-time guard (proposed): warn if any layer loses > 2 % of its shadow mass or has edge alpha > 16/255.

### How tests/validation would prove "applied and scaled"
The validator re-reads bytes but does not re-render, and the final image alone cannot separate art from shadow.
So the proof lives in tests, with the validator doing a cheap plausibility check:
1. **Unit test (exact):** a synthetic 16×16 opaque square at design size 32, rendered with and without shadow at
   n = 32, 64, 128. `diff = with − without` (alpha). Assert: diff's alpha-weighted centroid minus the square's centroid
   = (dx, dy)·n/32 ± 0.5 px; diff's spread (second moment along x outside the square) ∝ blur·n/32 within 10 %; peak
   shadow alpha ≤ 255·opacity; art pixels unchanged.
2. **Renderer independence:** the same test parametrized over cairosvg and resvg → identical diffs (± 1 alpha).
3. **e2e:** demo theme built with `shadow` on vs. off: every layer of every file differs only where the art is
   transparent; hotspots identical; validate OK; Test-LoadCursors OK.
4. **Validator (plausibility, optional):** when `shadow` is set, each layer must have semi-transparent pixels
   below-right of its opaque bbox (`shadow` off → none required). Catches "forgot to apply", not exact values.

## 13. Decisions (maintainer, 2026-10-07)

1. Timing: **spread pattern** `4,3,4,3,4,4,3,4,3,4,4,3,4,3,4,4,3,4` (1,083 ms). Fallback if stutter is ever seen: uniform 4.
2. Drop shadow: **none in the artwork** (option C, ADR-14) - Windows draws its own pointer shadow. §12 kept as an opt-in design.
3. Master viewBox different from `0 0 W H`: **error** (implemented).
4. `rotate.center` in **parent coordinates**, composed **in front of** an existing transform (implemented + tested).
5. Pin / Person (Polar): **`same_as = "link"`** for v1 (Windows' own Pin/Person are hand variants); README note.
   Badges drawn in `overrides/` may come later.
6. Diagonals: arrow centre exactly at **(9, 9)**, hotspot (9, 9) (implemented).

Status: §2-§4 implemented in the toolkit (split.py, ADR-13); Polar wired (themes/polar-cursors-w11-hidpi/theme.toml).
