"""Windows ile konuşan küçük yardımcılar: öndeki pencere, boşta kalma süresi,
pencere çerçeveleri, tıklamaların içinden geçmesi, en üstte kalma."""

import ctypes
import ctypes.wintypes as wt
import os

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi

user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
user32.MonitorFromWindow.restype = wt.HANDLE
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wt.UINT]
for _fn in ("IsWindow", "IsWindowVisible", "IsIconic"):
    getattr(user32, _fn).argtypes = [wt.HWND]
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CreateMutexW.restype = wt.HANDLE
dwmapi.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]

OWN_PID = os.getpid()
DESKTOP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]


user32.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.POINTER(MONITORINFO)]


def single_instance(name):
    """Aynı isimle ikinci kez açılırsa False döner."""
    handle = kernel32.CreateMutexW(None, False, name)
    return handle, kernel32.GetLastError() != 183


def _window_pid(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def foreground_info():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    cls_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls_buf, 256)
    cls = cls_buf.value

    pid = _window_pid(hwnd)
    proc = ""
    h = kernel32.OpenProcess(0x1000, False, pid)
    if h:
        size = wt.DWORD(1024)
        pbuf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, pbuf, ctypes.byref(size)):
            proc = os.path.basename(pbuf.value).lower()
        kernel32.CloseHandle(h)

    fullscreen, monitor = False, None
    if cls not in DESKTOP_CLASSES:
        r = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        mon = user32.MonitorFromWindow(hwnd, 2)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if mon and user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
            m = mi.rcMonitor
            monitor = (m.left, m.top, m.right, m.bottom)
            fullscreen = (r.left <= m.left and r.top <= m.top and
                          r.right >= m.right and r.bottom >= m.bottom)
    return {"hwnd": hwnd, "title": buf.value, "proc": proc, "cls": cls, "pid": pid,
            "fullscreen": fullscreen, "monitor": monitor}


def idle_seconds():
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0
    return ((kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0


def set_click_through(widget, on):
    hwnd = wt.HWND(int(widget.winId()))
    style = user32.GetWindowLongPtrW(hwnd, -20)
    style = (style | 0x20 | 0x80000) if on else (style & ~0x20)
    user32.SetWindowLongPtrW(hwnd, -20, style)


def keep_on_top(widget):
    """Tam ekran uygulamaların üstünde de kalmak için tekrar en üste al."""
    if widget.isVisible():
        user32.SetWindowPos(wt.HWND(int(widget.winId())), wt.HWND(-1), 0, 0, 0, 0,
                            0x0001 | 0x0002 | 0x0010)   # NOSIZE|NOMOVE|NOACTIVATE


# --- pencere çerçeveleri ---

def frame_rect(hwnd):
    r = wt.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
    return r.left, r.top, r.right, r.bottom


def is_perchable(hwnd):
    if not hwnd or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return False
    if user32.GetWindowLongPtrW(hwnd, -20) & (0x80 | 0x08000000):
        return False
    cloaked = wt.DWORD()
    if (dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4) == 0
            and cloaked.value):
        return False
    if user32.GetWindowTextLengthW(hwnd) == 0:
        return False
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    if cls.value in DESKTOP_CLASSES or _window_pid(hwnd) == OWN_PID:
        return False
    r = frame_rect(hwnd)
    return bool(r and r[2] - r[0] >= 220 and r[3] - r[1] >= 120)


def window_at(x, y):
    """Fiziksel (x, y) noktasında en üstte görünen uygulama penceresi."""
    found = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and is_perchable(hwnd):
            r = frame_rect(hwnd)
            if r[0] <= x < r[2] and r[1] <= y < r[3]:
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found[0] if found else None


def window_alive(hwnd):
    return bool(user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd)
                and not user32.IsIconic(hwnd))


# --- fiziksel <-> Qt koordinatları (farklı ölçekli ekranlar için) ---

def _native_screen(x, y):
    for s in QApplication.screens():
        g, d = s.geometry(), s.devicePixelRatio()
        if g.x() <= x < g.x() + g.width() * d and g.y() <= y < g.y() + g.height() * d:
            return s
    return QApplication.primaryScreen()


def to_logical(x, y):
    s = _native_screen(x, y)
    g, d = s.geometry(), s.devicePixelRatio()
    return g.x() + (x - g.x()) / d, g.y() + (y - g.y()) / d


def to_native(x, y):
    s = QApplication.screenAt(QPoint(int(x), int(y))) or QApplication.primaryScreen()
    g, d = s.geometry(), s.devicePixelRatio()
    return int(g.x() + (x - g.x()) * d), int(g.y() + (y - g.y()) * d)


def logical_frame(hwnd):
    """(sol, üst, sağ) — Qt koordinatlarında."""
    r = frame_rect(hwnd)
    if not r:
        return None
    left, top = to_logical(r[0], r[1])
    right, _ = to_logical(r[2] - 1, r[1])
    return left, top, right + 1
