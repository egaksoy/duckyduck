"""Örnek eklenti (adı "_" ile başladığı için yüklenmez).
Kendi eklentini yazmak için bu dosyayı kopyalayıp adını değiştir, örn. "kutlama.py"."""


def baslat(app):
    app.duck.hearts(2)


def ruh_hali(app, eski, yeni):
    if yeni == "music":
        app.duck.spawn("🎵", emoji=True)


def her_dakika(app):
    pass
