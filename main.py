"""BLE Remote - SENDER v2.
Rule: edit / save / preview are local. Receiver changes only via an explicit, confirmed send."""
import glob, hashlib, json, os, shutil, time
from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex as H
from protocol import Reassembler, encode, fragment, shape, to_bytes
from store import Store

APP_FONT = "fonts/NotoNaskhArabic-Regular.ttf"
BLUE, DARK, GREY, RED, GREEN = "#1565C0", "#0B0F1A", "#37474F", "#B71C1C", "#00897B"
PERMS = ["android.permission.BLUETOOTH_CONNECT", "android.permission.BLUETOOTH_SCAN",
         "android.permission.ACCESS_FINE_LOCATION"]
COLORS = {"أسود": "#000000", "أبيض": "#FFFFFF", "أزرق": "#1565C0", "أحمر": "#D32F2F",
          "أخضر": "#2E7D32", "أصفر": "#FDD835", "برتقالي": "#EF6C00"}
STATES = {"idle": "غير متصل", "scanning": "جاري البحث...", "connecting": "جاري الاتصال...",
          "ready": "متصل ✔", "disconnected": "انقطع الاتصال", "bt_off": "فعّل البلوتوث",
          "no_service": "الجهاز لا يحتوي الخدمة", "scan_failed": "فشل البحث"}
F = {"font_name": APP_FONT} if os.path.exists(APP_FONT) else {}

def T(s): return shape(s)

def L(text, h=None, **kw):
    kw = {**F, "color": (1, 1, 1, 1), "halign": "center", "valign": "middle", **kw}
    l = Label(text=T(text), **kw)
    l.bind(size=lambda i, v: setattr(i, "text_size", v))
    if h: l.size_hint_y = None; l.height = dp(h)
    return l

def B(text, cb, color=BLUE, h=48, wx=None):
    b = Button(text=T(text), background_normal="", background_color=H(color), size_hint_y=None,
               height=dp(h), **F)
    if wx: b.size_hint_x = wx
    b.bind(on_release=lambda *_: cb()); return b

def TI(text="", hint="", ml=False, h=44, **kw):
    return TextInput(text=text, hint_text=T(hint) if hint else "", multiline=ml, size_hint_y=None,
                     height=dp(h), **{**F, **kw})

def popup(title, content, size=(0.94, 0.8)):
    p = Popup(title=T(title), content=content, size_hint=size, title_font=APP_FONT if F else "Roboto")
    p.open(); return p

def confirm(msg, yes):
    box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
    box.add_widget(L(msg))
    row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    p = popup("تأكيد", box, (0.9, 0.4))
    row.add_widget(B("إلغاء", p.dismiss, GREY))
    row.add_widget(B("تأكيد", lambda: (p.dismiss(), yes()), GREEN))
    box.add_widget(row)

def hexof(spinner):
    for k, v in COLORS.items():
        if T(k) == spinner.text: return v
    return "#000000"

def color_spinner(default):
    return Spinner(text=T(default), values=[T(k) for k in COLORS], **F)

class Page(Screen):
    def __init__(self, app, key, title):
        super().__init__(name=key)
        self.app = app
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        hdr = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        hdr.add_widget(B("رجوع", lambda: app.go("home"), GREY, 44, 0.3))
        hdr.add_widget(L(title, bold=True))
        root.add_widget(hdr)
        self.body = BoxLayout(orientation="vertical", spacing=dp(6))
        root.add_widget(self.body)
        self.add_widget(root)
    def on_pre_enter(self, *a): self.refresh()
    def refresh(self): pass

# ---------- generic list pages (memos, pages, templates, playlists, schedules, projects) ----------
class ListPage(Page):
    def __init__(self, app, key, title, col, fields, send=None, extra=None):
        super().__init__(app, key, title)
        self.col, self.fields, self.send, self.extra = col, fields, send, extra
        self.q = TI(hint="بحث بالاسم أو المحتوى")
        self.q.bind(text=lambda *_: self.refresh())
        self.lst = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        self.lst.bind(minimum_height=self.lst.setter("height"))
        sv = ScrollView(); sv.add_widget(self.lst)
        self.body.add_widget(self.q); self.body.add_widget(sv)
        self.body.add_widget(B("+ جديد", lambda: self.edit({})))

    def refresh(self):
        self.lst.clear_widgets()
        for it in self.app.store.items(self.col, self.q.text):
            row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(3))
            row.add_widget(L(("★ " if it.get("fav") else "") + it.get("name", "؟"), halign="right"))
            row.add_widget(B("★", lambda i=it: self.fav(i), GREY, 44, 0.12))
            row.add_widget(B("تعديل", lambda i=it: self.edit(i), GREY, 44, 0.25))
            row.add_widget(B("نسخ", lambda i=it: self.dup(i), GREY, 44, 0.2))
            row.add_widget(B("حذف", lambda i=it: self.rm(i), RED, 44, 0.2))
            if self.extra: row.add_widget(B(self.extra[0], lambda i=it: self.extra[1](i), BLUE, 44, 0.25))
            if self.send: row.add_widget(B("إرسال", lambda i=it: self.send(i), GREEN, 44, 0.25))
            self.lst.add_widget(row)

    def fav(self, it): it["fav"] = not it.get("fav"); self.app.store.put(self.col, it); self.refresh()
    def dup(self, it):
        c = dict(it); c.pop("id", None); c["name"] = it.get("name", "") + " (نسخة)"
        self.app.store.put(self.col, c); self.refresh()
    def rm(self, it): confirm("حذف نهائي؟", lambda: (self.app.store.delete(self.col, it["id"]), self.refresh()))

    def edit(self, it):
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
        ins = {}
        for key, label, ml in self.fields:
            box.add_widget(L(label, 22))
            ins[key] = TI(it.get(key, ""), ml=ml, h=150 if ml else 44)
            box.add_widget(ins[key])
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        p = popup("تحرير", box)
        def save():
            n = dict(it); n.update({k: v.text for k, v in ins.items()})
            n.setdefault("name", "بدون اسم")
            if not n["name"].strip(): n["name"] = "بدون اسم"
            self.app.store.put(self.col, n); p.dismiss(); self.refresh()
        row.add_widget(B("إلغاء", p.dismiss, GREY)); row.add_widget(B("حفظ (لا يرسل)", save, BLUE))
        box.add_widget(row)

# ---------- Text Studio ----------
class TextStudio(Page):
    def __init__(self, app):
        super().__init__(app, "text", "Text Studio")
        self.inp = TI(hint="اكتب النص هنا", ml=True, h=100)
        r1 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        self.size = TI("48", input_filter="int", h=44, size_hint_x=.2)
        self.fg = color_spinner("أبيض"); self.bg = color_spinner("أزرق")
        self.align = Spinner(text="center", values=["right", "center", "left"], size_hint_x=.3)
        self.font = Spinner(text="الافتراضي", values=["الافتراضي"], **F)
        for w in (self.size, self.fg, self.bg, self.align): r1.add_widget(w)
        self.prev = Label(halign="center", valign="middle", **F)
        with self.prev.canvas.before:
            self.pc = Color(*H(BLUE)); self.pr = Rectangle()
        self.prev.bind(pos=self._u, size=self._u)
        for w in (self.inp, r1, self.font, self.prev,
                  B("معاينة (محلية فقط)", self.preview, GREY),
                  B("حفظ كمذكرة", self.save_memo, GREY),
                  B("إرسال واعتماد وعرض", self.do_send, GREEN)):
            self.body.add_widget(w)
    def _u(self, *a): self.pr.pos, self.pr.size = self.prev.pos, self.prev.size; self.prev.text_size = self.prev.size
    def refresh(self): self.font.values = ["الافتراضي"] + sorted(self.app.fonts)
    def style(self):
        return {"text": self.inp.text, "size": int(self.size.text or 48), "color": hexof(self.fg),
                "bg": hexof(self.bg), "align": self.align.text,
                "font": "" if self.font.text == "الافتراضي" else self.font.text}
    def preview(self):
        s = self.style(); self.pc.rgba = H(s["bg"]); self.prev.color = H(s["color"])
        self.prev.font_size = max(12, s["size"] // 2)
        self.prev.halign = s["align"]; self.prev.text = T(s["text"])
        fp = self.app.fonts.get(s["font"]);
        if fp: self.prev.font_name = fp
    def save_memo(self):
        s = self.style(); s["name"] = (s["text"][:20] or "مذكرة"); s["body"] = s["text"]
        self.app.store.put("memos", s); self.app.toast("تم الحفظ (لم يُرسل)")
    def do_send(self):
        s = self.style()
        confirm("سيتم استبدال المعروض على Receiver. متابعة؟", lambda: self.app.send("apply_text", s))

# ---------- Screen Designer ----------
class El(Label):
    def __init__(self, d, **kw):
        super().__init__(**{**F, **kw}); self.d = d; self.sel = False
        with self.canvas.before:
            self.bgc = Color(*H(d.get("bg") or "#00000000") if d.get("bg") else (0, 0, 0, 0)); self.bgr = Rectangle()
        self.bind(pos=self._u, size=self._u); self.apply()
    def _u(self, *a):
        self.bgr.pos, self.bgr.size = self.pos, self.size; self.text_size = self.size
    def apply(self):
        d = self.d; self.text = T(d.get("text", "")); self.font_size = d.get("size", 32)
        self.color = H(d.get("fg", "#FFFFFF"))
        self.bgc.rgba = H(d["bg"]) if d.get("bg") else (0, 0, 0, 0.15 if self.sel else 0)
    def on_touch_down(self, t):
        if self.collide_point(*t.pos):
            t.grab(self); self.parent.owner.select(self); return True
    def on_touch_move(self, t):
        if t.grab_current is self: self.x += t.dx; self.y += t.dy; return True
    def on_touch_up(self, t):
        if t.grab_current is self: t.ungrab(self); return True

class Area(FloatLayout):
    pass

class Designer(Page):
    def __init__(self, app):
        super().__init__(app, "designer", "Screen Designer")
        self.cur = None; self.name = "تصميم جديد"; self.hist = []; self.redo = []
        self.area = Area(size_hint=(1, 1)); self.area.owner = self
        with self.area.canvas.before:
            self.ac = Color(*H(BLUE)); self.ar = Rectangle()
        self.area.bind(pos=self._u, size=self._u)
        self.txt = TI(hint="نص العنصر المحدد", h=40); self.txt.bind(text=self.on_txt)
        r1 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(3))
        for t, cb in (("+نص", self.add_text), ("+مربع", self.add_box), ("نسخ", self.dup),
                      ("حذف", self.rm), ("A+", lambda: self.fs(6)), ("A-", lambda: self.fs(-6))):
            r1.add_widget(B(t, cb, GREY, 44))
        r2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(3))
        for t, cb in (("لون", lambda: self.cyc("fg")), ("خلفية عنصر", lambda: self.cyc("bg")),
                      ("خلفية شاشة", self.cyc_screen), ("تراجع", self.undo), ("إعادة", self.redo_)):
            r2.add_widget(B(t, cb, GREY, 44))
        r3 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(3))
        r3.add_widget(B("حفظ كصفحة", self.save, BLUE)); r3.add_widget(B("حفظ كقالب", lambda: self.save("templates"), BLUE))
        r3.add_widget(B("إرسال واعتماد", self.do_send, GREEN))
        for w in (self.area, self.txt, r1, r2, r3): self.body.add_widget(w)
        self.bgcol = "#1565C0"; self.pal = list(COLORS.values())

    def _u(self, *a): self.ar.pos, self.ar.size = self.area.pos, self.area.size
    def snap(self): self.hist.append(self.dump()); self.redo = []; self.hist = self.hist[-30:]
    def dump(self):
        w, h = self.area.size; x0, y0 = self.area.pos
        return {"bg": self.bgcol, "els": [{**e.d, "x": (e.x - x0) / w, "y": (e.y - y0) / h, "w": e.width / w,
                                          "h": e.height / h, "size": e.d.get("size", 32) / h}
                                         for e in self.area.children[::-1] if isinstance(e, El)]}
    def load(self, design):
        self.area.clear_widgets(); self.cur = None
        self.bgcol = design.get("bg", "#1565C0"); self.ac.rgba = H(self.bgcol)
        w, h = self.area.size; x0, y0 = self.area.pos
        for d in design.get("els", []):
            d = dict(d); d["size"] = d.get("size", 0.05) * h
            e = El(d, size_hint=(None, None), size=(d["w"] * w, d["h"] * h), pos=(x0 + d["x"] * w, y0 + d["y"] * h))
            self.area.add_widget(e)
    def add(self, d):
        self.snap(); w, h = self.area.size
        e = El(d, size_hint=(None, None), size=(w * 0.6, h * 0.12), pos=(self.area.x + w * .2, self.area.y + h * .4))
        self.area.add_widget(e); self.select(e)
    def add_text(self): self.add({"text": "نص جديد", "size": 32, "fg": "#FFFFFF"})
    def add_box(self): self.add({"text": "", "size": 20, "fg": "#FFFFFF", "bg": "#000000"})
    def select(self, e):
        if self.cur: self.cur.sel = False; self.cur.apply()
        self.cur = e; e.sel = True; e.apply(); self.txt.unbind(text=self.on_txt)
        self.txt.text = e.d.get("text", ""); self.txt.bind(text=self.on_txt)
    def on_txt(self, i, v):
        if self.cur: self.cur.d["text"] = v; self.cur.apply()
    def fs(self, n):
        if self.cur: self.snap(); self.cur.d["size"] = max(10, self.cur.d.get("size", 32) + n); self.cur.apply()
    def cyc(self, k):
        if not self.cur: return
        self.snap(); cur = self.cur.d.get(k); i = self.pal.index(cur) if cur in self.pal else -1
        self.cur.d[k] = self.pal[(i + 1) % len(self.pal)]; self.cur.apply()
    def cyc_screen(self):
        self.snap(); i = self.pal.index(self.bgcol) if self.bgcol in self.pal else -1
        self.bgcol = self.pal[(i + 1) % len(self.pal)]; self.ac.rgba = H(self.bgcol)
    def dup(self):
        if self.cur:
            d = dict(self.cur.d); self.add(d); self.cur.x += dp(15); self.cur.y -= dp(15)
    def rm(self):
        if self.cur: self.snap(); self.area.remove_widget(self.cur); self.cur = None
    def undo(self):
        if self.hist: self.redo.append(self.dump()); self.load(self.hist.pop())
    def redo_(self):
        if self.redo: self.hist.append(self.dump()); self.load(self.redo.pop())
    def save(self, col="pages"):
        d = self.dump(); item = {"name": "تصميم " + time.strftime("%H:%M:%S"), "body": json.dumps(d, ensure_ascii=False)}
        self.app.store.put(col, item); self.app.toast("تم الحفظ (لم يُرسل)")
    def do_send(self):
        d = self.dump(); confirm("سيتم استبدال المعروض على Receiver. متابعة؟", lambda: self.app.send("apply_design", d))

# ---------- other pages ----------
class Remote(Page):
    def __init__(self, app):
        super().__init__(app, "remote", "Remote Control")
        cmds = [("إخفاء المحتوى", "hide", {}), ("استعادة آخر عرض", "restore", {}), ("مسح الشاشة", "clear", {}),
                ("اختبار اتصال", "ping", {}), ("إعادة تحميل المعتمد", "reload", {}),
                ("المذكرة التالية", "next", {}), ("المذكرة السابقة", "prev", {}), ("إيقاف الطوارئ", "emergency_off", {})]
        for t, ty, d in cmds:
            self.body.add_widget(B(t, lambda ty=ty, d=d, t=t: confirm(t + "؟", lambda: app.send(ty, d)),
                                   RED if ty == "clear" else GREY))
        self.em = TI(hint="نص رسالة الطوارئ"); self.body.add_widget(self.em)
        self.body.add_widget(B("إرسال رسالة طوارئ", lambda: confirm("استبدال العرض برسالة الطوارئ؟",
            lambda: app.send("emergency", {"text": self.em.text, "color": "#FFFFFF", "bg": "#B71C1C",
                                           "size": 64, "seconds": 0})), RED))

class Devices(Page):
    def __init__(self, app):
        super().__init__(app, "devices", "Device Manager")
        self.info = L("")
        self.body.add_widget(self.info)
        self.body.add_widget(B("بحث واتصال", app.connect, BLUE)); self.body.add_widget(B("قطع الاتصال", app.disconnect, GREY))
        self.logv = Label(**F, color=(1, 1, 1, 1), halign="right", valign="top", size_hint_y=None)
        self.logv.bind(texture_size=lambda i, v: setattr(i, "height", v[1]),
                       width=lambda i, v: setattr(i, "text_size", (v, None)))
        sv = ScrollView(); sv.add_widget(self.logv); self.body.add_widget(sv)
    def refresh(self):
        self.info.text = T("الحالة: " + self.app.status_text() + "  | MTU/Chunk: " + str(self.app.chunk()))
        self.logv.text = "\n".join(T(x["t"][11:] + " " + x["m"]) for x in self.app.store.d["log"][-40:][::-1])

class Fonts(Page):
    def __init__(self, app):
        super().__init__(app, "fonts", "Font Library")
        self.v = L("", halign="right"); self.body.add_widget(self.v)
        self.path = TI(hint="مسار ملف TTF/OTF مثل /sdcard/Download/x.ttf"); self.body.add_widget(self.path)
        self.body.add_widget(B("استيراد خط", self.imp, BLUE))
        self.body.add_widget(B("حذف الخطوط المستوردة", self.clear, RED))
    def refresh(self): self.v.text = T("الخطوط: " + "، ".join(sorted(self.app.fonts)) or "لا يوجد")
    def imp(self):
        p = self.path.text.strip()
        try:
            shutil.copy(p, self.app.fdir); self.app.scan_fonts(); self.refresh(); self.app.toast("تم الاستيراد")
        except Exception as e: self.app.toast("فشل: %s" % e)
    def clear(self):
        for f in glob.glob(os.path.join(self.app.fdir, "*")): os.remove(f)
        self.app.scan_fonts(); self.refresh()

class Backup(Page):
    def __init__(self, app):
        super().__init__(app, "backup", "Backup & Restore")
        self.v = L(""); self.body.add_widget(self.v)
        self.body.add_widget(B("نسخ احتياطي الآن", self.backup, BLUE))
        self.path = TI(hint="مسار ملف نسخة للاستعادة"); self.body.add_widget(self.path)
        self.body.add_widget(B("استعادة", self.restore, GREY))
    def backup(self):
        name = "ble-remote-%s.json" % time.strftime("%Y%m%d-%H%M%S")
        p = os.path.join(self.app.bdir, name); self.app.store.export_to(p); msg = p
        try: d = "/sdcard/Download/" + name; shutil.copy(p, d); msg = d
        except Exception: pass
        self.v.text = T("تم: " + msg); self.path.text = msg
    def restore(self):
        try: self.app.store.import_from(self.path.text.strip()); self.v.text = T("تمت الاستعادة")
        except Exception as e: self.v.text = T("فشل: %s" % e)

class Settings(Page):
    def __init__(self, app):
        super().__init__(app, "settings", "Settings")
        self.pin = TI(hint="PIN جديد (اتركه فارغاً للإلغاء)", password=True); self.body.add_widget(self.pin)
        self.body.add_widget(B("حفظ PIN", self.save_pin, BLUE))
        self.body.add_widget(L("إعدادات اللغة والاتجاه: الواجهة عربية RTL حالياً"))
    def save_pin(self):
        p = self.pin.text; s = self.app.store.d["settings"]
        s["pin"] = hashlib.sha256(p.encode()).hexdigest() if p else ""
        self.app.store.save(); self.app.toast("تم")

class Soon(Page):
    def __init__(self, app, key, title, why):
        super().__init__(app, key, title)
        self.body.add_widget(L(why))

# ---------- app ----------
class SenderApp(App):
    def build(self):
        Window.clearcolor = H(DARK)
        self.store = Store(os.path.join(self.user_data_dir, "data.json"))
        self.fdir = os.path.join(self.user_data_dir, "fonts"); os.makedirs(self.fdir, exist_ok=True)
        self.bdir = os.path.join(self.user_data_dir, "backups"); os.makedirs(self.bdir, exist_ok=True)
        self.fonts = {}; self.scan_fonts()
        self.ble = None; self.ra = Reassembler(); self.pending = {}; self.fired = set(); self.msg = ""
        self.sm = ScreenManager(transition=NoTransition())
        self.status = L("غير متصل", 30)
        home = Screen(name="home"); hb = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        hb.add_widget(L("BLE Remote — Sender", 40, bold=True, font_size="22sp")); hb.add_widget(self.status)
        g = GridLayout(cols=2, spacing=dp(6)); hb.add_widget(g); home.add_widget(hb); self.sm.add_widget(home)
        memo_f = [("name", "الاسم", False), ("folder", "المجلد/التصنيف", False), ("body", "النص", True)]
        pages = [
            ("designer", "Screen Designer", Designer(self)), ("text", "Text Studio", TextStudio(self)),
            ("fonts", "Font Library", Fonts(self)),
            ("memos", "Memo Manager", ListPage(self, "memos", "Memo Manager", "memos", memo_f, send=self.send_memo)),
            ("media", "Media Studio", Soon(self, "media", "Media Studio", "الصور والفيديو والصوت: المرحلة القادمة (تحتاج نقل Wi-Fi)")),
            ("remote", "Remote Control", Remote(self)),
            ("touch", "Remote Touch", Soon(self, "touch", "Remote Touch", "يتطلب Accessibility Service على Receiver — مرحلة لاحقة")),
            ("live", "Live Screen", Soon(self, "live", "Live Screen", "يتطلب MediaProjection + Wi-Fi — مرحلة لاحقة")),
            ("voice", "Voice Control", Soon(self, "voice", "Voice Control", "الأوامر الصوتية: مرحلة لاحقة")),
            ("templates", "Templates", ListPage(self, "templates", "Templates", "templates",
                [("name", "الاسم", False), ("body", "التصميم (JSON)", True)], extra=("فتح", self.open_design))),
            ("playlists", "Playlists", ListPage(self, "playlists", "Playlists", "playlists",
                [("name", "الاسم", False), ("items", "أسماء المذكرات (سطر لكل عنصر)", True), ("secs", "ثواني لكل عنصر", False)],
                send=self.send_playlist)),
            ("sched", "Scheduler", ListPage(self, "sched", "Scheduler", "schedules",
                [("name", "الاسم", False), ("memo", "اسم المذكرة", False), ("when", "الموعد YYYY-MM-DD HH:MM", False)])),
            ("devices", "Device Manager", Devices(self)),
            ("projects", "Projects", ListPage(self, "projects", "Projects", "projects",
                [("name", "الاسم", False), ("body", "ملاحظات", True)])),
            ("backup", "Backup & Restore", Backup(self)), ("settings", "Settings", Settings(self)),
            ("pages", "Pages", ListPage(self, "pages", "Pages (تصاميم)", "pages",
                [("name", "الاسم", False), ("body", "التصميم (JSON)", True)], extra=("فتح", self.open_design),
                send=self.send_page)),
        ]
        for key, title, scr in pages:
            self.sm.add_widget(scr)
            g.add_widget(B(title, lambda k=key: self.go(k), BLUE, 56))
        self.designer = self.sm.get_screen("designer")
        return self.sm

    # navigation / helpers
    def go(self, k): self.sm.current = k
    def toast(self, m): self.msg = m; self.status.text = T(m)
    def scan_fonts(self):
        self.fonts = {}
        for d in ("fonts", self.fdir):
            for f in glob.glob(os.path.join(d, "*.[to]tf")):
                self.fonts[os.path.splitext(os.path.basename(f))[0]] = f
    def status_text(self): return STATES.get(str(self.ble.getState()), "") if self.ble else "غير جاهز"
    def chunk(self): return int(self.ble.chunkSize()) if self.ble else 0

    def on_start(self):
        pin = self.store.d["settings"].get("pin")
        if pin: self.ask_pin(pin)
        try:
            from android.permissions import request_permissions
            request_permissions(PERMS, lambda p, g: Clock.schedule_once(self.init_ble, 0))
        except Exception: self.init_ble()
        Clock.schedule_interval(self.check_schedule, 15)

    def ask_pin(self, h):
        box = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(8))
        ti = TI(hint="PIN", password=True); box.add_widget(L("أدخل PIN")); box.add_widget(ti)
        p = Popup(title="PIN", content=box, size_hint=(.9, .4), auto_dismiss=False); 
        def ok():
            if hashlib.sha256(ti.text.encode()).hexdigest() == h: p.dismiss()
            else: ti.text = ""
        box.add_widget(B("دخول", ok, GREEN)); p.open()

    def init_ble(self, *a):
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            self.ble = autoclass("org.bleremote.BleClient")(act)
            Clock.schedule_interval(self.tick, 0.1)
        except Exception as e: self.status.text = "BLE: %s" % e

    def connect(self):
        if self.ble: self.ble.connect()
    def disconnect(self):
        if self.ble: self.ble.close()

    def tick(self, dt):
        if not self.pending: self.status.text = T(self.msg or self.status_text())
        for _ in range(20):
            raw = self.ble.poll()
            if raw is None: break
            m = self.ra.feed(to_bytes(raw))
            if m and m.get("t") == "ack":
                mid = m["d"].get("id"); what = self.pending.pop(mid, None)
                if what:
                    ok = m["d"].get("ok"); self.store.log(("✔ " if ok else "✘ ") + what)
                    self.msg = "تم الاستلام والاعتماد ✔" if ok else "رفض Receiver الأمر"; self.status.text = T(self.msg)

    # sending (always explicit)
    def send(self, type_, data):
        if not self.ble or str(self.ble.getState()) != "ready":
            self.toast("غير متصل بـ Receiver"); return False
        env = encode(type_, data); mid = json.loads(env[8:].decode("utf-8"))["id"]
        self.pending[mid] = type_
        for p in fragment(env, int(self.ble.chunkSize())): self.ble.send(p)
        self.store.log("→ " + type_); self.status.text = T("جاري الإرسال..."); return True

    def style_of(self, memo):
        s = self.sm.get_screen("text").style(); s["text"] = memo.get("body", ""); return s
    def send_memo(self, it):
        confirm("إرسال «%s» واعتماده؟" % it.get("name", ""), lambda: self.send("apply_text", self.style_of(it)))
    def send_page(self, it):
        confirm("إرسال «%s» واعتماده؟" % it.get("name", ""),
                lambda: self.send("apply_design", json.loads(it.get("body") or "{}")))
    def send_playlist(self, it):
        names = [n.strip() for n in it.get("items", "").splitlines() if n.strip()]
        memos = {m["name"]: m for m in self.store.d["memos"]}
        items = [self.style_of(memos[n]) for n in names if n in memos]
        confirm("إرسال قائمة التشغيل كاملة؟", lambda: self.send("apply_playlist",
                {"items": items, "secs": int(it.get("secs") or 10), "loop": True}))
    def open_design(self, it):
        try: d = json.loads(it.get("body") or "{}")
        except Exception: self.toast("تصميم غير صالح"); return
        self.go("designer"); Clock.schedule_once(lambda *_: self.designer.load(d), 0.2)

    def check_schedule(self, dt):
        now = time.strftime("%Y-%m-%d %H:%M")
        for s in self.store.d["schedules"]:
            if s.get("when", "").strip() == now and s["id"] + now not in self.fired:
                self.fired.add(s["id"] + now)
                m = next((x for x in self.store.d["memos"] if x["name"] == s.get("memo")), None)
                if m: self.send("apply_text", self.style_of(m)); self.store.log("جدولة: " + s["name"])

SenderApp().run()
