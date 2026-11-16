"""Sağ tıklayınca ördeğin çevresinde yay şeklinde açılan komutlar.

Yay, bütün düğmeler ekranın içinde kalacak şekilde döndürülür/büyütülür:
ördek ekranın altındaysa yukarı doğru, köşedeyse yana doğru açılır.
"""

import math

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

import cizim

BTN = 25           # düğme yarıçapı
MARGIN = BTN + 8   # ekran kenarına en az bu kadar uzak


def _layout(n, center, area):
    """Ekrana sığan (yarıçap, açılar) bul. Açılar derece; 90 = yukarı."""
    cx, cy = center.x(), center.y()

    def fits(R, angles):
        for a in angles:
            x = cx + R * math.cos(math.radians(a))
            y = cy - R * math.sin(math.radians(a))
            if not (area.left() + MARGIN <= x <= area.right() - MARGIN
                    and area.top() + MARGIN <= y <= area.bottom() - MARGIN):
                return False
        return True

    orients = [90, 70, 110, 50, 130, 30, 150, 10, 170, 270, 250, 290, 0, 180]
    for R in (125, 140, 158, 178):
        for span in (180, 160, 140, 200, 230):
            step = span / max(1, n - 1)
            if R * math.radians(step) < 2 * BTN + 5:      # düğmeler üst üste binmesin
                continue
            for o in orients:
                angles = [o + span / 2 - i * step for i in range(n)]
                if fits(R, angles):
                    return R, angles
    # hiçbiri olmadıysa: yukarı doğru, sonra ekrana kaydırılacak
    R, span = 150, 180
    return R, [90 + span / 2 - i * span / max(1, n - 1) for i in range(n)]


class RadialMenu(QWidget):
    def __init__(self, items, center):
        """items: [(ikon, yazı, fonksiyon)]; ikon bir emoji ya da çizen fonksiyon(p, pos, r)."""
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.items = items
        self.hover = None
        self.prog = 0.0

        scr = (QApplication.screenAt(QPoint(int(center.x()), int(center.y())))
               or QApplication.primaryScreen())
        area = scr.availableGeometry()
        # ördek görev çubuğunun üstündeyse availableGeometry onu da kapsasın
        if center.y() > area.bottom():
            area = scr.geometry()
        self.R, angles = _layout(len(items), center, area)

        # sığmadıysa merkezi ekranın içine kaydır
        cx, cy = center.x(), center.y()
        for a in angles:
            x = cx + self.R * math.cos(math.radians(a))
            y = cy - self.R * math.sin(math.radians(a))
            cx += max(0, area.left() + MARGIN - x) - max(0, x - (area.right() - MARGIN))
            cy += max(0, area.top() + MARGIN - y) - max(0, y - (area.bottom() - MARGIN))

        self.dirs = [(math.cos(math.radians(a)), -math.sin(math.radians(a))) for a in angles]
        self.S = int(2 * (self.R + BTN + 70))
        self.setFixedSize(self.S, self.S)
        self.c = QPointF(self.S / 2, self.S / 2)
        self.move(int(cx - self.S / 2), int(cy - self.S / 2))

        self.timer = QTimer(self, interval=16, timeout=self._anim)
        self.timer.start()

    def _anim(self):
        self.prog = min(1.0, self.prog + 0.09)
        self.update()
        if self.prog >= 1.0:
            self.timer.stop()

    def _ease(self):
        t = self.prog
        return 1 + 2.4 * (t - 1) ** 3 + 1.4 * (t - 1) ** 2   # hafif yaylanma

    def _pos(self, i, ease=None):
        e = self._ease() if ease is None else ease
        dx, dy = self.dirs[i]
        return QPointF(self.c.x() + dx * self.R * e, self.c.y() + dy * self.R * e)

    def _hit(self, pt):
        for i in range(len(self.items)):
            d = self._pos(i, 1.0) - pt
            if math.hypot(d.x(), d.y()) < BTN * 1.25:
                return i
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position())
        if h != self.hover:
            self.hover = h
            self.setCursor(Qt.PointingHandCursor if h is not None else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, e):
        i = self._hit(e.position())
        self.close()
        if i is not None:
            QTimer.singleShot(0, self.items[i][2])

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setOpacity(min(1.0, self.prog * 1.6))
        for i, (icon, label, _) in enumerate(self.items):
            pos = self._pos(i)
            r = BTN * (1.16 if i == self.hover else 1.0)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(120, 80, 30, 45))
            p.drawEllipse(pos + QPointF(0, 3), r, r)
            p.setPen(QPen(QColor("#F7A21E"), 2.6))
            p.setBrush(QColor("#FFE2AE") if i == self.hover else QColor("#FFF3DC"))
            p.drawEllipse(pos, r, r)
            if callable(icon):
                icon(p, pos, r)
            else:
                p.setPen(QColor("black"))
                p.setFont(cizim.emoji_font(r * 0.95))
                p.drawText(QRectF(pos.x() - r, pos.y() - r, 2 * r, 2 * r), Qt.AlignCenter, icon)

        if self.hover is not None and self.prog > 0.6:
            label = self.items[self.hover][1]
            font = QFont("Segoe UI", 9, QFont.Bold)
            p.setFont(font)
            w = QFontMetrics(font).horizontalAdvance(label) + 20
            dx, dy = self.dirs[self.hover]
            pos = self._pos(self.hover)
            rect = QRectF(pos.x() + dx * 52 - w / 2, pos.y() + dy * 42 - 11, w, 22)
            rect.moveLeft(max(2, min(rect.left(), self.S - w - 2)))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#B8682C"))
            p.drawRoundedRect(rect, 11, 11)
            p.setPen(QColor("white"))
            p.drawText(rect, Qt.AlignCenter, label)
