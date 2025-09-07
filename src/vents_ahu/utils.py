from typing import Dict

from .constant import *


class VentsError(Exception): pass


def u16_le(v: int) -> bytes:
    return (v & 0xFFFF).to_bytes(2, "little")


def sum16(data: bytes) -> int:
    return sum(data) & 0xFFFF


def extract_inner(resp: bytes) -> bytes:
    i = resp.find(PACKET_PREFIX)
    if i < 0: raise RuntimeError("No PACKET_PREFIX in response")
    return resp[i:]


def validate(inner: bytes):
    expect = int.from_bytes(inner[-2:], "little")
    calc = sum16(inner[2:-2])
    if calc != expect:
        raise RuntimeError(f"Checksum mismatch: calc=0x{calc:04x} expect=0x{expect:04x}")


def decode_reply(inner: bytes) -> Dict[int, bytes]:
    # skip fixed header → fd fd | proto | size | id(16) | pwd_len | pwd | resp(0x06)
    pos = 2 + 1 + 1 + 16
    pwd_len = inner[pos]
    pos += 1 + pwd_len + 1
    end = len(inner) - 2  # strip checksum

    out: Dict[int, bytes] = {}
    i = pos
    while i < end:
        b = inner[i]
        if b == 0xFE:
            if i + 1 >= end:
                break
            vlen = inner[i + 1]

            # Prefer 2-byte LE param if it fits and the “page” byte looks sane (0x00..0x03)
            use_two = (i + 2 + 2 + vlen) <= end and (inner[i + 3] in (0x00, 0x01, 0x02, 0x03))
            if use_two:
                p_low = inner[i + 2]        # LE low byte
                val_start = i + 4
            else:
                p_low = inner[i + 2]        # 1-byte id
                val_start = i + 3

            val_end = val_start + vlen
            if val_end > end:
                break
            out[p_low] = inner[val_start:val_end]  # FE wins
            i = val_end
        else:
            # compact [low][value]
            if i + 1 >= end:
                break
            k = inner[i]
            v = inner[i + 1]
            out.setdefault(k, bytes([v]))
            i += 2
    return out
