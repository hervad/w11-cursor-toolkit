# Size policy & the size probe

## Test machine
Unless a result says otherwise, everything below was measured on one machine: **Windows 11 Pro, version 25H2,
OS build 26200.9457** (`[Environment]::OSVersion` = 10.0.26200; DisplayVersion `25H2` and UBR `9457` from
`HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion`), one display at **2560×1440**, display scales available
**100 / 125 / 150 / 175 %**. Read on 2026-10-08; no update was installed after 2026-10-06 and the last boot was
2026-10-07 14:53, before the first experiment, so all results here share this build. Every result is tagged
`[build 26200.9457]`; results from other builds must carry their own tag.

## The model (what's known)
- Settings → Accessibility → Mouse pointer → **Size 1–15** writes `HKCU\Control Panel\Cursors\CursorBaseSize`
  = 32, 48, 64 … 256 (16 px per step). Applied live via undocumented `SystemParametersInfo(0x2029, 0, px, …)`.
- Windows picks the layer **CursorBaseSize × bucket(display scale)**: bucket 1.0 for 100–149 %, 1.5 for 150–199 %
  (measured 2026-10-07, see "Visual probe results"; ≥ 200 % not verified). Layer present → crisp. Missing → resampled.
  (Earlier text here said "× display scale"; the probe refuted that.)
- Microsoft's own static cursors embed 32/48/64/96/128; animated ones only 32/48/64.

## Microsoft reference files
Measured [build 26200.9457] with `w11cursor inspect` plus a scan of every frame and layer of
`C:\Windows\Cursors\aero_*` (2026-10-07). Read-only reference; Microsoft's files are never redistributed (inspected locally only).

**Animated (`aero_busy`, `aero_working`, each with `_l`/`_xl`; 6 files, all 556,304 B)**
- Top-level chunk order: `anih -> LIST:fram`. **No `rate` chunk, no `seq ` chunk, no `LIST:INFO`.**
  `flags = 0x1` (AF_ICON only, no AF_SEQUENCE). The delay is uniform and lives in `anih.iDispRate` = 3 jiffies
  (3/60 s = 50 ms/frame). 18 frames, 18 steps.
- **Every frame** (not just frame 0) has exactly 3 layers, **64/48/32, BMP, largest-first**.
  Hotspot scales with the layer (`aero_working`: (0,8)/(0,12)/(0,16); `aero_busy`: centre).
- The `_l`/`_xl` variants have the same layer set and byte size as the base file (not checked byte-for-byte).

**Static (`aero_*.cur`; 42 files, all layers BMP, no PNG)**
- 35/42 files (incl. `aero_arrow.cur`, 136,606 B): **128/96/64/48/32, largest-first**.
- 6/42 files (`aero_person`, `aero_pin` and their `_l`/`_xl`): the same 5 sizes **smallest-first**.
- `aero_arrow_xl.cur`: the 5 standard layers plus a 6th 128 px layer of 19,496 B. That size fits an
  8-bit paletted BMP (40 + 1024 + 16384 + 2048), *inferred from the byte count, not decoded*.
- No stock static has layers above 128 or in between (40/56/72/80 …).

**What this does and doesn't tell us**
- Verified: Microsoft ships `.ani` without `rate`, and that layout loads on Win11 (it is the stock busy cursor).
- *Inference:* since both orders ship, the loader probably doesn't need largest-first layer order.
- Not answered here: whether Windows *requests* sizes like 40 or 80 (Microsoft just doesn't provide them,
  so it may resample), and whether PNG layers or >128 px are OK. The probe and `Test-LoadCursors.ps1` cover those.
- Our toolkit differs from Microsoft on purpose in three ways: PNG layers, sizes above 128, and the
  `anih -> LIST -> rate` order. Each needs its own evidence before it becomes a default.

## What's NOT settled (conflicting sources, including the maintainer's two existing ports)
1. ~~**Exact or bucketed scale?**~~ **SETTLED for 100-199 % (2026-10-07): bucketed** - see "Visual probe results".
   Capitaine embeds 40/80 (assumed exact 125 %/250 %); Layan Gold assumes buckets (100–149 % → 32, 150–199 % → 48 …).
   Layan is right for the tested range.
2. **.ani chunk order** the Win11 loader requires (`anih→LIST→rate` fixed Capitaine; textbook order is
   `anih→rate→LIST`).
3. ~~**.ani size limit**~~ **SETTLED (2026-10-07):** not a file-size limit - every image must start at byte ≤ 65,535
   of its frame (see ".ani size-limit experiment"). PNG frames are fully supported (29 MB PNG .ani loads).

## The probe (settles 1 on the test machine)
`w11cursor probe` writes `size-probe.cur`: every layer draws its own pixel size as a number
(plus odd sizes 36/44/60/88/… to catch unexpected requests).

```powershell
w11cursor probe --out probe
.\w11-cursor-toolkit\scripts\Run-SizeProbe.ps1 -ProbeCur .\probe\size-probe.cur
```
Repeat for each available display scale (100, 125, 150, 175, 200, 250, 300 %). The script restores the pointer
settings afterwards and appends to `probe-results.csv` (with an `os_build` column); the readings so far are
committed as `docs/probe-results.csv`.

**Which scales decide:** at 100/150/200 % both models predict the same layer (those are the bucket boundaries);
**125 % and 175 % discriminate** (e.g. slider 1 at 125 %: exact 40, bucketed 32). The probe has every layer either
model predicts at 100-200 % (toolkit commit adding 84/100/140/168/200; `tests/test_probe.py`).

Reading results: `shown == expected` → exact model. `shown` < expected and snapped to 32/48/64/96/128 →
bucketed model. A `?` (blurry) means the requested size wasn't in the file.

## Settling 2 and 3
```powershell
w11cursor inspect C:\Windows\Cursors\aero_working.ani      # Microsoft's own chunk order + frame layout
```
Then set `ani_chunk_order` in `sizes.py` to whatever passes `Test-LoadCursors.ps1` (CI does this on every
build). For the budget: build the demo with `animated` sizes up to 256 and see where the loader starts failing.

### .ani layout experiment (2026-10-07, [build 26200.9457])
Demo theme built three times (only `ani_chunk_order` / busy `delay` changed; all files also carry our
`LIST:INFO` first). `validate` OK and `Test-LoadCursors.ps1` = **34 files, 0 failures** for every variant.
Per-step delays read back from user32 with the undocumented `GetCursorFrameInfo` (control: Microsoft's
`aero_busy.ani`/`aero_working.ani` read back as 18 × 3 jiffies, matching `inspect`):

| Variant | Top-level chunks | anih rate | user32 per-step jiffies |
|---|---|---|---|
| A | INFO → anih → LIST:fram → rate (uniform) | 4 | 4,4,4,4,4,4,4,4 |
| B | INFO → anih → LIST:fram (no rate) | 4 | 4,4,4,4,4,4,4,4 |
| C | INFO → anih → LIST:fram → rate `[4,4,3,4,3,4,4,3]` | 4 | **4,4,3,4,3,4,4,3** |

Verified: both layouts load, and a `rate` chunk *after* `LIST` is actually used (C differs from its anih value).
Not verified: on-screen timing (GetCursorFrameInfo reports what was parsed, not what the animation timer does),
the textbook `anih → rate → LIST` order, and older Windows builds.
**Decision (ADR-11):** `ani_rate = "auto"`: no `rate` chunk when all delays are equal; `rate` after `LIST` otherwise.

### Visual probe results (Run-SizeProbe.ps1, [build 26200.9457], 2560×1440)
Readings by eye: the number the probe cursor showed; `?` would mark a blurry (resampled) image.

| Scale | 1 | 2 | 3 | 4 | 5 | 7 | 9 | 15 | Exact model | Bucketed model |
|---|---|---|---|---|---|---|---|---|---|---|
| 100 % (2026-10-07) | 32 | 48 | 64 | 80 | 96 | 128 | 160 | 256 | all match | all match |
| 125 % (2026-10-07) | 32 | 48 | 64 | 80 | 96 | 128 | 160 | 256 | **none match** | **all match** |
| 175 % (2026-10-07) | 48 | 72 | 96 | 120 | 144 | 192 | 240 | 256 | **none match** | **all match** |
| 125 %, slider 9 again | | | | | | | 160 | | 200 | 160 ✓ |
| 100 % replication (2026-10-08) | 32 | 48 | 64 | 80 | 96 | 128 | 160 | 256 | all match | all match |
| 125 % replication ×2 (2026-10-08) | 32 | 48 | 64 | 80 | 96 | 128 | 160 | 256 | **none match** | **all match** |

Replications (2026-10-08) repeated 100 % once and 125 % twice with identical readings; the second 125 % run started
from a different pointer state (Windows' accessibility pointer at size 160 instead of a 48 px scheme) - same
readings, restore verified. 49 readings in total, all tagged with the build in `docs/probe-results.csv`.
100 % baseline: every slider used the layer of exactly 16·(slider+1) px, all crisp. It does not separate the models
(they agree at 100 %), but shows Windows picks layers Microsoft doesn't ship (80, 160) when they exist.
125 %: Windows chose the layer of the BASE size (16·(slider+1)) for every slider, although 40/60/100/120/200 px layers
were in the file -> the exact model is refuted for LAYER CHOICE at 125 %. The maintainer: "not blurry, but the right lower side is
edgy". How that layer is then drawn (at its own size, or stretched to base × scale) is open, not needed - see the
conclusion. A third model also fits 125 %: layer = base size at ANY scale; the 175 %
run separates it (slider 1: exact 56, bucketed 48, base-only 32).

**CONCLUSION (2026-10-07): Windows chooses the layer by a BUCKETED rule, not base × exact scale.**
- Chosen layer = `CursorBaseSize × bucket(scale)`, with bucket = 1.0 for 100-149 % and 1.5 for 150-199 %
  (verified at 100, 125 and 175 %: 25/25 readings match the bucketed model, 0 match the exact model at 125/175 %,
  although every exact-model layer was in the file). The base-only model is refuted by 175 % (48, not 32).
- All readings were crisp (no `?`). At 125 % the maintainer saw "not blurry, but the right lower side is edgy".
- **Not verified:** buckets at ≥ 200 % (Layan assumes 2.0 / 2.5 / 3.0; the test display offers at most 175 %); exact bucket
  boundaries between the tested scales (e.g. 140 %, 150 %); what happens above 256 px (175 % slider 15 showed 256,
  the largest layer); other Windows builds; multi-monitor setups with different scales.
- **Open, not needed:** whether the chosen layer is drawn at its own size or stretched to base × scale at 125/175 %
  ("edgy" would fit a nearest-neighbour stretch) is not measured and won't be: no layer list can change it, because
  Windows never picks a base×1.25 layer, and no README claims crispness at those scales.
- Consequence: Capitaine's 40/80 layers for 125/250 % are never chosen by this rule (40: never; 80: only as a base
  size or 1.5 bucket). Layan Gold's bucket assumption is confirmed for 100-199 %.

### .ani size-limit experiment (2026-10-07, [build 26200.9457], unattended)
Judge: `Test-LoadCursors.ps1` (LoadCursorFromFile + LoadImage 32/48/64/128), as in CI. Content: Polar's real busy
frames, PNG layers, packed exactly as the toolkit ships them (more frames = the 18 real frames repeated).

| Ladder | Loads | Fails |
|---|---|---|
| layers, 18 frames | 8 → 13 layers (B … +224 +256), up to 1,261,600 B | 14 – 20 layers (from 1,344,550 B) |
| frames, 20 layers | – | 36 … 1,152 frames (4.7 – 150 MB) |
| frames, 8 layers (option B) | 36 … **1,152 frames, 29,182,916 B** | – |
| layer count, tiny PNG layers | 12 … 24 layers | – |
| one big layer per frame | PNG 262,825 B/frame; BMP 270,398 B/frame | – |

**Largest file that loads: 29,182,916 B. Smallest that fails: 1,344,550 B.** So total file size is NOT the limit.
Searching all 60 files for one measure that separates loads from failures: frame bytes, layer count and decoded size
do not; **the start offset of an image inside its frame does** (largest loading 65,221, smallest failing 65,894).
Pinned with crafted 2-layer frames: second image at **65,534 and 65,535 loads, 65,536 and 65,537 fail**.

**Rule (measured): in every .ani frame, every image must start at byte ≤ 65,535 of that frame.** *Inference:* the
loader stores that offset in 16 bits. Consequences:
- Single-layer frames can be any size (the only image starts at byte 22).
- Order matters: the toolkit writes the smallest layer first, so only the biggest layer may extend past 64 KiB.
  (Microsoft's own files are largest-first; with that order the limit would bite much earlier.)
- The old "16 layers up to 256 px ≈ 2.7 MB → corrupt" observation fits this rule (*inference*, not re-tested).
- Polar today (option B): largest offset 21,772 = 33 % of the limit. Option C (+144): 27,754 = 42 %.
  B + 144 + 160 + 192: 65 %. 13 layers incl. 224/256: 98 % (loads, no margin).

**Enforcement (toolkit `6efa805`):** `validate` errors when any frame has an image starting past 65,535 and warns above
90 % (the margin is for headroom when art changes; the check itself reads the real bytes of every built file).
Cross-checked against Windows: offsets 61,000 and 65,535 load, 66,000 fails. `ani_budget_bytes` (1 MB) stays as a
**download-size cap**; the evidence gives no loader reason for a byte budget.

### Static .cur: no 64 KiB limit (2026-10-08, [build 26200.9457], display 100 %)
`w11cursor inspect` now prints each image's start offset. `aero_arrow.cur` (largest-first, BMP): 128 @86, 96 @67,710,
64 @105,766, 48 @122,702, **32 @132,342**; 51 of 183 stock `.cur` files have an image starting past 65,535.
Controlled test: synthetic `.cur` files with one solid colour per layer; `LoadImage(IMAGE_CURSOR, n)` → GetIconInfo →
GetDIBits → centre pixel tells which layer Windows used. With pointer size set to 32 px (restored afterwards):

| File | Layout | 32 | 48 | 64 | 96 | 128 |
|---|---|---|---|---|---|---|
| C4 = aero_arrow layout | BMP 128/96/64/48/32, largest first, offsets as Microsoft's | 32 ✓ | 48 ✓ | 64 ✓ | 96 ✓ | 128 ✓ |
| C3 | BMP 256, 128, then 48 @338,070 and 32 @347,710 | 32 ✓ | 48 ✓ | 48 | big | big |
| C2 | all PNG, 48/32 last but < 64 KiB | 32 ✓ | 48 ✓ | 48 | big | big |
| late_layers | BMP 256/128 + **PNG** 48 @338,070 / 32 | big | big | big | big | big |
| C1 | **PNG** 48/32 FIRST (@70/@192) + BMP 256/128 | big | big | big | big | big |

**Conclusion: static .cur files have no image-offset limit** - Windows uses layers starting 67-347 KB into the file.
The 65,535 rule is `.ani`-only; the validator check stays `.ani`-only.
Two side findings:
- **LoadImage scales cursor requests by the pointer size:** with pointer size 48 (the test machine's setting) every request picked
  the layer nearest 1.5 × the requested size (C4: 32→48, 48→64, 64→96, 96→128) - the same base-size rule as the probe.
  `Test-LoadCursors.ps1` only checks loading, so this doesn't change its pass/fail, but its "size" arguments are not
  exact layer sizes unless the pointer size is 32.
- **Files mixing BMP and PNG layers never used their PNG layers** (late_layers, C1), even at offset 70; all-PNG and
  all-BMP files did. 2 of 2 files. **Mixing is now impossible** (ADR-4 update): `layer_format = "png" | "bmp"`
  replaced `png_min_size`, whose 256 setting would have created exactly such files; `validate` rejects mixed files.

### Directory/image size mismatch and anih/rate disagreement (2026-10-08, [build 26200.9457])
Why: a `.cur`/`.ani` directory entry can state a size its image doesn't have (e.g. "80" for a 96 px image), and
anih's default rate can disagree with the rate chunk. Measured what Windows does with both (synthetic files only).
Method: synthetic files, one PNG per entry; the 96 px image is a horizontal red gradient (R = x·255/95, B = 128), so the
returned bitmap's right-edge red tells shrink (≈255) from crop (≈212). `LoadImage(IMAGE_CURSOR, n)`, `.ani` frame 0 via
`GetCursorFrameInfo`, then GetIconInfo/GetDIBits. Pointer size set to 32 (restored afterwards, verified).

| File | Request | Windows built | Right-edge red | Meaning |
|---|---|---|---|---|
| .cur: 32, "80"→96 px gradient, 128 | 80 | 80×80 | 254 | 96 px image **shrunk** to 80 (resampled) |
| .cur: 32, 96 px gradient, 128 (no 80 entry) | 80 | 80×80 | 254 | the same - identical to the mislabelled file |
| .cur: 32, real 80 px (solid), 96, 128 | 80 | 80×80 | flat | the real 80 px layer, unscaled |
| .ani with the mislabelled / the no-80 frame | 80 | 80×80 | 254 | same as .cur |

**Conclusion:** a mislabelled entry behaves like a missing layer - Windows decodes the real image and resamples it to the
requested size (no crop, no failure). Only a real image of the requested size is used unscaled.

| .ani | anih rate | rate chunk | Parsed per-step jiffies (GetCursorFrameInfo) |
|---|---|---|---|
| A | 1 | 2,2,2,2,2,2 | **2**,2,2,2,2,2 |
| B | 2 | 1,1,1,1,1,1 | **1**,1,1,1,1,1 |
| control | 1 | none | 1,1,1,1,1,1 |

**Conclusion:** when a rate chunk exists, it wins; anih's default is used only without one. An anih/rate disagreement
therefore doesn't change parsed timing (on-screen timing not measured). Our packer writes anih = first delay anyway.

### Automatic measurement attempt (Measure-CursorSize.ps1, 2026-10-07, [build 26200.9457], 100 %) - REMOVED
The script was removed from `scripts/` (toolkit commit `233ebcc`); it is in git history at toolkit commit `6952e72`.
Per-monitor DPI aware (V2, confirmed), probe cursor as Arrow, sliders 1/2/3/4/5/7/9/15 (32…256 px):
`LoadCursor(IDC_ARROW) → GetIconInfo → GetObject(hbmColor)` = **32×32 for every slider**; `GetCursorInfo` (cursor on
screen) = 32×32 too; `SM_CXCURSOR` = 32. At slider 9 (160 px) the on-screen cursor happened to be Polar's I-beam:
32×32 with hotspot (5,9), i.e. its 32 px design values, not 160 px ones.
**Conclusion:** these APIs report the cursor's 32 px *logical* bitmap, not the size Windows draws. They cannot settle
exact-vs-bucketed. `probe-auto.csv` from this method is therefore NOT size evidence. Visual probe (Run-SizeProbe.ps1)
is the size evidence.
**Possible automated oracle (later, time-boxed spike AFTER the visual results; a cross-check, not a blocker):**
DXGI Desktop Duplication `GetFramePointerShape` returns the pointer shape as sent to the display. Compare the returned
shape pixels with the probe layers to detect exact vs. resampled (an exact layer matches one probe layer pixel-for-pixel;
a resampled one matches none). Untested.

## Current defaults (`w11cursor/sizes.py`) — change only with probe evidence
| | Sizes | Why |
|---|---|---|
| Static | 32 48 64 72 80 96 112 120 128 144 160 168 176 192 200 208 216 224 240 256 | computed in `sizes.py`: every size the bucketed rule can choose (bases 32…256 × 1.0, 1.5 verified; × 2.0, 2.5, 3.0 assumed), cap 256 (toolkit `89ed137`) |
| Animated | 32 48 64 72 80 96 120 128 144 | option C (2026-10-08): sliders 1-5 + 7 at 100-149 %, 1-5 at 150-199 %; Polar busy.ani ~569 KB, largest image offset ~42 % of the limit |
| Layer encoding | `layer_format = "png"` (every layer) | ~10–15× smaller than BMP; proven by Capitaine. One format per file - mixing is impossible and rejected by `validate` (ADR-4) |
| .ani image offset | ≤ 65,535 per frame (error), warn > 90 % | measured loader limit (toolkit `6efa805`) |
| .ani budget | 1,000,000 B | download-size cap only; not a Windows limit (29 MB loads) |
| .ani `rate` chunk | only when delays differ (`ani_rate = "auto"`), placed after `LIST` | ADR-11; matches Microsoft for uniform delays |
