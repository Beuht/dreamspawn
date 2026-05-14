@echo off
title Dreamspawn Builder
echo.
echo  ================================
echo   DREAMSPAWN — Build Windows
echo  ================================
echo.

cd /d "%~dp0"

pip show pyinstaller >nul 2>&1 || (
    echo Installation de PyInstaller...
    pip install pyinstaller
)

pyinstaller --name Dreamspawn --noconfirm --windowed --distpath dist --add-data "..\assets;assets" ..\src\main.py

echo.
echo  Build termine ! Retrouve ton .exe dans build/dist/
echo.
pause
