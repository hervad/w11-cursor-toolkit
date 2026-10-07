"""w11cursor - build Windows 11 HiDPI cursor schemes from vector sources.

Pipeline:  theme.toml -> config -> render (SVG -> RGBA per size)
           -> pack (.cur / .ani) -> install.inf -> validate -> zip
"""
__version__ = "0.1.0"
