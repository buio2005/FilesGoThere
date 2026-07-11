@echo off
REM ============================================================
REM  FilesGoThere - avvio GUI (Windows / cmd - doppio clic)
REM  Crea l'ambiente virtuale e installa le dipendenze al
REM  primo avvio, poi lancia l'interfaccia grafica.
REM ============================================================
setlocal
cd /d "%~dp0"

REM 1) Crea il virtualenv se manca
if not exist ".venv\Scripts\python.exe" (
    echo [FilesGoThere] Creo l'ambiente virtuale ^(.venv^)...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERRORE: Python non trovato. Installa Python 3.12+ da https://www.python.org
        echo e assicurati di spuntare "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )
)

set "PY=.venv\Scripts\python.exe"

REM 2) Installa le dipendenze solo al primo avvio (marker .deps_ok)
if not exist ".venv\.deps_ok" (
    echo [FilesGoThere] Installo le dipendenze ^(la prima volta puo' richiedere qualche minuto^)...
    "%PY%" -m pip install --upgrade pip
    "%PY%" -m pip install -r requirements.txt -r requirements-gui.txt
    if errorlevel 1 (
        echo.
        echo ERRORE durante l'installazione delle dipendenze.
        pause
        exit /b 1
    )
    type nul > ".venv\.deps_ok"
)

REM 3) Avvia la GUI
echo [FilesGoThere] Avvio dell'interfaccia...
"%PY%" main.py gui --config config\config.json

if errorlevel 1 pause
endlocal
