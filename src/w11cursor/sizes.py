"""Size policy defaults - derived from the MEASURED rule, see docs/SIZE_POLICY.md "Visual probe results".

How Windows picks a cursor layer (visual probe [build 26200.9457], 2026-10-07):
    layer = CursorBaseSize x bucket(display scale)
    CursorBaseSize = 16 * (slider + 1) for the pointer-size slider 1..15  (32, 48, ... 256 px)
    bucket = 1.0 for 100-149 %, 1.5 for 150-199 %             <- VERIFIED (100, 125, 175 %: 25/25 readings)
             2.0 / 2.5 / 3.0 for 200 / 250 / 300 %+           <- ASSUMED (Layan Gold's model; not measured)
NOT base x exact scale: at 125 % / 175 % Windows ignored the 40/56/... layers that were in the file.
If the chosen layer is missing, Windows resamples another one -> blur. So we ship exactly the choosable layers.

* Static cursors are cheap (Windows decodes only the layer it picks): ship every choosable size <= 256.
* Animated cursors are capped by the legacy .ani loader's size limit (ANI_BUDGET_BYTES): a subset.
"""
SLIDER_BASES: tuple[int, ...] = tuple(16 * (s + 1) for s in range(1, 16))      # 32 .. 256
VERIFIED_BUCKETS: tuple[float, ...] = (1.0, 1.5)
ASSUMED_BUCKETS: tuple[float, ...] = (2.0, 2.5, 3.0)
MAX_LAYER = 256   # largest layer we ship (the .cur directory format stores 256 as 0)


def choosable_sizes(buckets=VERIFIED_BUCKETS + ASSUMED_BUCKETS, bases=SLIDER_BASES, cap=MAX_LAYER) -> tuple[int, ...]:
    """Every layer size Windows can choose under the bucketed rule, capped at `cap`."""
    return tuple(sorted({min(cap, round(b * f)) for b in bases for f in buckets}))


# 20 sizes: 32 48 64 72 80 96 112 120 128 144 160 168 176 192 200 208 216 224 240 256
# (200 exists only because of the ASSUMED 2.5 bucket: 80 x 2.5)
STATIC_SIZES: tuple[int, ...] = choosable_sizes()
# Option C (maintainer, 2026-10-08): exact for sliders 1-5 and 7 at 100-149 %, sliders 1-5 at 150-199 %.
# Polar busy.ani ~569 KB; largest image offset ~42 % of the 65,535 loader limit. Every size is choosable (test_sizes).
ANIMATED_SIZES: tuple[int, ...] = (32, 48, 64, 72, 80, 96, 120, 128, 144)

# .ani loader limit (MEASURED 2026-10-07, docs/SIZE_POLICY.md ".ani size-limit experiment"): inside every frame,
# each image must START at byte <= 65,535 of that frame (65,535 loads, 65,536 fails - consistent with a 16-bit
# offset). Total file size is NOT limited by the loader (a 29 MB .ani loaded). Frames are written smallest layer
# first, so only the biggest layer may extend past 64 KiB. validate: error above the limit, warning above 90 %.
ANI_MAX_IMAGE_OFFSET = 65_535
ANI_OFFSET_WARN_FRACTION = 0.90

# Download-size cap per .ani file (bytes). NOT a Windows limit (see above); keeps zips reasonable.
ANI_BUDGET_BYTES = 1_000_000

# Layers at or above this size are stored PNG-compressed inside .cur; smaller ones
# use classic 32-bit BMP + AND mask. Default 1 = PNG for every layer:
#   * BMP is ~10-15x larger (15 BMP layers = ~800 KB per .cur, an 8-frame .ani > 1.3 MB)
#   * capitaine-cursors-w11-hidpi already ships PNG layers at all sizes and they load
#     on Windows 11 (its 7-layer .ani files are ~545 KB, only possible with PNG frames).
# WARNING (measured 2026-10-08, docs/SIZE_POLICY.md "Static .cur"): in .cur files that MIX BMP and PNG layers,
# Windows never used the PNG layers (2 of 2 files). png_min_size = 256 creates exactly such files (BMP below 256,
# PNG at 256), so don't use it as a fallback without a pixel test. All-PNG (1) and all-BMP (> 256) are fine.
PNG_MIN_SIZE = 1

# Top-level RIFF chunk order for .ani. The order below is the one that fixed the
# "corrupt" errors in capitaine-cursors-w11-hidpi. "rate" here only says WHERE the
# rate chunk goes when one is written (see ANI_RATE_MODE).
ANI_CHUNK_ORDER: tuple[str, ...] = ("anih", "LIST", "rate")

# When to write the optional rate chunk:
#   "auto"   - only when per-frame delays differ. A uniform delay lives in anih alone,
#              exactly like Microsoft's aero_busy.ani / aero_working.ani (anih -> LIST:fram).
#   "always" - every .ani gets a rate chunk (behaviour before ADR-11).
# Evidence: docs/SIZE_POLICY.md ".ani layout experiment" - both layouts load through
# user32 and a rate chunk after LIST is honoured per step.
ANI_RATE_MODE = "auto"
ANI_RATE_MODES = ("auto", "always")
