@echo off
chcp 65001 >nul
title Samsung TV Kanal Duzenleyici ve Temizleyici
cd /d "%~dp0"
echo ========================================================
echo   Samsung TV Kanal Duzenleyici ve Temizleyici
echo ========================================================
echo.
echo Program baslatiliyor, lutfen bekleyin...
start "" pythonw "%~dp0Samsung_Kanal_Yoneticisi.py"
exit
