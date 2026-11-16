"""Ördeğin logosu: krem-turuncu yuvarlak köşeli rozet üstünde ördek.
Eklentiler logoya çizim ekleyebilir (örn. bir aksesuar)."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap

import cizim


def draw_logo(p, size, ekstra=None):
    """size x size alana logoyu çizer. ekstra: ördeğe eklenecek çizimler listesi."""
    p.save()
    k = size / 256
    p.scale(k, k)
    r = QRectF(8, 8, 240, 240)
    g = QLinearGradient(0, 8, 0, 248)
    g.setColorAt(0, QColor("#FFF1D6"))
    g.setColorAt(1, QColor("#FFC977"))
    p.setPen(QPen(QColor("#E8962F"), 7))
    p.setBrush(g)
    p.drawRoundedRect(r, 58, 58)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 90))              # üstte yumuşak parlaklık
    p.drawRoundedRect(QRectF(26, 20, 204, 70), 40, 40)
    p.setBrush(QColor(150, 80, 20, 55))                # ördeğin gölgesi
    p.drawEllipse(QPointF(132, 214), 66, 11)
    pose = {"x": 136, "y": 212, "scale": 1.66, "legs": "stand"}
    if ekstra:
        pose["ekstra"] = list(ekstra)
    cizim.draw_duck(p, pose)
    p.restore()


def logo_pixmap(size, ekstra=None):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    draw_logo(p, size, ekstra)
    p.end()
    return pix


def logo_icon(ekstra=None):
    icon = QIcon()
    for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(s, ekstra))
    return icon


def save_ico(path, ekstra=None):
    return logo_pixmap(256, ekstra).save(path, "ICO")
