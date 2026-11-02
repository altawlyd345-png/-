import os
import json
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

from store import Store
from protocol import encode, fragment

BLUE = "#1565C0"
DARK = "#101827"
GREY = "#37474F"
GREEN = "#00897B"
RED = "#B71C1C"
WHITE = "#FFFFFF"

SECTIONS = [
("text", "استوديو النصوص"),
("designer", "مصمم الشاشة"),
("memos", "المذكرات"),
("pages", "الصفحات"),
("templates", "القوالب"),
("playlists", "قوائم التشغيل"),
("schedules", "الجداول الزمنية"),
("projects", "المشاريع"),
("remote", "التحكم عن بعد"),
("devices", "إدارة الأجهزة"),
("fonts", "مكتبة الخطوط"),
("backup", "النسخ الاحتياطي"),
("logs", "سجل العمليات"),
("settings", "الإعدادات"),
("about", "حول التطبيق"),
]

def arabic(text):
return str(text)

def label(text, size=18, height=None):
w = Label(
text=arabic(text),
font_size=dp(size),
color=get_color_from_hex(WHITE),
halign="center",
valign="middle"
)
w.bind(size=lambda obj, value: setattr(obj, "text_size", value))

if height:
    w.size_hint_y = None
    w.height = dp(height)

return w

def button(text, callback, color=BLUE, height=48):
b = Button(
text=arabic(text),
size_hint_y=None,
height=dp(height),
background_normal="",
background_color=get_color_from_hex(color),
color=get_color_from_hex(WHITE),
font_size=dp(16)
)
b.bind(on_release=lambda *_: callback())
return b

def make_popup(title, content):
p = Popup(
title=arabic(title),
content=content,
size_hint=(0.92, 0.85)
)
p.open()
return p

class BasePage(Screen):

def __init__(self, app, name, title):
    super().__init__(name=name)
    self.app = app

    root = BoxLayout(
        orientation="vertical",
        padding=dp(8),
        spacing=dp(6)
    )

    header = BoxLayout(
        size_hint_y=None,
        height=dp(50)
    )

    header.add_widget(
        button("رجوع", lambda: app.go("home"), GREY)
    )

    header.add_widget(label(title, 19))

    root.add_widget(header)

    self.content = BoxLayout(
        orientation="vertical",
        spacing=dp(7)
    )

    root.add_widget(self.content)
    self.add_widget(root)

def refresh(self):
    pass

class HomePage(Screen):

def __init__(self, app):
    super().__init__(name="home")
    self.app = app

    root = BoxLayout(
        orientation="vertical",
        padding=dp(10),
        spacing=dp(8)
    )

    root.add_widget(label("BLE REMOTE", 25, 55))
    root.add_widget(label("نظام التحكم والعرض اللاسلكي", 16, 35))

    self.status = label("حالة الاتصال: غير متصل", 16, 40)
    root.add_widget(self.status)

    scroll = ScrollView()

    grid = GridLayout(
        cols=2,
        spacing=dp(8),
        padding=dp(5),
        size_hint_y=None
    )

    grid.bind(minimum_height=grid.setter("height"))

    grid.add_widget(
        button("الرئيسية", lambda: app.go("home"), GREY, 65)
    )

    for key, title in SECTIONS:
        grid.add_widget(
            button(title, lambda k=key: app.go(k), BLUE, 65)
        )

    scroll.add_widget(grid)
    root.add_widget(scroll)

    root.add_widget(
        button("خروج", app.stop, RED)
    )

    self.add_widget(root)

def refresh_status(self):
    self.status.text = (
        "حالة الاتصال: " + self.app.connection_status
    )

class TextStudio(BasePage):

def __init__(self, app):
    super().__init__(app, "text", "استوديو النصوص")

    self.text = TextInput(
        hint_text="اكتب النص المراد عرضه",
        multiline=True,
        size_hint_y=None,
        height=dp(130)
    )

    self.size = TextInput(
        text="48",
        hint_text="حجم الخط",
        input_filter="int",
        size_hint_y=None,
        height=dp(45)
    )

    self.preview = label("معاينة النص", 24, 130)

    self.content.add_widget(self.text)
    self.content.add_widget(self.size)

    self.content.add_widget(
        button("معاينة محلية", self.show_preview, GREY)
    )

    self.content.add_widget(self.preview)

    self.content.add_widget(
        button("حفظ كمذكرة", self.save)
    )

    self.content.add_widget(
        button("إرسال واعتماد وعرض", self.send, GREEN)
    )

def show_preview(self):
    self.preview.text = self.text.text
    self.app.toast("معاينة محلية فقط")

def save(self):
    self.app.store.put(
        "memos",
        {
            "name": self.text.text[:25] or "مذكرة جديدة",
            "body": self.text.text,
            "size": self.size.text
        }
    )

    self.app.toast("تم الحفظ محلياً")

def send(self):
    self.app.confirm_send(
        "apply_text",
        {
            "text": self.text.text,
            "size": int(self.size.text or 48),
            "color": "#FFFFFF",
            "bg": "#1565C0"
        }
    )

class Designer(BasePage):

def __init__(self, app):
    super().__init__(app, "designer", "مصمم الشاشة")

    self.elements = []
    self.bg = "#1565C0"

    self.name = TextInput(
        hint_text="اسم التصميم",
        size_hint_y=None,
        height=dp(45)
    )

    self.text = TextInput(
        hint_text="نص العنصر",
        size_hint_y=None,
        height=dp(100)
    )

    self.content.add_widget(self.name)
    self.content.add_widget(self.text)

    self.preview = label("معاينة التصميم", 24, 150)
    self.content.add_widget(self.preview)

    self.content.add_widget(
        button("إضافة نص", self.add_text)
    )

    self.content.add_widget(
        button("مسح العناصر", self.clear, RED)
    )

    self.content.add_widget(
        button("حفظ كصفحة", self.save)
    )

    self.content.add_widget(
        button("إرسال واعتماد", self.send, GREEN)
    )

def add_text(self):
    self.elements.append({
        "text": self.text.text,
        "size": 32,
        "fg": "#FFFFFF",
        "x": 0.2,
        "y": 0.4,
        "w": 0.6,
        "h": 0.15
    })

    self.update_preview()

def clear(self):
    self.elements = []
    self.update_preview()

def update_preview(self):
    self.preview.text = "\n".join(
        item["text"] for item in self.elements
    )

def design(self):
    return {
        "bg": self.bg,
        "els": self.elements
    }

def save(self):
    self.app.store.put(
        "pages",
        {
            "name": self.name.text or "تصميم جديد",
            "body": json.dumps(
                self.design(),
                ensure_ascii=False
            )
        }
    )

    self.app.toast("تم حفظ التصميم محلياً")

def send(self):
    self.app.confirm_send(
        "apply_design",
        self.design()
    )

class ListPage(BasePage):

def __init__(self, app, key, title):
    super().__init__(app, key, title)
    self.collection = key

    self.search = TextInput(
        hint_text="بحث",
        size_hint_y=None,
        height=dp(45)
    )

    self.search.bind(text=lambda *_: self.refresh())

    self.scroll = ScrollView()

    self.items_box = GridLayout(
        cols=1,
        spacing=dp(5),
        size_hint_y=None
    )

    self.items_box.bind(
        minimum_height=self.items_box.setter("height")
    )

    self.scroll.add_widget(self.items_box)

    self.content.add_widget(self.search)
    self.content.add_widget(self.scroll)

    self.content.add_widget(
        button("+ إضافة جديد", self.add)
    )

def refresh(self):
    self.items_box.clear_widgets()

    for item in self.app.store.items(
        self.collection,
        self.search.text
    ):

        row = BoxLayout(
            size_hint_y=None,
            height=dp(55),
            spacing=dp(4)
        )

        row.add_widget(
            label(item.get("name", "بدون اسم"), 15)
        )

        row.add_widget(
            button(
                "عرض",
                lambda i=item: self.view(i),
                GREY,
                45
            )
        )

        row.add_widget(
            button(
                "حذف",
                lambda i=item: self.delete(i),
                RED,
                45
            )
        )

        self.items_box.add_widget(row)

def add(self):
    box = BoxLayout(
        orientation="vertical",
        spacing=dp(8),
        padding=dp(8)
    )

    name = TextInput(
        hint_text="الاسم",
        size_hint_y=None,
        height=dp(45)
    )

    body = TextInput(
        hint_text="المحتوى",
        multiline=True
    )

    box.add_widget(name)
    box.add_widget(body)

    p = make_popup("إضافة جديد", box)

    box.add_widget(
        button(
            "حفظ محلياً",
            lambda: self.save_item(p, name.text, body.text),
            GREEN
        )
    )

def save_item(self, popup, name, body):
    self.app.store.put(
        self.collection,
        {
            "name": name or "بدون اسم",
            "body": body
        }
    )

    popup.dismiss()
    self.refresh()
    self.app.toast("تم الحفظ محلياً")

def view(self, item):
    box = BoxLayout(
        orientation="vertical",
        padding=dp(8)
    )

    box.add_widget(
        label(item.get("body", ""), 18)
    )

    make_popup(item.get("name", "عرض"), box)

def delete(self, item):
    self.app.confirm_action(
        "هل تريد حذف هذا العنصر؟",
        lambda: self.remove_item(item)
    )

def remove_item(self, item):
    self.app.store.delete(
        self.collection,
        item["id"]
    )
    self.refresh()

class RemotePage(BasePage):

def __init__(self, app):
    super().__init__(app, "remote", "التحكم عن بعد")

    commands = [
        ("إخفاء المحتوى", "hide"),
        ("استعادة العرض", "restore"),
        ("مسح الشاشة", "clear"),
        ("اختبار الاتصال", "ping"),
        ("إعادة تحميل العرض", "reload"),
        ("التالي", "next"),
        ("السابق", "prev"),
        ("إيقاف الطوارئ", "emergency_off")
    ]

    for title, command in commands:
        self.content.add_widget(
            button(
                title,
                lambda c=command, t=title:
                app.confirm_send(c, {}, t)
            )
        )

    self.emergency = TextInput(
        hint_text="رسالة الطوارئ",
        size_hint_y=None,
        height=dp(70)
    )

    self.content.add_widget(self.emergency)

    self.content.add_widget(
        button(
            "إرسال رسالة طوارئ",
            lambda: app.confirm_send(
                "emergency",
                {
                    "text": self.emergency.text,
                    "color": "#FFFFFF",
                    "bg": "#B71C1C",
                    "size": 64,
                    "seconds": 0
                }
            ),
            RED
        )
    )

class DevicesPage(BasePage):

def __init__(self, app):
    super().__init__(app, "devices", "إدارة الأجهزة")

    self.info = label(
        "لم يتم الاتصال بأي جهاز",
        18,
        70
    )

    self.content.add_widget(self.info)

    self.content.add_widget(
        button(
            "البحث عن أجهزة BLE",
            app.connect
        )
    )

    self.content.add_widget(
        button(
            "قطع الاتصال",
            app.disconnect,
            RED
        )
    )

def refresh(self):
    self.info.text = self.app.connection_status

class LogsPage(BasePage):

def __init__(self, app):
    super().__init__(app, "logs", "سجل العمليات")

    self.log_text = label("", 14)

    scroll = ScrollView()
    scroll.add_widget(self.log_text)

    self.content.add_widget(scroll)

def refresh(self):
    entries = self.app.store.d.get("log", [])

    self.log_text.text = "\n".join(
        entry["t"] + " : " + entry["m"]
        for entry in reversed(entries[-200:])
    )

class BackupPage(BasePage):

def __init__(self, app):
    super().__init__(app, "backup", "النسخ الاحتياطي")

    self.path = TextInput(
        hint_text="مسار ملف النسخة",
        size_hint_y=None,
        height=dp(50)
    )

    self.content.add_widget(
        button("إنشاء نسخة احتياطية", self.backup)
    )

    self.content.add_widget(self.path)

    self.content.add_widget(
        button("استعادة نسخة", self.restore, GREY)
    )

def backup(self):
    name = "BLE_Backup_" + time.strftime("%Y%m%d_%H%M%S") + ".json"

    path = os.path.join(
        self.app.user_data_dir,
        name
    )

    self.app.store.export_to(path)

    self.path.text = path
    self.app.toast("تم إنشاء النسخة الاحتياطية")

def restore(self):
    try:
        self.app.store.import_from(self.path.text.strip())
        self.app.toast("تمت الاستعادة")
    except Exception as e:
        self.app.toast("فشلت الاستعادة: " + str(e))

class SettingsPage(BasePage):

def __init__(self, app):
    super().__init__(app, "settings", "الإعدادات")

    self.pin = TextInput(
        hint_text="رمز سري جديد",
        password=True,
        size_hint_y=None,
        height=dp(50)
    )

    self.content.add_widget(self.pin)

    self.content.add_widget(
        button("حفظ الرمز السري", self.save_pin)
    )

    self.content.add_widget(
        label("إعدادات BLE Remote", 18)
    )

def save_pin(self):
    import hashlib

    value = self.pin.text

    self.app.store.d["settings"]["pin"] = (
        hashlib.sha256(value.encode()).hexdigest()
        if value else ""
    )

    self.app.store.save()
    self.app.toast("تم حفظ الإعدادات")

class SimplePage(BasePage):

def __init__(self, app, key, title):
    super().__init__(app, key, title)

    self.content.add_widget(
        label("هذا القسم جاهز للربط بوظائفه التفصيلية.", 17)
    )

class SenderApp(App):

def build(self):

    Window.clearcolor = get_color_from_hex(DARK)

    self.store = Store(
        os.path.join(
            self.user_data_dir,
            "data.json"
        )
    )

    self.connection_status = "غير متصل"
    self.connected = False

    self.sm = ScreenManager()

    self.sm.add_widget(HomePage(self))

    self.sm.add_widget(TextStudio(self))
    self.sm.add_widget(Designer(self))

    for key, title in SECTIONS:

        if key in ("text", "designer"):
            continue

        if key in (
            "memos",
            "pages",
            "templates",
            "playlists",
            "schedules",
            "projects"
        ):
            page = ListPage(self, key, title)

        elif key == "remote":
            page = RemotePage(self)

        elif key == "devices":
            page = DevicesPage(self)

        elif key == "logs":
            page = LogsPage(self)

        elif key == "backup":
            page = BackupPage(self)

        elif key == "settings":
            page = SettingsPage(self)

        else:
            page = SimplePage(self, key, title)

        self.sm.add_widget(page)

    return self.sm

def go(self, name):
    self.sm.current = name

    page = self.sm.get_screen(name)

    if hasattr(page, "refresh"):
        page.refresh()

def toast(self, message):
    content = BoxLayout(
        orientation="vertical",
        padding=dp(10)
    )

    content.add_widget(label(message, 17))

    p = make_popup("رسالة", content)

    Clock.schedule_once(
        lambda *_: p.dismiss(),
        1.8
    )

def confirm_action(self, message, callback):
    box = BoxLayout(
        orientation="vertical",
        padding=dp(10),
        spacing=dp(10)
    )

    box.add_widget(label(message, 18))

    p = make_popup("تأكيد", box)

    row = BoxLayout(
        size_hint_y=None,
        height=dp(48),
        spacing=dp(5)
    )

    row.add_widget(
        button("إلغاء", p.dismiss, GREY)
    )

    row.add_widget(
        button(
            "تأكيد",
            lambda: (p.dismiss(), callback()),
            GREEN
        )
    )

    box.add_widget(row)

def confirm_send(self, command, payload, title="إرسال واعتماد"):
    if not self.connected:
        self.toast("يجب الاتصال بجهاز المستقبل أولاً")
        return

    self.confirm_action(
        "سيتم تغيير العرض على جهاز المستقبل. هل تريد المتابعة؟",
        lambda: self.send(command, payload)
    )

def send(self, command, payload):
    if not self.connected:
        self.toast("لا يوجد اتصال")
        return

    try:
        data = encode(command, payload)
        packets = fragment(data)

        # ستُرسل الحزم هنا بعد إضافة محرك BLE.

        self.store.log(
            "تم تجهيز أمر الإرسال: " + command
        )

        self.toast(
            "تم تجهيز البيانات. محرك BLE غير مفعّل بعد."
        )

    except Exception as e:
        self.toast("خطأ: " + str(e))

def connect(self):
    self.toast(
        "محرك Bluetooth LE سيُفعّل في مرحلة الربط"
    )

def disconnect(self):
    self.connected = False
    self.connection_status = "غير متصل"
    self.go("devices")
    self.toast("تم قطع الاتصال")

def on_stop(self):
    self.store.save()

if name == "main":
SenderApp().run()
