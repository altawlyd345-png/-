from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle


class ReceiverDisplay(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical",
            padding=15,
            spacing=12,
            **kwargs
        )

        with self.canvas.before:
            Color(0.06, 0.08, 0.13, 1)
            self.bg = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[15]
            )

        self.bind(
            pos=self.update_bg,
            size=self.update_bg
        )

        self.title = Label(
            text="BLE Remote",
            font_size="25sp",
            bold=True,
            size_hint_y=None,
            height=65
        )

        self.status = Label(
            text="بانتظار الاتصال...",
            font_size="17sp",
            size_hint_y=None,
            height=45
        )

        self.content = Label(
            text="لم يتم استلام أي محتوى بعد",
            font_size="22sp",
            halign="right",
            valign="top",
            size_hint_y=None
        )

        self.content.bind(
            texture_size=self.update_content_size
        )

        scroll = ScrollView()
        scroll.add_widget(self.content)

        self.add_widget(self.title)
        self.add_widget(self.status)
        self.add_widget(scroll)

    def update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def update_content_size(self, instance, size):
        instance.height = size[1]

    def set_status(self, text):
        self.status.text = text

    def show_message(self, text):
        self.content.text = str(text)
