"""w11cursor CLI.

  w11cursor build    theme.toml [--out dist] [--variant ID ...]
  w11cursor validate theme.toml [--dist dist] [--variant ID ...]
  w11cursor inspect  FILE.cur|FILE.ani ...        (works on any cursor, incl. other ports / C:\\Windows\\Cursors)
  w11cursor probe    [--out probe]                 (size-probe cursor, see docs/SIZE_POLICY.md)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="w11cursor")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="render + pack a theme")
    b.add_argument("theme", type=Path)
    b.add_argument("--out", type=Path, default=Path("dist"))
    b.add_argument("--variant", action="append")

    v = sub.add_parser("validate", help="re-parse built files and check against theme.toml")
    v.add_argument("theme", type=Path)
    v.add_argument("--dist", type=Path, default=Path("dist"))
    v.add_argument("--variant", action="append")

    i = sub.add_parser("inspect", help="dump layers/hotspots/chunk order of .cur/.ani files")
    i.add_argument("files", type=Path, nargs="+")

    p = sub.add_parser("probe", help="write the size-probe cursor")
    p.add_argument("--out", type=Path, default=Path("probe"))

    a = ap.parse_args(argv)

    if a.cmd == "inspect":
        from .validate import describe

        rc = 0
        for f in a.files:
            try:
                print(describe(f))
            except (ValueError, OSError) as e:
                print(f"{f}: ERROR {e}")
                rc = 1
        return rc

    if a.cmd == "probe":
        from .probe import make_probe

        print(f"wrote {make_probe(a.out)}")
        return 0

    from .config import ConfigError, load_theme

    try:
        theme = load_theme(a.theme)
    except (ConfigError, OSError) as e:
        print(f"theme.toml error: {e}", file=sys.stderr)
        return 2

    if a.cmd == "build":
        from .build import build_theme

        try:
            build_theme(theme, a.out, a.variant)
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 3
        return 0

    from .validate import validate_theme

    rep = validate_theme(theme, a.dist, a.variant)
    for w in rep.warnings:
        print(f"WARN  {w}")
    for e in rep.errors:
        print(f"FAIL  {e}")
    print("OK - all checks passed" if rep.ok else f"{len(rep.errors)} error(s)")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
