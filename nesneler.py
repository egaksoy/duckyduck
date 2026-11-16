"""Ekrana düşen ekmek kırıntıları ve ördeğin peşinden gelen yavru."""

import math
import random

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QApplication, QWidget

import cizim
import pencereler as pw

FLAGS = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
         | Qt.WindowDoesNotAcceptFocus)


class Crumb(QWidget):
    S = 34
    LIFE = 240.0     # saniye; tıklanmazsa sonra kaybolur

    def __init__(self, app, cx, bottom, drop=260):
        super().__init__(None, FLAGS)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(self.S, self.S)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Ördeği besle!")
        self.cx = cx
        self.bottom = bottom
        self.y = bottom - drop
        self.vy = 0.0
        self.landed = False
        self.age = 0.0
        self.seed = random.randint(0, 9999)
        self.rot = random.uniform(0, 360)
        self.spin = random.uniform(-300, 300)
        self.reserved = False
        self.dead = False
        self._place()

    def set_bottom(self, bottom):
        if bottom != self.bottom:
            self.bottom = bottom
            self.landed = False

    def step(self, dt):
        if self.dead:
            return
        if not self.landed:
            self.vy += 1900 * dt
            self.y += self.vy * dt
            self.rot += self.spin * dt
            if self.y >= self.bottom:
                self.y = self.bottom
                if self.vy > 300:
                    self.vy = -self.vy * 0.3
                    self.spin *= 0.4
                else:
                    self.vy, self.landed = 0.0, True
            elif self.y < self.bottom - 2000:
                self.y = self.bottom
        self.age += dt
        if self.age > self.LIFE and not self.reserved:
            self.eat()
            return
        self._place()
        self.update()

    def _place(self):
        self.move(int(self.cx - self.S / 2), int(self.y - self.S + 6))

    def eat(self):
        self.dead = True
        self.close()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left = self.LIFE - self.age
        if left < 3:
            p.setOpacity(max(0.0, left / 3))
        cizim.draw_crumb(p, self.S / 2, self.S - 7, self.seed, self.rot * 0.3,
                         shadow=self.landed)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.app.duck.go_eat(self)


class Duckling(QWidget):
    W, H, FOOT = 110, 90, 6
    SCALE = 0.44          # ördeğin (0.8) yarısından biraz büyük

    def __init__(self, app, stay=None):
        super().__init__(None, FLAGS)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(self.W, self.H)
        duck = app.duck
        geo = duck.screen_obj().geometry()
        from_left = duck.center_x() > geo.center().x()      # uzak kenardan gelsin
        self.dir = 1 if from_left else -1
        self.wx = (geo.left() - self.W) if from_left else (geo.right())
        self.wy = duck.feet_y() - self.H / 2
        self.wy = self._ground_y()
        self.stay = stay
        self.leaving = False
        self.leave_x = None
        self.phase = 0.0
        self.moving = True
        self.jump_y = self.jump_v = 0.0
        self.t = 0.0
        self.blink = 0.0
        self.fast = False
        self.duck_was_up = False
        self.mode = "ground"          # ground / fly / perch / fall
        self.fl = None
        self.vy = 0.0
        self.fly_wait = 0.0
        # sakarlık: ara sıra tökezleyip düşer, başı döner, kalkar, şaşırır, vaklar
        self.tripping = False
        self.trip = 0.0
        self.next_trip = random.uniform(25, 60)
        self.huh_done = self.quack_done = False
        self.quack_t = 0.0
        self.particles = []
        self.move(int(self.wx), int(self.wy))

    def center_x(self):
        return self.wx + self.W / 2

    def body_rect(self):
        """Yavrunun ekrandaki gövdesi (saydamlaşma için)."""
        feet = self.wy + self.H - self.FOOT + self.jump_y
        return QRect(int(self.center_x() - 26), int(feet - 52), 52, 54)

    def _screen(self):
        return (QApplication.screenAt(QPoint(int(self.center_x()), int(self.wy + self.H / 2)))
                or self.app.duck.screen_obj())

    def _ground_y(self):
        return self.app.ground_bottom(self._screen()) + 1 - (self.H - self.FOOT)

    def leave(self):
        if self.leaving:
            return
        self.leaving = True
        geo = self._screen().geometry()
        go_left = self.center_x() < geo.center().x()
        self.leave_x = geo.left() - 150 if go_left else geo.right() + 150

    def hop(self):
        if self.jump_y == 0 and not self.tripping:
            self.jump_v = -260

    # ----- ördek bir pencerenin üstündeyse o pencere -----
    def _duck_window(self):
        duck = self.app.duck
        if self.leaving:
            return None
        h = None
        if duck.mode == "perch":
            h = duck.perch
        elif duck.mode == "flight" and duck.flight:
            h = duck.flight.get("hwnd")
        if not h or not pw.window_alive(h):
            return None
        return pw.logical_frame(h)

    def _perch_target(self, f):
        duck = self.app.duck
        cx = max(f[0] + 28, min(duck.center_x() - duck.dir * 94, f[2] - 28))
        return cx - self.W / 2, f[1] - (self.H - self.FOOT)

    def _follow(self, tx, dt, lo=None, hi=None):
        if lo is not None:
            tx = max(lo, min(tx, hi))
        dx = tx - self.center_x()
        if abs(dx) > 10 and not self.tripping:
            speed = 330 if abs(dx) > 170 or self.leaving else 150
            self.dir = 1 if dx > 0 else -1
            self.wx += self.dir * min(abs(dx), speed * dt)
            self.phase += speed * dt * 0.32
            self.moving = True
            self.fast = speed > 200
        else:
            self.moving = self.fast = False
            if not self.tripping:
                self.dir = self.app.duck.dir     # ördek nereye bakıyorsa oraya bakar

    def step(self, dt):
        duck = self.app.duck
        self.t += dt
        if self.stay is not None and not self.leaving:
            self.stay -= dt
            if self.stay <= 0:
                self.leave()

        f = self._duck_window()
        if f is not None and self.mode in ("ground", "fall"):
            self.fly_wait += dt
            if self.fly_wait > 0.3 and not self.tripping:   # ördeğin ardından havalanır
                self.fly_wait = 0.0
                tx, ty = self._perch_target(f)
                dist = math.hypot(tx - self.wx, ty - self.wy)
                self.fl = {"t": 0.0, "sx": self.wx, "sy": self.wy,
                           "dur": max(0.5, min(1.4, dist / 600)), "arc": 40 + min(120, dist * 0.18)}
                self.mode = "fly"
        elif f is None:
            self.fly_wait = 0.0
            if self.mode in ("fly", "perch"):
                self.mode, self.vy, self.fl = "fall", -120.0, None

        if self.mode == "fly":
            fl = self.fl
            fl["t"] += dt
            tx, ty = self._perch_target(f)
            s = min(1.0, fl["t"] / fl["dur"])
            e = s * s * (3 - 2 * s)
            self.dir = 1 if tx >= fl["sx"] else -1
            self.wx = fl["sx"] + (tx - fl["sx"]) * e
            self.wy = fl["sy"] + (ty - fl["sy"]) * e - math.sin(math.pi * s) * fl["arc"]
            self.phase += dt * 12
            if s >= 1.0:
                self.mode, self.fl = "perch", None
                self.hop()
        elif self.mode == "fall":
            self.vy = min(self.vy + 2600 * dt, 1500)
            self.wy += self.vy * dt
            g = self._ground_y()
            if self.wy >= g:
                self.wy, self.mode = g, "ground"
                self.hop()
        elif self.mode == "perch":
            self.wy = f[1] - (self.H - self.FOOT)
            self._follow(duck.center_x() - duck.dir * 94, dt, f[0] + 28, f[2] - 28)
        else:
            if self.leaving:
                tx = self.leave_x
            elif duck.mode == "nest":
                tx = duck.center_x() + 92
            elif duck.mode == "ground":
                tx = duck.center_x() - duck.dir * 94    # kuyruğun arkasında, gagası görünsün
            else:
                tx = duck.center_x() + 30               # ördek havadaysa altında bekler
            self._follow(tx, dt)
            self.wy = self._ground_y()

        # ördek zıplayınca o da zıplar
        duck_up = duck.jump_y < -2 and duck.jump_v < 0
        if duck_up and not self.duck_was_up and not self.leaving and self.mode in ("ground", "perch"):
            self.hop()
        self.duck_was_up = duck_up

        self._update_trip(dt)

        if self.jump_v or self.jump_y < 0:
            self.jump_v += 1900 * dt
            self.jump_y += self.jump_v * dt
            if self.jump_y >= 0:
                self.jump_y = self.jump_v = 0.0
        if self.blink <= 0 and random.random() < dt * 0.4:
            self.blink = 0.12
        self.blink = max(0.0, self.blink - dt)
        self.quack_t = max(0.0, self.quack_t - dt)
        for pt in self.particles:
            pt["y"] += pt["vy"] * dt
            pt["life"] -= dt
        self.particles = [pt for pt in self.particles if pt["life"] > 0]

        if self.leaving and self.mode == "ground":
            geo = self._screen().geometry()
            if self.wx > geo.right() + 20 or self.wx + self.W < geo.left() - 20:
                self.app.remove_duckling()
                return
        self.move(int(self.wx), int(self.wy))
        self.update()

    # ----- sakarlık -----
    T_FALL, T_LIE, T_UP, T_HUH = 0.22, 1.1, 0.35, 1.3     # her bölümün süresi (sn)

    def _update_trip(self, dt):
        duck = self.app.duck
        if self.tripping:
            self.trip += dt
            t_up_end = self.T_FALL + self.T_LIE + self.T_UP
            end = t_up_end + self.T_HUH
            if self.trip >= t_up_end and not self.huh_done:      # kalktı: kafası karıştı
                self.huh_done = True
                self.particles.append({"text": "?", "x": self.W / 2 + self.dir * 6,
                                       "y": self.H - self.FOOT - 46, "vy": -26, "life": 1.3})
            if self.trip >= end - 0.4 and not self.quack_done:   # sonunda vaklar
                self.quack_done = True
                self.quack_t = 0.35
            if self.trip >= end:
                self.tripping = False
                self.next_trip = random.uniform(30, 80)          # her zaman değil, arada bir
            return
        if (self.mode not in ("ground", "perch") or self.leaving
                or duck.mode == "nest" or duck.action == "sleep"):
            return
        self.next_trip -= dt * (1.0 if self.moving else 0.35)    # yürürken daha sakar
        if self.next_trip <= 0:
            self.tripping, self.trip = True, 0.0
            self.huh_done = self.quack_done = False
            self.moving = self.fast = False

    def _trip_pose(self, pose):
        t = self.trip
        lie = 82
        a, b, c = self.T_FALL, self.T_FALL + self.T_LIE, self.T_FALL + self.T_LIE + self.T_UP
        if t < a:                                   # tökezleyip öne düşer
            k = (t / a) ** 2
            pose.update(rot=lie * k, eyes="wide", wing=35 * k, legs="dangle")
        elif t < b:                                 # yüzüstü yatar, başı döner
            pose.update(rot=lie, eyes="dizzy", spin=self.t * 9,
                        wing=abs(math.sin(self.t * 10)) * 12)
            pose["y"] -= 3
        elif t < c:                                 # silkinip kalkar
            k = (t - b) / (c - b)
            pose.update(rot=lie * (1 - k) ** 2, eyes="closed", wing=20 * (1 - k))
        else:                                       # şaşkın şaşkın başını sallar
            k = (t - c) / self.T_HUH
            pose.update(head=(math.sin(k * 26) * 3 * (1 - k), 0), eyes="wide" if k < 0.5 else "open")
        if self.quack_t:
            pose.update(quack=True, wing=max(pose.get("wing", 0), 22))
        return pose

    # ördekten aynen kopyalanan duruş özellikleri
    COPY = ("sit", "legs", "bob", "rot", "head", "eyes", "wing", "quack",
            "glasses", "brow", "prop", "headphones", "headband")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        duck = self.app.duck
        dp = duck.current_pose()
        base_y = self.H - self.FOOT
        pose = {"x": self.W / 2, "y": base_y + self.jump_y, "baby": True,
                "scale": self.SCALE, "facing": self.dir, "leg_phase": self.phase,
                "t": self.t + 0.37, "outfit": set(dp.get("outfit", set()))}   # aynı kıyafet
        in_nest = False
        if self.mode in ("fly", "fall"):
            # kendisi uçuyor / düşüyor: kanat çırpar, ayaklar sallanır
            pose.update(legs="dangle", eyes="wide" if self.mode == "fall" else "open",
                        wing=abs(math.sin(self.t * 15)) * 48, rot=-6)
        elif self.tripping:
            self._trip_pose(pose)
        elif self.moving or self.leaving:
            # yetişmek için yürür/koşar ama kulaklık, gözlük, kaş gibi şeyleri korur
            pose.update(legs="run" if self.fast else "walk",
                        bob=abs(math.sin(self.phase)) * (3 if self.fast else 2),
                        rot=7 if self.fast else 0)
            for k in ("glasses", "brow", "headphones", "headband"):
                if k in dp:
                    pose[k] = dp[k]
        elif duck.mode in ("drag", "fall", "flight") and self.mode == "ground":
            # ördek havadayken (ve yavru yerdeyse) aşağıdan endişeyle bakıp kanat çırpar
            pose.update(eyes="wide", head=(0, -3), wing=abs(math.sin(self.t * 12)) * 30)
        else:
            for k in self.COPY:                # ördek ne yapıyorsa aynısı
                if k in dp:
                    pose[k] = dp[k]
            if pose.get("legs") in ("walk", "run") and duck.action not in ("dance",):
                pose["legs"] = "stand"
                pose["bob"] = 0
                pose["rot"] = 0
            in_nest = duck.mode == "nest"
        if self.blink and pose.get("eyes", "open") == "open":
            pose["eyes"] = "closed"

        if in_nest:                            # ördek yuvadaysa onun da minik yuvası olur
            p.save()
            p.translate(self.W / 2, base_y)
            p.scale(self.SCALE, self.SCALE)
            cizim.draw_nest(p, 0, 0, eggs=0, part="back")
            p.restore()
            pose["y"] = base_y - 16 * self.SCALE + self.jump_y
            cizim.draw_duck(p, pose)
            p.save()
            p.translate(self.W / 2, base_y)
            p.scale(self.SCALE, self.SCALE)
            cizim.draw_nest(p, 0, 0, part="front")
            p.restore()
        else:
            cizim.draw_duck(p, pose)

        # yüzüstü yatarken başının etrafında dönen yıldızlar
        if self.tripping and self.T_FALL < self.trip < self.T_FALL + self.T_LIE + 0.2:
            p.setPen(QColor("#FFD23F"))
            p.setFont(QFont("Segoe UI Symbol", 9, QFont.Bold))
            hx, hy = self.W / 2 + self.dir * 30, base_y - 16
            for i in range(3):
                a = self.t * 6 + i * 2.1
                p.drawText(QPointF(hx + math.cos(a) * 11 - 4, hy + math.sin(a) * 4), "✦")
        for pt in self.particles:
            p.setOpacity(max(0.0, min(1.0, pt["life"])))
            p.setPen(QColor("#6B7FA8"))
            p.setFont(QFont("Segoe UI", 13, QFont.Bold))
            p.drawText(QPointF(pt["x"], pt["y"]), pt["text"])
        p.setOpacity(1.0)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.hop()
