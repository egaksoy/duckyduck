"""Ördek, yavru, yuva, kırıntı ve aksesuarların çizimi (hepsi kodla çiziliyor)."""

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QPainterPath,
                           QPainterPathStroker, QPen, QPolygonF, QTransform)

OUTLINE = QColor("#3A3A46")
LEG = QColor("#F59A1B")
LEG_DARK = QColor("#C9661A")
BEAK = QColor("#F7A21E")
BEAK_LOW = QColor("#E4840F")
BLUSH = QColor(255, 150, 170, 105)

PALETTES = {
    "adult": {"body": QColor("#FFFFFF"), "shade": QColor(196, 208, 228, 110),
              "wing": QColor("#FBFCFE"), "wing_line": QColor("#8E97A8")},
    "baby": {"body": QColor("#FFFFFF"), "shade": QColor(196, 208, 228, 100),
             "wing": QColor("#FBFCFE"), "wing_line": QColor("#9AA3B4")},
}

EMOJI_FONT = "Segoe UI Emoji"


def _pen(color, w=2.0):
    return QPen(color, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


# ---------------------------------------------------------------------------
# Ördek
# ---------------------------------------------------------------------------

def draw_duck(p, pose):
    """(x, y) = ayakların bastığı nokta. Sağa bakarken çizilir, facing=-1 aynalar.

    pose: facing, scale, rot, bob, sit, legs(stand/walk/run/dangle), leg_phase,
          head(dx,dy), eyes(open/closed/half/wide), wing, quack, glasses, brow,
          prop(laptop/popcorn/gamepad/phone), headphones, outfit(set), baby
    """
    pal = PALETTES["baby" if pose.get("baby") else "adult"]
    p.save()
    p.translate(pose["x"], pose["y"])
    s = pose.get("scale", 1.0)
    p.scale(pose.get("facing", 1) * s, s)
    p.rotate(pose.get("rot", 0))
    sit = pose.get("sit", False)
    baby = pose.get("baby", False)
    outfit = pose.get("outfit", set())

    # --- bacaklar ---
    if not sit:
        p.translate(0, -pose.get("bob", 0))
        mode = pose.get("legs", "stand")
        for i, lx in enumerate((-7, 6)):
            ph = pose.get("leg_phase", 0) + (math.pi if i else 0)
            if mode == "walk":
                fx, lift = math.sin(ph) * 6, max(0.0, math.cos(ph)) * 4
            elif mode == "run":
                fx, lift = math.sin(ph) * 10, max(0.0, math.cos(ph)) * 7
            elif mode == "dangle":
                fx, lift = math.sin(ph) * 3, -6
            else:
                fx, lift = 0, 0
            foot_x, foot_y = lx + fx, -lift
            p.setPen(_pen(LEG, 3.2))
            p.drawLine(QPointF(lx, -18), QPointF(foot_x, foot_y - 1))
            foot = QPainterPath()
            foot.moveTo(foot_x - 4, foot_y)
            foot.quadTo(foot_x + 2, foot_y - 5, foot_x + 9, foot_y - 3)
            foot.quadTo(foot_x + 15, foot_y - 2, foot_x + 14, foot_y + 0.5)
            foot.quadTo(foot_x + 5, foot_y + 2, foot_x - 4, foot_y)
            p.setPen(_pen(LEG_DARK, 1.3))
            p.setBrush(LEG)
            p.drawPath(foot)
    else:
        p.translate(0, 14 - pose.get("bob", 0))

    hx, hy = pose.get("head", (0, 0))
    hr = 16.5 * (1.25 if baby else 1.0)
    hcx, hcy = 19 + hx, (-70 if baby else -80) + hy

    # --- gövde siluet: tombul yatay gövde + sivri kalkık kuyruk + kalın boyun + yuvarlak kafa ---
    body = QPainterPath()
    body.addEllipse(QRectF(-40, -59, 70, 47))
    body = QTransform().translate(-5, -35).rotate(-20).translate(5, 35).map(body)
    # kuyruk: arkası yukarı doğru incelip üç sivri tüye ayrılır (en üstteki en uzun)
    tail = QPainterPath()
    tail.moveTo(-22, -47)
    tail.quadTo(-40, -49, -58, -62)        # 1. (üst) tüy ucu
    tail.quadTo(-51, -53, -47, -50)        # çentik
    tail.quadTo(-55, -51, -62, -52)        # 2. (orta) tüy ucu
    tail.quadTo(-53, -45, -48, -42)        # çentik
    tail.quadTo(-54, -42, -59, -41)        # 3. (alt) tüy ucu
    tail.quadTo(-49, -31, -34, -22)
    tail.closeSubpath()
    neck = QPainterPath()
    neck.moveTo(0, -46)
    neck.cubicTo(0 + hx * 0.3, -62 + hy * 0.4, 4 + hx * 0.6, -76 + hy * 0.7, hcx - 11, hcy + 4)
    neck.lineTo(hcx + 11, hcy + 9)
    neck.cubicTo(20 + hx * 0.5, -64 + hy * 0.5, 27, -54, 30, -38)
    neck.closeSubpath()
    head = QPainterPath()
    head.addEllipse(QPointF(hcx, hcy), hr, hr)
    sil = body.united(tail).united(neck).united(head)

    if baby:   # yavrunun kafasında küçük tüy perçemi
        p.setPen(_pen(OUTLINE, 2.4))
        for dx, ang in ((-4, -20), (0, 0), (4, 22)):
            a = math.radians(ang - 90)
            x1, y1 = hcx + dx * 0.6, hcy - hr + 1
            p.drawLine(QPointF(x1, y1), QPointF(x1 + math.cos(a) * 7, y1 + math.sin(a) * 7))
    p.setPen(_pen(OUTLINE, 2.2))
    p.setBrush(pal["body"])
    p.drawPath(sil)

    # karın gölgesi
    p.save()
    p.setClipPath(sil)
    p.setPen(Qt.NoPen)
    p.setBrush(pal["shade"])
    p.drawEllipse(QRectF(-40, -30, 76, 30))
    p.restore()

    # --- atkı ---
    if "scarf" in outfit or "scarf_autumn" in outfit:
        c = QColor("#F08A24") if "scarf_autumn" in outfit else QColor("#E5484D")
        dark = c.darker(135)
        ny = -61 + hy * 0.45
        sx0 = hx * 0.35
        # boynun etrafına dolanan yuvarlak rulo: arkadan öne hafifçe aşağı kıvrılır
        roll = QPainterPath()
        roll.moveTo(-1 + sx0, ny - 2)
        roll.quadTo(14 + sx0, ny + 5, 31 + sx0, ny + 1)
        stroker = QPainterPathStroker()
        stroker.setWidth(9.5)
        stroker.setCapStyle(Qt.RoundCap)
        wrap = stroker.createStroke(roll)
        # önden sarkan iki uç + düğüm
        kx = 28 + sx0
        ends = QPainterPath()
        ends.addRoundedRect(QRectF(-3.5, 0, 7, 17), 3, 3)
        e1 = QTransform().translate(kx - 2, ny + 3).rotate(12).map(ends)
        e2 = QTransform().translate(kx + 3, ny + 3).rotate(-14).map(QTransform().scale(1, 0.8).map(ends))
        for e in (e1, e2):
            p.setPen(_pen(dark, 1.4))
            p.setBrush(c)
            p.drawPath(e)
        p.setPen(_pen(dark, 1.5))
        p.setBrush(c)
        p.drawPath(wrap)
        p.save()
        p.setClipPath(wrap.united(e1).united(e2))
        p.setPen(_pen(QColor(255, 255, 255, 150), 1.6))
        for sx in range(-12, 50, 7):
            p.drawLine(QPointF(sx, ny + 14), QPointF(sx + 8, ny - 8))
        p.restore()
        p.setPen(_pen(dark, 1.4))
        p.setBrush(c.lighter(108))
        p.drawEllipse(QPointF(kx + 1, ny + 3), 4.2, 3.6)

    # --- kanat ---
    p.save()
    p.translate(10, -44)
    p.rotate(pose.get("wing", 0))
    wing = QPainterPath()
    wing.moveTo(0, 0)
    wing.cubicTo(-4, -10, -30, -6, -48, 15)
    wing.cubicTo(-30, 22, -6, 20, 0, 0)
    p.setPen(_pen(pal["wing_line"], 1.6))
    p.setBrush(pal["wing"])
    p.drawPath(wing)
    # kanat ucundaki koyu tüy çizgileri
    p.setPen(_pen(pal["wing_line"].darker(150), 1.8))
    p.drawLine(QPointF(-30, 6), QPointF(-44, 13))
    p.drawLine(QPointF(-28, 10), QPointF(-42, 16))
    p.drawLine(QPointF(-24, 14), QPointF(-36, 17))
    p.restore()

    # --- gaga ---
    # Yüzün alt-önünden aşağı eğik çıkar; ucu genişleyip kepçe gibi yukarı kalkar.
    quack = pose.get("quack")
    k = 1.0 if not baby else 0.7
    p.save()
    p.translate(hcx + hr * 0.78, hcy + 4)
    p.rotate(10 - (8 if quack else 0))         # hafif aşağı eğik
    p.scale(k * 0.74, k)                       # kısa gaga
    if quack:                                   # alt çene açılır
        p.save()
        p.rotate(18)
        jaw = QPainterPath()
        jaw.moveTo(-2, 0)
        jaw.cubicTo(6, 2, 12, 3, 17, 3)
        jaw.cubicTo(19, 5, 17, 7, 13, 7)
        jaw.cubicTo(8, 6.5, 3, 6, -2, 5)
        jaw.closeSubpath()
        p.setPen(_pen(LEG_DARK, 1.5))
        p.setBrush(BEAK_LOW)
        p.drawPath(jaw)
        p.restore()
    # kısa gaga (kafa genişliğinin ~2/3'ü): kökte kalın, ortada incelir, ucu genişleyip yukarı kalkar
    beak = QPainterPath()
    beak.moveTo(-3, -4)
    beak.cubicTo(4, -3.2, 9, -1.8, 13, -2.2)
    beak.cubicTo(16, -3, 18, -5.5, 20.5, -5.8)
    beak.cubicTo(23.5, -6, 24, -2.5, 22.8, 0.2)
    beak.cubicTo(21, 2.8, 16, 3.6, 11, 3.6)
    beak.cubicTo(6, 3.6, 2, 4.2, -3, 4.4)
    beak.closeSubpath()
    p.setPen(_pen(LEG_DARK, 1.6))
    p.setBrush(BEAK)
    p.drawPath(beak)
    mouth = QPainterPath()
    mouth.moveTo(2, 1.5)
    mouth.cubicTo(9, 2.2, 15, 2, 21, -1.5)
    p.setPen(_pen(LEG_DARK, 1.3))
    p.setBrush(Qt.NoBrush)
    p.drawPath(mouth)
    p.setPen(_pen(QColor(255, 226, 165, 210), 1.2))
    p.drawLine(QPointF(1, -2.4), QPointF(9, -1.6))
    p.setPen(Qt.NoPen)
    p.setBrush(LEG_DARK)
    p.drawEllipse(QPointF(6, -0.8), 1.0, 0.6)
    p.restore()

    # yanak
    p.setPen(Qt.NoPen)
    p.setBrush(BLUSH)
    p.drawEllipse(QRectF(hcx - 1, hcy + 3, 8, 4.5))

    # --- göz: kafanın ön üstünde küçük siyah nokta ---
    ex, ey = hcx + 5, hcy - 5
    eyes = pose.get("eyes", "open")
    if eyes == "closed":
        p.setPen(_pen(OUTLINE, 1.9))
        p.setBrush(Qt.NoBrush)
        arc = QPainterPath()
        arc.moveTo(ex - 3.5, ey)
        arc.quadTo(ex, ey + 3.5, ex + 3.5, ey)
        p.drawPath(arc)
    elif eyes == "dizzy":                      # başı dönünce sarmal göz
        p.setPen(_pen(OUTLINE, 1.4))
        p.setBrush(Qt.NoBrush)
        spiral = QPainterPath()
        spin = pose.get("spin", 0.0)
        for i in range(30):
            a = spin + i * 0.42
            r = 0.4 + i * 0.12
            pt = QPointF(ex + math.cos(a) * r, ey + math.sin(a) * r)
            if i == 0:
                spiral.moveTo(pt)
            else:
                spiral.lineTo(pt)
        p.drawPath(spiral)
    else:
        rx, ry = (3.6, 4.4) if eyes == "wide" else (2.7, 3.4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#151519"))
        p.drawEllipse(QPointF(ex, ey), rx, ry)
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(ex - 0.8, ey - 1.3), 1.0, 1.0)
        if eyes == "half":
            p.setBrush(pal["body"])
            p.drawRect(QRectF(ex - 5, ey - 6, 10, 5.4))
            p.setPen(_pen(OUTLINE, 1.5))
            p.drawLine(QPointF(ex - 4, ey - 0.6), QPointF(ex + 4, ey - 0.6))
    if pose.get("brow"):
        p.setPen(_pen(OUTLINE, 2.0))
        p.drawLine(QPointF(ex - 5, ey - 9), QPointF(ex + 4, ey - 6))

    # --- gözlükler ---
    if pose.get("glasses"):
        p.setPen(_pen(OUTLINE, 1.6))
        p.setBrush(QColor(180, 220, 255, 60))
        p.drawEllipse(QPointF(ex, ey), 7, 7)
        p.drawLine(QPointF(ex - 7, ey), QPointF(hcx - hr + 4, ey + 1))
    elif "sunglasses" in outfit:
        p.setPen(_pen(QColor("#111"), 1.4))
        p.setBrush(QColor(20, 20, 30, 235))
        p.drawEllipse(QPointF(ex + 0.5, ey + 0.5), 7.5, 5.5)
        p.drawLine(QPointF(ex - 7, ey), QPointF(hcx - hr + 3, ey + 1))
        p.setPen(_pen(QColor(255, 255, 255, 150), 1.4))
        p.drawLine(QPointF(ex - 3, ey - 2), QPointF(ex, ey - 3))

    # --- kulaklık ---
    if pose.get("headphones"):
        c = QColor("#FF7AA2")
        p.setPen(_pen(c.darker(120), 3))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(hcx - hr - 1, hcy - hr - 3, 2 * hr + 2, 2 * hr + 4), 40 * 16, 120 * 16)
        p.setPen(_pen(c.darker(130), 1.3))
        p.setBrush(c)
        p.drawEllipse(QPointF(hcx - 9, hcy + 1), 5, 7)

    # --- odak bandı (kafaya bağlanan kırmızı bant, uçları arkada dalgalanır) ---
    if pose.get("headband"):
        t = pose.get("t", 0.0)
        red, dark = QColor("#E5484D"), QColor("#A92B30")
        kx, ky = hcx - hr + 1, hcy - 8
        for i, (ln, ph) in enumerate(((17, 0.0), (13, 1.3))):
            tail = QPainterPath()
            tail.moveTo(kx, ky)
            wave = math.sin(t * 9 + ph) * 3
            tail.cubicTo(kx - ln * 0.4, ky - 2 + wave, kx - ln * 0.7, ky + 3 - wave + i * 3,
                         kx - ln, ky + 2 + wave + i * 4)
            st = QPainterPathStroker()
            st.setWidth(4.2 - i * 0.6)
            st.setCapStyle(Qt.RoundCap)
            p.setPen(_pen(dark, 1.1))
            p.setBrush(red)
            p.drawPath(st.createStroke(tail))
        p.save()
        p.setClipPath(head)
        p.setPen(Qt.NoPen)
        p.setBrush(red)
        p.drawRect(QRectF(hcx - hr - 2, hcy - 12.5, 2 * hr + 4, 6.5))
        p.setBrush(QColor(255, 255, 255, 120))
        p.drawRect(QRectF(hcx - hr - 2, hcy - 11.6, 2 * hr + 4, 1.3))
        p.restore()
        p.setPen(_pen(dark, 1.2))
        p.setBrush(red)
        p.drawEllipse(QPointF(kx, ky - 1), 3.2, 3.6)

    # --- şapkalar ---
    top = hcy - hr
    if "nightcap" in outfit:
        cap = QPainterPath()
        cap.moveTo(hcx - 13, top + 6)
        cap.quadTo(hcx - 8, top - 16, hcx - 30, top - 6)
        cap.quadTo(hcx - 8, top - 22, hcx + 11, top + 7)
        cap.closeSubpath()
        p.setPen(_pen(QColor("#4552A8"), 1.4))
        p.setBrush(QColor("#6C7BD9"))
        p.drawPath(cap)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRectF(hcx - 14, top + 2, 26, 6), 3, 3)
        p.drawEllipse(QPointF(hcx - 30, top - 6), 4.5, 4.5)
    elif "party" in outfit:
        p.save()
        p.translate(hcx - 2, top + 4)
        p.rotate(-14)
        cone = QPolygonF([QPointF(-10, 0), QPointF(10, 0), QPointF(0, -26)])
        p.setPen(_pen(QColor("#3D6FD8"), 1.4))
        p.setBrush(QColor("#6BA8FF"))
        p.drawPolygon(cone)
        p.setPen(_pen(QColor("#FFD23F"), 2.4))
        p.drawLine(QPointF(-6, -6), QPointF(6, -6))
        p.drawLine(QPointF(-3, -15), QPointF(3, -15))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FF6B8B"))
        p.drawEllipse(QPointF(0, -27), 4.5, 4.5)
        p.restore()
    elif "beanie" in outfit:
        bean = QPainterPath()
        bean.moveTo(hcx - hr + 1, top + 9)
        bean.cubicTo(hcx - hr + 1, top - 10, hcx + hr - 1, top - 10, hcx + hr - 1, top + 9)
        bean.closeSubpath()
        p.setPen(_pen(QColor("#B3262B"), 1.4))
        p.setBrush(QColor("#E5484D"))
        p.drawPath(bean)
        p.setBrush(QColor("#F4F1EA"))
        p.drawRoundedRect(QRectF(hcx - hr, top + 4, 2 * hr, 7), 3.5, 3.5)
        p.drawEllipse(QPointF(hcx, top - 6), 5, 5)
    elif "flower" in outfit:
        fx, fy = hcx - 8, top + 1
        p.setPen(_pen(QColor("#E0628E"), 1))
        p.setBrush(QColor("#FF9EC0"))
        for k in range(5):
            a = k * 2 * math.pi / 5
            p.drawEllipse(QPointF(fx + math.cos(a) * 4, fy + math.sin(a) * 4), 3.6, 3.6)
        p.setBrush(QColor("#FFD23F"))
        p.drawEllipse(QPointF(fx, fy), 2.6, 2.6)

    # --- elde tutulanlar ---
    prop = pose.get("prop")
    if prop == "popcorn":
        p.setPen(_pen(QColor("#C9A453"), 1))
        p.setBrush(QColor("#FFF4CC"))
        for i, px in enumerate((29, 35, 41, 47, 32, 38, 44)):
            p.drawEllipse(QPointF(px, -37 if i < 4 else -41), 4.3, 4.3)
        bowl = QPolygonF([QPointF(25, -36), QPointF(52, -36), QPointF(48, -14), QPointF(29, -14)])
        p.setPen(_pen(OUTLINE, 1.6))
        p.setBrush(QColor("#E8473F"))
        p.drawPolygon(bowl)
        p.setPen(_pen(QColor("white"), 3))
        for sx in (34, 43):
            p.drawLine(QPointF(sx, -34), QPointF(sx, -16))
    elif prop == "laptop":
        p.setPen(_pen(OUTLINE, 1.4))
        p.setBrush(QColor("#A9B2C3"))
        p.drawRoundedRect(QRectF(24, -17, 30, 4), 1.5, 1.5)
        p.setPen(_pen(QColor("#525A6B"), 3.4))
        p.drawLine(QPointF(53, -16), QPointF(59, -40))
        p.setPen(_pen(QColor("#9FD8FF"), 1.6))
        p.drawLine(QPointF(51, -18), QPointF(56.5, -39))
    elif prop == "gamepad":
        p.setPen(_pen(OUTLINE, 1.4))
        p.setBrush(QColor("#6C6F7D"))
        p.drawRoundedRect(QRectF(16, -44, 26, 12), 6, 6)
        p.setPen(Qt.NoPen)
        for c, (bx, by) in ((QColor("#FF6B8B"), (35, -40)), (QColor("#6BD0FF"), (38, -37))):
            p.setBrush(c)
            p.drawEllipse(QPointF(bx, by), 1.8, 1.8)
        p.setBrush(QColor("#E6E8EE"))
        p.drawRect(QRectF(20, -39.5, 7, 2))
        p.drawRect(QRectF(22.5, -42, 2, 7))
    elif prop == "phone":
        draw_phone_in_wing(p, pal)

    # eklentilerin ördeğe eklediği çizimler (ördeğin kendi koordinatlarında çizilir)
    for fn in pose.get("ekstra", ()):
        fn(p, {"hcx": hcx, "hcy": hcy, "hr": hr, "sit": sit, "pal": pal})

    p.restore()


def draw_focus_timer(p, cx, cy, seconds_left, total, t, scale=1.0):
    """Sade odak sayacı (ördek renklerinde): krem daire, ortada dakika:saniye,
    kalan süreyle azalan turuncu halka ve halkada yavaşça dönen tek bir parıltı."""
    p.save()
    p.translate(cx, cy)
    p.scale(scale, scale)
    R = 25
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(120, 80, 30, 40))                    # yumuşak gölge
    p.drawEllipse(QPointF(0, 2), R + 4, R + 4)
    p.setBrush(QColor("#FFF6E6"))
    p.drawEllipse(QPointF(0, 0), R + 4, R + 4)
    track = QRectF(-R, -R, 2 * R, 2 * R)
    p.setPen(QPen(QColor("#F3DDB4"), 3.6, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(track)
    frac = max(0.0, min(1.0, seconds_left / max(1.0, total)))
    p.setPen(QPen(QColor("#F7A21E"), 3.6, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(track, 90 * 16, int(360 * 16 * frac))        # kalan süre
    a = math.radians(90 + t * 40)                           # tek, yavaş dönen parıltı
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 230))
    p.drawEllipse(QPointF(math.cos(a) * R, -math.sin(a) * R), 2.0, 2.0)
    s = max(0, int(seconds_left))
    f = QFont("Segoe UI", 10)
    f.setWeight(QFont.Bold)
    p.setFont(f)
    p.setPen(QColor("#B8682C"))
    p.drawText(QRectF(-R, -10, 2 * R, 20), Qt.AlignCenter, f"{s // 60:02d}:{s % 60:02d}")
    p.restore()


def draw_phone_in_wing(p, pal):
    """Kanadını kol gibi öne uzatıp telefonu yüzünün önünde tutar."""
    # öne uzanan kanat-kol
    arm_line = QPainterPath()
    arm_line.moveTo(16, -45)
    arm_line.cubicTo(28, -40, 42, -42, 54, -51)
    stroker = QPainterPathStroker()
    stroker.setWidth(7)
    stroker.setCapStyle(Qt.RoundCap)
    arm = stroker.createStroke(arm_line)
    p.setPen(_pen(pal["wing_line"], 1.5))
    p.setBrush(pal["wing"])
    p.drawPath(arm)
    # ekranın hafif ışığı
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(150, 215, 255, 55))
    p.drawEllipse(QPointF(63, -60), 16, 18)
    # telefon
    p.save()
    p.translate(63, -60)
    p.rotate(-14)
    p.setPen(_pen(QColor("#1F232C"), 1.4))
    p.setBrush(QColor("#2E3340"))
    p.drawRoundedRect(QRectF(-7, -12, 14, 24), 3.2, 3.2)
    g = QLinearGradient(0, -10, 0, 9)
    g.setColorAt(0, QColor("#7CCBFF"))
    g.setColorAt(1, QColor("#D4F3FF"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(-5.6, -9.6, 11.2, 18.4), 1.8, 1.8)
    p.setBrush(QColor(255, 255, 255, 235))         # mesaj baloncukları
    p.drawRoundedRect(QRectF(-4.4, -7.6, 6.4, 3), 1.4, 1.4)
    p.drawRoundedRect(QRectF(-1.6, -3.2, 6, 3), 1.4, 1.4)
    p.setBrush(QColor("#FF6B8B"))
    p.drawEllipse(QPointF(-1.8, 3.2), 1.6, 1.4)
    p.setBrush(QColor("#6C7480"))
    p.drawEllipse(QPointF(0, -11), 0.8, 0.8)
    p.restore()
    # telefonu kavrayan kanat ucu
    tip = QPainterPath()
    tip.addEllipse(QRectF(-6, -4.5, 12, 9))
    tip = QTransform().translate(57, -50).rotate(-35).map(tip)
    p.setPen(_pen(pal["wing_line"], 1.5))
    p.setBrush(pal["wing"])
    p.drawPath(tip)
    p.setPen(_pen(pal["wing_line"], 1.0))
    p.drawLine(QPointF(54, -49), QPointF(58, -53))
    p.drawLine(QPointF(56.5, -47.5), QPointF(60.5, -51.5))


def draw_anger(p, x, y, size=1.0):
    """Küsünce kafasının yanında çıkan kırmızı 'kızgınlık' işareti."""
    p.save()
    p.translate(x, y)
    p.scale(size, size)
    p.setPen(_pen(QColor("#E5484D"), 2.2))
    p.setBrush(Qt.NoBrush)
    for a in range(4):
        p.save()
        p.rotate(a * 90)
        path = QPainterPath()
        path.moveTo(2, -7)
        path.quadTo(2, -2, 7, -2)
        p.drawPath(path)
        p.restore()
    p.restore()


# ---------------------------------------------------------------------------
# Yuva, kırıntı
# ---------------------------------------------------------------------------

NEST_W = 116


def draw_nest(p, cx, bottom, eggs=3, part="all"):
    """part: 'back' (iç + yumurtalar), 'front' (ön saman), 'all'."""
    rng = random.Random(7)
    if part in ("back", "all"):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#9C4F1E"))
        p.drawEllipse(QPointF(cx, bottom - 30), 50, 12)
        slots = [(-22, 0), (22, 0), (0, -3), (-11, 2), (11, 2)][:max(0, min(5, eggs))]
        for ex, ey in sorted(slots, key=lambda e: e[1]):
            egg = QRectF(cx + ex - 9, bottom - 49 + ey, 18, 24)
            p.setPen(_pen(QColor("#DCC59A"), 1.3))
            p.setBrush(QColor("#FFF3DC"))
            p.drawEllipse(egg)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 200))
            p.drawEllipse(QPointF(cx + ex - 3, bottom - 43 + ey), 2.5, 4)
    if part in ("front", "all"):
        bowl = QPainterPath()
        bowl.moveTo(cx - 58, bottom - 31)
        bowl.cubicTo(cx - 56, bottom + 3, cx + 56, bottom + 3, cx + 58, bottom - 31)
        bowl.quadTo(cx, bottom - 19, cx - 58, bottom - 31)
        g = QLinearGradient(0, bottom - 34, 0, bottom)
        g.setColorAt(0, QColor("#F2A75A"))
        g.setColorAt(1, QColor("#D8692A"))
        p.setPen(_pen(QColor("#B85A22"), 1.4))
        p.setBrush(g)
        p.drawPath(bowl)
        # saman püsküller
        rim = QPolygonF()
        x = cx - 60
        up = True
        while x <= cx + 60:
            t = (x - cx) / 60
            base = bottom - 25 - (1 - t * t) * 3
            rim.append(QPointF(x, base - (rng.uniform(7, 12) if up else rng.uniform(0, 3))))
            x += rng.uniform(5, 8)
            up = not up
        for x2 in range(int(cx + 58), int(cx - 59), -6):
            t = (x2 - cx) / 60
            rim.append(QPointF(x2, bottom - 18 + (1 - t * t) * 2))
        p.setPen(_pen(QColor("#D98E3E"), 1.2))
        p.setBrush(QColor("#F7C57E"))
        p.drawPolygon(rim)
        p.setPen(_pen(QColor("#FBDDA4"), 1.4))
        for _ in range(16):
            sx = cx + rng.uniform(-48, 48)
            sy = bottom - rng.uniform(6, 20)
            p.drawLine(QPointF(sx, sy), QPointF(sx + rng.uniform(-10, 10), sy - rng.uniform(-3, 3)))
        p.setPen(_pen(QColor("#B85A22"), 1.1))
        for _ in range(10):
            sx = cx + rng.uniform(-44, 44)
            sy = bottom - rng.uniform(4, 16)
            p.drawLine(QPointF(sx, sy), QPointF(sx + rng.uniform(-8, 8), sy + rng.uniform(-2, 2)))


SEED_COLORS = [(QColor("#F6C453"), QColor("#C98A1E")),     # altın buğday
               (QColor("#FBE3A2"), QColor("#C9A256")),     # krem
               (QColor("#E9A24B"), QColor("#A8641F")),     # bal rengi
               (QColor("#F3D27A"), QColor("#B88A2A"))]


def _seed(p, x, y, ang, length, color, edge):
    """Tek bir tohum tanesi: ucu hafif sivri, parlak, minik."""
    p.save()
    p.translate(x, y)
    p.rotate(ang)
    w = length * 0.62
    s = QPainterPath()
    s.moveTo(-length / 2, 0)
    s.cubicTo(-length / 2, -w / 2, length * 0.2, -w / 2, length / 2, 0)
    s.cubicTo(length * 0.2, w / 2, -length / 2, w / 2, -length / 2, 0)
    g = QLinearGradient(0, -w / 2, 0, w / 2)
    g.setColorAt(0, color.lighter(118))
    g.setColorAt(1, color)
    p.setPen(_pen(edge, 0.9))
    p.setBrush(g)
    p.drawPath(s)
    p.setPen(_pen(QColor(edge.red(), edge.green(), edge.blue(), 120), 0.7))
    p.drawLine(QPointF(-length * 0.3, 0.2), QPointF(length * 0.3, 0.2))     # ortadaki çizgi
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 200))
    p.drawEllipse(QPointF(-length * 0.12, -w * 0.2), length * 0.14, w * 0.11)
    p.restore()


def draw_crumb(p, cx, cy, seed=1, rot=0.0, shadow=True):
    """Yere düşen yem: birkaç minik, parlak tohum tanesi. (cx, cy) = yere değdiği nokta."""
    rng = random.Random(seed)
    p.save()
    p.translate(cx, cy)
    if shadow:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(60, 40, 20, 45))
        p.drawEllipse(QPointF(0, 0.5), 12, 2.6)
    n = rng.randint(6, 7)
    xs = [-9 + 18 * (i + rng.uniform(0.15, 0.85)) / n for i in range(n)]   # eşit dağılmış
    rng.shuffle(xs)
    for i, x in enumerate(xs):
        y = -rng.uniform(1.6, 3.4) - (3.0 if abs(x) < 4 and i % 2 else 0)
        col, edge = SEED_COLORS[rng.randrange(len(SEED_COLORS))]
        _seed(p, x, y, rot + rng.uniform(-60, 60), rng.uniform(6.2, 7.6), col, edge)
    p.restore()


def draw_seed_bowl(p, cx, cy, size=24):
    """Menü ikonu: tohumla dolu küçük krem kase."""
    p.save()
    p.translate(cx, cy)
    k = size / 24
    p.scale(k, k)
    rng = random.Random(5)
    # tepecik tohumlar
    for i in range(11):
        x = rng.uniform(-8, 8)
        y = -3 - rng.uniform(0, 3.5) * (1 - abs(x) / 10)
        col, edge = SEED_COLORS[i % len(SEED_COLORS)]
        _seed(p, x, y, rng.uniform(-70, 70), 5.2, col, edge)
    bowl = QPainterPath()
    bowl.moveTo(-11, -2)
    bowl.lineTo(11, -2)
    bowl.cubicTo(11, 6, 6, 9, 0, 9)
    bowl.cubicTo(-6, 9, -11, 6, -11, -2)
    bowl.closeSubpath()
    g = QLinearGradient(0, -2, 0, 9)
    g.setColorAt(0, QColor("#FFFFFF"))
    g.setColorAt(1, QColor("#F2E3C6"))
    p.setPen(_pen(QColor("#C79A64"), 1.2))
    p.setBrush(g)
    p.drawPath(bowl)
    p.setPen(_pen(QColor("#F7A21E"), 1.6))
    p.drawLine(QPointF(-8, 2.5), QPointF(8, 2.5))
    p.restore()


def emoji_font(px):
    f = QFont(EMOJI_FONT)
    f.setPixelSize(int(px))
    return f
