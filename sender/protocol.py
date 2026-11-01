import json
import struct
import uuid

MAGIC = b"BLER"
HEADER_SIZE = 8
MAX_MESSAGE_SIZE = 1024 * 1024


def shape(text):
    """Arabic text shaping with safe fallback."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def to_bytes(data):
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, (list, tuple)):
        return bytes(data)
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def encode(message_type, data=None):
    message = {
        "id": uuid.uuid4().hex,
        "t": str(message_type),
        "d": data if data is not None else {}
    }

    payload = json.dumps(
        message,
        ensure_ascii=False,
        separators=(",", ":")
    ).encode("utf-8")

    if len(payload) > MAX_MESSAGE_SIZE:
        raise ValueError("Message too large")

    return MAGIC + struct.pack(">I", len(payload)) + payload


def fragment(data, chunk_size):
    data = to_bytes(data)
    chunk_size = int(chunk_size)

    if chunk_size < 1:
        raise ValueError("Invalid chunk size")

    return [
        data[i:i + chunk_size]
        for i in range(0, len(data), chunk_size)
    ]


class Reassembler:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(to_bytes(data))

        while len(self.buffer) >= HEADER_SIZE:
            if self.buffer[:4] != MAGIC:
                del self.buffer[0]
                continue

            length = struct.unpack(">I", self.buffer[4:8])[0]

            if length > MAX_MESSAGE_SIZE:
                del self.buffer[0]
                continue

            total = HEADER_SIZE + length

            if len(self.buffer) < total:
                return None

            payload = bytes(self.buffer[HEADER_SIZE:total])
            del self.buffer[:total]

            try:
                return json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

        return None
