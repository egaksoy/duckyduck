"""Arkadaşına göndermek için kurulum paketi hazırlar.

    paylas.bat                  → dist/duckyduck_kurulum.zip            (herkese açık, zip)
    paylas.bat <kisi>           → dist/duckyduck_kurulum_<kisi>.zip  (ozel/<kisi>/ eklentileriyle)
    paylas.bat exe              → dist/duckyduck.exe                 (tek dosya, çift tıkla kurulur)
    paylas.bat <kisi> exe       → dist/duckyduck_<kisi>.exe            (tek dosya + özel eklenti)

Pakete ASLA girmeyenler:
    veri/      senin notların, ayarların, doğum günün, açlık durumu
    ozel/      tek kişiye özel eklentiler (yalnızca adı verilen kişininki, o da eklentiler/ içine)
    dist/, __pycache__/, .git, paylas.py, paylas.bat
"""

import os
import shutil
import subprocess
import sys
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT_FILES = {"baslat.bat", "kur.bat", "KURULUM.txt", ".gitignore"}
SKIP_ROOT = {"paylas.py"}


def files_to_pack(kisi=None):
    out = []
    for name in sorted(os.listdir(BASE)):
        full = os.path.join(BASE, name)
        if os.path.isfile(full) and name not in SKIP_ROOT and (name.endswith(".py") or name in ROOT_FILES):
            out.append((full, name))
    ek = os.path.join(BASE, "eklentiler")
    if os.path.isdir(ek):
        for name in sorted(os.listdir(ek)):
            full = os.path.join(ek, name)
            if os.path.isfile(full):
                out.append((full, f"eklentiler/{name}"))
    if kisi:
        oz = os.path.join(BASE, "ozel", kisi)
        for name in sorted(os.listdir(oz)):
            full = os.path.join(oz, name)
            if os.path.isfile(full) and name.endswith(".py"):
                out.append((full, f"eklentiler/{name}"))
    return out


def make_icon(path, kisi=None):
    """Logodan .ico üretir. Özel eklentide logo_ekstra varsa (örn. bir aksesuar) logoya eklenir."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, BASE)
    import importlib.util
    from PySide6.QtGui import QGuiApplication
    import logo
    app = QGuiApplication.instance() or QGuiApplication([])
    ekstra = []
    if kisi:
        folder = os.path.join(BASE, "ozel", kisi)
        for name in sorted(os.listdir(folder)):
            if name.endswith(".py"):
                spec = importlib.util.spec_from_file_location(f"ozel_{name[:-3]}", os.path.join(folder, name))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if callable(getattr(mod, "logo_ekstra", None)):
                    ekstra.append(mod.logo_ekstra)
    logo.save_ico(path, ekstra)
    return app


def build_exe(kisi):
    stage = os.path.join(BASE, "build", f"stage_{kisi or 'genel'}")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(os.path.join(stage, "eklentiler"))
    for full, arc in files_to_pack(kisi):
        if arc.endswith(".py") or arc.startswith("eklentiler/"):
            dst = os.path.join(stage, *arc.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(full, dst)
    ico = os.path.join(stage, "ordek.ico")
    make_icon(ico, kisi)
    name = f"duckyduck_{kisi}" if kisi else "duckyduck"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
           "--name", name, "--icon", ico,
           "--add-data", f"{os.path.join(stage, 'eklentiler')};eklentiler",
           "--distpath", os.path.join(BASE, "dist"),
           "--workpath", os.path.join(BASE, "build", "work"),
           "--specpath", os.path.join(BASE, "build"),
           "--exclude-module", "anthropic", "--exclude-module", "tkinter",
           os.path.join(stage, "ordek.py")]
    print("EXE hazırlanıyor (1-3 dakika sürebilir)...")
    subprocess.run(cmd, cwd=stage, check=True,
                   stdout=subprocess.DEVNULL if "--sessiz" in sys.argv else None)
    exe = os.path.join(BASE, "dist", name + ".exe")
    print(f"\nHazır: {exe}  ({os.path.getsize(exe) / 1e6:.0f} MB)")
    print("Arkadaşın çift tıklayınca kendini kurar, masaüstüne kısayol açar ve ördek gelir.")
    print("Notların, ayarların ve doğum günün (veri/) bu dosyada yok.")
    return 0


def main():
    args = [a for a in sys.argv[1:] if a.strip() and not a.startswith("--")]
    want_exe = "exe" in [a.lower() for a in args]
    args = [a for a in args if a.lower() != "exe"]
    kisi = args[0].strip() if args else None
    if kisi:
        oz = os.path.join(BASE, "ozel", kisi)
        if not os.path.isdir(oz):
            mevcut = sorted(os.listdir(os.path.join(BASE, "ozel"))) if os.path.isdir(os.path.join(BASE, "ozel")) else []
            print(f"'ozel/{kisi}' klasörü yok. Mevcut özel klasörler: {', '.join(mevcut) or '(yok)'}")
            return 1
    os.makedirs(os.path.join(BASE, "dist"), exist_ok=True)
    if want_exe:
        return build_exe(kisi)
    zip_name = f"duckyduck_kurulum_{kisi}.zip" if kisi else "duckyduck_kurulum.zip"
    zip_path = os.path.join(BASE, "dist", zip_name)
    files = files_to_pack(kisi)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for full, arc in files:
            z.write(full, f"duckyduck/{arc}")
    print(f"Hazır: {zip_path}")
    print("İçindekiler:")
    for _, arc in files:
        print(f"   duckyduck/{arc}")
    print("\nNotların, ayarların ve doğum günün (veri/) pakete eklenmedi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
