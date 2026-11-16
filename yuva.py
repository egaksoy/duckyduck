"""Yuva menüsünden açılan not defteri ve notların kaydı.

Tasarım: sıcak krem bir defter; solda renk şeritli not kartları, sağda büyük
başlık + çizgili kâğıt gibi yazı alanı. Notlar renklendirilebilir, sabitlenebilir
ve aranabilir; her şey yazarken kendiliğinden kaydedilir.
"""

import math
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QKeySequence, QPainter,
                           QPainterPath, QPen, QShortcut)
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

import ayarlar
import cizim
from pencereler import keep_on_top

# (ad, kâğıt rengi, vurgu rengi)
RENKLER = [("sari", "#FFF1C9", "#F2B84B"), ("pembe", "#FFE1E8", "#EE7F9C"),
           ("mavi", "#E0EEFF", "#6EA8E8"), ("yesil", "#E2F4DC", "#6CBF73"),
           ("mor", "#ECE4FF", "#9C82E0")]
RENK = {ad: (QColor(k), QColor(v)) for ad, k, v in RENKLER}
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
         "Eylül", "Ekim", "Kasım", "Aralık"]

BROWN = QColor("#B8682C")
INK = QColor("#5A3D1E")
SOFT = QColor("#B9976E")


def tarih_yazisi(ts):
    t = time.localtime(ts)
    return f"{t.tm_mday} {AYLAR[t.tm_mon - 1]} {t.tm_year}, {t.tm_hour:02d}:{t.tm_min:02d}"


# ---------------------------------------------------------------------------
# Notlar (veri)
# ---------------------------------------------------------------------------

class Notes:
    def __init__(self, on_change=None):
        self.items = ayarlar.oku("notlar.json", [])
        for n in self.items:                       # eski notları yeni biçime getir
            n.setdefault("baslik", "")
            n.setdefault("renk", "sari")
            n.setdefault("sabit", False)
            n.setdefault("guncel", n.get("id", 0) / 1000)
        self.on_change = on_change

    def save(self):
        ayarlar.yaz("notlar.json", self.items)

    def add(self):
        now = time.time()
        renk = RENKLER[len(self.items) % len(RENKLER)][0]
        note = {"id": int(now * 1000), "baslik": "", "metin": "", "renk": renk,
                "sabit": False, "guncel": now, "tarih": time.strftime("%Y-%m-%d %H:%M")}
        self.items.insert(0, note)
        self.save()
        self._changed()
        return note

    def delete(self, note_id):
        self.items = [n for n in self.items if n["id"] != note_id]
        self.save()
        self._changed()

    def sorted(self, query=""):
        q = query.strip().lower()
        out = [n for n in self.items
               if not q or q in n["baslik"].lower() or q in n["metin"].lower()]
        return sorted(out, key=lambda n: (not n.get("sabit"), -n.get("guncel", 0)))

    def _changed(self):
        if self.on_change:
            self.on_change()


def baslik_gorunen(n):
    if n["baslik"].strip():
        return n["baslik"].strip()
    first = n["metin"].strip().splitlines()[0] if n["metin"].strip() else ""
    return first or "Başlıksız not"


def onizleme(n):
    lines = [x.strip() for x in n["metin"].strip().splitlines() if x.strip()]
    if not n["baslik"].strip() and lines:
        lines = lines[1:]
    return " ".join(lines) or "Boş not"


# ---------------------------------------------------------------------------
# Liste kartları
# ---------------------------------------------------------------------------

class CardDelegate(QStyledItemDelegate):
    H = 66

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.H)

    def paint(self, p, option, index):
        n = index.data(Qt.UserRole + 1)
        if not n:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(option.rect).adjusted(3, 4, -6, -4)
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)
        paper, accent = RENK.get(n.get("renk"), RENK["sari"])
        if selected:
            p.setPen(QPen(accent, 1.6))
            p.setBrush(paper)
        else:
            p.setPen(QPen(QColor("#F1E3C9"), 1.2))
            p.setBrush(QColor("#FFF7EA") if hover else QColor("#FFFFFF"))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(r.left() + 7, r.top() + 10, 4, r.height() - 20), 2, 2)

        x = r.left() + 19
        right = r.right() - 10
        f1 = QFont("Segoe UI", 10)
        f1.setWeight(QFont.DemiBold)
        f3 = QFont("Segoe UI", 7.5)
        date = time.strftime("%d.%m", time.localtime(n.get("guncel", 0)))
        dw = QFontMetrics(f3).horizontalAdvance(date)
        title_w = right - x - dw - 8 - (16 if n.get("sabit") else 0)
        p.setFont(f1)
        p.setPen(INK)
        title = QFontMetrics(f1).elidedText(baslik_gorunen(n), Qt.ElideRight, int(title_w))
        p.drawText(QRectF(x, r.top() + 9, title_w, 20), Qt.AlignVCenter | Qt.AlignLeft, title)
        if n.get("sabit"):
            p.setFont(cizim.emoji_font(11))
            p.drawText(QRectF(right - dw - 22, r.top() + 9, 16, 20), Qt.AlignCenter, "📌")
        p.setFont(f3)
        p.setPen(SOFT)
        p.drawText(QRectF(right - dw, r.top() + 9, dw, 20), Qt.AlignVCenter | Qt.AlignRight, date)
        f2 = QFont("Segoe UI", 8.5)
        p.setFont(f2)
        p.setPen(QColor("#A88A66"))
        prev = QFontMetrics(f2).elidedText(onizleme(n), Qt.ElideRight, int(right - x))
        p.drawText(QRectF(x, r.top() + 31, right - x, 18), Qt.AlignVCenter | Qt.AlignLeft, prev)
        p.restore()


# ---------------------------------------------------------------------------
# Çizgili kâğıt yazı alanı
# ---------------------------------------------------------------------------

class LinedEdit(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.line_color = QColor(242, 184, 75, 70)
        self.setFrameShape(QFrame.NoFrame)
        self.document().setDocumentMargin(4)

    def paintEvent(self, e):
        p = QPainter(self.viewport())
        ls = self.fontMetrics().lineSpacing()
        block = self.firstVisibleBlock()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top() if block.isValid() else 4
        y = top + ls - 1
        while y > ls:
            y -= ls
        p.setPen(QPen(self.line_color, 1))
        h = self.viewport().height()
        while y < h:
            p.drawLine(0, int(y), self.viewport().width(), int(y))
            y += ls
        p.end()
        super().paintEvent(e)


# ---------------------------------------------------------------------------
# Boş hâl (hiç not yokken)
# ---------------------------------------------------------------------------

class EmptyState(QWidget):
    def __init__(self, on_new):
        super().__init__()
        self.t = 0.0
        btn = QPushButton("＋ İlk notunu yaz", objectName="ana", clicked=on_new)
        lay = QVBoxLayout(self)
        lay.addStretch(5)
        lay.addWidget(btn, 0, Qt.AlignHCenter)
        lay.addStretch(1)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2, self.height() * 0.48
        p.save()
        p.translate(cx, cy)
        p.scale(0.95, 0.95)
        cizim.draw_nest(p, 0, 0, eggs=0, part="back")
        cizim.draw_duck(p, {"x": 0, "y": -16, "sit": True, "eyes": "closed",
                            "outfit": {"nightcap"}, "bob": math.sin(self.t * 2) * 1.2})
        cizim.draw_nest(p, 0, 0, part="front")
        p.restore()
        p.setPen(QColor("#9AA6C4"))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        z = (self.t * 0.5) % 1
        p.drawText(QPointF(cx + 26 + z * 10, cy - 90 - z * 16), "z")
        p.setPen(BROWN)
        p.setFont(QFont("Segoe Print", 13, QFont.Bold))
        p.drawText(QRectF(0, cy + 18, self.width(), 30), Qt.AlignCenter, "Henüz not yok")
        p.setPen(SOFT)
        p.setFont(QFont("Segoe UI", 9.5))
        p.drawText(QRectF(0, cy + 46, self.width(), 22), Qt.AlignCenter,
                   "Aklındakileri yaz, ördek yuvasında saklasın 🥚")


# ---------------------------------------------------------------------------
# Not defteri penceresi
# ---------------------------------------------------------------------------

STYLE = """
QWidget { font-family: "Segoe UI"; }
QLineEdit#ara { background:#FFFFFF; border:1.5px solid #F0DDBB; border-radius:15px;
                padding:6px 12px; color:#5A3D1E; font-size:9.5pt; }
QLineEdit#ara:focus { border-color:#F2B84B; }
QLineEdit#baslik { background:transparent; border:none; color:#5A3D1E;
                   font-size:17pt; font-weight:600; padding:2px 0; }
QListWidget { background:transparent; border:none; outline:0; }
QPlainTextEdit { background:transparent; color:#4E3A24; font-size:11pt;
                 selection-background-color:#F9D59A; }
QPushButton#ana { background:#F7A21E; color:white; border:none; border-radius:15px;
                  padding:8px 16px; font-size:10pt; font-weight:bold; }
QPushButton#ana:hover { background:#FFB540; }
QPushButton#ikon { background:transparent; border:none; border-radius:13px;
                   font-size:12pt; padding:2px 6px; }
QPushButton#ikon:hover { background:rgba(184,104,44,0.12); }
QPushButton#ikon:checked { background:rgba(242,184,75,0.35); }
QPushButton#sil { background:transparent; border:none; border-radius:13px;
                  color:#C0504D; font-size:9pt; font-weight:bold; padding:4px 8px; }
QPushButton#sil:hover { background:rgba(192,80,77,0.12); }
QPushButton#kapat { background:#F7C57E; color:white; border:none; border-radius:15px;
                    font-size:12pt; font-weight:bold; }
QPushButton#kapat:hover { background:#F08A24; }
QLabel#meta { color:#B9976E; font-size:8.5pt; }
QScrollBar:vertical { background:transparent; width:8px; margin:4px 0; }
QScrollBar::handle:vertical { background:#EAD2A8; border-radius:4px; min-height:24px; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; }
QScrollBar::add-page, QScrollBar::sub-page { background:transparent; }
"""


class NotesWindow(QWidget):
    W, H = 780, 560
    PANEL = QRectF(14, 50, 752, 496)

    def __init__(self, app, notes):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.app = app
        self.notes = notes
        self.current = None
        self.loading = False
        self.confirm_delete = False
        self.drag_offset = None
        self.t = 0.0
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)
        self.setWindowTitle("Notlarım")
        self.setStyleSheet(STYLE)

        self.save_timer = QTimer(self, singleShot=True, interval=500, timeout=self._save_now)

        # --- üst satır: arama + kapat ---
        self.search = QLineEdit(self, objectName="ara")
        self.search.setPlaceholderText("🔍  Notlarda ara…")
        self.search.setFixedSize(230, 32)
        self.search.move(int(self.PANEL.right() - 300), int(self.PANEL.top() + 20))
        self.search.textChanged.connect(lambda _: self.refresh())
        close = QPushButton("✕", self, objectName="kapat", clicked=self.close)
        close.setFixedSize(30, 30)
        close.move(int(self.PANEL.right() - 52), int(self.PANEL.top() + 21))

        # --- sol: yeni not + kartlar ---
        new_btn = QPushButton("＋  Yeni not", objectName="ana", clicked=self.new_note)
        self.list = QListWidget()
        self.list.setItemDelegate(CardDelegate(self.list))
        self.list.setMouseTracking(True)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.currentItemChanged.connect(self.select)
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(new_btn)
        left.addWidget(self.list, 1)
        left_box = QWidget()
        left_box.setLayout(left)
        left_box.setFixedWidth(250)

        # --- sağ: düzenleyici kartı ---
        self.title = QLineEdit(objectName="baslik")
        self.title.setPlaceholderText("Başlık")
        self.title.textChanged.connect(self.edited)
        self.date = QLabel(objectName="meta")
        self.dots = []
        dots_row = QHBoxLayout()
        dots_row.setSpacing(6)
        for ad, kagit, vurgu in RENKLER:
            b = QPushButton()
            b.setFixedSize(18, 18)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip("Not rengi")
            b.clicked.connect(lambda _=False, a=ad: self.set_color(a))
            b._renk = (ad, kagit, vurgu)
            self.dots.append(b)
            dots_row.addWidget(b)
        self.pin = QPushButton("📌", objectName="ikon", checkable=True)
        self.pin.setToolTip("Sabitle (listede en üstte durur)")
        self.pin.clicked.connect(self.toggle_pin)
        self.del_btn = QPushButton("Sil", objectName="sil", clicked=self.delete_note)
        meta = QHBoxLayout()
        meta.addWidget(self.date)
        meta.addStretch()
        meta.addLayout(dots_row)
        meta.addSpacing(10)
        meta.addWidget(self.pin)
        meta.addWidget(self.del_btn)
        self.body = LinedEdit()
        self.body.setPlaceholderText("Yazmaya başla…")
        self.body.textChanged.connect(self.edited)
        self.status = QLabel(objectName="meta")
        self.status.setAlignment(Qt.AlignRight)

        self.editor = QFrame()
        self.editor.setObjectName("kagit")
        ed = QVBoxLayout(self.editor)
        ed.setContentsMargins(22, 14, 22, 10)
        ed.setSpacing(6)
        ed.addWidget(self.title)
        ed.addLayout(meta)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#F0DDBB;")
        ed.addWidget(line)
        ed.addWidget(self.body, 1)
        ed.addWidget(self.status)

        self.empty = EmptyState(self.new_note)

        body = QHBoxLayout(self)
        body.setContentsMargins(int(self.PANEL.left() + 22), int(self.PANEL.top() + 72),
                                int(self.W - self.PANEL.right() + 22), int(self.H - self.PANEL.bottom() + 20))
        body.setSpacing(16)
        body.addWidget(left_box)
        body.addWidget(self.editor, 1)
        body.addWidget(self.empty, 1)

        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_note)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search.setFocus)
        QShortcut(QKeySequence("Escape"), self, activated=self.close)

        self.anim = QTimer(self, interval=50, timeout=self._tick)
        self.refresh()

    # ----- liste -----
    def refresh(self, select_id=None):
        keep = select_id or (self.current["id"] if self.current else None)
        self.loading = True
        self.list.clear()
        shown = self.notes.sorted(self.search.text())
        for n in shown:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, n["id"])
            item.setData(Qt.UserRole + 1, n)
            self.list.addItem(item)
        self.loading = False
        has_any = bool(self.notes.items)
        self.empty.setVisible(not has_any)
        self.editor.setVisible(has_any)
        if not shown:
            self.current = None if not has_any else self.current
            self._load(self.current)
            return
        row = 0
        for i, n in enumerate(shown):
            if n["id"] == keep:
                row = i
                break
        self.list.setCurrentRow(row)
        self.update()

    def _repaint_list(self):
        self.list.viewport().update()

    def select(self, item, _prev=None):
        if self.loading or item is None:
            return
        nid = item.data(Qt.UserRole)
        self.current = next((n for n in self.notes.items if n["id"] == nid), None)
        self.confirm_delete = False
        self.del_btn.setText("Sil")
        self._load(self.current)

    def _load(self, n):
        self.loading = True
        enabled = n is not None
        for w in (self.title, self.body, self.pin, self.del_btn, *self.dots):
            w.setEnabled(enabled)
        self.title.setText(n["baslik"] if n else "")
        self.body.setPlainText(n["metin"] if n else "")
        self.pin.setChecked(bool(n and n.get("sabit")))
        self.date.setText(tarih_yazisi(n["guncel"]) if n else "")
        self._apply_color(n.get("renk", "sari") if n else "sari")
        self._status("")
        self.loading = False

    def _apply_color(self, ad):
        paper, accent = RENK.get(ad, RENK["sari"])
        self.editor.setStyleSheet(
            f"QFrame#kagit {{ background:{paper.name()}; border:1.5px solid {accent.lighter(130).name()};"
            f" border-radius:18px; }}")
        lc = QColor(accent)
        lc.setAlpha(75)
        self.body.line_color = lc
        self.body.viewport().update()
        for b in self.dots:
            a, kagit, vurgu = b._renk
            border = "2.5px solid #5A3D1E" if a == ad else f"1.5px solid {vurgu}"
            b.setStyleSheet(f"QPushButton {{ background:{kagit}; border:{border}; border-radius:9px; }}")

    def _status(self, extra):
        n = len(self.body.toPlainText())
        self.status.setText(f"{n} karakter" + (f"  ·  {extra}" if extra else ""))

    # ----- düzenleme -----
    def edited(self):
        if self.loading or not self.current:
            return
        self.current["baslik"] = self.title.text()
        self.current["metin"] = self.body.toPlainText()
        self.current["guncel"] = time.time()
        self.date.setText(tarih_yazisi(self.current["guncel"]))
        self._repaint_list()
        self._status("kaydediliyor…")
        self.save_timer.start()

    def _save_now(self):
        self.notes.save()
        self._status("kaydedildi ✓")

    def set_color(self, ad):
        if not self.current:
            return
        self.current["renk"] = ad
        self._apply_color(ad)
        self._repaint_list()
        self.save_timer.start()

    def toggle_pin(self):
        if not self.current:
            return
        self.current["sabit"] = self.pin.isChecked()
        self.save_timer.start()
        self.refresh(self.current["id"])

    def new_note(self):
        self.search.clear()
        note = self.notes.add()
        self.current = note
        self.refresh(note["id"])
        self.title.setFocus()

    def delete_note(self):
        if not self.current:
            return
        if not self.confirm_delete:                  # önce bir kez sor
            self.confirm_delete = True
            self.del_btn.setText("Emin misin?")
            QTimer.singleShot(3000, self._reset_delete)
            return
        nid = self.current["id"]
        self.current = None
        self.confirm_delete = False
        self.del_btn.setText("Sil")
        self.notes.delete(nid)
        self.refresh()

    def _reset_delete(self):
        self.confirm_delete = False
        self.del_btn.setText("Sil")

    # ----- pencere -----
    def show_near(self, gx, gy):
        scr = QApplication.screenAt(QPoint(int(gx), int(gy))) or QApplication.primaryScreen()
        a = scr.availableGeometry()
        x = max(a.left(), min(int(gx - self.W / 2), a.right() - self.W))
        y = max(a.top(), min(int(gy - self.H - 20), a.bottom() - self.H))
        self.move(x, y)
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()
        keep_on_top(self)
        self.anim.start()

    def closeEvent(self, e):
        if self.save_timer.isActive():
            self.save_timer.stop()
        self.notes.save()
        self.anim.stop()
        super().closeEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_offset = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.drag_offset is not None:
            self.move(e.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, e):
        self.drag_offset = None

    def _tick(self):
        self.t += 0.05
        self.empty.t = self.t
        if self.empty.isVisible():
            self.empty.update()
        self.update(int(self.PANEL.left()), 0, 140, int(self.PANEL.top() + 80))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.PANEL
        # yumuşak gölge + krem defter
        for i, a in enumerate((18, 12, 7)):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(120, 80, 30, a))
            p.drawRoundedRect(r.adjusted(-i, 2 - i, i, 6 + i), 28 + i, 28 + i)
        p.setPen(QPen(QColor("#F0DDBB"), 2))
        p.setBrush(QColor("#FFF9EF"))
        p.drawRoundedRect(r, 28, 28)

        # kenardan bakan ördek
        bob = math.sin(self.t * 2.2) * 1.2
        cizim.draw_duck(p, {"x": r.left() + 70, "y": r.top() + 4 + bob, "sit": True,
                            "scale": 0.62, "blink": False,
                            "eyes": "closed" if (self.t % 4) < 0.12 else "open"})
        # başlık
        p.setPen(BROWN)
        p.setFont(QFont("Segoe Print", 18, QFont.Bold))
        p.drawText(QPointF(r.left() + 118, r.top() + 50), "Notlarım")
        count = len(self.notes.items)
        p.setPen(SOFT)
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QPointF(r.left() + 262, r.top() + 48), f"{count} not" if count else "")
        # başlığın altındaki ayak izi şeridi
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(242, 184, 75, 60))
        for k in range(14):
            fx = r.left() + 36 + k * 50
            fy = r.top() + 70 + (3 if k % 2 else -1)
            self._footprint(p, fx, fy)

    @staticmethod
    def _footprint(p, x, y):
        path = QPainterPath()
        path.moveTo(x, y + 4)
        path.lineTo(x - 4.5, y - 2)
        path.lineTo(x - 1, y - 0.6)
        path.lineTo(x, y - 4.5)
        path.lineTo(x + 1, y - 0.6)
        path.lineTo(x + 4.5, y - 2)
        path.closeSubpath()
        p.drawPath(path)
