"""The 17 Windows 10 1903+/Windows 11 pointer roles.

ORDER MATTERS: the comma-separated value stored under
HKCU\\Control Panel\\Cursors\\Schemes must list the files in exactly this order.
(A wrong order assigns files to the wrong roles - a known failure mode of generated INFs.)

`xcursor_hints` are common Linux Xcursor names for the role. They are HINTS for
filling in theme.toml, not an automatic mapping - always check the artwork.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    key: str            # key used in theme.toml  [cursors.<key>]
    reg_value: str      # value name under HKCU\Control Panel\Cursors
    filename: str       # output file stem (pointer.cur, busy.ani, ...)
    label: str          # what Windows calls it in Mouse Properties
    xcursor_hints: tuple[str, ...]


ROLES: tuple[Role, ...] = (
    Role("arrow", "Arrow", "pointer", "Normal Select", ("left_ptr", "default", "arrow")),
    Role("help", "Help", "help", "Help Select", ("help", "question_arrow", "left_ptr_help", "whats_this")),
    Role("working", "AppStarting", "working", "Working in Background", ("left_ptr_watch", "progress", "half-busy")),
    Role("busy", "Wait", "busy", "Busy", ("wait", "watch")),
    Role("precision", "Crosshair", "precision", "Precision Select", ("crosshair", "cross", "tcross")),
    Role("text", "IBeam", "text", "Text Select", ("xterm", "text", "ibeam")),
    Role("handwriting", "NWPen", "handwriting", "Handwriting", ("pencil", "draft")),
    Role("unavailable", "No", "unavailable", "Unavailable", ("not-allowed", "circle", "forbidden", "crossed_circle")),
    Role("vert", "SizeNS", "vert", "Vertical Resize", ("size_ver", "ns-resize", "sb_v_double_arrow", "v_double_arrow")),
    Role("horz", "SizeWE", "horz", "Horizontal Resize", ("size_hor", "ew-resize", "sb_h_double_arrow", "h_double_arrow")),
    # NW-SE diagonal (top-left <-> bottom-right). Verify visually - diagonals are the classic mix-up.
    Role("dgn1", "SizeNWSE", "dgn1", "Diagonal Resize 1", ("size_fdiag", "nwse-resize", "bd_double_arrow")),
    # NE-SW diagonal (top-right <-> bottom-left)
    Role("dgn2", "SizeNESW", "dgn2", "Diagonal Resize 2", ("size_bdiag", "nesw-resize", "fd_double_arrow")),
    Role("move", "SizeAll", "move", "Move", ("fleur", "size_all", "move", "all-scroll")),
    Role("alternate", "UpArrow", "alternate", "Alternate Select", ("up-arrow", "center_ptr", "up_arrow")),
    Role("link", "Hand", "link", "Link Select", ("pointer", "hand2", "hand1", "pointing_hand")),
    Role("pin", "Pin", "pin", "Location Select", ()),      # Windows 10 1903+
    Role("person", "Person", "person", "Person Select", ()),  # Windows 10 1903+
)

ROLE_BY_KEY: dict[str, Role] = {r.key: r for r in ROLES}
