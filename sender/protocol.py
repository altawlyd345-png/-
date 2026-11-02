import json
import struct
import zlib
import uuid
import time

MAGIC = b"BL"
HEADER = struct.Struct("!2sIHHI")

DEFAULT_CHUNK = 6
MAX_PARTS = 65535
MESSAGE_TIMEOUT = 30

def shape(value):
"""تحويل القيم إلى نص مناسب للواجهة العربية."""
if value is None:
return ""
return str(value)

def to_bytes(data):
"""تحويل البيانات إلى bytes."""
if isinstance(data, bytes):
return data

if isinstance(data, bytearray):
    return bytes(data)

if isinstance(data, str):
    return data.encode("utf-8")

return json.dumps(
    data,
    ensure_ascii=False,
    separators=(",", ":")
).encode("utf-8")

def encode(command, payload=None):
"""إنشاء رسالة JSON موحدة."""

message = {
    "version": 1,
    "id": uuid.uuid4().hex,
    "command": str(command),
    "payload": payload if payload is not None else {},
    "timestamp": time.time()
}

return to_bytes(message)

def decode(data):
"""فك رسالة JSON والتحقق من بنيتها."""

try:
    message = json.loads(to_bytes(data).decode("utf-8"))
except (ValueError, UnicodeDecodeError):
    raise ValueError("رسالة غير صالحة")

if not isinstance(message, dict):
    raise ValueError("تنسيق الرسالة غير صحيح")

if message.get("version") != 1:
    raise ValueError("إصدار البروتوكول غير مدعوم")

if not isinstance(message.get("command"), str):
    raise ValueError("الأمر غير صالح")

if not isinstance(message.get("payload"), dict):
    raise ValueError("محتوى الرسالة غير صالح")

return message

def fragment(data, chunk_size=DEFAULT_CHUNK):
"""تقسيم الرسالة إلى حزم BLE مرقمة."""

data = to_bytes(data)

if chunk_size <= HEADER.size:
    raise ValueError("حجم الحزمة صغير جداً")

payload_size = chunk_size - HEADER.size

count = max(
    1,
    (len(data) + payload_size - 1) // payload_size
)

if count > MAX_PARTS:
    raise ValueError("الرسالة أكبر من الحد المسموح")

msg_id = uuid.uuid4().int & 0xFFFFFFFF
checksum = zlib.crc32(data) & 0xFFFFFFFF

packets = []

for index in range(count):

    start = index * payload_size
    end = start + payload_size

    part = data[start:end]

    header = HEADER.pack(
        MAGIC,
        msg_id,
        index,
        count,
        checksum
    )

    packets.append(header + part)

return packets

class Reassembler:
"""إعادة تجميع الحزم المستلمة عبر BLE."""

def __init__(self, timeout=MESSAGE_TIMEOUT):
    self.timeout = timeout
    self.messages = {}

def clear(self):
    self.messages.clear()

def cleanup(self):
    now = time.time()

    expired = [
        key for key, value in self.messages.items()
        if now - value["time"] > self.timeout
    ]

    for key in expired:
        del self.messages[key]

def feed(self, packet):
    """إضافة حزمة وإرجاع الرسالة عند اكتمالها."""

    packet = to_bytes(packet)

    if len(packet) < HEADER.size:
        return None

    try:
        magic, msg_id, index, count, checksum = (
            HEADER.unpack(packet[:HEADER.size])
        )
    except struct.error:
        return None

    if magic != MAGIC:
        return None

    if count < 1 or index >= count:
        return None

    payload = packet[HEADER.size:]

    self.cleanup()

    if msg_id not in self.messages:

        self.messages[msg_id] = {
            "count": count,
            "checksum": checksum,
            "parts": {},
            "time": time.time()
        }

    message = self.messages[msg_id]

    if (
        message["count"] != count
        or message["checksum"] != checksum
    ):
        del self.messages[msg_id]
        return None

    message["parts"][index] = payload
    message["time"] = time.time()

    if len(message["parts"]) != count:
        return None

    try:
        result = b"".join(
            message["parts"][i]
            for i in range(count)
        )
    except KeyError:
        return None

    del self.messages[msg_id]

    actual_checksum = zlib.crc32(result) & 0xFFFFFFFF

    if actual_checksum != checksum:
        return None

    return result
