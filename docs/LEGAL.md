# Legal & safety notes

*Factual summary to make decisions with — not legal advice. Re-check each upstream LICENSE file before the first
public release.* Per-theme licence status is tracked in each theme repo (LICENSE, COPYRIGHT, CREDITS.md,
PORT_STATUS.md), not here.

### What GPL requires from a theme port
1. **Same license** for the port: ship the upstream `LICENSE`/`COPYING` text in the repo *and* in every release zip
   (the toolkit copies `LICENSE`, `COPYING`, `COPYRIGHT`, `NOTICE`, `AUTHORS`, `CREDITS.md` from the theme root into
   every variant folder and zip; `validate` fails if a folder or zip lacks LICENSE/COPYING or any of those files).
2. **Keep notices**: upstream author + copyright stay visible (README + CREDITS.md).
3. **Source availability**: for cursors, the "source" is the SVGs + build recipe. A public repo with the
   pinned upstream (submodule, or the ORIGINAL tarball committed unmodified with its SHA-256 pinned and
   extracted by `w11cursor unpack`) + `theme.toml` + `overrides/` satisfies this; releases are published from
   the same tagged repo.
4. **State your changes** (CREDITS.md → "Changes from upstream").
5. Don't add restrictions (no "non-commercial" clauses, no extra terms).

### Things you must NOT redistribute
- `C:\Windows\Cursors\aero_*` (Microsoft) — only inspect them locally.
- Files from existing third-party ports (firstfooter = CC BY-NC-SA; rw-designer "public domain" re-uploads;
  chiyuki0325 repo has no license file). Build everything from upstream sources.

### Toolkit
`w11-cursor-toolkit` is the maintainer's own code → MIT. It never contains artwork (except the self-drawn
demo), so the GPL boundary stays clean: artwork repos are GPL, the packer is MIT.

### Naming / courtesy
Call each repo an **unofficial Windows 11 HiDPI port** of "<upstream name>" by <author>; don't
imply endorsement. Optional but good: open an issue upstream linking your port.

## Safety (for maintainers and users)
- **install.inf** copies cursors to `C:\Windows\Cursors\<scheme>` (needs UAC), writes cursor values
  under `HKCU\Control Panel\Cursors`, and one `HKLM ... RunOnce\Setup` entry that opens Mouse Properties
  once. No executables, no services. It's plain text — users can read it before installing.
- **Cursor files are parsed by Windows** (`.ani` parsing had a famous RCE in 2007, MS07-017, long patched).
  We only ship files produced by our own packer from SVG, re-parsed by the validator and loaded through
  `user32` in CI before release. No third-party binaries are repackaged.
- **SVG input**: every SVG passes ONE shared pre-render guard (`render/guard.py`) before either backend sees it.
  It rejects any `href`/`xlink:href` and any CSS `url(...)` (style attributes, `<style>`, presentation attributes)
  that is not a same-document `#id` or an embedded `data:` URI, rejects CSS `@import`, and rejects `<text>`
  (fonts differ per machine; convert text to paths). Why one guard: cairosvg has blocked external files by
  default since 2.7 (`unsafe=False`; verified on 2.9.1: external image not loaded, loaded only with
  `unsafe=True`), but resvg has no such switch — it loads `<image>` files by absolute path even without
  `resources_dir` (verified with resvg-py 0.5.0). Never pass `unsafe=True` to cairosvg.
- **Supply chain**: pin upstream submodules to commits, pin the toolkit by tag in theme workflows,
  publish `SHA256SUMS.txt` with every release (done by the reusable workflow).
