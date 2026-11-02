import json
import struct
import time

MAGIC = b"BL"
HEADER = struct.Struct("!2sIHHI")

DEFAULT_CHUNK = 6
MESSAGE_TIMEOUT = 30

def encode(command, payload):
message = {
"version": 1,
"command": command,
"payload": payload,
"timestamp": time.time()
}
return json.dumps(
message,
ensure_ascii=False
).encode("utf-8")

def decode(data):
return json.loads(data.decode("utf-8"))

def fragment(data, chunk_size=DEFAULT_CHUNK):
message_id = int(time.time() * 1000) & 0xFFFFFFFF
parts = [
data[i:i + chunk_size]
for i in range(0, len(data), chunk_size)
]

packets = []

for index, part in enumerate(parts):
    header = HEADER.pack(
        MAGIC,
        message_id,
        index,
        len(parts),
        len(data)
    )
    packets.append(header + part)

return packets

class Reassembler:

def __init__(self):
    self.messages = {}

def feed(self, packet):
    if len(packet) < HEADER.size:
        return None

    magic, msg_id, index, total, size = HEADER.unpack(
        packet[:HEADER.size]
    )

    if magic != MAGIC or total == 0 or index >= total:
        return None

    now = time.time()

    for key in list(self.messages):
        if now - self.messages[key]["time"] > MESSAGE_TIMEOUT:
            del self.messages[key]

    if msg_id not in self.messages:
        self.messages[msg_id] = {
            "parts": {},
            "total": total,
            "size": size,
            "time": now
        }

    message = self.messages[msg_id]

    if message["total"] != total or message["size"] != size:
        del self.messages[msg_id]
        return None

    message["parts"][index] = packet[HEADER.size:]

    if len(message["parts"]) != total:
        return None

    result = b"".join(
        message["parts"][i]
        for i in range(total)
    )

    del self.messages[msg_id]

    if len(result) != size:
        return None

    return result
