"""
duckyduck — masaüstü yol arkadaşın (bir ördek).

Ekranında yürür, pencerelerin üstüne çıkar, ne yaptığına göre ruh hali
değiştirir ve seninle birlikte yapar. Ekran görüntüsü almaz: sadece öndeki
pencerenin adına/uygulamasına ve ne kadar süredir dokunmadığına bakar.

Çalıştırmak: baslat.bat
Dosyalar:
  ordek.py      ördeğin kendisi ve her şeyi yöneten kısım
  cizim.py      ördek, yavru, yuva, kırıntı ve aksesuar çizimleri
  yuva.py       yuva + not defteri
  sohbet.py     sohbet kutusu
  menu.py       sağ tık halka menüsü
  nesneler.py   kırıntılar ve yavru ördek
  pencereler.py Windows yardımcıları
  ayarlar.py    veri/ klasöründeki ayar ve kayıtlar
"""

import math
import os
import random
import sys
import time
import winreg
from datetime import datetime

import glob
import importlib.util
import shutil
import subprocess
import traceback

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QCursor, QFont, QFontMetrics, QIcon, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon, QWidget

import ayarlar
import cizim
import logo
import pencereler as pw
from dogumgunu import BirthdayDialog, InfoCard
from menu import RadialMenu
from nesneler import Crumb, Duckling
from sohbet import ChatWindow
from yuva import Notes, NotesWindow

# (ruh hali, uygulama dosya adları, pencere başlığında geçen kelimeler)
RULES = [
    ("music",  {"spotify.exe"},
               ["spotify", "youtube music", "soundcloud", "apple music"]),
    ("watch",  {"vlc.exe", "potplayermini64.exe", "mpc-hc64.exe", "netflix.exe"},
               ["youtube", "netflix", "prime video", "disney+", "twitch",
                "blutv", "exxen", "max |", "mubi", "dizi", "film izle"]),
    ("focus",  {"code.exe", "cursor.exe", "pycharm64.exe", "idea64.exe",
                "devenv.exe", "windowsterminal.exe", "powershell.exe",
                "cmd.exe", "winword.exe", "excel.exe", "powerpnt.exe",
                "notion.exe", "obsidian.exe", "acrobat.exe", "claude.exe"},
               ["visual studio", "overleaf", "google docs", "google dokümanlar",
                "notion", "leetcode", "github", "stack overflow", "chatgpt"]),
    ("social", {"whatsapp.exe", "whatsapp.root.exe", "discord.exe", "telegram.exe"},
               ["whatsapp", "instagram", "twitter", "/ x", "reddit", "discord",
                "telegram", "tiktok"]),
    ("game",   {"steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe",
                "riotclientux.exe", "minecraft.exe", "javaw.exe"},
               ["steam", "minecraft"]),
]
PERCH_MOODS = {"normal", "focus", "watch", "music", "night"}

OUTFITS = [("otomatik", "Otomatik"), ("yok", "Yok"), ("kis", "Kışlık"),
           ("sonbahar", "Sonbahar"), ("cicek", "Çiçek"), ("gunes", "Güneş gözlüğü"),
           ("parti", "Parti"), ("gece", "Gece şapkası")]
OUTFIT_SETS = {"yok": set(), "kis": {"beanie", "scarf"}, "sonbahar": {"scarf_autumn"},
               "cicek": {"flower"}, "gunes": {"sunglasses"}, "parti": {"party"},
               "gece": {"nightcap"}}
HATS = {"beanie", "party", "flower", "nightcap"}


LONG_PRESS = 1.0        # ekranda bu kadar saniye basılı tutunca ördek oraya gelir


# --- Eklentiler ---------------------------------------------------------------
# eklentiler/ klasörüne konan her .py dosyası açılışta yüklenir ("_" ile başlayanlar hariç).
# Bir eklenti şu fonksiyonlardan istediklerini tanımlayabilir (hepsi app'i alır):
#   baslat(app)                  ördek açılınca bir kez
#   ruh_hali(app, eski, yeni)    ruh hali değişince
#   tiklandi(app)                ördeğe tıklanınca
#   her_dakika(app)              dakikada bir
# Hata veren eklenti ördeği bozmaz; hata veri/eklenti_hatalari.log dosyasına yazılır.

def eklentileri_yukle():
    mods = []
    folder = os.path.join(ayarlar.BASE, "eklentiler")
    for path in sorted(glob.glob(os.path.join(folder, "*.py"))):
        name = os.path.basename(path)
        if name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"eklenti_{name[:-3]}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mods.append(mod)
        except Exception:
            eklenti_hatasi(name)
    return mods


def eklenti_hatasi(name):
    try:
        with open(os.path.join(ayarlar.VERI, "eklenti_hatalari.log"), "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M} {name}\n{traceback.format_exc()}\n")
    except OSError:
        pass


class CallMarker(QWidget):
    """Basılı tutulan noktada dolan halka; dolunca küçük bir patlamayla ördeği çağırır.
    Tıklamalar içinden geçer, hiçbir şeye engel olmaz."""
    S = 76

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(self.S, self.S)
        self.progress = 0.0
        self.burst = 0.0          # >0 iken "çağrıldı" patlaması oynar

    def place(self, pos):
        self.move(pos.x() - self.S // 2, pos.y() - self.S // 2)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.S / 2, self.S / 2)
        if self.burst > 0:
            k = 1 - self.burst / 0.45
            p.setPen(QPen(QColor(247, 162, 30, int(230 * (1 - k))), 3))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, 12 + 22 * k, 12 + 22 * k)
            return
        a = min(1.0, self.progress * 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 243, 220, int(170 * a)))
        p.drawEllipse(c, 17, 17)
        p.setPen(QPen(QColor(233, 207, 160, int(255 * a)), 3.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, 17, 17)
        p.setPen(QPen(QColor(247, 162, 30, int(255 * a)), 3.5, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(c.x() - 17, c.y() - 17, 34, 34), 90 * 16, -int(360 * 16 * self.progress))
        p.setOpacity(a)                    # ortada küçük bir ördek ayak izi
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F28C1B"))
        foot = QPainterPath()
        x, y = c.x(), c.y() + 1
        foot.moveTo(x, y + 6)
        foot.lineTo(x - 6.5, y - 3)
        foot.lineTo(x - 1.5, y - 1)
        foot.lineTo(x, y - 7)
        foot.lineTo(x + 1.5, y - 1)
        foot.lineTo(x + 6.5, y - 3)
        foot.closeSubpath()
        p.drawPath(foot)


def icon_nest(p, pos, r):
    """Menüdeki yuva düğmesi: yumurtalı küçük yuva."""
    p.save()
    p.translate(pos.x(), pos.y() + r * 0.42)
    p.scale(r / 62, r / 62)
    cizim.draw_nest(p, 0, 0, eggs=3)
    p.restore()


def icon_crumb(p, pos, r):
    cizim.draw_seed_bowl(p, pos.x(), pos.y() + 2, r * 1.15)


def classify(info):
    if not info:
        return "normal"
    for mood, procs, _ in RULES:
        if info["proc"] in procs:
            return mood
    title = info["title"].lower()
    for mood, _, words in RULES:
        if any(w in title for w in words):
            return mood
    return "normal"


# --- Bilgisayarla birlikte başlama ---

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "duckyduckApp" if ayarlar.FROZEN else "duckyduck"   # exe ile geliştirme sürümü birbirini bozmasın


def autostart_command():
    if ayarlar.FROZEN:                         # tek .exe sürümü
        return f'"{sys.executable}"'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    return f'"{exe}" "{os.path.abspath(__file__)}"'


def autostart_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return winreg.QueryValueEx(k, RUN_NAME)[0]
    except OSError:
        return None


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# Ördek
# ---------------------------------------------------------------------------

class Duck(QWidget):
    W, H, FOOT = 260, 224, 8
    WALK, RUN, SLOW = 115, 300, 70      # piksel / saniye
    STRIDE = 0.21                        # adım animasyonu (radyan / piksel)
    SCALE = 0.8                          # ördeğin ekrandaki boyutu
    BEAK_REACH = 58 * SCALE              # yerdeki kırıntıya uzanma mesafesi

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(self.W, self.H)

        geo = QApplication.primaryScreen().geometry()
        self.wx = geo.left() + random.uniform(200, max(201, geo.width() - 460))
        self.wy = 0.0
        self.wy = self.ground_y()

        self.mode = "ground"          # ground / perch / flight / fall / nest / drag
        self.mood = "normal"
        self.action, self.action_left = "idle", 1.0
        self.dir, self.speed, self.phase = 1, self.WALK, 0.0
        self.t = 0.0
        self.jump_y = self.jump_v = 0.0
        self.hops = 0
        self.peck = self.quack_t = self.blink = self.startle = self.shaken = 0.0
        self.next_blink = 3.0
        self.emit_t = 0.0
        self.hunger_t = 0.0
        self.particles = []
        self.goal = None
        self.flight = None
        self.perch = None
        self.perch_rel = self.perch_w = self.perch_left = 0.0
        self.cover_t = 0.0
        self.ignore_hwnd = None
        self.fall_v = 0.0
        self.nest_stay = None
        self.eat_queue = []
        self.eating = None
        self.still = False
        self.thinking = False
        self.scripted = False      # True iken ördeği bir eklenti yönetir (kendi kendine dolaşmaz)

        self.pressed = False
        self.press_pos = QPointF()
        self.drag_offset = QPointF()
        self.hover_t = 0.0
        self.faded = False
        self.opacity = 1.0
        self.cursor_prev = QCursor.pos()
        self.cursor_v = (0.0, 0.0)
        self.cursor_speed = 0.0
        self.play_cool = 3.0
        self.back_cool = 0.0
        self.notice = 0.0
        self.look_dir = 1
        self.back_dir = -1
        self.move(int(self.wx), int(self.wy))

    # ----- konum yardımcıları -----
    def center_x(self):
        return self.wx + self.W / 2

    def feet_y(self):
        return self.wy + self.H - self.FOOT

    def screen_obj(self):
        return (QApplication.screenAt(QPoint(int(self.center_x()), int(self.feet_y() - 40)))
                or QApplication.primaryScreen())

    def ground_y(self):
        return self.app.ground_bottom(self.screen_obj()) + 1 - (self.H - self.FOOT)

    def x_bounds(self):
        geo = self.screen_obj().geometry()
        return geo.left() + 50 - self.W / 2, geo.right() - 50 - self.W / 2

    # ----- küçük animasyonlar -----
    def jump(self, power=-300, hops=0):
        if self.jump_y == 0 and self.jump_v == 0:
            self.jump_v = power
            self.hops = hops

    def quack(self):
        self.quack_t = 0.35
        self.jump(-220)

    def set_thinking(self, on):
        self.thinking = on

    def spawn(self, text, color="#FF6B8B", count=1, spread=10, emoji=False, size=None):
        for _ in range(count):
            self.particles.append({
                "text": text, "color": QColor(color), "emoji": emoji,
                "x": self.W / 2 + self.dir * 16 + random.uniform(-spread, spread),
                "y": self.H - self.FOOT - 96 * self.SCALE + self.jump_y,
                "vx": random.uniform(-15, 15) + self.dir * 10,
                "vy": random.uniform(-60, -38),
                "life": 2.2, "max": 2.2,
                "size": size or random.randint(13, 17),
            })

    def hearts(self, n=2):
        self.spawn("♥", "#FF6B8B", count=n, spread=14)

    # ----- davranış seçimi -----
    def set_action(self, action, seconds, speed=None, direction=None):
        self.action, self.action_left = action, seconds
        if speed is not None:
            self.speed = speed
        if direction is not None:
            self.dir = direction

    def walk(self, speed, lo, hi):
        lo_x, hi_x = self.x_bounds()
        mid = (lo_x + hi_x) / 2
        d = (1 if self.wx < mid else -1) if random.random() < 0.3 else random.choice((-1, 1))
        self.set_action("run" if speed >= self.RUN else "walk",
                        random.uniform(lo, hi), speed, d)

    def pick_action(self):
        m, r = self.mood, random.random()
        if self.perch and self.perch_left <= 0:
            self.drop_off()
            return
        if m == "sleep" and self.mode == "ground" and not self.still:
            self.go_to_nest()
            return
        if (self.mode == "ground" and not self.still and m in PERCH_MOODS
                and not self.app.sulky()
                and random.random() < self.app.settings["pencereye_cikma"]
                and self.try_perch(self.app.last_hwnd)):
            return
        if self.still:
            self.set_action("sleep" if m == "sleep" else "sit", 4)
        elif self.app.sulky():
            if r < 0.8:
                self.set_action("sit", random.uniform(6, 10))
                cx = QCursor.pos().x()
                self.dir = -1 if cx > self.center_x() else 1      # sana arkasını döner
            else:
                self.walk(self.SLOW, 1.5, 3)
        elif m == "watch":
            self.set_action("eat", 8)
        elif m == "music":
            self.set_action("dance", 8)
        elif m == "sleep":
            self.set_action("sleep", 8)
        elif m == "focus":
            self.set_action("type", random.uniform(10, 20))   # odakta yerinden kalkmaz
        elif m == "night":
            if r < 0.6:
                self.set_action("sit", random.uniform(5, 10))
            else:
                self.walk(self.SLOW, 2, 4)
        elif m == "social":
            if r < 0.5:
                self.set_action("idle", random.uniform(3, 6))
            else:
                self.walk(140, 2, 4)
        elif m == "game":
            if r < 0.5:
                self.set_action("hop", random.uniform(2, 4))
            else:
                self.walk(self.RUN, 0.8, 1.8)
        else:
            if r < 0.45:
                self.walk(self.WALK, 2, 5)
            elif r < 0.53:
                self.walk(self.RUN, 0.8, 1.5)
            elif r < 0.83:
                self.set_action("idle", random.uniform(2, 5))
            else:
                self.set_action("sit", random.uniform(4, 8))

    def update_action(self, dt):
        a = self.action
        self.action_left -= dt
        if a == "peck_food":
            if self.peck <= 0:
                self.peck = 0.28
            if self.action_left <= 0:
                self._finish_eat()
            return
        if self.action_left <= 0:
            self.pick_action()
            a = self.action

        if a in ("walk", "run", "flee"):
            sp = self.speed
            if self.mode == "perch":
                sp = min(sp, self.WALK)
                self.perch_rel += self.dir * sp * dt
                if self.perch_rel < 40:
                    self.perch_rel, self.dir = 40, 1
                elif self.perch_rel > self.perch_w - 40:
                    self.perch_rel, self.dir = self.perch_w - 40, -1
            else:
                self.wx += self.dir * sp * dt
                lo, hi = self.x_bounds()
                if self.wx < lo or self.wx > hi:
                    self.wx = max(lo, min(self.wx, hi))
                    if a == "flee":
                        self.set_action("idle", 1.5)
                    else:
                        self.dir = -self.dir
            self.phase += sp * dt * self.STRIDE
        elif a == "backstep":                      # imlece bakarak geri geri yürür
            sp = self.SLOW
            self.wx += self.back_dir * sp * dt
            lo, hi = self.x_bounds()
            self.wx = max(lo, min(self.wx, hi))
            self.phase += sp * dt * self.STRIDE
        elif a == "chase":
            dx = QCursor.pos().x() - self.center_x()
            if abs(dx) > 30:
                self.dir = 1 if dx > 0 else -1
                self.wx += self.dir * min(abs(dx), self.RUN * dt)
                lo, hi = self.x_bounds()
                self.wx = max(lo, min(self.wx, hi))
                self.phase += self.RUN * dt * self.STRIDE
            elif random.random() < dt * 2:
                self.jump(-260)
                self.hearts(1)
        elif a in ("idle", "sit"):
            if self.peck <= 0 and random.random() < dt * 0.25:
                self.peck = 0.45
            if random.random() < dt * 0.08:
                self.dir = -self.dir
        elif a == "dance":
            self.phase += dt * 9
            self._emit(dt, 0.45, lambda: self.spawn(random.choice("♪♫"), random.choice(
                ["#FF6B8B", "#6BA8FF", "#9B6BFF", "#3CB98A"])))
        elif a == "sleep":
            self._emit(dt, 1.1, lambda: self.spawn(random.choice(["z", "Z"]), "#8A9BC4", spread=3))
        elif a == "hop":
            if random.random() < dt * 1.3:
                self.jump(-260)
        elif a == "type":
            self._emit(dt, 15, lambda: self.spawn("💡", emoji=True, size=15, spread=4))

    def _emit(self, dt, every, fn):
        self.emit_t += dt
        if self.emit_t >= every:
            self.emit_t = 0.0
            fn()

    # ----- hedefe gitme (kırıntı, yuva, yanına gel) -----
    def set_goal(self, x, speed, arrive=None):
        self.goal = {"x": x, "speed": speed, "arrive": arrive}
        if self.mode == "perch":
            self.drop_off()
        elif self.mode == "nest":
            self.exit_nest(hop=False)

    def update_goal(self, dt):
        g = self.goal
        tx = g["x"]
        target_scr = QApplication.screenAt(QPoint(int(tx), int(self.feet_y() - 20)))
        if target_scr and target_scr.name() != self.screen_obj().name():
            bottom = self.app.ground_bottom(target_scr)
            self.fly_to_point(tx, bottom)
            return
        dx = tx - self.center_x()
        if abs(dx) <= 6:
            self.goal = None
            self.set_action("idle", 0.6)
            if g["arrive"]:
                g["arrive"]()
            return
        self.dir = 1 if dx > 0 else -1
        sp = g["speed"]
        step = min(abs(dx), sp * dt)
        self.wx += self.dir * step
        self.phase += step * self.STRIDE
        self.action, self.speed = ("run" if sp >= self.RUN else "walk"), sp

    def come_here(self, pos=None):
        """Verilen noktaya (yoksa imlecin olduğu yere; başka ekrandaysa uçarak) koşar gelir."""
        if self.scripted:
            return
        pos = pos or QCursor.pos()
        scr = QApplication.screenAt(pos) or self.screen_obj()
        geo = scr.geometry()
        x = max(geo.left() + 50, min(pos.x(), geo.right() - 50))
        self.play_cool = self.back_cool = 3.0          # gelirken imleçten kaçmasın
        self.set_goal(x, self.RUN, lambda: (self.quack(), self.hearts(2)))

    # ----- yemek -----
    def go_eat(self, crumb):
        if crumb.reserved or crumb.dead:
            return
        crumb.reserved = True
        self.eat_queue.append(crumb)
        if len(self.eat_queue) == 1 and not self.eating:
            self._next_crumb()

    def _next_crumb(self):
        while self.eat_queue and self.eat_queue[0].dead:
            self.eat_queue.pop(0)
        if not self.eat_queue:
            return
        c = self.eat_queue[0]
        if not c.landed:
            QTimer.singleShot(250, self._next_crumb)
            return
        side = 1 if c.cx > self.center_x() else -1
        self.set_goal(c.cx - side * self.BEAK_REACH, self.RUN, lambda: self._start_eat(c, side))

    def _start_eat(self, crumb, side):
        if crumb.dead:
            self.eating = None
            self._next_crumb()
            return
        self.dir = side
        self.eating = crumb
        self.set_action("peck_food", 1.2)

    def _finish_eat(self):
        c = self.eating
        self.eating = None
        if c in self.eat_queue:
            self.eat_queue.remove(c)
        if c and not c.dead:
            c.eat()
            self.app.fed()
        self.set_action("idle", 0.8)
        if self.eat_queue:
            self._next_crumb()

    # ----- yuva: uyurken olduğu yerde altında bir yuva belirir -----
    def go_to_nest(self, stay=None):
        self.nest_stay = stay
        self.mode = "nest"
        self.set_action("sleep" if self.mood == "sleep" else "sit", 5)
        self.jump(-200)
        self.update_nest(0)

    def update_nest(self, dt):
        self.wy = self.ground_y()
        if self.mood == "sleep" or self.still:
            self.action = "sleep" if self.mood == "sleep" else "sit"
            if self.action == "sleep":
                self._emit(dt, 1.1, lambda: self.spawn(random.choice(["z", "Z"]), "#8A9BC4", spread=3))
            return
        if self.nest_stay is None:
            self.exit_nest()
            return
        self.action = "sit"
        self.nest_stay -= dt
        if self.peck <= 0 and random.random() < dt * 0.3:
            self.peck = 0.45
        if self.nest_stay <= 0:
            self.exit_nest()

    def exit_nest(self, hop=True):
        if self.mode != "nest":
            return
        self.mode = "ground"
        self.nest_stay = None
        self.wy = self.ground_y()
        if hop:
            self.jump(-320)
            self.set_action("walk", 0.8, self.WALK, random.choice((-1, 1)))

    # ----- pencere üstünde oturma -----
    def perch_ok(self, frame):
        left, top, right = frame
        scr = QApplication.screenAt(QPoint(int(left + 20), int(top + 20)))
        if not scr:
            return False
        return top - scr.availableGeometry().top() >= 110 and right - left >= 120

    def try_perch(self, hwnd):
        if not hwnd or not pw.is_perchable(hwnd):
            return False
        f = pw.logical_frame(hwnd)
        if not f or not self.perch_ok(f):
            return False
        width = f[2] - f[0]
        for _ in range(6):
            rel = random.uniform(45, width - 45)
            if pw.window_at(*pw.to_native(f[0] + rel, f[1] + 4)) == hwnd:
                def target(h=hwnd, rel=rel):
                    if not pw.window_alive(h):
                        return None
                    fr = pw.logical_frame(h)
                    if not fr or not self.perch_ok(fr):
                        return None
                    return fr[0] + rel - self.W / 2, fr[1] - (self.H - self.FOOT)

                def land(h=hwnd, rel=rel):
                    fr = pw.logical_frame(h)
                    if fr:
                        self.land_on(h, fr, fr[0] + rel)
                    else:
                        self.start_fall(0)

                return self.fly(target, land, hwnd=hwnd)
        return False

    def land_on(self, hwnd, frame, cx):
        self.mode = "perch"
        self.flight = None
        self.ignore_hwnd = None
        self.perch = hwnd
        self.perch_w = frame[2] - frame[0]
        self.perch_rel = max(40, min(cx - frame[0], self.perch_w - 40))
        self.perch_left = random.uniform(30, 120)
        self.wx = frame[0] + self.perch_rel - self.W / 2
        self.wy = frame[1] - (self.H - self.FOOT)
        self.quack_t = 0.25
        self.jump(-160)
        self.set_action("idle", 1.0)

    def drop_off(self):
        self.ignore_hwnd = self.perch
        self.perch = None
        self.start_fall(-280)

    def start_fall(self, v):
        self.mode = "fall"
        self.flight = None
        self.fall_v = v

    def follow_perch(self, dt):
        h = self.perch
        f = pw.logical_frame(h) if pw.window_alive(h) else None
        if not f or not self.perch_ok(f):
            self.startle = 0.6
            self.drop_off()
            return
        self.perch_w = f[2] - f[0]
        self.perch_rel = max(40, min(self.perch_rel, self.perch_w - 40))
        cx = f[0] + self.perch_rel
        nx, ny = cx - self.W / 2, f[1] - (self.H - self.FOOT)
        if abs(nx - self.wx) + abs(ny - self.wy) > 6:
            self.shaken = 0.35          # pencereyi sürüklüyorsun
        self.wx, self.wy = nx, ny
        self.cover_t += dt
        if self.cover_t > 0.2:
            self.cover_t = 0.0
            if pw.window_at(*pw.to_native(cx, f[1] + 4)) != h:
                self.startle = 0.6
                self.drop_off()
                return
        if self.mood != "sleep":
            self.perch_left -= dt

    # ----- uçma / düşme -----
    def fly(self, target, on_land, hwnd=None):
        tgt = target()
        if tgt is None:
            return False
        dist = math.hypot(tgt[0] - self.wx, tgt[1] - self.wy)
        self.flight = {"target": target, "on_land": on_land, "t": 0.0, "hwnd": hwnd,
                       "sx": self.wx, "sy": self.wy,
                       "dur": max(0.45, min(1.3, dist / 650)),
                       "arc": 40 + min(140, dist * 0.18)}
        self.mode = "flight"
        self.perch = None
        return True

    def fly_to_point(self, cx, bottom):
        def land():
            self.mode = "ground"
            self.jump(-150)
        self.fly(lambda: (cx - self.W / 2, bottom + 1 - (self.H - self.FOOT)), land)

    def update_flight(self, dt):
        fl = self.flight
        fl["t"] += dt
        tgt = fl["target"]()
        if tgt is None:
            self.start_fall(0)
            return
        tx, ty = tgt
        s = min(1.0, fl["t"] / fl["dur"])
        e = s * s * (3 - 2 * s)
        self.dir = 1 if tx >= fl["sx"] else -1
        self.wx = fl["sx"] + (tx - fl["sx"]) * e
        self.wy = fl["sy"] + (ty - fl["sy"]) * e - math.sin(math.pi * s) * fl["arc"]
        if s >= 1.0:
            self.flight = None
            fl["on_land"]()

    def update_fall(self, dt):
        prev = self.feet_y()
        self.fall_v = min(self.fall_v + 2600 * dt, 1600)
        self.wy += self.fall_v * dt
        feet = self.feet_y()
        if self.fall_v > 0 and not self.goal:
            cx = self.center_x()
            h = pw.window_at(*pw.to_native(cx, feet))
            if h and h != self.ignore_hwnd:
                f = pw.logical_frame(h)
                if f and prev - 1 <= f[1] <= feet and self.perch_ok(f):
                    self.land_on(h, f, cx)
                    return
        g = self.ground_y()
        if self.wy >= g:
            self.wy, self.mode = g, "ground"
            self.ignore_hwnd = None
            self.quack_t = 0.25
            self.jump(-150)
            if not self.goal:
                self.action_left = 0.5

    # ----- fareyle oyun -----
    def track_cursor(self, dt):
        pos = QCursor.pos()
        vx = (pos.x() - self.cursor_prev.x()) / max(dt, 1e-3)
        vy = (pos.y() - self.cursor_prev.y()) / max(dt, 1e-3)
        self.cursor_prev = pos
        self.cursor_v = (vx, vy)
        self.cursor_speed = self.cursor_speed * 0.6 + math.hypot(vx, vy) * 0.4
        self.play_cool -= dt
        self.back_cool -= dt
        self.notice = max(0.0, self.notice - dt)

        bx, by = self.center_x(), self.feet_y() - 45 * self.SCALE
        dx, dy = bx - pos.x(), by - pos.y()
        dist = math.hypot(dx, dy)
        if self.scripted:
            return
        busy = (self.pressed or self.goal or self.mode not in ("ground", "perch")
                or self.mood == "sleep" or self.action in ("sleep", "peck_food", "chase", "flee"))

        # --- yavaş yaklaşma: fark edip bakar, çok yaklaşırsa geri geri çekilir ---
        if not busy and dist < 230:
            if self.notice == 0:
                self.startle = 0.25                 # "aa, sen misin?"
            self.notice = 0.6
            self.look_dir = 1 if pos.x() > self.center_x() else -1
            if self.action not in ("walk", "run", "backstep") and not self.app.sulky():
                self.dir = self.look_dir            # dönüp imlece bakar
            approach = (vx * dx + vy * dy) / max(dist, 1.0)   # + ise imleç ona doğru geliyor
            if (dist < 120 and approach > 60 and self.back_cool <= 0
                    and self.mode == "ground" and not self.still and self.mood != "focus"):
                self.back_cool = 2.5
                if random.random() < 0.7:
                    self.dir = self.look_dir
                    self.back_dir = -self.look_dir
                    self.set_action("backstep", random.uniform(0.5, 0.9))
                else:
                    self.jump(-200)                 # bazen kaçmaz, merakla zıplar
                    self.set_action("idle", 1.5)

        if (self.mode != "ground" or self.goal or self.pressed or self.play_cool > 0
                or self.still or self.mood == "sleep"
                or self.action in ("sleep", "peck_food", "chase")):
            return
        if dist > 160 or self.cursor_speed < 1500:
            return
        if vx * dx + vy * dy <= 0:          # imleç ördeğe doğru gelmiyor
            return
        self.play_cool = 5.0
        self.startle = 0.6
        self.jump(-240)
        if self.mood == "focus" or self.app.sulky():
            return
        if random.random() < 0.6:
            self.set_action("flee", random.uniform(1.0, 1.6), self.RUN, 1 if dx > 0 else -1)
        else:
            self.set_action("chase", 4.0)

    # ----- tıklama / sürükleme / saydamlaşma -----
    def duck_rect(self):
        s = self.SCALE
        top = int(self.feet_y() - 100 * s)
        h = int((74 if self.mode == "nest" else 98) * s)
        return QRect(int(self.center_x() - 50 * s), top, int(100 * s), h)

    def update_hover(self, dt):
        """İmleç ördeğin ya da yavrunun üstünde bekleyince ikisi birlikte saydamlaşır
        ve tıklamalar içlerinden geçer; imleç ikisinden de çıkınca geri gelirler."""
        pos = QCursor.pos()
        baby = self.app.duckling
        inside = self.duck_rect().contains(pos) or (baby is not None and baby.body_rect().contains(pos))
        if inside and not self.pressed and not self.app.radial_open() and self.action != "chase":
            self.hover_t += dt
        elif not inside:
            self.hover_t = 0.0
        fade = self.hover_t > 1.3
        if fade != self.faded:
            self.faded = fade
            pw.set_click_through(self, fade)
            if baby is not None:
                pw.set_click_through(baby, fade)
        target = 0.25 if self.faded else 1.0
        if abs(self.opacity - target) > 0.01:
            self.opacity += (target - self.opacity) * min(1.0, dt * 12)
            self.setWindowOpacity(self.opacity)
            if baby is not None:
                baby.setWindowOpacity(self.opacity)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.pressed = True
            self.hover_t = 0.0
            self.press_pos = e.globalPosition()
            self.drag_offset = e.globalPosition() - QPointF(self.wx, self.wy)

    def mouseMoveEvent(self, e):
        if not self.pressed:
            return
        if self.mode != "drag" and (e.globalPosition() - self.press_pos).manhattanLength() > 6:
            if self.mode == "nest":
                self.exit_nest(hop=False)
            self.mode = "drag"
            self.perch = self.flight = self.ignore_hwnd = self.goal = None
        if self.mode == "drag":
            pos = e.globalPosition() - self.drag_offset
            self.wx, self.wy = pos.x(), pos.y()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self.pressed = False
        if self.mode == "drag":
            lo, hi = self.x_bounds()
            self.wx = max(lo, min(self.wx, hi))
            self.start_fall(0)
            return
        if self.mode == "nest" and e.position().y() > self.H - self.FOOT - 26:
            self.app.open_notes()
            return
        self.quack()
        self.hearts(2)
        self.app.toggle_chat()
        self.app.hook("tiklandi")

    def contextMenuEvent(self, e):
        self.app.open_radial()

    # ----- her karede -----
    def step(self, dt):
        self.t += dt
        self.track_cursor(dt)
        self.update_hover(dt)

        m = self.mode
        if m == "drag":
            self.phase += dt * 12
        elif m == "flight":
            self.update_flight(dt)
        elif m == "fall":
            self.update_fall(dt)
        elif m == "nest":
            self.update_nest(dt)
        elif m == "perch":
            if self.goal:
                self.drop_off()
            else:
                self.follow_perch(dt)
                if self.mode == "perch":
                    self.update_action(dt)
        else:
            g = self.ground_y()
            if self.wy < g - 2:
                self.start_fall(0)          # zemin aşağı indi (tam ekran)
            else:
                self.wy = g
                if self.goal:
                    self.update_goal(dt)
                elif not self.scripted:
                    self.update_action(dt)

        # zıplama
        if self.jump_v or self.jump_y < 0:
            self.jump_v += 1900 * dt
            self.jump_y += self.jump_v * dt
            if self.jump_y >= 0:
                self.jump_y, self.jump_v = 0.0, 0.0
                if self.hops > 0:
                    self.hops -= 1
                    self.jump_v = -300

        # sayaçlar
        self.next_blink -= dt
        if self.next_blink <= 0:
            self.blink = 0.12
            self.next_blink = random.uniform(2.5, 6)
        self.blink = max(0.0, self.blink - dt)
        self.peck = max(0.0, self.peck - dt)
        self.quack_t = max(0.0, self.quack_t - dt)
        self.startle = max(0.0, self.startle - dt)
        self.shaken = max(0.0, self.shaken - dt)

        # açlık işaretleri
        self.hunger_t += dt
        if self.app.hungry() and not self.app.sulky() and self.hunger_t > 40 and self.mood != "sleep":
            self.hunger_t = 0.0
            self.spawn("🍞", emoji=True, size=16)

        for pt in self.particles:
            pt["x"] += pt["vx"] * dt
            pt["y"] += pt["vy"] * dt
            pt["life"] -= dt
        self.particles = [pt for pt in self.particles if pt["life"] > 0]

        self.move(int(self.wx), int(self.wy))
        self.update()

    def set_mood(self, mood):
        old, self.mood = self.mood, mood
        self.action_left = 0
        if old != mood:
            self.app.hook("ruh_hali", old, mood)
        if old == "sleep":
            if self.mode == "nest":
                self.exit_nest()
            else:
                self.jump(-300)
        if mood == "music":
            self.spawn("♪", "#9B6BFF", count=3, spread=18)
        elif mood == "focus" and old != "focus":
            self.spawn("✨", emoji=True, count=2, size=16, spread=20)   # bandını takıp hazırlanır
            self.jump(-200)
            self.emit_t = 0.0
        elif mood == "game":
            self.jump(-320, hops=1)

    # ----- çizim -----
    def current_pose(self):
        a, m = self.action, self.mode
        sleeping = a == "sleep" and m not in ("drag", "fall", "flight")
        pose = {"x": self.W / 2, "y": self.H - self.FOOT + self.jump_y, "facing": self.dir,
                "scale": self.SCALE, "leg_phase": self.phase, "t": self.t,
                "outfit": self.app.outfit_set(sleeping)}
        if m in ("drag", "fall", "flight"):
            pose.update(legs="dangle", eyes="wide" if m != "flight" else "open",
                        wing=abs(math.sin(self.t * (14 if m == "flight" else 10))) * 48,
                        rot=-6 if m == "flight" else math.sin(self.t * 18) * 9)
            if m == "drag":
                pose["y"] = self.H - self.FOOT - 4
        else:
            pose["sit"] = a in ("sit", "eat", "sleep", "type") or m == "nest"
            if a in ("walk", "backstep"):
                pose.update(legs="walk", bob=abs(math.sin(self.phase)) * 2.5)
            elif a in ("run", "flee", "chase") and (self.goal or a != "chase"
                                                     or abs(QCursor.pos().x() - self.center_x()) > 30):
                pose.update(legs="run", bob=abs(math.sin(self.phase)) * 4, rot=7,
                            wing=abs(math.sin(self.phase)) * 18)
            elif a == "dance":
                pose.update(legs="walk", bob=abs(math.sin(self.phase * 2)) * 5,
                            rot=math.sin(self.phase) * 8, wing=abs(math.sin(self.phase * 2)) * 26)
            elif a == "sleep":
                pose.update(head=(-2, 7), bob=math.sin(self.t * 2.2) * 1.2)
            elif a == "eat":
                k = self.t % 2.4
                d = math.sin(math.pi * k / 0.5) if k < 0.5 else 0
                pose.update(head=(5 * d, 18 * d), prop="popcorn")
            elif a == "type":
                pose.update(head=(3, 5), prop="laptop")
            elif a == "peck_food":
                d = math.sin(math.pi * (1 - self.peck / 0.28)) if self.peck else 0
                pose.update(rot=40 * d, head=(2 * d, 26 * d))
            if self.peck and a != "peck_food":
                d = math.sin(math.pi * (1 - self.peck / 0.45))
                pose["head"] = (4 * d, 12 * d)
            if self.mood == "game" and a in ("hop", "idle"):
                pose["prop"] = "gamepad"
                pose["wing"] = -6 + abs(math.sin(self.t * 14)) * 6
            if self.mood == "social" and a in ("idle", "sit"):
                pose["prop"] = "phone"
                pose["head"] = (2, 4)
            if (self.notice and "prop" not in pose and not self.peck
                    and a not in ("sleep", "eat", "type", "peck_food", "dance")):
                pose["head"] = (1, -3)                     # merakla imlece bakar
                pose["rot"] = pose.get("rot", 0) - 4
            if self.thinking:
                pose["head"] = (-2, -2)
                pose["rot"] = -5 + math.sin(self.t * 3) * 2
            if self.shaken:
                pose["wing"] = abs(math.sin(self.t * 30)) * 35
                pose["rot"] = math.sin(self.t * 28) * 6
        pose["headphones"] = self.mood == "music"
        pose["glasses"] = self.mood == "focus"
        pose["headband"] = self.mood == "focus" and not sleeping
        sulky = self.app.sulky() and not sleeping
        if sulky:
            pose["brow"] = True
        if "eyes" not in pose:
            if sleeping or self.blink:
                pose["eyes"] = "closed"
            elif self.startle or self.shaken:
                pose["eyes"] = "wide"
            elif self.mood == "night" or sulky:
                pose["eyes"] = "half"
            else:
                pose["eyes"] = "open"
        if self.quack_t:
            pose["quack"] = True
            pose["wing"] = max(pose.get("wing", 0), 20)
        self.app.hook("poz", pose)          # eklentiler duruşu değiştirebilir / çizim ekleyebilir
        return pose

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        pose = self.current_pose()
        S = self.SCALE
        if self.mode == "nest":
            base = self.H - self.FOOT
            p.save()
            p.translate(self.W / 2, base)
            p.scale(S, S)
            cizim.draw_nest(p, 0, 0, eggs=self.app.egg_count(), part="back")
            p.restore()
            pose["y"] = base - 16 * S + self.jump_y
            cizim.draw_duck(p, pose)
            p.save()
            p.translate(self.W / 2, base)
            p.scale(S, S)
            cizim.draw_nest(p, 0, 0, part="front")
            p.restore()
        else:
            cizim.draw_duck(p, pose)

        if self.app.sulky() and self.mode not in ("drag", "fall"):
            s = (1 + 0.12 * math.sin(self.t * 6)) * S
            cizim.draw_anger(p, self.W / 2 - self.dir * 14 * S,
                             self.H - self.FOOT - 108 * S + self.jump_y, s)

        for pt in self.particles:
            c = QColor(pt["color"])
            a = max(0.0, min(1.0, pt["life"] / pt["max"] * 1.6))
            p.setOpacity(a)
            if pt["emoji"]:
                p.setFont(cizim.emoji_font(pt["size"] + 4))
            else:
                p.setFont(QFont("Segoe UI Symbol", pt["size"], QFont.Bold))
            p.setPen(c)
            p.drawText(QPointF(pt["x"], pt["y"]), pt["text"])
        p.setOpacity(1.0)

        if self.app.focus_end:
            # odak sayacı: başının biraz yukarısında, ördek renklerinde
            left = max(0.0, self.app.focus_end - time.time())
            head_top = self.H - self.FOOT - 98 * S + self.jump_y
            cizim.draw_focus_timer(p, self.W / 2 + self.dir * 6, head_top - 22 - 29 * 0.9,
                                   left, self.app.focus_total, self.t, scale=0.9)


# ---------------------------------------------------------------------------
# Hepsini yöneten kısım
# ---------------------------------------------------------------------------

class App:
    def __init__(self, qapp):
        self.qapp = qapp
        self.settings = ayarlar.ayarlari_yukle()
        self.state = ayarlar.oku("durum.json", ayarlar.VARSAYILAN_DURUM)
        self.full_screen_name = None
        self.last_hwnd, self.last_app, self.last_title = None, "", ""
        self.focus_end = None
        self.focus_total = 1.0
        self.crumbs = []
        self.duckling = None
        self.notes_win = None
        self.chat_win = None
        self.radial = None

        # eklentiler (eklentiler/ klasöründeki .py dosyaları) — logo ve menü için önce yüklenir
        self.plugins = eklentileri_yukle()
        self.notes = Notes(on_change=self.notes_changed)
        self.duck = Duck(self)

        now = time.monotonic()
        self.last_frame = now
        lo, hi = self.settings["kirinti_dakika"]
        self.next_crumb = now + random.uniform(lo, hi) * 60
        lo, hi = self.settings["yavru_dakika"]
        self.next_duckling = now + random.uniform(lo, hi) * 60

        self.timers = [
            QTimer(timeout=self.frame, interval=16),
            QTimer(timeout=self.check_activity, interval=1000),
            QTimer(timeout=self.reassert_top, interval=2000),
            QTimer(timeout=self.save_state, interval=30000),
        ]
        for t in self.timers:
            t.start()
        qapp.aboutToQuit.connect(self.save_state)

        self.setup_tray()
        self.duck.show()
        self.check_activity()
        # ördeği çağırma: ekranda bir yere ~1 sn SAĞ tuşla basılı tut
        self.press = None
        self.marker = CallMarker()
        self.tray.setToolTip("duckyduck — çağırmak için ekranda bir yere sağ tuşla 1 saniye basılı tut")
        # yeni kullanıcı: önce doğum günü (eklenti karşılama yazısı başlığa gelir), sonra ipucu kartı
        self.bday_win = None
        self.card = None
        self.greeting = None
        self.new_user = self.settings.get("dogum_gunu_sahibi") != ayarlar.sahip_kimligi()
        QTimer.singleShot(0, lambda: self.hook("baslat"))
        self.minute_timer = QTimer(timeout=lambda: self.hook("her_dakika"), interval=60000)
        self.minute_timer.start()
        if self.new_user:
            QTimer.singleShot(1500, self.ask_birthday)
        else:
            QTimer.singleShot(1500, self.maybe_celebrate)

        # her kurulumda: bilgisayar açılınca ördek kendiliğinden gelsin (bir kez ayarlanır)
        if not ayarlar.FROZEN and not self.state.get("oto_baslat_ayarlandi"):
            self.state["oto_baslat_ayarlandi"] = True
            if autostart_value() is None:
                set_autostart(True)

    # ----- eklentiler ve bildirimler -----
    def hook(self, name, *args):
        for mod in getattr(self, "plugins", []):
            fn = getattr(mod, name, None)
            if callable(fn):
                try:
                    fn(self, *args)
                except Exception:
                    eklenti_hatasi(getattr(mod, "__file__", "?"))

    def bildirim(self, text, seconds=8):
        """Saatin yanında küçük bir Windows bildirimi gösterir."""
        self.tray.showMessage("duckyduck", text, self.qapp.windowIcon(), int(seconds * 1000))

    # ----- ekranda sağ tuşa basılı tutunca çağırma -----
    def update_long_press(self, dt):
        down = bool(pw.user32.GetAsyncKeyState(0x02) & 0x8000)      # 0x02 = sağ fare tuşu
        pos = QCursor.pos()
        if not down:
            if self.press is not None:
                self.press = None
                if self.marker.burst <= 0:
                    self.marker.hide()
            return
        if self.press is None:
            on_own = QApplication.widgetAt(pos) is not None or self.duck.pressed
            self.press = {"pos": pos, "t": 0.0, "done": False,
                          "skip": on_own or self.duck.mood == "game"}
            return
        pr = self.press
        if pr["skip"] or pr["done"]:
            return
        if (pos - pr["pos"]).manhattanLength() > 10:      # sürükleme/seçme: çağırma değil
            pr["skip"] = True
            self.marker.hide()
            return
        pr["t"] += dt
        k = (pr["t"] - 0.25) / (LONG_PRESS - 0.25)          # ilk çeyrek saniye hiçbir şey göstermez
        if k > 0:
            self.marker.progress = min(1.0, k)
            self.marker.place(pr["pos"])
            if not self.marker.isVisible():
                self.marker.show()
            self.marker.update()
        if pr["t"] >= LONG_PRESS:
            pr["done"] = True
            self.marker.burst = 0.45
            self.duck.come_here(pr["pos"])

    # ----- doğum günü -----
    def karsilama(self, text):
        """Eklentiler için karşılama: yeni kullanıcıysa doğum günü penceresinin başlığına,
        değilse ekranın ortasında küçük bir kart olarak gösterilir."""
        if self.new_user:
            self.greeting = text
        else:
            self.show_card(text, "")

    def show_card(self, title, text, seconds=None):
        self.card = InfoCard(title, text, seconds)
        self.card.show_centered()

    def ask_birthday(self):
        mine = self.settings.get("dogum_gunu_sahibi") == ayarlar.sahip_kimligi()
        self.bday_win = BirthdayDialog(self.set_birthday,
                                       self.settings.get("dogum_gunu", "") if mine else "",
                                       greeting=self.greeting)
        self.bday_win.show_centered()

    def set_birthday(self, mmdd):
        self.settings["dogum_gunu"] = mmdd
        self.settings["dogum_gunu_sahibi"] = ayarlar.sahip_kimligi()
        ayarlar.yaz("ayarlar.json", self.settings)
        self.duck.quack()
        self.duck.hearts(3)
        self.maybe_celebrate()
        if self.new_user and not self.state.get("ipucu_kart"):
            self.state["ipucu_kart"] = True
            self.new_user = False
            QTimer.singleShot(600, lambda: self.show_card(
                "Beni nasıl çağırırsın?",
                "Ekranda istediğin yere sağ tuşla 1 saniye basılı tut, hemen gelirim. "
                "Bana sağ tıklarsan menüm açılır, tıklarsan sohbet ederiz 💛"))

    def maybe_celebrate(self):
        bd = self.settings.get("dogum_gunu")
        if bd and datetime.now().strftime("%m-%d") == bd:
            self.duck.jump(-340, hops=3)
            for ch in "🎉🎂🎈":
                self.duck.spawn(ch, emoji=True, size=18, spread=24)

    # ----- ortak -----
    def ground_bottom(self, screen):
        geo = screen.geometry() if screen.name() == self.full_screen_name else screen.availableGeometry()
        return geo.bottom()

    def egg_count(self):
        return min(5, len(self.notes.items))

    def notes_changed(self):
        self.duck.update()

    def hungry(self):
        return self.state["aclik_sn"] > self.settings["aciktim_saat"] * 3600

    def sulky(self):
        return (self.state["aclik_sn"] > self.settings["kusme_saat"] * 3600
                and self.duck.mood != "sleep")

    def fed(self):
        was_sulky = self.sulky()
        self.state["aclik_sn"] = 0.0
        self.duck.hearts(3)
        self.duck.quack()
        if was_sulky:
            self.duck.hops = 2

    def outfit_set(self, sleeping=False):
        mode = self.state.get("kiyafet", "otomatik")
        now = datetime.now()
        if mode == "otomatik":
            md = now.strftime("%m-%d")
            if md == self.settings.get("dogum_gunu") or md in ("12-31", "01-01"):
                s = {"party"}
            elif now.month in (12, 1, 2):
                s = {"beanie", "scarf"}
            elif now.month in (3, 4, 5):
                s = {"flower"}
            elif now.month in (6, 7, 8):
                s = {"sunglasses"} if 10 <= now.hour < 18 else set()
            else:
                s = {"scarf_autumn"}
            if sleeping or now.hour < 6:
                s = (s - HATS - {"sunglasses"}) | ({"nightcap"} if sleeping else set())
        else:
            s = set(OUTFIT_SETS.get(mode, set()))
            if sleeping:
                s -= {"sunglasses"}
        return s

    def screen_context(self):
        if not self.settings["sohbet"].get("ekran_bilgisi", True) or not self.last_app:
            return ""
        return f"{self.last_app} — {self.last_title[:90]}"

    def radial_open(self):
        return self.radial is not None and self.radial.isVisible()

    # ----- zamanlayıcılar -----
    def frame(self):
        now = time.monotonic()
        dt = min(0.05, now - self.last_frame)
        self.last_frame = now
        self.state["aclik_sn"] += dt

        self.duck.step(dt)
        self.update_long_press(dt)
        if self.marker.burst > 0:
            self.marker.burst = max(0.0, self.marker.burst - dt)
            self.marker.update()
            if self.marker.burst == 0:
                self.marker.hide()
        for c in self.crumbs:
            c.step(dt)
        self.crumbs = [c for c in self.crumbs if not c.dead]
        if self.duckling:
            self.duckling.step(dt)

        if now >= self.next_crumb:
            lo, hi = self.settings["kirinti_dakika"]
            self.next_crumb = now + random.uniform(lo, hi) * 60
            if len(self.crumbs) < 3:
                geo = self.duck.screen_obj().geometry()
                self.spawn_crumb(random.uniform(geo.left() + 120, geo.right() - 120))

        if now >= self.next_duckling:
            lo, hi = self.settings["yavru_dakika"]
            self.next_duckling = now + random.uniform(lo, hi) * 60
            if not self.duckling and not self.sulky() and self.duck.mood != "sleep":
                self.spawn_duckling(stay=random.uniform(180, 360))

        if self.focus_end and time.time() >= self.focus_end:
            self.focus_end = None
            self.duck.jump(-320, hops=3)
            self.duck.hearts(4)
            QApplication.beep()
            self.check_activity()

    def check_activity(self):
        info = pw.foreground_info()
        if info and info["pid"] == pw.OWN_PID:
            return
        if info:
            self.last_hwnd, self.last_app, self.last_title = info["hwnd"], info["proc"], info["title"]

        full_name = None
        if info and info["fullscreen"] and info["monitor"]:
            m = info["monitor"]
            lx, ly = pw.to_logical((m[0] + m[2]) // 2, (m[1] + m[3]) // 2)
            scr = QApplication.screenAt(QPoint(int(lx), int(ly)))
            full_name = scr.name() if scr else None
        if full_name != self.full_screen_name:
            self.full_screen_name = full_name
            for c in self.crumbs:
                scr = QApplication.screenAt(QPoint(int(c.cx), int(c.bottom - 10))) or QApplication.primaryScreen()
                c.set_bottom(self.ground_bottom(scr))

        mood = classify(info)
        if self.focus_end:
            mood = "focus"
        if (mood not in ("watch", "music")
                and pw.idle_seconds() >= self.settings["uyku_dakika"] * 60):
            mood = "sleep"
        if mood == "normal" and datetime.now().hour < 6:
            mood = "night"
        if mood != self.duck.mood:
            self.duck.set_mood(mood)
        if os.environ.get("ORDEK_DEBUG"):
            d = self.duck
            print(f"{d.mood:6s} {d.mode:6s} {d.action:9s} app={self.last_app} "
                  f"full={full_name} pos={int(d.wx)},{int(d.wy)}", flush=True)

    def reassert_top(self):
        for w in [*self.crumbs, self.duckling, self.duck]:
            if w is not None:
                pw.keep_on_top(w)

    def save_state(self):
        ayarlar.yaz("durum.json", self.state)
        self.notes.save()

    # ----- komutlar -----
    def open_radial(self):
        d = self.duck
        nm = dict(OUTFITS)[self.state.get("kiyafet", "otomatik")]
        items = [
            (icon_nest, "Yuva · notlarım", self.open_notes),
            (icon_crumb, "Yem ver", self.feed_now),
            ("⏳", "Odağı bitir" if self.focus_end
             else f"Odak ({self.settings['odak_dakika']} dk)", self.toggle_focus),
            ("💬", "Sohbet", self.open_chat),
            ("🐣", "Yavruyu gönder" if self.duckling else "Yavruyu çağır", self.toggle_duckling),
            ("🎀", f"Kıyafet: {nm}", self.cycle_outfit),
            ("🪟", "Aşağı in" if d.mode == "perch" else "Pencereye çık", self.toggle_perch),
            ("▶️" if d.still else "⏸️", "Devam et" if d.still else "Yerinde dur", self.toggle_still),
        ]
        for mod in getattr(self, "plugins", []):           # eklentilerin menü düğmeleri
            fn = getattr(mod, "menu_ogeleri", None)
            if callable(fn):
                try:
                    items.extend(fn(self) or [])
                except Exception:
                    eklenti_hatasi(getattr(mod, "__file__", "?"))
        items.append(("✖️", "Kapat", self.qapp.quit))
        center = QPointF(d.wx + d.W / 2, d.feet_y() - 48 * d.SCALE + d.jump_y)
        self.radial = RadialMenu(items, center)
        self.radial.show()

    def open_notes(self):
        if self.notes_win and self.notes_win.isVisible():
            self.notes_win.raise_()
            self.notes_win.activateWindow()
            return
        if not self.notes_win:
            self.notes_win = NotesWindow(self, self.notes)
        d = self.duck
        self.notes_win.show_near(d.center_x(), d.feet_y() - 100)

    def open_chat(self):
        if not self.chat_win:
            self.chat_win = ChatWindow(self)
        d = self.duck
        self.chat_win.show_near(d.center_x(), d.feet_y() - 110)

    def toggle_chat(self):
        if self.chat_win and self.chat_win.isVisible():
            self.chat_win.close()
        else:
            self.open_chat()

    def spawn_crumb(self, cx, drop=260):
        scr = QApplication.screenAt(QPoint(int(cx), int(self.duck.feet_y() - 20))) or self.duck.screen_obj()
        c = Crumb(self, cx, self.ground_bottom(scr), drop)
        self.crumbs.append(c)
        c.show()
        return c

    def feed_now(self):
        d = self.duck
        lo, hi = d.x_bounds()
        for k in range(3):
            side = random.choice((-1, 1))
            x = d.center_x() + side * random.uniform(90, 170)
            x = max(lo + d.W / 2, min(x, hi + d.W / 2))
            c = self.spawn_crumb(x, drop=random.uniform(200, 320))
            d.go_eat(c)

    def toggle_focus(self):
        if self.focus_end:
            self.focus_end = None
            self.check_activity()
        else:
            self.focus_total = self.settings["odak_dakika"] * 60
            self.focus_end = time.time() + self.focus_total
            self.duck.set_mood("focus")

    def spawn_duckling(self, stay=None):
        self.duckling = Duckling(self, stay)
        self.duckling.show()
        if self.duck.faded:
            pw.set_click_through(self.duckling, True)
            self.duckling.setWindowOpacity(self.duck.opacity)
        self.duck.hearts(2)

    def remove_duckling(self):
        if self.duckling:
            self.duckling.close()
            self.duckling = None

    def toggle_duckling(self):
        if self.duckling and not self.duckling.leaving:
            self.duckling.leave()
        elif not self.duckling:
            self.spawn_duckling(stay=None)

    def cycle_outfit(self):
        keys = [k for k, _ in OUTFITS]
        cur = self.state.get("kiyafet", "otomatik")
        self.state["kiyafet"] = keys[(keys.index(cur) + 1) % len(keys)] if cur in keys else "otomatik"
        self.duck.jump(-260)
        self.duck.spawn("✨", emoji=True, size=16)

    def toggle_perch(self):
        d = self.duck
        if d.mode == "perch":
            d.drop_off()
        elif not d.try_perch(self.last_hwnd):
            d.startle = 0.5
            d.jump(-200)

    def toggle_still(self):
        self.duck.still = not self.duck.still
        self.duck.action_left = 0

    # ----- tepsi simgesi -----
    def setup_tray(self):
        ekstra = [m.logo_ekstra for m in self.plugins if callable(getattr(m, "logo_ekstra", None))]
        icon = logo.logo_icon(ekstra)
        self.qapp.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("duckyduck")
        menu = QMenu()

        def fill():
            menu.clear()
            menu.addAction("Notlar", self.open_notes)
            menu.addAction("Sohbet", self.open_chat)
            menu.addAction("Yanıma gel", self.duck.come_here)
            menu.addAction("Doğum günümü değiştir", self.ask_birthday)
            a = menu.addAction("Bilgisayarla başlasın",
                               lambda: set_autostart(autostart_value() is None))
            a.setCheckable(True)
            a.setChecked(autostart_value() is not None)
            menu.addSeparator()
            if ayarlar.FROZEN:
                menu.addAction("duckyduck'ı bilgisayardan kaldır", lambda: exe_kaldir(self.qapp))
            menu.addAction("Kapat", self.qapp.quit)

        menu.aboutToShow.connect(fill)
        self.tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.duck.come_here() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()


# --- Tek .exe sürümü: ilk açılışta kendini kurar -------------------------------

LOCAL_SERVER = "OrdekMasaustuArkadasi_kanal"

INSTALL_DIR = os.environ.get("ORDEK_INSTALL_DIR") or os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "duckyduck")
NO_WINDOW = 0x08000000


def _powershell(cmd):
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                   creationflags=NO_WINDOW, check=False)


def _shortcuts(target, remove=False):
    """Masaüstü + Başlat menüsü kısayolu. Aynı adda BAŞKA bir programın kısayolu varsa ona
    dokunmaz, "duckyduck 2" adıyla açar; kaldırırken yalnızca bu exe'yi gösterenleri siler."""
    t = target.replace("'", "''")
    d = os.path.dirname(target).replace("'", "''")
    sh = "$sh=New-Object -ComObject WScript.Shell;"
    for folder in ("Desktop", "Programs"):
        base = f"[Environment]::GetFolderPath('{folder}')"
        if remove:
            _powershell(sh + f"foreach($n in 'duckyduck.lnk','duckyduck 2.lnk'){{"
                        f"$p=Join-Path ({base}) $n;"
                        f"if((Test-Path $p) -and ($sh.CreateShortcut($p).TargetPath -eq '{t}')){{Remove-Item -Force $p}}}}")
        else:
            _powershell(sh + f"$p=Join-Path ({base}) 'duckyduck.lnk';"
                        f"if((Test-Path $p) -and ($sh.CreateShortcut($p).TargetPath -ne '{t}')){{"
                        f"$p=Join-Path ({base}) 'duckyduck 2.lnk'}};"
                        f"$s=$sh.CreateShortcut($p);$s.TargetPath='{t}';$s.WorkingDirectory='{d}';"
                        f"$s.IconLocation='{t},0';$s.Description='duckyduck';$s.Save()")


def exe_kur():
    """İndirilen duckyduck.exe'ye çift tıklanınca: kendini kurar, kısayol açar, ördeği başlatır.
    True dönerse bu (indirilen) kopya kapanmalıdır."""
    if not ayarlar.FROZEN or os.environ.get("ORDEK_NO_INSTALL"):
        return False
    if os.path.normcase(os.path.dirname(sys.executable)) == os.path.normcase(INSTALL_DIR):
        return False                                        # zaten kurulu yerden açıldı
    target = os.path.join(INSTALL_DIR, "duckyduck.exe")
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        shutil.copy2(sys.executable, target)
    except OSError:
        QMessageBox.information(None, "duckyduck", "duckyduck şu an açık görünüyor. Önce saatin yanındaki "
                                "ördek simgesine sağ tıklayıp “Kapat” de, sonra tekrar dene.")
        return True
    if not os.environ.get("ORDEK_SKIP_SYSTEM"):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, f'"{target}"')
        _shortcuts(target)
    subprocess.Popen([target], close_fds=True, creationflags=0x00000008)   # DETACHED_PROCESS
    return True


def exe_kaldir(qapp):
    """Tray menüsünden: kısayolları, başlangıç kaydını ve programı kaldırır (notlar kalır)."""
    ans = QMessageBox.question(None, "duckyduck", "duckyduck bilgisayarından kaldırılsın mı?\n"
                               "(Notların %APPDATA%\\duckyduck klasöründe saklı kalır.)")
    if ans != QMessageBox.Yes:
        return
    set_autostart(False)
    _shortcuts(sys.executable, remove=True)
    folder = os.path.dirname(sys.executable)
    subprocess.Popen(f'cmd /c timeout /t 2 /nobreak >nul & rmdir /s /q "{folder}"',
                     creationflags=NO_WINDOW | 0x00000008, close_fds=True)
    qapp.quit()


def main():
    qapp = QApplication(sys.argv)
    if exe_kur():
        return
    qapp._mutex, first = pw.single_instance("Local\\OrdekMasaustuArkadasi")
    if not first:
        # ördek zaten açık: kısayola tekrar tıklandıysa ördeği yanına çağır
        sock = QLocalSocket()
        sock.connectToServer(LOCAL_SERVER)
        if sock.waitForConnected(500):
            sock.write(b"gel")
            sock.waitForBytesWritten(500)
            sock.disconnectFromServer()
        return
    if not ayarlar.FROZEN:
        # eski adlarla kaydedilmiş başlangıç kayıtlarını yeni ada ("duckyduck") taşı
        for old in ("Ordek", "duckduck"):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                    winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as k:
                    winreg.QueryValueEx(k, old)
                    winreg.DeleteValue(k, old)
                set_autostart(True)
            except OSError:
                pass
        if autostart_value() not in (None, autostart_command()):
            set_autostart(True)          # klasör taşındıysa başlangıç kaydını güncelle
    qapp.setQuitOnLastWindowClosed(False)
    qapp._ordek = App(qapp)
    QLocalServer.removeServer(LOCAL_SERVER)
    server = QLocalServer()
    server.listen(LOCAL_SERVER)

    def on_message():
        conn = server.nextPendingConnection()
        if conn is None:
            return

        def read():
            if b"gel" in bytes(conn.readAll()):
                qapp._ordek.duck.come_here()
                qapp._ordek.duck.hearts(2)
        conn.readyRead.connect(read)
        if conn.bytesAvailable():
            read()

    server.newConnection.connect(on_message)
    qapp._server = server
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
