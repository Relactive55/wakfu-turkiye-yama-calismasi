@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0WakfuTurkceCeviri.ps1"
if errorlevel 1 pause
