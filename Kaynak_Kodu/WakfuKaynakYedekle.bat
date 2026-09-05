@echo off
chcp 65001 >nul
set "SCRIPT=%~dp0WakfuKaynakYedekle.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
if errorlevel 1 (
    echo Yedekleme basarisiz.
    pause
    exit /b 1
)
echo Yedekleme tamam.
pause
