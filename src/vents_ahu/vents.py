import socket, binascii
from typing import Optional
from .constant import *
from .utils import *


class Vents:
    def __init__(self, device_id: str, address: str, port: int = 4000,
                 passwd: str = "1111", timeout: float = 3.5, debug: bool = False):
        self.address = address
        self.port = port
        self.device_id = device_id.encode()[:16].ljust(16, b"0")
        self.passwd = passwd.encode()
        self.timeout = timeout
        self.debug = debug
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(self.timeout)

    def _hexdump(self, label: str, data: bytes):
        if self.debug:
            print(f"{label} ({len(data)} bytes): {binascii.hexlify(data).decode()}")

    def _build_frame(self, function: bytes, body: bytes) -> bytes:
        buf = bytearray()
        buf += PACKET_PREFIX
        buf += PROTOCOL_TYPE
        buf += SIZE_ID
        buf += self.device_id
        buf += len(self.passwd).to_bytes(1, "big")
        buf += self.passwd
        buf += function
        buf += body
        buf += u16_le(sum16(buf[2:]))
        return bytes(buf)

    def _request_raw(self, function: bytes, body: bytes) -> Dict[int, bytes]:
        frame = self._build_frame(function, body)
        self._hexdump("TX", frame)
        self.sock.sendto(frame, (self.address, self.port))
        resp = self.sock.recv(4096)
        self._hexdump("RX", resp)
        inner = extract_inner(resp)
        self._hexdump("RX_inner", inner)
        validate(inner)
        return decode_reply(inner)

    def _request(self, function: bytes, registers: list[bytes], value: Optional[int] = None) -> Dict[int, bytes]:
        """
        READ:  body = concat of 2B BE register codes (one or many)
        WRITE: body = [lowbyte(register)][value]  (only for compact-writable regs you’ve verified)
        Returns decoded map {low_byte: raw_value_bytes}
        """
        if value is None:
            body = b"".join(registers)
        else:
            # For now we only support compact write (lowbyte + 1 byte value) as confirmed for SPEED.
            low = registers[0][1]
            if not (0 <= value <= 255):
                raise VentsError("Only 1-byte compact writes supported right now")
            body = bytes([low, value])

        return self._request_raw(function, body)

    def _key_for(self, reg: Register) -> str:
        return reg.get("name") or reg["parameter"].hex()

    def _byteorder(self, reg: Register) -> Literal["big", "little"]:
        # default is "big" if not provided
        return reg.get("endian", "big")

    def _format_value(self, reg: Register, raw: bytes):
        f = reg["fmt"]
        if f is int:
            val = int.from_bytes(raw, self._byteorder(reg), signed=False)
            if "scale" in reg:
                return int(val * float(reg["scale"]))
            return val
        if f is float:
            val = float(int.from_bytes(raw, self._byteorder(reg), signed=False))
            if "scale" in reg:
                val = val * float(reg["scale"])
            return round(val, 1)
        if f is str:
            try:
                return raw.decode("ascii")
            except UnicodeDecodeError:
                return raw.hex()
        if f is bool:
            return bool(int.from_bytes(raw, self._byteorder(reg), signed=False))
        if f == "ip":
            return ".".join(str(x) for x in raw) if len(raw) == 4 else ""
        # default
        return raw

    def _coerce_to_bytes(self, reg: Register, value) -> bytes:
        """
        Convert a Python value into the exact byte representation required by reg['count'] and reg['fmt'].
        Supports:
          - int           -> big-endian signed=False
          - float         -> uses optional reg['scale'] (float); stored as integer
          - 'bool'        -> 1 byte 0/1
          - str           -> ASCII bytes
          - 'raw' / bytes -> use as-is, but must match count
        """
        cnt = int(reg["count"])
        fmt = reg["fmt"]

        if fmt is int:
            if not isinstance(value, int):
                raise VentsError("value must be int for fmt=int")
            return int(value).to_bytes(cnt, self._byteorder(reg), signed=False)

        if fmt is float:
            # optional scale: device stores integer = round(value / scale)
            scale = float(reg.get("scale", 1.0))  # default no scaling
            raw_int = int(round(float(value) / scale))
            return raw_int.to_bytes(cnt, self._byteorder(reg), signed=False)

        if fmt == bool:
            if cnt != 1:
                raise VentsError("bool registers must have count=1")
            b = 1 if bool(value) else 0
            return bytes([b])

        if fmt is str:
            b = str(value).encode("ascii", "strict")
            if len(b) != cnt:
                raise VentsError(f"string length mismatch: need {cnt}, got {len(b)}")
            return b

        if fmt == "raw":
            if not isinstance(value, (bytes, bytearray)):
                raise VentsError("fmt='raw' expects bytes-like value")
            b = bytes(value)
            if len(b) != cnt:
                raise VentsError(f"raw length mismatch: need {cnt}, got {len(b)}")
            return b

        raise VentsError(f"unsupported register fmt: {fmt!r}")

    def read_register(self, reg: Register) -> Union[int, str, float, bytes]:
        kv = self._request(PARAMETER_READ, [reg["parameter"]])
        raw = kv.get(reg["parameter"][1])
        if raw is None:
            raise VentsError("register not found in reply")
        return self._format_value(reg, raw)

    def read_registers(self, regs: list[Register]) -> dict[str, object]:
        codes = [r["parameter"] for r in regs]
        kv = self._request(PARAMETER_READ, codes)  # {low_byte: raw}
        out = {}
        for r in regs:
            raw = kv.get(r["parameter"][1])
            if raw is not None:
                out[self._key_for(r)] = self._format_value(r, raw)
        return out

    def write_register(self, reg: Register, value) -> Union[int, str, float, bytes]:
        # 1) read-only guard
        if reg.get("read_only"):
            raise VentsError(f"register '{reg.get('name', reg['parameter'].hex())}' is read-only")

        # 2) normalize to exact bytes per register definition
        raw = self._coerce_to_bytes(reg, value)

        # 3) optional bounds (only meaningful for numeric types)
        if reg["fmt"] in (int, float):
            if "min" in reg:
                # interpret bounds in user units for numeric; for bool it’s fine (0..1)
                if value < reg["min"]:
                    raise VentsError(f"value {value} < min {reg['min']}")
            if "max" in reg:
                if value > reg["max"]:
                    raise VentsError(f"value {value} > max {reg['max']}")

        # 4) send — compact writer supports ONLY 1-byte bodies today
        if len(raw) != 1:
            # Placeholder for FE/TLV writer when you implement it:
            # self._write_tlv(reg['parameter'], raw)
            raise VentsError("only 1-byte compact writes supported for now (FE/TLV write not implemented)")

        # compact body = [lowbyte(param)][value_byte]
        low = reg["parameter"][1]
        kv = self._request(PARAMETER_WRITE_WITH_RESPONSE, [reg["parameter"]], value=raw[0])
        echo = kv.get(low)

        # 5) format echo (or fall back to read-back)
        if echo is None:
            # some firmwares may ACK without echo; read-back for confirmation
            return self.read_register(reg)
        return self._format_value(reg, echo)
