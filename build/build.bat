@echo off
title Dreamspawn Builder
echo.
echo  ================================================
echo   DREAMSPAWN - Build Windows
echo  ================================================
echo.

cd /d "%~dp0"

::---- 1. Trouver Python -----------------------------------------
set "PY="

where python >nul 2>&1
if %errorlevel% equ 0 set "PY=python"

if not defined PY (
    where py >nul 2>&1
    if %errorlevel% equ 0 set "PY=py"
)

if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PY if exist "%ProgramFiles%\Python313\python.exe"               set "PY=%ProgramFiles%\Python313\python.exe"
if not defined PY if exist "%ProgramFiles%\Python312\python.exe"               set "PY=%ProgramFiles%\Python312\python.exe"

if not defined PY (
    echo [!] Python introuvable. Tentative d'installation automatique...
    echo.
    winget --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo     Via winget...
        winget install Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    ) else (
        echo     Telechargement de Python 3.12...
        curl -L -o "%TEMP%\python_setup.exe" "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
        if exist "%TEMP%\python_setup.exe" (
            "%TEMP%\python_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
            del "%TEMP%\python_setup.exe" >nul 2>&1
        )
    )
    if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if not defined PY (
        where py >nul 2>&1
        if %errorlevel% equ 0 set "PY=py"
    )
    if not defined PY (
        where python >nul 2>&1
        if %errorlevel% equ 0 set "PY=python"
    )
)

if not defined PY (
    echo.
    echo  !! ECHEC : Python n'a pas pu etre installe automatiquement.
    echo  Installe Python manuellement : https://www.python.org/downloads/
    echo  IMPORTANT : coche "Add Python to PATH" pendant l'installation !
    echo.
    pause
    exit /b 1
)

echo  Python trouve : %PY%
echo.

::---- 2. pip a jour ---------------------------------------------
"%PY%" -m pip install --upgrade pip --quiet 2>nul

::---- 3. pygame-ce ----------------------------------------------
"%PY%" -m pip show pygame-ce >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installation de pygame-ce...
    "%PY%" -m pip install pygame-ce
    if %errorlevel% neq 0 (
        echo  ERREUR : impossible d'installer pygame-ce.
        pause
        exit /b 1
    )
)

::---- 4. PyInstaller --------------------------------------------
"%PY%" -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installation de PyInstaller...
    "%PY%" -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo  ERREUR : impossible d'installer PyInstaller.
        pause
        exit /b 1
    )
)

::---- 5. Fermer l'exe si ouvert + nettoyer les anciens fichiers -----
echo  Nettoyage avant compilation...

taskkill /f /im Dreamspawn.exe >nul 2>&1
timeout /t 1 /nobreak >nul

if exist "dist\Dreamspawn.exe"  del /f /q "dist\Dreamspawn.exe"  >nul 2>&1
if exist "Dreamspawn.spec"      del /f /q "Dreamspawn.spec"      >nul 2>&1
if exist "..\Dreamspawn.spec"   del /f /q "..\Dreamspawn.spec"   >nul 2>&1
if exist "work"                 rmdir /s /q "work"               >nul 2>&1

::---- 6. Chemins absolus (pushd/popd = methode la plus fiable) ---
pushd "%~dp0.."
set "ROOT=%CD%"
popd
set "ASSETS=%ROOT%\assets"
set "MUSIC=%ROOT%\assets\music"
set "SOUNDS=%ROOT%\assets\sounds"
set "MAIN=%ROOT%\src\main.py"
set "DIST=%ROOT%\build\dist"
set "WORK=%ROOT%\build\work"
set "SPEC=%ROOT%\build"

::---- 7. Compilation --------------------------------------------
echo  Compilation en cours...
echo.

"%PY%" -m PyInstaller --name Dreamspawn --noconfirm --windowed --onefile ^
    --distpath "%DIST%" ^
    --workpath "%WORK%" ^
    --specpath "%SPEC%" ^
    --add-data "%ASSETS%;assets" ^
    --add-data "%MUSIC%;assets\music" ^
    --add-data "%SOUNDS%;assets\sounds" ^
    "%MAIN%"

if %errorlevel% neq 0 (
    echo.
    echo  ================================================
    echo   ERREUR : le build a echoue.
    echo   Lis les messages ci-dessus pour le detail.
    echo  ================================================
    echo.
    pause
    exit /b 1
)

echo.
echo  ================================================
echo   Build termine !
echo   Ton .exe est ici :
echo   %~dp0dist\Dreamspawn.exe
echo  ================================================
echo.
pause
