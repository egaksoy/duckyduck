@echo off
chcp 65001 >nul
title duckyduck kurulumu
cd /d "%~dp0"
echo.
echo   ======================================
echo      duckyduck - masaüstü yol arkadaşın
echo   ======================================
echo.

set "VENV=%USERPROFILE%\.ordek-venv"
set "PY="

rem --- Python var mı? (Microsoft Store kısayolu sahte olabilir, gerçekten çalışıyor mu bak) ---
py -3 -c "print(1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "print(1)" >nul 2>nul && set "PY=python"
if not defined PY (
    echo Python bulunamadı. Ördeğin çalışması için Python gerekiyor.
    choice /C EH /M "Python şimdi kurulsun mu (E=evet, H=hayır)"
    if errorlevel 2 goto iptal
    winget install -e --id Python.Python.3.12 --scope user
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PY (
    echo Python kurulamadı. python.org adresinden Python 3 kurup bu dosyayı tekrar çalıştır.
    goto bitis
)

echo [1/3] Ördeğe özel Python ortamı hazırlanıyor...
if not exist "%VENV%\Scripts\python.exe" %PY% -m venv "%VENV%"
echo [2/3] Gerekli parçalar indiriliyor (birkaç dakika sürebilir)...
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -q PySide6-Essentials anthropic
if errorlevel 1 (
    echo Parçalar indirilemedi. İnternet bağlantını kontrol edip tekrar dene.
    goto bitis
)

echo.
echo [3/3] Ördekle sohbet için ücretsiz yapay zekâ (Ollama + model, toplam yaklaşık 5 GB).
echo       İstemezsen ördek yine her şeyi yapar, sadece sohbet kutusu cevap vermez.
choice /C EH /M "Ollama kurulsun mu (E=evet, H=hayır)"
if errorlevel 2 goto baslat
where ollama >nul 2>nul || winget install -e --id Ollama.Ollama
set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
timeout /t 5 /nobreak >nul
if exist "%OLLAMA%" ("%OLLAMA%" pull gemma3:4b) else (ollama pull gemma3:4b)

:baslat
echo.
echo Kurulum bitti! duckyduck açılıyor, ördek geliyor...
echo  - Çağırmak için: ekranda bir yere sağ tuşla 1 saniye basılı tut
echo  - Menü için: ördeğe sağ tıkla
echo  - Bilgisayar açılınca ördek kendiliğinden gelir (istemezsen saatin yanındaki simgeden kapatabilirsin)
start "" "%VENV%\Scripts\pythonw.exe" "%~dp0ordek.py"
goto bitis

:iptal
echo Kurulum iptal edildi.

:bitis
echo.
pause
