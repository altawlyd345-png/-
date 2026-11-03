"""Receiver v3: pure white until Sender sends an explicit command. Approved content persists.
Understands: hello, apply_scene, apply_design, apply_playlist, store_project, play_project,
clear, hide, restore, reload, next, prev, emergency, emergency_off, ping.
Media arrives over Wi-Fi (mediaserver.py); BLE carries the commands."""
import json, os, threading, uuid
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.utils import get_color_from_hex as H
from protocol import Reassembler, encode, fragment, shape, to_bytes, dyn_text
import mediaserver

PORT = 8765

FONT = next((p for p in ("fonts/Amiri-Regular.ttf", "fonts/NotoNaskhArabic-Regular.ttf") if os.path.exists(p)), "fonts/NotoNaskhArabic-Regular.ttf")
F = {"font_name": FONT} if os.path.exists(FONT) else {}
PERMS = ["android.permission.BLUETOOTH_CONNECT", "android.permission.BLUETOOTH_ADVERTISE",
         "android.permission.BLUETOOTH_SCAN", "android.permission.ACCESS_FINE_LOCATION",
         "android.permission.READ_MEDIA_IMAGES", "android.permission.READ_MEDIA_VIDEO",
         "android.permission.READ_MEDIA_AUDIO", "android.permission.READ_EXTERNAL_STORAGE"]

def lab(text, size, color, **kw):
    return Label(text=shape(text), font_size=size, color=H(color), **F, **kw)

def clamp_speed(v):
    try: return max(1, min(10, int(v)))
    except (TypeError, ValueError): return 5

def keep_awake():
    try:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass
        @run_on_ui_thread
        def go():
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            w = act.getWindow(); w.addFlags(128)
            w.getDecorView().setSystemUiVisibility(5894)
        go()
    except Exception as e:
        print("keep_awake:", e)

class Stage(FloatLayout):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        with self.canvas.before:
            self.c = Color(1, 1, 1, 1)
            self.r = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._u, size=self._u)
        self._evs = []; self._fx = []; self.lbl = None

    def _u(self, *a): self.r.pos, self.r.size = self.pos, self.size

    def _sched(self, fn, dt, once=False, fx=False):
        ev = (Clock.schedule_once if once else Clock.schedule_interval)(fn, dt)
        (self._fx if fx else self._evs).append(ev); return ev

    def _clear_fx(self):
        for e in self._fx: e.cancel()
        self._fx = []
        if self.lbl: Animation.cancel_all(self.lbl); self.lbl.opacity = 1

    def stop(self):
        self._clear_fx()
        for e in self._evs: e.cancel()
        self._evs = []
        self.app.stop_media()

    def render(self, c):
        self.stop(); self.clear_widgets(); self.lbl = None
        if not c:
            self.c.rgba = (1, 1, 1, 1); return
        (self.scene if c["kind"] == "scene" else self.design)(c["d"])

    # ---------- scene: background + image/video + audio + animated text ----------
    def scene(self, sc):
        self.c.rgba = H(sc.get("bg", "#FFFFFF"))
        t = sc.get("text") or {}
        msgs = [m for m in t.get("msgs", []) if str(m).strip()]
        v, a = sc.get("visual"), sc.get("audio")
        vpath = self.app.media_path(v) if v else None
        video = bool(vpath) and v.get("kind") == "video"
        if vpath and v.get("kind") == "image":
            self.add_widget(Image(source=vpath, fit_mode="contain", size_hint=(1, 1)))
        if video:
            self.app.play_video(vpath, bool(v.get("loop", True)), str(msgs[0]) if msgs else "",
                                t.get("color", "#FFFFFF"), int(t.get("size", 48)))
        apath = self.app.media_path(a) if a else None
        if apath: self.app.play_audio(apath, bool(a.get("loop", True)))
        if msgs and not video: self.text_layer(t, msgs)

    def text_layer(self, t, msgs):
        mode = t.get("mode", "static"); speed = clamp_speed(t.get("speed", 5))
        size = str(t.get("size", 48)) + "sp"; color = t.get("color", "#000000")
        align = t.get("align", "center")
        if mode in ("ticker_h", "ticker_v"):
            txt = ("     ".join(map(str, msgs))) if mode == "ticker_h" else "\n\n".join(map(str, msgs))
            self._sched(lambda dt: self.ticker(txt, size, color, align, mode, t.get("tdir", "r2l"), speed), 0.2, once=True)
            return
        l = lab("", size, color, size_hint=(1, 1), halign=align, valign="middle")
        l.bind(size=lambda i, v: setattr(i, "text_size", (v[0] * 0.92, v[1] * 0.92)))
        self.add_widget(l); self.lbl = l
        st = {"i": 0}
        def show(dt=0):
            self._clear_fx()
            self.effect(l, str(msgs[st["i"] % len(msgs)]), mode, speed)
        show()
        if len(msgs) > 1:
            hold = max(2, int(t.get("hold", 5) or 5))
            def nxt(dt): st["i"] += 1; show()
            self._sched(nxt, hold)

    def effect(self, l, txt, mode, speed):
        l.text = shape(txt)
        if mode == "blink":
            self._sched(lambda dt: setattr(l, "opacity", 0 if l.opacity > 0.5 else 1), 1.1 - speed * 0.1, fx=True)
        elif mode == "typewriter":
            st = {"n": 0}; l.text = ""
            def step(dt):
                st["n"] = min(st["n"] + 1, len(txt)); l.text = shape(txt[:st["n"]])
            self._sched(step, 0.6 / speed, fx=True)
        elif mode == "fade":
            l.opacity = 0; Animation(opacity=1.0, duration=3.0 / speed).start(l)
        elif mode == "fade_loop":
            d = 3.0 / speed
            a = Animation(opacity=0.0, duration=d) + Animation(opacity=1.0, duration=d); a.repeat = True; a.start(l)

    def ticker(self, txt, size, color, align, mode, tdir, speed):
        v = 40.0 * speed
        if mode == "ticker_h":
            l = lab(txt, size, color, size_hint=(None, None)); l.texture_update(); l.size = l.texture_size
            self.add_widget(l)
            left = tdir == "r2l"
            l.x = self.right if left else self.x - l.width
            def step(dt):
                l.center_y = self.center_y
                if left:
                    l.x -= v * dt
                    if l.right < self.x: l.x = self.right
                else:
                    l.x += v * dt
                    if l.x > self.right: l.x = self.x - l.width
            self._sched(step, 1 / 60.0)
        else:
            l = lab(txt, size, color, size_hint=(None, None), halign=align)
            l.text_size = (self.width * 0.92, None); l.texture_update(); l.size = l.texture_size
            self.add_widget(l); l.center_x = self.center_x; l.y = self.y - l.height
            def step(dt):
                l.center_x = self.center_x; l.y += v * dt
                if l.y > self.top: l.y = self.y - l.height
            self._sched(step, 1 / 60.0)

    # ---------- designed screen ----------
    def design(self, d):
        self.c.rgba = H(d.get("bg", "#FFFFFF")); dyn = []
        for e in d.get("els", []):
            frac = float(e.get("size", 0.05))
            l = lab(e.get("text", ""), 20, e.get("fg", "#000000"), size_hint=(e["w"], e["h"]),
                    pos_hint={"x": e["x"], "y": e["y"]}, halign="center", valign="middle")
            l.font_size = frac * max(self.height, 1)
            self.bind(height=lambda i, v, l=l, frac=frac: setattr(l, "font_size", frac * v))
            l.bind(size=lambda i, v: setattr(i, "text_size", v))
            if e.get("bg"):
                with l.canvas.before:
                    Color(*H(e["bg"])); rr = Rectangle(pos=l.pos, size=l.size)
                l.bind(pos=lambda i, v, rr=rr: setattr(rr, "pos", v), size=lambda i, v, rr=rr: setattr(rr, "size", v))
            if dyn_text(e) is not None: dyn.append((l, e))
            self.add_widget(l)
        def tick(dt):
            for l, e in dyn: l.text = shape(dyn_text(e))
        if dyn: tick(0); self._sched(tick, 1.0)

class ReceiverApp(App):
    def build(self):
        Window.clearcolor = (1, 1, 1, 1)
        self.stage = Stage(self)
        self.rdir = os.path.join(self.user_data_dir, "received"); os.makedirs(self.rdir, exist_ok=True)
        self.store = os.path.join(self.user_data_dir, "approved.json")
        self.pstore = os.path.join(self.user_data_dir, "projects.json")
        self.tfile = os.path.join(self.user_data_dir, "token.txt")
        self.token = self._token()
        self.seen = set(); self.ra = Reassembler(); self.ble = None; self.mh = None; self.act = None
        self.base = None; self.projects = {}; self.hidden = False; self.emerg = None
        self.idx = 0; self._pl = None; self._em = None
        try:
            with open(self.store, encoding="utf-8") as f:
                data = json.load(f)
            self.base = data.get("content"); self.seen = set(data.get("seen", []))
        except Exception: pass
        try:
            with open(self.pstore, encoding="utf-8") as f: self.projects = json.load(f)
        except Exception: pass
        Clock.schedule_once(lambda dt: self.refresh(), 0.6)
        return self.stage

    def _token(self):
        try:
            with open(self.tfile) as f: return f.read().strip() or self._new_token()
        except Exception: return self._new_token()
    def _new_token(self):
        t = uuid.uuid4().hex[:10]
        try:
            with open(self.tfile, "w") as f: f.write(t)
        except Exception: pass
        return t

    # ---------- lifecycle ----------
    def on_start(self):
        keep_awake()
        try:
            from jnius import autoclass
            self.act = autoclass("org.kivy.android.PythonActivity").mActivity
            self.mh = autoclass("org.bleremote.MediaHelper")
        except Exception as e: print("jnius:", e)
        try:
            mediaserver.start(PORT, self.token, self.rdir,
                              lambda: str(self.mh.listMedia(self.act)),
                              lambda uri: (lambda b: bytes((x & 0xFF) for x in b) if b else None)(self.mh.thumb(self.act, uri, 256)))
        except Exception as e: print("http server:", e)
        try:
            from android.permissions import request_permissions
            request_permissions(PERMS, lambda p, g: Clock.schedule_once(self.start_ble, 0))
        except Exception: self.start_ble()

    def on_pause(self): return True
    def on_resume(self): keep_awake()

    def start_ble(self, *a):
        if self.ble: return
        try:
            from jnius import autoclass
            self.ble = autoclass("org.bleremote.BleServer")(self.act)
            self.ble.start()
            Clock.schedule_interval(self.poll, 0.05)
        except Exception as e: print("BLE start failed:", e)

    # ---------- media helpers ----------
    def media_path(self, m):
        if not m: return None
        p = os.path.join(self.rdir, os.path.basename(str(m.get("name", ""))))
        return p if os.path.isfile(p) else None
    def play_video(self, path, loop, text, color, size):
        if not self.mh: return
        try:
            c = 0xFF000000 | int(color.lstrip("#")[:6], 16)
            if c > 0x7FFFFFFF: c -= 1 << 32
            self.mh.playVideo(self.act, path, loop, text, c, int(max(14, size * 0.6)))
        except Exception as e: print("video:", e)
    def play_audio(self, path, loop):
        if self.mh:
            try: self.mh.playAudio(path, loop)
            except Exception as e: print("audio:", e)
    def stop_media(self):
        if self.mh:
            try: self.mh.stopAudio(); self.mh.stopVideo(self.act)
            except Exception: pass

    def prepare(self, content, done):
        """Copy gallery items of this phone into app storage (background), then done(content)."""
        d = content["d"]
        scenes = [d] if content["kind"] == "scene" else (d.get("scenes", []) if content["kind"] == "playlist" else [])
        need = [m for s in scenes for k in ("visual", "audio") for m in [s.get(k)] if m and m.get("src") == "gallery"]
        if not need or not self.mh: return done(content)
        def run():
            cache = {}
            for m in need:
                u = m.get("uri", "")
                if u not in cache: cache[u] = str(self.mh.copyUri(self.act, u, self.rdir))
                m["src"] = "upload"; m["name"] = cache[u]
            Clock.schedule_once(lambda dt: done(content), 0)
        threading.Thread(target=run, daemon=True).start()

    # ---------- state ----------
    def current(self):
        if self.emerg: return self.emerg
        if self.hidden: return None
        b = self.base
        if b and b["kind"] == "playlist":
            sc = b["d"].get("scenes", [])
            return {"kind": "scene", "d": sc[self.idx % len(sc)]} if sc else None
        return b

    def refresh(self):
        if self._pl: self._pl.cancel(); self._pl = None
        self.stage.render(self.current())
        b = self.base
        if b and b["kind"] == "playlist" and len(b["d"].get("scenes", [])) > 1 and not self.emerg and not self.hidden:
            self._pl = Clock.schedule_interval(self.advance, max(2, int(b["d"].get("secs", 10) or 10)))

    def advance(self, dt): self.idx += 1; self.stage.render(self.current())

    def set_base(self, c):
        self.base = c; self.idx = 0; self.hidden = False; self.emerg = None
        self.save(); self.refresh()

    def save(self):
        tmp = self.store + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"content": self.base, "seen": list(self.seen)[-50:]}, f, ensure_ascii=False)
        os.replace(tmp, self.store)

    def save_projects(self):
        with open(self.pstore, "w", encoding="utf-8") as f: json.dump(self.projects, f, ensure_ascii=False)

    # ---------- BLE ----------
    def ack(self, mid, ok=True, extra=None):
        for p in fragment(encode("ack", {"id": mid, "ok": ok, **(extra or {})}), self.ble.chunkSize()):
            self.ble.notifyData(p)

    def poll(self, dt):
        for _ in range(20):
            raw = self.ble.poll()
            if raw is None: return
            msg = self.ra.feed(to_bytes(raw))
            if msg: self.handle(msg)

    def handle(self, m):
        mid, t, d = m["id"], m["t"], m.get("d", {})
        if mid in self.seen: self.ack(mid); return
        def finish(ok=True, extra=None):
            if ok and t != "hello": self.seen.add(mid)
            self.ack(mid, ok, extra)
        if t == "hello":
            ip = ""
            try: ip = str(self.mh.localIp())
            except Exception: pass
            return finish(True, {"ip": ip, "port": PORT, "token": self.token})
        if t in ("apply_scene", "apply_design", "apply_playlist"):
            kind = {"apply_scene": "scene", "apply_design": "design", "apply_playlist": "playlist"}[t]
            return self.prepare({"kind": kind, "d": d}, lambda c: (self.set_base(c), finish()))
        if t == "store_project":
            def stored(c):
                self.projects[str(d.get("id"))] = {"name": d.get("name", ""), "scenes": c["d"].get("scenes", []),
                                                   "secs": d.get("secs", 10)}
                self.save_projects(); finish()
            return self.prepare({"kind": "playlist", "d": d}, stored)
        if t == "play_project":
            p = self.projects.get(str(d.get("id")))
            if not p: return finish(False)
            self.set_base({"kind": "playlist", "d": {"scenes": p["scenes"], "secs": p["secs"], "loop": True}})
            return finish()
        if t == "clear": self.base = None; self.hidden = False; self.emerg = None; self.save(); self.refresh()
        elif t == "hide": self.hidden = True; self.refresh()
        elif t == "restore": self.hidden = False; self.emerg = None; self.refresh()
        elif t == "reload": self.refresh()
        elif t in ("next", "prev"):
            self.idx += 1 if t == "next" else -1; self.stage.render(self.current())
        elif t == "emergency":
            self.emerg = {"kind": "scene", "d": {"bg": d.get("bg", "#B71C1C"), "text": {
                "msgs": [d.get("text", "")], "color": d.get("color", "#FFFFFF"), "size": d.get("size", 64),
                "mode": "blink", "speed": 5}}}
            self.refresh()
            if self._em: self._em.cancel(); self._em = None
            try: secs = int(d.get("seconds", 0) or 0)
            except (TypeError, ValueError): secs = 0
            if secs > 0: self._em = Clock.schedule_once(lambda dt: self.end_emergency(), secs)
        elif t == "emergency_off": self.end_emergency()
        elif t != "ping": return finish(False)
        finish()

    def end_emergency(self): self.emerg = None; self.refresh()

ReceiverApp().run()
