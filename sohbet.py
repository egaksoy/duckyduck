"""Ördekle sohbet kutusu. Cevapları Claude (internet) ya da Ollama (bilgisayarında) verir."""

import html
import json
import threading
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLineEdit, QPushButton,
                               QTextBrowser, QVBoxLayout, QWidget)

import cizim
from pencereler import keep_on_top

SYSTEM = (
    "Sen, kullanıcının bilgisayar ekranında yaşayan sevimli, beyaz bir ördeksin; "
    "onun yol arkadaşısın. Türkçe konuş; sıcak, neşeli ve kısa cevap ver "
    "(genelde 1-3 cümle, kullanıcı uzun bir şey isterse daha uzun). Ara sıra 'vak' "
    "diyebilirsin ama abartma. Bilmediğin şeyi uydurma."
)


def sistem_metni(context):
    if not context:
        return SYSTEM
    return (SYSTEM + f"\n\nKullanıcının ekranında şu an açık olan pencere: {context}. "
            "İşe yararsa buna değin; bu bilgiyi aynen tekrar etme.")


def _temizle(text):
    """Model ekran bilgisini cevabın başına kopyalarsa sil."""
    lines = text.strip().splitlines()
    while lines and lines[0].strip().startswith("[") and lines[0].strip().endswith("]"):
        lines.pop(0)
    return "\n".join(lines).strip()

KURULUM_CLAUDE = (
    "Konuşabilmem için bir Claude API anahtarı lazım. "
    "console.anthropic.com adresinden bir anahtar al, sonra PowerShell'de "
    "<b>setx ANTHROPIC_API_KEY \"anahtarın\"</b> yaz ve beni yeniden başlat. "
    "Ya da bilgisayarında çalışan ücretsiz bir model istersen veri/ayarlar.json "
    "içinde saglayici'yi \"ollama\" yap."
)


# ---------------------------------------------------------------------------
# Cevap üreticiler (arka planda çalışır)
# ---------------------------------------------------------------------------

def claude_cevap(gecmis, model, sistem=SYSTEM):
    try:
        import anthropic
    except ImportError:
        return ("Bu sürümde Claude bağlantısı yok. Ücretsiz sohbet için Ollama'yı kurup "
                "veri/ayarlar.json içinde saglayici'yi \"ollama\" yapabilirsin."), False
    try:
        client = anthropic.Anthropic()
        resp = client.beta.messages.create(
            model=model,
            max_tokens=1024,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low"},
            system=sistem,
            messages=gecmis,
        )
    except anthropic.AuthenticationError:
        return "API anahtarım çalışmıyor gibi. Anahtarı kontrol eder misin? " + KURULUM_CLAUDE, False
    except anthropic.RateLimitError:
        return "Vak… biraz yoruldum, birazdan tekrar sorar mısın?", False
    except anthropic.APIConnectionError:
        return "İnternete bağlanamadım. Bağlantın açık mı?", False
    except anthropic.APIStatusError as e:
        return f"Bir sorun çıktı (hata {e.status_code}). Birazdan tekrar dene.", False
    except Exception as e:   # anahtar hiç yoksa SDK burada hata verir
        if "auth" in str(e).lower() or "api_key" in str(e).lower():
            return KURULUM_CLAUDE, False
        return f"Bir şeyler ters gitti: {e}", False
    if resp.stop_reason == "refusal":
        return "Vak… buna cevap veremem, başka bir şey soralım mı?", True
    text = _temizle("".join(b.text for b in resp.content if b.type == "text"))
    return text or "Vak?", True


def ollama_cevap(gecmis, model, sistem=SYSTEM):
    body = json.dumps({"model": model, "stream": False, "keep_alive": "20m",
                       "messages": [{"role": "system", "content": sistem}] + gecmis}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return _temizle(json.load(r)["message"]["content"]) or "Vak?", True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"“{model}” modeli yok. Terminalde <b>ollama pull {model}</b> yazar mısın?", False
        return f"Ollama hata verdi ({e.code}).", False
    except (urllib.error.URLError, OSError):
        return ("Ollama çalışmıyor gibi. Ollama'yı kurup açtın mı? "
                f"Sonra <b>ollama pull {model}</b> yazman yeterli."), False


class _Bridge(QObject):
    done = Signal(str, bool)


# ---------------------------------------------------------------------------
# Pencere
# ---------------------------------------------------------------------------

STYLE = """
QTextBrowser { background:#FFFDF7; border:2px solid #EBD5AE; border-radius:14px;
               padding:6px; color:#5A4630; font: 10.5pt "Segoe UI"; }
QLineEdit { background:#FFFDF7; border:2px solid #EBD5AE; border-radius:14px;
            padding:7px 10px; color:#5A4630; font: 10.5pt "Segoe UI"; }
QLineEdit:focus { border-color:#F7A21E; }
QPushButton#gonder { background:#F7A21E; color:white; border:none; border-radius:14px;
                     padding:7px 14px; font: bold 10pt "Segoe UI"; }
QPushButton#gonder:hover { background:#FFB540; }
QPushButton#gonder:disabled { background:#F3D3A0; }
QPushButton#kapat { background:#F7C57E; color:white; border:none; border-radius:13px;
                    font: bold 11pt "Segoe UI"; }
QPushButton#kapat:hover { background:#F08A24; }
QScrollBar:vertical { background:transparent; width:8px; margin:4px; }
QScrollBar::handle:vertical { background:#EBD5AE; border-radius:4px; min-height:24px; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; }
"""


class ChatWindow(QWidget):
    W, H = 380, 480
    PANEL = QRectF(10, 40, 360, 430)

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)
        self.setWindowTitle("Ördekle sohbet")
        self.setStyleSheet(STYLE)
        self.history = []          # API'ye giden mesajlar
        self.rows = []             # ekranda gösterilenler (kim, html)
        self.busy = False
        self.drag_offset = None
        self.bridge = _Bridge()
        self.bridge.done.connect(self._answer)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ördeğe bir şey sor…")
        self.input.returnPressed.connect(self.send)
        self.send_btn = QPushButton("Gönder", objectName="gonder", clicked=self.send)

        row = QHBoxLayout()
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 104, 26, 24)
        lay.setSpacing(10)
        lay.addWidget(self.view, 1)
        lay.addLayout(row)

        close = QPushButton("✕", self, objectName="kapat", clicked=self.close)
        close.setFixedSize(26, 26)
        close.move(int(self.PANEL.right() - 40), int(self.PANEL.top() + 14))

        self._add("duck", "Vak! Merhaba 💛 Bana ne istersen sorabilirsin.")

    # ----- mesajlar -----
    def _add(self, who, text_html):
        self.rows.append((who, text_html))
        self._render()

    def _render(self):
        parts = []
        for who, t in self.rows:
            if who == "user":
                parts.append(
                    "<table width='100%' cellspacing='0' cellpadding='0' style='margin:4px 0'><tr>"
                    "<td width='22%'></td><td bgcolor='#F9D59A' style='padding:8px 10px'>"
                    f"{t}</td></tr></table>")
            else:
                parts.append(
                    "<table width='100%' cellspacing='0' cellpadding='0' style='margin:4px 0'><tr>"
                    "<td width='26' valign='top' style='font-size:16pt'>🦆</td>"
                    f"<td bgcolor='#FFF1D6' style='padding:8px 10px'>{t}</td>"
                    "<td width='12%'></td></tr></table>")
        self.view.setHtml("".join(parts))
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def send(self):
        text = self.input.text().strip()
        if not text or self.busy:
            return
        self.input.clear()
        self._add("user", html.escape(text).replace("\n", "<br>"))
        sistem = sistem_metni(self.app.screen_context())
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-20:]
        if self.history[0]["role"] != "user":
            self.history = self.history[1:]
        self.busy = True
        self.send_btn.setEnabled(False)
        self._add("duck", "<i>düşünüyor… 🤔</i>")
        self.app.duck.set_thinking(True)

        cfg = self.app.settings["sohbet"]
        msgs = list(self.history)

        def work():
            if cfg.get("saglayici") == "ollama":
                ans, ok = ollama_cevap(msgs, cfg.get("ollama_model", "gemma3:4b"), sistem)
            else:
                ans, ok = claude_cevap(msgs, cfg.get("claude_model", "claude-opus-5-5"), sistem)
            self.bridge.done.emit(ans, ok)

        threading.Thread(target=work, daemon=True).start()

    def _answer(self, text, ok):
        self.busy = False
        self.send_btn.setEnabled(True)
        self.rows.pop()            # "düşünüyor" satırı
        if ok:
            self.history.append({"role": "assistant", "content": text})
            shown = html.escape(text).replace("\n", "<br>")
        else:
            self.history.pop()     # başarısız soruyu geçmişten çıkar
            shown = text           # kurulum mesajları biçimli
        self._add("duck", shown)
        self.app.duck.set_thinking(False)
        self.app.duck.quack()
        self.input.setFocus()

    # ----- pencere -----
    def show_near(self, gx, gy):
        scr = QApplication.screenAt(QPoint(int(gx), int(gy))) or QApplication.primaryScreen()
        a = scr.availableGeometry()
        x = max(a.left(), min(int(gx - self.W / 2), a.right() - self.W))
        y = max(a.top(), min(int(gy - self.H - 10), a.bottom() - self.H))
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        keep_on_top(self)
        self.input.setFocus()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_offset = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.drag_offset is not None:
            self.move(e.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, e):
        self.drag_offset = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.PANEL
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(120, 80, 30, 40))
        p.drawRoundedRect(r.translated(0, 5), 24, 24)
        p.setPen(QPen(QColor("#E9CFA0"), 3))
        p.setBrush(QColor("#FFF3DC"))
        p.drawRoundedRect(r, 24, 24)
        cizim.draw_duck(p, {"x": r.left() + 56, "y": r.top() + 58, "scale": 0.62,
                            "sit": True, "quack": self.busy})
        p.setPen(QColor("#B8682C"))
        p.setFont(QFont("Segoe Print", 15, QFont.Bold))
        p.drawText(QRectF(r.left() + 100, r.top() + 14, 220, 40), Qt.AlignVCenter, "Ördekle sohbet")
        p.setPen(QColor("#C79A64"))
        p.setFont(QFont("Segoe UI", 8))
        cfg = self.app.settings["sohbet"]
        src = "Ollama · bilgisayarında" if cfg.get("saglayici") == "ollama" else "Claude ile"
        p.drawText(QPointF(r.left() + 104, r.top() + 56), src)
