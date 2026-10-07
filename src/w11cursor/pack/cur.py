"""Windows .cur writer/reader (no external tools).

File layout (all little-endian):
    ICONDIR        reserved=0 (u16), type=2 for cursor (u16), count (u16)
    ICONDIRENTRY*  width(u8, 0=256), height(u8), colors(u8)=0, reserved(u8)=0,
                   hotspot_x(u16), hotspot_y(u16), bytes(u32), offset(u32)
    image data*    either a PNG stream, or a DIB:
                   BITMAPINFOHEADER (height is DOUBLED: XOR + AND mask),
                   32-bit BGRA pixels bottom-up, then a 1-bit AND mask
                   (rows padded to 4 bytes, bit=1 means transparent).

Think of a .cur as a folder of pictures of the same cursor at different sizes,
each with its own "click point". Windows opens the folder and picks the one
whose size matches what it needs right now.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass

from PIL import Image

from ..sizes import LAYER_FORMAT, LAYER_FORMATS

PNG_SIG = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class CursorImage:
    image: Image.Image          # square RGBA
    hotspot: tuple[int, int]


@dataclass(frozen=True)
class CurEntry:
    size: int
    hotspot: tuple[int, int]
    fmt: str                    # "png" | "bmp"
    nbytes: int
    offset: int = 0             # where the image data starts in the .cur (an .ani frame must keep every one <= 65,535)


def _bmp_payload(img: Image.Image) -> bytes:
    img = img.convert("RGBA")
    w, h = img.size
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    flipped = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    xor = flipped.tobytes("raw", "BGRA")
    alpha = flipped.getchannel("A").tobytes()
    row_bytes = ((w + 31) // 32) * 4
    mask = bytearray(row_bytes * h)
    for y in range(h):
        base = y * w
        rbase = y * row_bytes
        for x in range(w):
            if alpha[base + x] == 0:
                mask[rbase + (x >> 3)] |= 0x80 >> (x & 7)
    return header + xor + bytes(mask)


def _png_payload(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def pack_cur(images: list[CursorImage], layer_format: str = LAYER_FORMAT) -> bytes:
    """Every layer in ONE format ("png" or "bmp") - mixed files lose their PNG layers on Windows (ADR-4)."""
    if layer_format not in LAYER_FORMATS:
        raise ValueError(f"layer_format must be one of {LAYER_FORMATS}, got {layer_format!r}")
    encode = _png_payload if layer_format == "png" else _bmp_payload
    if not images:
        raise ValueError("a cursor needs at least one image")
    images = sorted(images, key=lambda c: c.image.width)
    sizes = [c.image.width for c in images]
    if len(set(sizes)) != len(sizes):
        raise ValueError(f"duplicate layer sizes: {sizes}")

    count = len(images)
    out_header = struct.pack("<HHH", 0, 2, count)
    offset = 6 + 16 * count
    entries, data = bytearray(), bytearray()
    for ci in images:
        w, h = ci.image.size
        if w != h:
            raise ValueError(f"cursor images must be square, got {w}x{h}")
        if not 1 <= w <= 256:
            raise ValueError(f"layer size {w} outside 1..256")
        hx, hy = ci.hotspot
        if not (0 <= hx < w and 0 <= hy < h):
            raise ValueError(f"hotspot {ci.hotspot} outside {w}x{h}")
        payload = encode(ci.image)
        entries += struct.pack(
            "<BBBBHHII", w % 256, h % 256, 0, 0, hx, hy, len(payload), offset + len(data)
        )
        data += payload
    return out_header + bytes(entries) + bytes(data)


def parse_cur(blob: bytes) -> list[CurEntry]:
    """Parse a .cur and return its layers. Raises ValueError on malformed data."""
    if len(blob) < 6:
        raise ValueError("file too short")
    reserved, typ, count = struct.unpack_from("<HHH", blob, 0)
    if reserved != 0 or typ != 2:
        raise ValueError(f"not a .cur (reserved={reserved}, type={typ})")
    out: list[CurEntry] = []
    for i in range(count):
        off = 6 + 16 * i
        if off + 16 > len(blob):
            raise ValueError("truncated directory")
        w, h, _c, _r, hx, hy, nbytes, doff = struct.unpack_from("<BBBBHHII", blob, off)
        w = w or 256
        h = h or 256
        if doff + nbytes > len(blob):
            raise ValueError(f"entry {i} points outside file")
        payload = blob[doff : doff + nbytes]
        if payload[:8] == PNG_SIG:
            fmt = "png"
            pw, ph = struct.unpack_from(">II", payload, 16)
        else:
            fmt = "bmp"
            _sz, pw, ph2 = struct.unpack_from("<Iii", payload, 0)
            ph = ph2 // 2
        if (pw, ph) != (w, h):
            raise ValueError(f"entry {i}: directory says {w}x{h}, image is {pw}x{ph}")
        out.append(CurEntry(size=w, hotspot=(hx, hy), fmt=fmt, nbytes=nbytes, offset=doff))
    return out
