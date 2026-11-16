@echo off
chcp 65001 >nul
rem Kullanım:  paylas.bat                → herkese açık zip
rem            paylas.bat <kisi>        → ozel\<kisi>\ eklentisiyle, o kişiye özel zip
rem            paylas.bat exe            → tek dosya duckyduck.exe (çift tıkla kurulur)
rem            paylas.bat <kisi> exe    → o kişiye özel tek dosya exe
"%USERPROFILE%\.ordek-venv\Scripts\python.exe" "%~dp0paylas.py" %*
explorer "%~dp0dist"
pause
