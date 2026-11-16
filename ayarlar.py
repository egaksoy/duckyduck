"""Ayarlar ve kayıtlı veriler (veri/ klasöründe JSON dosyaları)."""

import copy
import hashlib
import json
import os

import sys

# Tek .exe olarak çalışırken (PyInstaller) program dosyaları geçici bir klasörden açılır;
# kişisel veriler o yüzden kullanıcının kendi klasöründe (%APPDATA%\duckyduck\veri) tutulur.
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    BASE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    VERI = os.environ.get("ORDEK_VERI") or os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "duckyduck", "veri")
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
    VERI = os.environ.get("ORDEK_VERI") or os.path.join(BASE, "veri")
os.makedirs(VERI, exist_ok=True)

# veri/ayarlar.json — istediğin gibi değiştirebilirsin, ördeği yeniden başlatınca geçerli olur
VARSAYILAN_AYARLAR = {
    "dogum_gunu": "",              # "AA-GG", örn. "07-23" → o gün parti şapkası takar
    "dogum_gunu_sahibi": "",       # doğum gününü kimin söylediği (bilgisayar+kullanıcı izi)
    "uyku_dakika": 3,              # bu kadar dokunmazsan uyur
    "odak_dakika": 25,
    "kirinti_dakika": [20, 40],    # ara sıra kendiliğinden kırıntı düşme aralığı
    "aciktim_saat": 3,             # bu kadar beslenmezse acıkır
    "kusme_saat": 6,               # bu kadar beslenmezse küser
    "yavru_dakika": [30, 60],      # yavru ördeğin kendiliğinden gelme aralığı
    "pencereye_cikma": 0.12,
    "sohbet": {
        "saglayici": "ollama",     # "ollama" (bilgisayarında, ücretsiz) ya da "claude"
        "claude_model": "claude-opus-5-5",
        "ollama_model": "gemma3:4b",
        "ekran_bilgisi": True,     # ördek hangi uygulamada olduğunu bilsin mi
    },
}

VARSAYILAN_DURUM = {
    "aclik_sn": 0.0,
    "yuva_x": None,
    "kiyafet": "otomatik",
}


def _yol(ad):
    return os.path.join(VERI, ad)


def oku(ad, varsayilan):
    try:
        with open(_yol(ad), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return copy.deepcopy(varsayilan)
    if isinstance(varsayilan, dict) and isinstance(data, dict):
        merged = copy.deepcopy(varsayilan)
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k].update(v)
            else:
                merged[k] = v
        return merged
    return data


def yaz(ad, veri):
    tmp = _yol(ad) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _yol(ad))


def sahip_kimligi():
    """Bu bilgisayar + Windows kullanıcısı için kısa bir iz. Ördek başka birinin
    bilgisayarına kopyalanırsa iz değişir ve doğum günü yeniden sorulur."""
    raw = f"{os.environ.get('COMPUTERNAME', '')}\\{os.environ.get('USERNAME', '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def ayarlari_yukle():
    ayarlar = oku("ayarlar.json", VARSAYILAN_AYARLAR)
    if not os.path.exists(_yol("ayarlar.json")):
        yaz("ayarlar.json", ayarlar)
    return ayarlar
