"""Shared pre-render check: SVG input may never reach outside the file, and must not need fonts.

Runs on the (recoloured) SVG text before ANY backend sees it - see render_svg().
* cairosvg has blocked external files by default since 2.7 (unsafe=False), but resvg has no such switch:
  it loads <image> files by absolute path even without resources_dir (verified 2026-10-07). One guard
  for both backends keeps the rule in one place instead of relying on each renderer's defaults.
* Allowed references are only same-document ("#id") and embedded ("data:") ones.
* <text> needs fonts, which differ per machine (and resvg skips them for reproducibility) -> reject;
  convert text to paths in the SVG instead.

The check scans the raw text (not a parsed tree), so namespace prefixes or parser quirks can't hide a
reference. It is deliberately strict: a false alarm is fixed with an override; a leak is not visible.
"""
from __future__ import annotations

import re

# href / xlink:href / any-prefix:href attribute (not e.g. "xmlns:xlink" or "data-href")
_HREF_ATTR = re.compile(r"""(?<![\w.:-])(?:[\w.-]+:)?href\s*=\s*(["'])(.*?)\1""", re.S)
# CSS url(...) anywhere: style="...", <style>, presentation attributes such as fill="url(#g)"
_CSS_URL = re.compile(r"""url\(\s*(["']?)(.*?)\1\s*\)""", re.S | re.I)
_CSS_IMPORT = re.compile(r"@import\b", re.I)
_TEXT = re.compile(r"<(?:[\w.-]+:)?text\b")


def _is_local(ref: str) -> bool:
    ref = ref.strip()
    return ref.startswith("#") or ref.lower().startswith("data:")


def _short(s: str, n: int = 80) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n] + "..."


def check_svg(svg: str, name: str) -> None:
    """Raise ValueError if the SVG references anything outside itself or contains <text>."""
    for m in _HREF_ATTR.finditer(svg):
        if not _is_local(m.group(2)):
            raise ValueError(f"{name}: external reference not allowed: href={_short(m.group(2))!r} "
                             "(only '#id' and 'data:' are allowed)")
    for m in _CSS_URL.finditer(svg):
        if not _is_local(m.group(2)):
            raise ValueError(f"{name}: external CSS url() not allowed: url({_short(m.group(2))}) "
                             "(only '#id' and 'data:' are allowed)")
    if _CSS_IMPORT.search(svg):
        raise ValueError(f"{name}: CSS @import not allowed (it loads external stylesheets)")
    if _TEXT.search(svg):
        raise ValueError(f"{name}: contains <text>; convert text to paths (fonts differ per machine)")
