import json
import os
import time
import uuid

class Store:

COLLECTIONS = [
    "memos",
    "pages",
    "templates",
    "playlists",
    "schedules",
    "projects"
]

def __init__(self, path):
    self.path = path
    os.makedirs(os.path.dirname(path), exist_ok=True)

    self.d = {
        "settings": {"pin": ""},
        "log": []
    }

    for name in self.COLLECTIONS:
        self.d[name] = []

    self.load()

def load(self):
    if not os.path.exists(self.path):
        self.save()
        return

    try:
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.d.update(data)

        for name in self.COLLECTIONS:
            self.d.setdefault(name, [])

        self.d.setdefault("settings", {"pin": ""})
        self.d.setdefault("log", [])

    except (ValueError, OSError):
        self.save()

def save(self):
    temp = self.path + ".tmp"

    with open(temp, "w", encoding="utf-8") as f:
        json.dump(self.d, f, ensure_ascii=False, indent=2)

    os.replace(temp, self.path)

def put(self, collection, item):
    if collection not in self.COLLECTIONS:
        raise ValueError("قسم غير معروف")

    item = dict(item)
    item.setdefault("id", str(uuid.uuid4()))
    item["updated"] = time.time()

    items = self.d[collection]

    for index, old in enumerate(items):
        if old["id"] == item["id"]:
            items[index] = item
            self.save()
            return item

    items.append(item)
    self.save()
    return item

def items(self, collection, query=""):
    if collection not in self.COLLECTIONS:
        raise ValueError("قسم غير معروف")

    query = query.strip().casefold()

    result = self.d[collection]

    if query:
        result = [
            item for item in result
            if query in str(item.get("name", "")).casefold()
            or query in str(item.get("body", "")).casefold()
        ]

    return sorted(
        result,
        key=lambda x: x.get("updated", 0),
        reverse=True
    )

def delete(self, collection, item_id):
    if collection not in self.COLLECTIONS:
        raise ValueError("قسم غير معروف")

    self.d[collection] = [
        item for item in self.d[collection]
        if item["id"] != item_id
    ]

    self.save()

def log(self, message):
    self.d["log"].append({
        "t": time.strftime("%Y-%m-%d %H:%M:%S"),
        "m": message
    })

    self.d["log"] = self.d["log"][-500:]
    self.save()

def export_to(self, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(self.d, f, ensure_ascii=False, indent=2)

def import_from(self, path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for name in self.COLLECTIONS:
        data.setdefault(name, [])

    data.setdefault("settings", {"pin": ""})
    data.setdefault("log", [])

    self.d = data
    self.save()
