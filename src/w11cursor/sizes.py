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
# Option B (maintainer, 2026-10-07): exact for sliders 1-5 and 7 at 100-149 %, sliders 1-4 at 150-199 %;
# Polar busy.ani = 456 KB. Every size here is choosable (tests/test_sizes.py).
ANIMATED_SIZES: tuple[int, ...] = (32, 48, 64, 72, 80, 96, 120, 128)

# Hard CI budget per .ani file (bytes). Empirical, not a documented Microsoft limit.
ANI_BUDGET_BYTES = 1_000_000

# Layers at or above this size are stored PNG-compressed inside .cur; smaller ones
# use classic 32-bit BMP + AND mask. Default 1 = PNG for every layer:
#   * BMP is ~10-15x larger (15 BMP layers = ~800 KB per .cur, an 8-frame .ani > 1.3 MB)
#   * capitaine-cursors-w11-hidpi already ships PNG layers at all sizes and they load
#     on Windows 11 (its 7-layer .ani files are ~545 KB, only possible with PNG frames).
# Set [sizes] png_min_size = 256 in theme.toml to fall back to BMP below 256 if the
# Windows load test ever rejects a PNG layer.
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
