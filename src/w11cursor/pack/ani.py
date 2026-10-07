"""Windows .ani (RIFF/ACON) writer/reader.

    RIFF <size> "ACON"
      [LIST "INFO" (INAM title, IART artist)]   optional metadata
      anih  ANIHEADER: cbSize=36, nFrames, nSteps, cx, cy, bitCount, planes,
            jifRate (default delay, 1 jiffy = 1/60 s), flags (1 = AF_ICON: frames are .cur/.ico)
      rate  one u32 delay per step; with rate_mode "auto" written only when delays differ
      LIST "fram"  one "icon" chunk per frame, each holding a COMPLETE .cur file
    Every chunk is padded to an even length (RIFF rule - win2xcur 0.2.1 had to fix this).

The top-level order of anih/rate/LIST is configurable because it is still an
open question which order the Windows 11 loader insists on (see docs/SIZE_POLICY.md).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..sizes import ANI_CHUNK_ORDER, ANI_RATE_MODE, ANI_RATE_MODES

AF_ICON = 0x1
AF_SEQUENCE = 0x2


def _chunk(cid: bytes, data: bytes) -> bytes:
    out = cid + struct.pack("<I", len(data)) + data
    if len(data) % 2:
        out += b"\x00"
    return out


def _zstr(s: str) -> bytes:
    return s.encode("ascii", "replace") + b"\x00"


def pack_ani(
    frames: list[bytes],
    delay_jiffies: int | list[int],
    order: tuple[str, ...] = ANI_CHUNK_ORDER,
    title: str | None = None,
    artist: str | None = None,
    rate_mode: str = ANI_RATE_MODE,
) -> bytes:
    if not frames:
        raise ValueError("an animated cursor needs frames")
    n = len(frames)
    delays = [delay_jiffies] * n if isinstance(delay_jiffies, int) else list(delay_jiffies)
    if len(delays) != n:
        raise ValueError("one delay per frame required")
    if not set(order) <= {"anih", "rate", "LIST"} or "anih" not in order or "LIST" not in order:
        raise ValueError(f"bad chunk order {order}")
    if rate_mode not in ANI_RATE_MODES:
        raise ValueError(f"bad rate_mode {rate_mode!r}; valid: {', '.join(ANI_RATE_MODES)}")
    uniform = len(set(delays)) == 1
    if not uniform and "rate" not in order:
        # Without a rate chunk Windows plays every step at anih's delay - fail instead of losing timing.
        raise ValueError(f"per-frame delays {delays} need a 'rate' chunk, but chunk order is {order}")

    anih = struct.pack("<9I", 36, n, n, 0, 0, 0, 0, delays[0], AF_ICON)
    parts = {
        "anih": _chunk(b"anih", anih),
        "rate": _chunk(b"rate", struct.pack(f"<{n}I", *delays)),
        "LIST": _chunk(b"LIST", b"fram" + b"".join(_chunk(b"icon", f) for f in frames)),
    }
    body = bytearray(b"ACON")
    if title or artist:
        info = b"INFO"
        if title:
            info += _chunk(b"INAM", _zstr(title))
        if artist:
            info += _chunk(b"IART", _zstr(artist))
        body += _chunk(b"LIST", info)
    for name in order:
        if name == "rate" and uniform and rate_mode == "auto":
            continue  # Microsoft layout: a uniform delay lives in anih only
        body += parts[name]
    return b"RIFF" + struct.pack("<I", len(body)) + bytes(body)


@dataclass
class AniInfo:
    chunk_order: list[str]                 # e.g. ["LIST:INFO", "anih", "LIST:fram", "rate"]
    n_frames: int
    n_steps: int
    default_rate: int
    flags: int
    rates: list[int] | None
    seq: list[int] | None
    frames: list[bytes] = field(repr=False, default_factory=list)


def parse_ani(blob: bytes) -> AniInfo:
    if blob[:4] != b"RIFF" or blob[8:12] != b"ACON":
        raise ValueError("not a RIFF/ACON file")
    riff_size = struct.unpack_from("<I", blob, 4)[0]
    if riff_size + 8 > len(blob):
        raise ValueError(f"RIFF size {riff_size} exceeds file length {len(blob)}")
    end = 8 + riff_size
    pos = 12
    order: list[str] = []
    anih = None
    rates = seq = None
    frames: list[bytes] = []
    while pos + 8 <= end:
        cid = blob[pos : pos + 4].decode("ascii", "replace")
        size = struct.unpack_from("<I", blob, pos + 4)[0]
        data = blob[pos + 8 : pos + 8 + size]
        if len(data) != size:
            raise ValueError(f"chunk {cid!r} truncated")
        if cid == "LIST":
            ltype = data[:4].decode("ascii", "replace")
            order.append(f"LIST:{ltype}")
            if ltype == "fram":
                p = 4
                while p + 8 <= len(data):
                    sid = data[p : p + 4]
                    ssz = struct.unpack_from("<I", data, p + 4)[0]
                    if sid == b"icon":
                        frames.append(data[p + 8 : p + 8 + ssz])
                    p += 8 + ssz + (ssz & 1)
        else:
            order.append(cid.strip())
            if cid == "anih":
                anih = struct.unpack_from("<9I", data, 0)
            elif cid == "rate":
                rates = list(struct.unpack_from(f"<{size // 4}I", data, 0))
            elif cid == "seq ":
                seq = list(struct.unpack_from(f"<{size // 4}I", data, 0))
        pos += 8 + size + (size & 1)
    if anih is None:
        raise ValueError("missing anih chunk")
    if anih[1] != len(frames):
        raise ValueError(f"anih says {anih[1]} frames, LIST:fram has {len(frames)}")
    return AniInfo(order, anih[1], anih[2], anih[7], anih[8], rates, seq, frames)
