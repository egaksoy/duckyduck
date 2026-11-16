"""Ördekle sohbet kutusu. Cevapları Claude (internet) ya da Ollama (bilgisayarında) verir."""

import html
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QProgressBar, QPushButton, QTextBrowser, QVBoxLayout, QWidget)

import cizim
from pencereler import keep_on_top

SYSTEM = (
    "Sen, kullanıcının bilgisayar ekranında yaşayan sevimli, beyaz bir ördeksin; "
    "onun yol arkadaşısın. Türkçe konuş; sıcak, neşeli ve kısa cevap ver "
    "(genelde 1-3 cümle, kullanıcı uzun bir şey isterse daha uzun). Ara sıra 'vak' "
    "diyebilirsin ama abartma. Bilmediğin şeyi uydurma."
)


# ---------------------------------------------------------------------------
# Ollama: hazır mı? değilse tek tıkla kurulum
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_SETUP_URL = "https://ollama.com/download/OllamaSetup.exe"
NO_WINDOW = 0x08000000


def ollama_exe():
    yol = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    if os.path.exists(yol):
        return yol
    return shutil.which("ollama")


def ollama_durum(model):
    """(sunucu_açık, model_var)"""
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=1.5) as r:
            names = [m.get("name", "") for m in json.load(r).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return False, False
    return True, any(n == model or n == model + ":latest" for n in names)


def _sunucu_bekle(saniye=60):
    for _ in range(saniye * 2):
        try:
            urllib.request.urlopen(OLLAMA_URL + "/api/version", timeout=1).close()
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def ollama_kur(model, bildir):
    """Arka planda çalışır. bildir(yazı, oran) — oran 0..1 ya da -1 (süre belirsiz)."""
    exe = ollama_exe()
    if not exe:
        bildir("Ollama kuruluyor…", -1)
        if shutil.which("winget"):
            subprocess.run(["winget", "install", "-e", "--id", "Ollama.Ollama", "--silent",
                            "--accept-package-agreements", "--accept-source-agreements",
                            "--disable-interactivity"], creationflags=NO_WINDOW, check=False)
            exe = ollama_exe()
        if not exe:                                    # winget yoksa: resmî siteden indir
            hedef = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
            with urllib.request.urlopen(OLLAMA_SETUP_URL, timeout=30) as r, open(hedef, "wb") as f:
                toplam = int(r.headers.get("Content-Length") or 0)
                inen = 0
                while True:
                    parca = r.read(1 << 20)
                    if not parca:
                        break
                    f.write(parca)
                    inen += len(parca)
                    if toplam:
                        bildir(f"Ollama indiriliyor… %{inen * 100 // toplam}", inen / toplam)
            bildir("Ollama kuruluyor…", -1)
            subprocess.run([hedef, "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"], check=False)
            exe = ollama_exe()
        if not exe:
            raise RuntimeError("Ollama kurulamadı.")

    if not ollama_durum(model)[0]:
        bildir("Ollama başlatılıyor…", -1)
        app_exe = os.path.join(os.path.dirname(exe), "ollama app.exe")
        cmd = [app_exe] if os.path.exists(app_exe) else [exe, "serve"]
        subprocess.Popen(cmd, creationflags=NO_WINDOW | 0x00000008, close_fds=True)
        if not _sunucu_bekle():
            raise RuntimeError("Ollama açılamadı.")

    bildir("Sohbet modeli indiriliyor…", 0.0)
    req = urllib.request.Request(OLLAMA_URL + "/api/pull",
                                 data=json.dumps({"model": model, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        for line in r:
            if not line.strip():
                continue
            d = json.loads(line)
            if "error" in d:
                raise RuntimeError(d["error"])
            if d.get("total") and d.get("completed") is not None:
                tot, done = d["total"], d["completed"]
                bildir(f"Model indiriliyor… %{done * 100 // tot}  "
                       f"({done / 1e9:.1f} / {tot / 1e9:.1f} GB)", done / tot)
            elif d.get("status") == "success":
                break
    if not ollama_durum(model)[1]:
        raise RuntimeError("Model indirilemedi.")


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
            return "Konuşmam için sohbet modelini indirmem lazım. Aşağıdaki <b>Sohbeti kur</b> düğmesine bas 🦆", False
        return f"Ollama hata verdi ({e.code}).", False
    except (urllib.error.URLError, OSError):
        return ("Konuşabilmem için ücretsiz yapay zekâyı kurmam lazım. "
                "Aşağıdaki <b>Sohbeti kur</b> düğmesine basman yeterli 🦆"), False


class _Bridge(QObject):
    done = Signal(str, bool)
    checked = Signal(bool, bool)          # (sunucu açık, model var)
    progress = Signal(str, float)         # (yazı, oran; -1 = belirsiz)
    setup_done = Signal(bool, str)        # (başarılı mı, hata)


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
QFrame#kurulum { background:#FFF1D6; border:2px dashed #F2B84B; border-radius:14px; }
QLabel#kurulum_yazi { color:#7A5530; font: 9.5pt "Segoe UI"; background:transparent; border:none; }
QPushButton#kur { background:#F7A21E; color:white; border:none; border-radius:13px;
                  padding:7px 14px; font: bold 10pt "Segoe UI"; }
QPushButton#kur:hover { background:#FFB540; }
QProgressBar { background:#FFFDF7; border:1.5px solid #EBD5AE; border-radius:7px; height:14px;
               text-align:center; color:#7A5530; font: 8pt "Segoe UI"; }
QProgressBar::chunk { background:#F7A21E; border-radius:6px; }
QScrollBar:vertical { background:transparent; width:8px; margin:4px; }
QScrollBar::handle:vertical { background:#EBD5AE; border-radius:4px; min-height:24px; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; }
"""


class ChatWindow(QWidget):
    W, H = 380, 520
    PANEL = QRectF(10, 40, 360, 470)

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
        self.bridge.checked.connect(self._checked)
        self.bridge.progress.connect(self._progress)
        self.bridge.setup_done.connect(self._setup_done)
        self.setting_up = False

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ördeğe bir şey sor…")
        self.input.returnPressed.connect(self.send)
        self.send_btn = QPushButton("Gönder", objectName="gonder", clicked=self.send)

        # sohbet hazır değilse çıkan kurulum alanı
        self.setup_box = QFrame(objectName="kurulum")
        self.setup_text = QLabel(objectName="kurulum_yazi")
        self.setup_text.setWordWrap(True)
        self.setup_bar = QProgressBar()
        self.setup_bar.setRange(0, 1000)
        self.setup_bar.setTextVisible(False)
        self.setup_bar.hide()
        self.setup_btn = QPushButton("🦆  Sohbeti kur", objectName="kur", clicked=self.start_setup)
        sb_lay = QVBoxLayout(self.setup_box)
        sb_lay.setContentsMargins(12, 10, 12, 10)
        sb_lay.setSpacing(8)
        sb_lay.addWidget(self.setup_text)
        sb_lay.addWidget(self.setup_bar)
        sb_lay.addWidget(self.setup_btn, 0, Qt.AlignHCenter)
        self.setup_box.hide()

        row = QHBoxLayout()
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 104, 26, 24)
        lay.setSpacing(10)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.setup_box)
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
            self._check()          # Ollama yüzünden olduysa kurulum düğmesini göster
        self._add("duck", shown)
        self.app.duck.set_thinking(False)
        self.app.duck.quack()
        self.input.setFocus()

    # ----- tek tıkla sohbet kurulumu (Ollama + model) -----
    def _model(self):
        return self.app.settings["sohbet"].get("ollama_model", "gemma3:4b")

    def _check(self):
        if self.app.settings["sohbet"].get("saglayici") != "ollama" or self.setting_up:
            return
        model = self._model()
        threading.Thread(target=lambda: self.bridge.checked.emit(*ollama_durum(model)),
                         daemon=True).start()

    def _checked(self, server_ok, model_ok):
        if self.setting_up:
            return
        if server_ok and model_ok:
            self.setup_box.hide()
            return
        if ollama_exe() and server_ok:
            msg = "Konuşabilmem için sohbet modelini indirmem lazım (yaklaşık 3,5 GB, bir kez)."
        else:
            msg = ("Benimle konuşabilmen için ücretsiz yapay zekâyı (Ollama) kurmam lazım. "
                   "Her şey senin bilgisayarında çalışır; toplam yaklaşık 5 GB, bir kez iner.")
        self.setup_text.setText(msg)
        self.setup_bar.hide()
        self.setup_btn.setText("🦆  Sohbeti kur")
        self.setup_btn.show()
        self.setup_box.show()

    def start_setup(self):
        if self.setting_up:
            return
        self.setting_up = True
        self.setup_btn.hide()
        self.setup_bar.show()
        self._progress("Hazırlanıyor…", -1)
        model = self._model()

        def work():
            try:
                ollama_kur(model, lambda t, f: self.bridge.progress.emit(t, f))
                self.bridge.setup_done.emit(True, "")
            except Exception as e:                      # internet yok, disk dolu vb.
                self.bridge.setup_done.emit(False, str(e))

        threading.Thread(target=work, daemon=True).start()

    def _progress(self, text, frac):
        self.setup_text.setText(text)
        if frac < 0:
            self.setup_bar.setRange(0, 0)               # süresi belirsiz: kayan çubuk
        else:
            self.setup_bar.setRange(0, 1000)
            self.setup_bar.setValue(int(frac * 1000))

    def _setup_done(self, ok, err):
        self.setting_up = False
        if ok:
            self.setup_box.hide()
            self._add("duck", "Hazırım! Artık konuşabiliriz 💛 Bana bir şey sor.")
            self.app.duck.quack()
            self.app.duck.hearts(3)
        else:
            self.setup_bar.hide()
            self.setup_text.setText(f"Kurulum yarım kaldı: {html.escape(err)[:120]}. "
                                    "İnternetini kontrol edip tekrar dener misin?")
            self.setup_btn.setText("Tekrar dene")
            self.setup_btn.show()

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
        self._check()

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
