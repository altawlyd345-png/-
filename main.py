"""Receiver: pure white screen until Sender sends an explicit apply command.
Approved content is persisted and restored on every launch."""
import json, os
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.utils import get_color_from_hex
from protocol import Reassembler, encode, fragment, shape, to_bytes

FONT = "fonts/NotoNaskhArabic-Regular.ttf"
PERMS = ["android.permission.BLUETOOTH_CONNECT", "android.permission.BLUETOOTH_ADVERTISE",
         "android.permission.BLUETOOTH_SCAN", "android.permission.ACCESS_FINE_LOCATION"]

class Screen(FloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            self.c = Color(1, 1, 1, 1)
            self.r = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._u, size=self._u)
        self.content = None
        self.lbl = None
    def _u(self, *a):
        self.r.pos, self.r.size = self.pos, self.size
        if self.lbl:
            self.lbl.text_size = (self.width * 0.92, self.height * 0.92)
    def show(self, d):
        self.clear_widgets(); self.lbl = None
        if not d:
            self.c.rgba = (1, 1, 1, 1); return
        self.c.rgba = get_color_from_hex(d.get("bg", "#FFFFFF"))
        txt = d.get("text", "")
        if txt:
            kw = {"font_name": FONT} if os.path.exists(FONT) else {}
            self.lbl = Label(text=shape(txt), font_size=str(d.get("size", 48)) + "sp",
                             color=get_color_from_hex(d.get("color", "#000000")),
                             halign=d.get("align", "center"), valign="middle",
                             size_hint=(1, 1), pos_hint={"x": 0, "y": 0}, **kw)
            self.lbl.text_size = (self.width * 0.92, self.height * 0.92)
            self.add_widget(self.lbl)

class ReceiverApp(App):
    def build(self):
        Window.clearcolor = (1, 1, 1, 1)
        self.screen = Screen()
        self.store = os.path.join(self.user_data_dir, "approved.json")
        self.seen = set(); self.ra = Reassembler(); self.ble = None
        self.restore()
        return self.screen

    def on_start(self):
        try:
            from android.permissions import request_permissions
            request_permissions(PERMS, lambda p, g: Clock.schedule_once(self.start_ble, 0))
        except Exception:
            self.start_ble()

    def start_ble(self, *a):
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            self.ble = autoclass("org.bleremote.BleServer")(act)
            self.ble.start()
            Clock.schedule_interval(self.poll, 0.05)
        except Exception as e:
            print("BLE start failed:", e)

    # persistence
    def restore(self):
        try:
            with open(self.store, encoding="utf-8") as f:
                d = json.load(f)
            self.screen.show(d.get("content"))
            self.seen = set(d.get("seen", []))
        except Exception:
            self.screen.show(None)   # first launch -> pure white

    def save(self, content):
        tmp = self.store + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"content": content, "seen": list(self.seen)[-50:]}, f, ensure_ascii=False)
        os.replace(tmp, self.store)

    def ack(self, mid, ok=True):
        env = encode("ack", {"id": mid, "ok": ok})
        for p in fragment(env, self.ble.chunkSize()):
            self.ble.notifyData(p)

    def poll(self, dt):
        for _ in range(20):
            raw = self.ble.poll()
            if raw is None:
                return
            msg = self.ra.feed(to_bytes(raw))
            if msg:
                self.handle(msg)

    def handle(self, m):
        mid, t, d = m["id"], m["t"], m.get("d", {})
        if mid in self.seen:            # duplicate -> never re-execute
            self.ack(mid); return
        if t == "apply_text":
            self.save(d); self.screen.show(d)
        elif t == "clear":
            self.save(None); self.screen.show(None)
        elif t != "ping":
            self.ack(mid, False); return
        self.seen.add(mid)
        self.ack(mid)

ReceiverApp().run()
