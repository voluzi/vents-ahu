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
    """
    Parse payload after the response byte (0x06), supporting:
      - FE/TLV blocks: FE <len> <param_id(1 or 2 LE)> <value:len>
      - Compact pairs: [low][value]  (1+1)
    Returns {low_byte: raw_value_bytes}. If the same key appears twice,
    FE/TLV wins (it’s length-accurate).
    """
    # skip fixed header → fd fd | proto | size | id(16) | pwd_len | pwd | resp(0x06)
    pos = 2 + 1 + 1 + 16
    pwd_len = inner[pos]
    pos += 1 + pwd_len + 1
    end = len(inner) - 2

    out: Dict[int, bytes] = {}
    i = pos
    while i < end:
        b = inner[i]
        if b == 0xFE:
            # TLV
            if i + 1 >= end: break
            vlen = inner[i + 1]
            # Determine if param id is 1 byte (e.g. 0x9c) or 2-byte LE (e.g. 0x25 0x00)
            if i + 3 < end and inner[i + 3] == 0x00:
                p_low = inner[i + 2]  # low byte from LE
                id_size = 2
            else:
                p_low = inner[i + 2]
                id_size = 1
            val_start = i + 2 + id_size
            val_end = val_start + vlen
            if val_end > end: break
            out[p_low] = inner[val_start:val_end]  # FE wins
            i = val_end
        else:
            # compact pair [low][value]
            if i + 1 >= end: break
            k = inner[i];
            v = inner[i + 1]
            out.setdefault(k, bytes([v]))  # don’t override FE value
            i += 2
    return out
