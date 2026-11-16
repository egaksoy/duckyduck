"""İlk açılışta doğum gününü soran küçük pencere."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QPushButton,
                               QVBoxLayout, QWidget)

import cizim

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
         "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUN_SAYISI = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

STYLE = """
QComboBox { background:#FFFDF7; border:2px solid #EBD5AE; border-radius:12px;
            padding:6px 12px; color:#5A4630; font: 11pt "Segoe UI"; min-width:70px; }
QComboBox:focus { border-color:#F7A21E; }
QComboBox::drop-down { border:none; width:22px; }
QComboBox QAbstractItemView { background:#FFFDF7; color:#5A4630; border:2px solid #EBD5AE;
            selection-background-color:#F9D59A; selection-color:#5A3D1E; outline:0; }
QPushButton#ana { background:#F7A21E; color:white; border:none; border-radius:14px;
                  padding:8px 18px; font: bold 10.5pt "Segoe UI"; }
QPushButton#ana:hover { background:#FFB540; }
QPushButton#ikincil { background:transparent; color:#B08458; border:none;
                      font: 9.5pt "Segoe UI"; text-decoration: underline; }
QPushButton#ikincil:hover { color:#8A5A25; }
"""


class InfoCard(QWidget):
    """Kısa bilgi kartı (bildirim yerine; gözden kaçmasın diye ekranın ortasında)."""
    W, H = 420, 300
    PANEL = QRectF(14, 96, 392, 194)

    def __init__(self, title, text, seconds=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)
        self.setStyleSheet(STYLE)
        self.title, self.text, self.t = title, text, 0.0
        ok = QPushButton("Tamam 🦆", objectName="ana", clicked=self.close)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 0, 40, 22)
        lay.addStretch()
        lay.addWidget(ok, 0, Qt.AlignHCenter)
        self.anim = QTimer(self, interval=40, timeout=self._tick)
        if seconds:
            QTimer.singleShot(int(seconds * 1000), self.close)

    def show_centered(self):
        a = QApplication.primaryScreen().availableGeometry()
        self.move(a.center().x() - self.W // 2, a.center().y() - self.H // 2)
        self.show()
        self.raise_()
        self.anim.start()

    def _tick(self):
        self.t += 0.04
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.PANEL
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(120, 80, 30, 40))
        p.drawRoundedRect(r.translated(0, 5), 26, 26)
        p.setPen(QPen(QColor("#E9CFA0"), 3))
        p.setBrush(QColor("#FFF3DC"))
        p.drawRoundedRect(r, 26, 26)
        hop = abs(math.sin(self.t * 3)) * 4
        cizim.draw_duck(p, {"x": r.center().x() - 6, "y": r.top() + 2 - hop, "scale": 0.8,
                            "quack": (self.t % 2) < 0.25, "wing": 10 + abs(math.sin(self.t * 6)) * 22})
        p.setPen(QColor("#B8682C"))
        p.setFont(QFont("Segoe Print", 14, QFont.Bold))
        p.drawText(QRectF(r.left(), r.top() + 14, r.width(), 38), Qt.AlignCenter, self.title)
        p.setPen(QColor("#8A6A45"))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(r.left() + 26, r.top() + 54, r.width() - 52, 80),
                   Qt.AlignCenter | Qt.TextWordWrap, self.text)


class BirthdayDialog(QWidget):
    W, H = 420, 372
    PANEL = QRectF(14, 112, 392, 250)

    def __init__(self, on_done, current="", greeting=None):
        """on_done("AA-GG") ya da on_done("") (söylemek istemedi).
        greeting: verilirse başlıkta o yazar (örn. "Merhaba! 👋")."""
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.on_done = on_done
        self.greeting = greeting
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)
        self.setWindowTitle("Doğum günün")
        self.setStyleSheet(STYLE)
        self.t = 0.0
        self.drag = None

        self.day = QComboBox()
        self.month = QComboBox()
        self.month.addItems(AYLAR)
        self.month.currentIndexChanged.connect(self._fill_days)
        self._fill_days()
        if current and len(current) == 5:
            m, d = int(current[:2]), int(current[3:])
            self.month.setCurrentIndex(m - 1)
            self.day.setCurrentIndex(d - 1)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.day)
        row.addWidget(self.month)
        row.addStretch()
        save = QPushButton("Kaydet 🎂", objectName="ana", clicked=self._save)
        skip = QPushButton("Söylemek istemiyorum", objectName="ikincil", clicked=self._skip)
        btns = QHBoxLayout()
        btns.addStretch()
        btns.addWidget(save)
        btns.addStretch()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 220, 40, 26)
        lay.setSpacing(12)
        lay.addLayout(row)
        lay.addLayout(btns)
        lay.addWidget(skip, 0, Qt.AlignHCenter)

        self.anim = QTimer(self, interval=40, timeout=self._tick)

    def _fill_days(self):
        keep = self.day.currentIndex()
        self.day.clear()
        self.day.addItems([str(d) for d in range(1, GUN_SAYISI[self.month.currentIndex()] + 1)])
        self.day.setCurrentIndex(max(0, min(keep, self.day.count() - 1)))

    def _save(self):
        m = self.month.currentIndex() + 1
        d = self.day.currentIndex() + 1
        self.close()
        self.on_done(f"{m:02d}-{d:02d}")

    def _skip(self):
        self.close()
        self.on_done("")

    def show_centered(self):
        a = QApplication.primaryScreen().availableGeometry()
        self.move(a.center().x() - self.W // 2, a.center().y() - self.H // 2)
        self.show()
        self.raise_()
        self.activateWindow()
        self.anim.start()

    def closeEvent(self, e):
        self.anim.stop()
        super().closeEvent(e)

    def _tick(self):
        self.t += 0.04
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.drag is not None:
            self.move(e.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, e):
        self.drag = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.PANEL
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(120, 80, 30, 40))
        p.drawRoundedRect(r.translated(0, 5), 26, 26)
        p.setPen(QPen(QColor("#E9CFA0"), 3))
        p.setBrush(QColor("#FFF3DC"))
        p.drawRoundedRect(r, 26, 26)
        # parti şapkalı ördek panelin üstünde oturuyor
        hop = abs(math.sin(self.t * 3)) * 4
        cizim.draw_duck(p, {"x": r.center().x() - 6, "y": r.top() + 2 - hop, "scale": 0.8,
                            "outfit": {"party"}, "quack": (self.t % 2) < 0.25,
                            "wing": 10 + abs(math.sin(self.t * 6)) * 18})
        p.setFont(cizim.emoji_font(20))
        for i, ch in enumerate("🎈🎉"):
            x = r.left() + 14 if i == 0 else r.right() - 40
            p.drawText(QPointF(x, r.top() + 46 + math.sin(self.t * 2 + i) * 4), ch)
        p.setPen(QColor("#B8682C"))
        p.setFont(QFont("Segoe Print", 15, QFont.Bold))
        p.drawText(QRectF(r.left(), r.top() + 18, r.width(), 40), Qt.AlignCenter,
                   self.greeting or "Doğum günün ne zaman?")
        p.setPen(QColor("#A07850"))
        p.setFont(QFont("Segoe UI", 9.5))
        sub = ("Doğum günün ne zaman? O gün parti şapkamı takıp seninle kutlayacağım!"
               if self.greeting else "O gün parti şapkamı takıp seninle kutlayacağım!")
        p.drawText(QRectF(r.left() + 20, r.top() + 56, r.width() - 40, 44),
                   Qt.AlignCenter | Qt.TextWordWrap, sub)
