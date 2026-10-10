import colorsys
import datetime
import json
import os
import shutil
import traceback

from kivy.animation import Animation
from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Rectangle, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import escape_markup

Window.softinput_mode = "below_target"  # keyboard does not hide the fields

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

# Folder where records are kept. It is replaced with the app's private
# storage folder when the app starts (this survives closing / force closing).
DATA_DIR = BASE_DIR

# ----------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------
RATE = 10  # Rs per electricity unit

FLOORS = {
    "Ground": ["1", "2", "3", "4"],
    "1st": ["101", "102", "103", "104"],
    "2nd": ["201", "202", "203", "204"],
}
ALL_ROOMS = [r for rooms in FLOORS.values() for r in rooms]

# Intro slides: list of (text, font size). Each slide stays 4 seconds.
SLIDES = [
    [("Welcome sir", 44)],
    [("Pushpanjali Hostel Bhopal", 36)],
    [("Hostel maintained by:", 22), ("Prakash Mishra", 36)],
    [
        ("Developer name:", 22),
        ("Vansh Bhargava", 36),
        ("Contact no.", 22),
        ("9201741227", 32),
    ],
]

# key, label, kind, max characters
# kinds: text, num, int, multi, calc (read only, auto)
FIELDS = [
    ("patient", "Patient name", "text", 0),
    ("patient_aadhar", "Patient Aadhaar no.", "int", 12),
    ("attender", "Attender name", "text", 0),
    ("attender_aadhar", "Attender Aadhaar no.", "int", 12),
    ("contact", "Contact no.", "int", 10),
    ("address", "Address", "multi", 0),
    ("checkin_date", "Check in date (DD-MM-YYYY)", "text", 0),
    ("checkout_date", "Check out date (DD-MM-YYYY)", "text", 0),
    ("checkin_reading", "Check in reading (electricity)", "num", 0),
    ("checkout_reading", "Check out reading (electricity)", "num", 0),
    ("elec_cost", "Electricity reading cost", "calc", 0),
    ("elec_due", "Electricity payment due", "num", 0),
    ("rent", "Rent", "num", 0),
    ("advance", "Advance deposit", "num", 0),
    ("balance", "Balance", "num", 0),
    ("final", "Final payment", "num", 0),
    ("remark", "Remark", "multi", 0),
]

# Colours
ACCENT = (0.18, 0.50, 0.98, 1)
PURPLE = (0.52, 0.33, 0.95, 1)
GREEN = (0.12, 0.65, 0.40, 1)
RED = (0.85, 0.25, 0.35, 1)
INACTIVE = (1, 1, 1, 0.12)
CARD_BG = (1, 1, 1, 0.07)


# ----------------------------------------------------------------------
# Data helpers
# ----------------------------------------------------------------------
def data_file():
    return os.path.join(DATA_DIR, "hostel_data.json")


def log_error(text):
    try:
        with open(os.path.join(DATA_DIR, "error_log.txt"), "a", encoding="utf-8") as f:
            f.write(
                "---- %s ----\n%s\n"
                % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text)
            )
    except Exception:
        pass


def load_data():
    data = {"current": {}, "history": {}}
    path = data_file()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                if "current" in loaded or "history" in loaded:
                    cur = loaded.get("current", {})
                    his = loaded.get("history", {})
                    data["current"] = cur if isinstance(cur, dict) else {}
                    data["history"] = his if isinstance(his, dict) else {}
                else:
                    # very old format: {room: record}
                    data["current"] = loaded
        except Exception:
            log_error(traceback.format_exc())
    return data


def save_data(data):
    """Save to disk. Never raises. Returns True if saved."""
    path = data_file()
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        try:
            os.replace(tmp, path)
        except OSError:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        log_error(traceback.format_exc())
        return False


def to_num(text):
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def fmt(n):
    return str(int(n)) if n == int(n) else str(round(n, 2))


def today():
    return datetime.date.today().strftime("%d-%m-%Y")


def pretty_ts(iso):
    try:
        return datetime.datetime.strptime(iso, "%Y-%m-%d %H:%M:%S").strftime(
            "%d-%m-%Y %H:%M"
        )
    except Exception:
        return "-"


def floor_of(room):
    for floor, rooms in FLOORS.items():
        if room in rooms:
            return floor
    return ""


def rainbow(text, phase=0.0, step=0.07):
    out = []
    n = 0
    for ch in text:
        if ch == " ":
            out.append(" ")
            continue
        r, g, b = colorsys.hsv_to_rgb((phase + n * step) % 1.0, 0.65, 1.0)
        out.append(
            "[color=%02x%02x%02x]%s[/color]"
            % (int(r * 255), int(g * 255), int(b * 255), escape_markup(ch))
        )
        n += 1
    return "".join(out)


# ----------------------------------------------------------------------
# UI building blocks
# ----------------------------------------------------------------------
def round_bg(widget, rgba, radius=14):
    with widget.canvas.before:
        widget._bgc = Color(*rgba)
        widget._bgr = RoundedRectangle(
            pos=widget.pos, size=widget.size, radius=[dp(radius)]
        )

    def upd(*a):
        widget._bgr.pos = widget.pos
        widget._bgr.size = widget.size

    widget.bind(pos=upd, size=upd)


class RButton(Button):
    """Rounded, flat, modern button."""

    def __init__(self, bg=ACCENT, radius=14, **kw):
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("background_color", (0, 0, 0, 0))
        kw.setdefault("bold", True)
        super().__init__(**kw)
        self.bg = list(bg)
        round_bg(self, bg, radius)
        self.bind(state=self._on_state)

    def set_bg(self, rgba):
        self.bg = list(rgba)
        self._bgc.rgba = rgba

    def _on_state(self, inst, st):
        r, g, b, a = self.bg
        if st == "down":
            self._bgc.rgba = (r * 0.7, g * 0.7, b * 0.7, a)
        else:
            self._bgc.rgba = (r, g, b, a)


def style_input(ti, readonly=False):
    ti.background_normal = ""
    ti.background_active = ""
    ti.background_disabled_normal = ""
    base = (0.0, 0.8, 0.9, 0.14) if readonly else (1, 1, 1, 0.12)
    focus = (0.0, 0.8, 0.9, 0.14) if readonly else (1, 1, 1, 0.22)
    ti.background_color = base
    ti.foreground_color = (1, 1, 1, 1)
    ti.disabled_foreground_color = (1, 1, 1, 0.6)
    ti.cursor_color = (0.3, 0.9, 1, 1)
    ti.selection_color = (0.2, 0.6, 1, 0.4)
    ti.padding = [dp(12), dp(11), dp(12), dp(8)]
    ti.bind(
        focus=lambda inst, f: setattr(inst, "background_color", focus if f else base)
    )


def limit_chars(ti, mx):
    def _lim(inst, value):
        if len(value) > mx:
            inst.text = value[:mx]

    ti.bind(text=_lim)


def make_gradient():
    # rows are bottom -> top
    stops = [
        (0.02, 0.16, 0.26, 1),
        (0.09, 0.07, 0.26, 1),
        (0.04, 0.05, 0.15, 1),
    ]
    tex = Texture.create(size=(1, 3), colorfmt="rgba")
    buf = bytes(int(c * 255) for s in stops for c in s)
    tex.blit_buffer(buf, colorfmt="rgba", bufferfmt="ubyte")
    tex.mag_filter = "linear"
    tex.min_filter = "linear"
    return tex


def toast(msg):
    lb = Label(text=msg, font_size=dp(17), halign="center", valign="middle")
    lb.bind(size=lambda i, s: setattr(i, "text_size", s))
    pop = Popup(
        title="",
        separator_height=0,
        content=lb,
        size_hint=(0.8, 0.18),
        auto_dismiss=True,
    )
    pop.open()
    Clock.schedule_once(lambda dt: pop.dismiss(), 1.6)


def confirm(message, on_yes, yes_text="Yes"):
    box = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(12))
    lb = Label(text=message, halign="center", valign="middle")
    lb.bind(size=lambda i, s: setattr(i, "text_size", s))
    box.add_widget(lb)
    row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
    yes = RButton(text=yes_text, bg=GREEN)
    no = RButton(text="Cancel", bg=(1, 1, 1, 0.18))
    row.add_widget(yes)
    row.add_widget(no)
    box.add_widget(row)
    pop = Popup(
        title="Confirm",
        content=box,
        size_hint=(0.88, 0.36),
        auto_dismiss=False,
    )

    def _yes(*a):
        pop.dismiss()
        # run the action a moment later, after the popup has closed
        Clock.schedule_once(lambda dt: on_yes(), 0.15)

    yes.bind(on_release=_yes)
    no.bind(on_release=pop.dismiss)
    pop.open()


_error_open = [False]


def show_error(text):
    """Show an error on screen instead of letting the app crash."""
    if _error_open[0]:
        return
    try:
        _error_open[0] = True
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        lb = Label(
            text="Something went wrong, but the app is still running.\n\n" + text[:350],
            halign="center",
            valign="middle",
            font_size=dp(14),
        )
        lb.bind(size=lambda i, s: setattr(i, "text_size", s))
        ok = RButton(text="OK", bg=ACCENT, size_hint_y=None, height=dp(46))
        box.add_widget(lb)
        box.add_widget(ok)
        pop = Popup(title="Error", content=box, size_hint=(0.92, 0.5))

        def _close(*a):
            _error_open[0] = False
            pop.dismiss()

        ok.bind(on_release=_close)
        pop.bind(on_dismiss=lambda *a: _error_open.__setitem__(0, False))
        pop.open()
    except Exception:
        _error_open[0] = False


class SafeHandler(ExceptionHandler):
    """Keeps the app alive if some button handler fails."""

    def handle_exception(self, inst):
        if isinstance(inst, (KeyboardInterrupt, SystemExit)):
            return ExceptionManager.RAISE
        try:
            tb = "".join(
                traceback.format_exception(type(inst), inst, inst.__traceback__)
            )
            log_error(tb)
            msg = "%s: %s" % (type(inst).__name__, inst)
            Clock.schedule_once(lambda dt: show_error(msg), 0)
        except Exception:
            pass
        return ExceptionManager.PASS


ExceptionManager.add_handler(SafeHandler())


# ----------------------------------------------------------------------
# Screens
# ----------------------------------------------------------------------
class BgScreen(Screen):
    """Screen with a gradient background and soft glowing circles."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._tex = make_gradient()
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = Rectangle(texture=self._tex, pos=self.pos, size=self.size)
            Color(0.55, 0.35, 1, 0.13)
            self._c1 = Ellipse()
            Color(0.0, 0.8, 0.9, 0.10)
            self._c2 = Ellipse()
            Color(1, 0.3, 0.6, 0.08)
            self._c3 = Ellipse()
        self.bind(pos=self._upd_bg, size=self._upd_bg)

    def _upd_bg(self, *a):
        x, y = self.pos
        w, h = self.size
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._c1.size = (w * 0.9, w * 0.9)
        self._c1.pos = (x - w * 0.3, y + h * 0.62)
        self._c2.size = (w * 1.1, w * 1.1)
        self._c2.pos = (x + w * 0.2, y - w * 0.5)
        self._c3.size = (w * 0.6, w * 0.6)
        self._c3.pos = (x + w * 0.55, y + h * 0.42)


class IntroScreen(BgScreen):
    def __init__(self, on_done, **kw):
        super().__init__(**kw)
        self.on_done = on_done
        self.phase = 0.0
        self.lines = []
        self.running = False
        self.tick = None
        self.box = BoxLayout(
            orientation="vertical",
            size_hint=(0.94, 0.7),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            spacing=dp(10),
            opacity=0,
        )
        self.add_widget(self.box)

    def start(self, *a):
        if self.running:
            return
        self.running = True
        self.tick = Clock.schedule_interval(self.recolor, 0.12)
        self.show_slide(0)

    def show_slide(self, i):
        if not self.running:
            return
        if i >= len(SLIDES):
            self.finish()
            return
        self.box.clear_widgets()
        self.lines = []
        for text, size in SLIDES[i]:
            lb = Label(
                markup=True,
                bold=True,
                halign="center",
                valign="middle",
                font_size=dp(size * 0.8),
            )
            lb.bind(size=lambda inst, s: setattr(inst, "text_size", s))
            self.box.add_widget(lb)
            self.lines.append((lb, text))
            Animation(font_size=dp(size), d=0.7, t="out_back").start(lb)
        self.recolor()

        # 0.6s fade in + 2.8s hold + 0.6s fade out = 4 seconds
        Animation.cancel_all(self.box)
        self.box.opacity = 0
        anim = (
            Animation(opacity=1, d=0.6)
            + Animation(opacity=1, d=2.8)
            + Animation(opacity=0, d=0.6)
        )
        anim.bind(on_complete=lambda *a: self.show_slide(i + 1))
        anim.start(self.box)

    def recolor(self, dt=0):
        self.phase = (self.phase + 0.03) % 1.0
        for lb, text in self.lines:
            lb.text = rainbow(text, self.phase)

    def finish(self):
        if not self.running:
            return
        self.running = False
        if self.tick:
            self.tick.cancel()
            self.tick = None
        self.on_done()

    def on_touch_down(self, touch):
        # tap anywhere to skip the intro
        if self.running:
            Animation.cancel_all(self.box)
            self.finish()
        return True


class MainScreen(BgScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.data = load_data()
        self.current_room = None
        self.hist_room = "ALL"
        self.inputs = {}
        self.field_labels = {}
        self._loading = False
        self._save_trigger = Clock.create_trigger(self._autosave, 1.5)

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        self.add_widget(root)

        # ---- Header ----
        header = Label(
            markup=True,
            size_hint_y=None,
            height=dp(76),
            halign="center",
            valign="middle",
            text="[size=%d][b]%s[/b][/size]\n[size=%d][color=8fe9ff]BHOPAL  |  PATIENT RECORDS[/color][/size]"
            % (int(dp(28)), rainbow("Pushpanjali Hostel"), int(dp(12))),
        )
        header.bind(size=lambda i, s: setattr(i, "text_size", s))
        root.add_widget(header)

        # ---- Mode toggle ----
        toggle = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        self.btn_rooms = RButton(text="ROOMS", bg=ACCENT, radius=23)
        self.btn_hist = RButton(text="ROOM HISTORY", bg=INACTIVE, radius=23)
        self.btn_rooms.bind(on_release=lambda *a: self.set_mode("rooms"))
        self.btn_hist.bind(on_release=lambda *a: self.set_mode("history"))
        toggle.add_widget(self.btn_rooms)
        toggle.add_widget(self.btn_hist)
        root.add_widget(toggle)

        # ---- Content container ----
        self.container = BoxLayout(orientation="vertical", spacing=dp(6))
        root.add_widget(self.container)

        self.rooms_view = self.build_rooms_view()
        self.history_view = self.build_history_view()

        self.set_mode("rooms")
        self.select_room(ALL_ROOMS[0])

    # ------------------------------------------------------------------
    # Common widgets
    # ------------------------------------------------------------------
    def make_room_bar(self, callback, include_all=False):
        scroll = ScrollView(
            size_hint_y=None,
            height=dp(66),
            do_scroll_x=True,
            do_scroll_y=False,
            bar_width=dp(3),
            bar_color=(0.3, 0.8, 1, 0.8),
        )
        row = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            spacing=dp(8),
            padding=[dp(2), dp(6), dp(2), dp(6)],
        )
        row.bind(minimum_width=row.setter("width"))
        btns = {}

        def add_btn(key, text, width):
            b = RButton(
                text=text,
                size_hint_x=None,
                width=dp(width),
                bg=INACTIVE,
                font_size=dp(18),
            )
            b.bind(on_release=lambda inst, k=key: callback(k))
            btns[key] = b
            row.add_widget(b)

        if include_all:
            add_btn("ALL", "ALL", 70)
        for floor, rooms in FLOORS.items():
            fl = Label(
                text=floor.upper() + "\nFLOOR",
                size_hint_x=None,
                width=dp(60),
                halign="center",
                valign="middle",
                font_size=dp(11),
                bold=True,
                color=(1, 0.8, 0.3, 1),
            )
            fl.bind(size=lambda i, s: setattr(i, "text_size", s))
            row.add_widget(fl)
            for r in rooms:
                add_btn(r, r, 74)
        scroll.add_widget(row)
        return scroll, btns

    # ------------------------------------------------------------------
    # Rooms view
    # ------------------------------------------------------------------
    def build_rooms_view(self):
        view = BoxLayout(orientation="vertical", spacing=dp(6))

        bar, self.room_btns = self.make_room_bar(self.select_room)
        view.add_widget(bar)

        self.room_label = Label(
            markup=True,
            size_hint_y=None,
            height=dp(32),
            font_size=dp(19),
            color=(0.55, 0.9, 1, 1),
        )
        view.add_widget(self.room_label)

        form_scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        form = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=dp(12),
        )
        form.bind(minimum_height=form.setter("height"))
        round_bg(form, CARD_BG, 18)

        for key, label, kind, mx in FIELDS:
            multi = kind == "multi"
            row = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp(106) if multi else dp(72),
                spacing=dp(2),
            )
            lbl = Label(
                text=label,
                size_hint_y=None,
                height=dp(22),
                halign="left",
                valign="middle",
                font_size=dp(13),
                color=(0.72, 0.82, 1, 1),
            )
            lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
            ti = TextInput(multiline=multi, font_size=dp(17), write_tab=False)
            if kind == "num":
                ti.input_filter = "float"
            elif kind == "int":
                ti.input_filter = "int"
            if mx:
                limit_chars(ti, mx)
            ti.readonly = kind == "calc"
            style_input(ti, readonly=(kind == "calc"))
            if not multi:
                ti.size_hint_y = None
                ti.height = dp(46)
            ti.bind(text=self._on_change)
            self.inputs[key] = ti
            self.field_labels[key] = lbl
            row.add_widget(lbl)
            row.add_widget(ti)
            form.add_widget(row)

        # auto calculations
        self.inputs["checkin_reading"].bind(text=self.recalc_elec)
        self.inputs["checkout_reading"].bind(text=self.recalc_elec)
        self.inputs["rent"].bind(text=self.recalc_balance)
        self.inputs["advance"].bind(text=self.recalc_balance)

        # buttons
        btns = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(8))
        save_btn = RButton(text="SAVE", bg=GREEN)
        arch_btn = RButton(text="ARCHIVE & NEW", bg=PURPLE)
        clear_btn = RButton(text="CLEAR", bg=RED)
        save_btn.bind(on_release=self.save_room)
        arch_btn.bind(on_release=self.archive_room)
        clear_btn.bind(on_release=self.confirm_clear)
        btns.add_widget(save_btn)
        btns.add_widget(arch_btn)
        btns.add_widget(clear_btn)
        form.add_widget(btns)

        form_scroll.add_widget(form)
        view.add_widget(form_scroll)
        return view

    # ---- auto save (so nothing is lost even if the app is force closed) ----
    def _on_change(self, *a):
        if not self._loading:
            self._save_trigger()

    def _autosave(self, dt):
        self.store_current()

    # ---- calculations ----
    def recalc_balance(self, *a):
        if self._loading:
            return
        rent = to_num(self.inputs["rent"].text)
        adv = to_num(self.inputs["advance"].text)
        if rent is not None:
            self.inputs["balance"].text = fmt(rent - (adv or 0))

    def recalc_elec(self, *a):
        if self._loading:
            return
        cin = to_num(self.inputs["checkin_reading"].text)
        cout = to_num(self.inputs["checkout_reading"].text)
        if cin is None or cout is None or cout < cin:
            self.inputs["elec_cost"].text = ""
            self.refresh_units_label()
            return
        cost = (cout - cin) * RATE
        self.inputs["elec_cost"].text = fmt(cost)
        self.inputs["elec_due"].text = fmt(cost)
        self.refresh_units_label()

    def refresh_units_label(self):
        cin = to_num(self.inputs["checkin_reading"].text)
        cout = to_num(self.inputs["checkout_reading"].text)
        lab = self.field_labels["elec_cost"]
        if cin is not None and cout is not None:
            if cout >= cin:
                lab.text = "Electricity reading cost (%s units x Rs %d)" % (
                    fmt(cout - cin),
                    RATE,
                )
            else:
                lab.text = "Electricity reading cost (check the readings)"
        else:
            lab.text = "Electricity reading cost (Rs %d per unit)" % RATE

    # ---- room data ----
    def collect(self):
        return {key: ti.text for key, ti in self.inputs.items()}

    def load_room(self, room):
        rec = self.data["current"].get(room, {})
        self._loading = True
        try:
            for key, ti in self.inputs.items():
                ti.text = str(rec.get(key, ""))
        finally:
            self._loading = False
        self.refresh_units_label()

    def select_room(self, room):
        if self.current_room:
            self.store_current()
        self.current_room = room
        for r, b in self.room_btns.items():
            b.set_bg(ACCENT if r == room else INACTIVE)
        self.room_label.text = (
            "Room No. %s   [size=%d][color=ffcc55]%s Floor[/color][/size]"
            % (room, int(dp(13)), floor_of(room))
        )
        self.load_room(room)

    def store_current(self):
        if not self.current_room:
            return True
        rec = self.collect()
        if any(v.strip() for v in rec.values()):
            self.data["current"][self.current_room] = rec
        else:
            self.data["current"].pop(self.current_room, None)
        return save_data(self.data)

    def save_room(self, *a):
        if self.store_current():
            toast("Room %s saved" % self.current_room)
        else:
            toast("Could not save. Check storage space")

    def archive_room(self, *a):
        room = self.current_room
        rec = self.collect()
        if not any(v.strip() for v in rec.values()):
            toast("Room %s is empty" % room)
            return

        def do():
            if not rec.get("checkout_date", "").strip():
                rec["checkout_date"] = today()
            rec["archived_ts"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            hist = self.data["history"].get(room)
            if not isinstance(hist, list):
                hist = []
                self.data["history"][room] = hist
            hist.insert(0, rec)
            self.data["current"].pop(room, None)
            ok = save_data(self.data)
            self.load_room(room)
            if ok:
                toast("Moved to history.\nRoom %s is ready for a new patient" % room)
            else:
                toast("Could not save. Check storage space")

        confirm(
            "Move room %s details to Room History\nand start fresh for a new patient?"
            % room,
            do,
            "Archive",
        )

    def confirm_clear(self, *a):
        room = self.current_room

        def do():
            self._loading = True
            try:
                for ti in self.inputs.values():
                    ti.text = ""
            finally:
                self._loading = False
            self.data["current"].pop(room, None)
            save_data(self.data)
            self.refresh_units_label()

        confirm(
            "Clear all details of room %s?\n(This does NOT save to history)" % room,
            do,
            "Clear",
        )

    # ------------------------------------------------------------------
    # History view
    # ------------------------------------------------------------------
    def build_history_view(self):
        view = BoxLayout(orientation="vertical", spacing=dp(6))

        bar, self.hist_btns = self.make_room_bar(self.select_hist_room, include_all=True)
        view.add_widget(bar)

        self.hist_info = Label(
            size_hint_y=None,
            height=dp(30),
            font_size=dp(16),
            color=(0.55, 0.9, 1, 1),
        )
        view.add_widget(self.hist_info)

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        self.hist_list = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=[0, 0, 0, dp(10)],
        )
        self.hist_list.bind(minimum_height=self.hist_list.setter("height"))
        scroll.add_widget(self.hist_list)
        view.add_widget(scroll)
        return view

    def select_hist_room(self, key):
        self.hist_room = key
        self.refresh_history()

    def refresh_history(self):
        for k, b in self.hist_btns.items():
            b.set_bg(ACCENT if k == self.hist_room else INACTIVE)

        rooms = ALL_ROOMS if self.hist_room == "ALL" else [self.hist_room]
        items = []
        for room in rooms:
            recs = self.data["history"].get(room, [])
            if isinstance(recs, list):
                for rec in recs:
                    if isinstance(rec, dict):
                        items.append((room, rec))
        items.sort(key=lambda it: str(it[1].get("archived_ts", "")), reverse=True)

        title = "All rooms" if self.hist_room == "ALL" else "Room %s" % self.hist_room
        self.hist_info.text = "%s  -  %d old record(s)" % (title, len(items))

        self.hist_list.clear_widgets()
        if not items:
            empty = Label(
                text="No old records yet.\nUse ARCHIVE & NEW in a room when a patient leaves.",
                halign="center",
                valign="middle",
                size_hint_y=None,
                height=dp(120),
                color=(1, 1, 1, 0.6),
            )
            empty.bind(size=lambda i, s: setattr(i, "text_size", s))
            self.hist_list.add_widget(empty)
            return
        for room, rec in items:
            self.hist_list.add_widget(self.make_card(room, rec))

    def make_line(self, markup_text):
        lb = Label(
            markup=True,
            text=markup_text,
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(22),
            font_size=dp(14),
        )
        lb.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        lb.bind(
            texture_size=lambda i, s: setattr(i, "height", max(dp(22), s[1] + dp(2)))
        )
        return lb

    def make_card(self, room, rec):
        card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(12),
            spacing=dp(2),
        )
        card.bind(minimum_height=card.setter("height"))
        round_bg(card, CARD_BG, 16)

        card.add_widget(
            self.make_line(
                "[b][color=8fe9ff]Room %s[/color][/b]   [color=9aa7c7]archived %s[/color]"
                % (escape_markup(str(room)), pretty_ts(str(rec.get("archived_ts", ""))))
            )
        )
        shown = 0
        for key, label, kind, mx in FIELDS:
            val = str(rec.get(key, "")).strip()
            if not val:
                continue
            short = label.split(" (")[0]
            card.add_widget(
                self.make_line(
                    "[color=9aa7c7]%s:[/color] %s"
                    % (escape_markup(short), escape_markup(val))
                )
            )
            shown += 1
        if not shown:
            card.add_widget(self.make_line("[color=9aa7c7](empty record)[/color]"))

        row = BoxLayout(size_hint_y=None, height=dp(44), padding=[0, dp(6), 0, 0])
        row.add_widget(Label())
        delete = RButton(
            text="Delete record",
            bg=RED,
            size_hint=(None, 1),
            width=dp(130),
            font_size=dp(14),
        )

        def ask_delete(*a):
            def do():
                try:
                    self.data["history"][room].remove(rec)
                except (KeyError, ValueError):
                    pass
                save_data(self.data)
                self.refresh_history()

            confirm("Delete this old record of room %s permanently?" % room, do, "Delete")

        delete.bind(on_release=ask_delete)
        row.add_widget(delete)
        card.add_widget(row)
        return card

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------
    def set_mode(self, mode):
        self.store_current()
        self.container.clear_widgets()
        if mode == "rooms":
            self.btn_rooms.set_bg(ACCENT)
            self.btn_hist.set_bg(INACTIVE)
            self.container.add_widget(self.rooms_view)
        else:
            self.btn_rooms.set_bg(INACTIVE)
            self.btn_hist.set_bg(ACCENT)
            self.container.add_widget(self.history_view)
            self.refresh_history()


# ----------------------------------------------------------------------
# App
# ----------------------------------------------------------------------
class HostelApp(App):
    def build(self):
        global DATA_DIR
        self.title = "Pushpanjali Hostel"
        Window.clearcolor = (0.04, 0.05, 0.15, 1)

        # Keep records in the app's private storage (survives app close / force close)
        try:
            DATA_DIR = self.user_data_dir
            os.makedirs(DATA_DIR, exist_ok=True)
            old = os.path.join(BASE_DIR, "hostel_data.json")
            if os.path.exists(old) and not os.path.exists(data_file()):
                shutil.copy(old, data_file())
        except Exception:
            DATA_DIR = BASE_DIR

        self.sm = ScreenManager(transition=FadeTransition(duration=0.6))
        self.intro = IntroScreen(self.go_main, name="intro")
        self.main = MainScreen(name="main")
        self.sm.add_widget(self.intro)
        self.sm.add_widget(self.main)
        self.sm.current = "intro"
        return self.sm

    def on_start(self):
        Clock.schedule_once(self.intro.start, 0.3)

    def go_main(self):
        self.sm.current = "main"

    def on_pause(self):
        self.main.store_current()
        return True

    def on_stop(self):
        self.main.store_current()


if __name__ == "__main__":
    HostelApp().run()
