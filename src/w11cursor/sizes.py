"""Size policy defaults.

These are STARTING VALUES. Replace them with the results of the on-device size
probe (see docs/SIZE_POLICY.md) - that table is the source of truth, not forum posts.

Why these numbers:
* Windows asks for  CursorBaseSize (32..256, slider 1..15 in 16px steps) x display scale.
  If the file has that exact layer -> crisp. Otherwise Windows resamples -> blur.
* Static cursors are cheap (Windows decodes only the layer it picks), so we cover
  every slider step at 100% plus common 125/150/175/200/250/300% products.
* Animated cursors are capped: the legacy .ani loader rejects files with too much
  frame data (observed: 16 layers up to 256px ~2.7 MB -> "corrupt"; 7 layers to 128 OK).
"""
STATIC_SIZES: tuple[int, ...] = (32, 40, 48, 56, 64, 72, 80, 96, 112, 128, 144, 160, 192, 224, 256)
ANIMATED_SIZES: tuple[int, ...] = (32, 40, 48, 64, 80, 96, 128)

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
