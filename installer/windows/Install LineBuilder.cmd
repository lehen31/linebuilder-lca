@echo off
rem Installs LineBuilder into this folder (Python 3.11, Brightway2, the app, its Brightway project). The work is done by install.ps1.
chcp 65001 >nul
cd /d "%~dp0"
title LineBuilder: installation
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
pause
