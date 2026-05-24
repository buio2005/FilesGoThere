# Build (Windows)

This document describes how to create a local **test .exe** for FilesGoThere using PyInstaller.

The goal is a reproducible build you can run on the same machine (and later share for testing), without publishing anything.

## Prerequisites
- Windows 10/11
- Python 3.12+
- A virtual environment (recommended)

## 1) Setup
From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-gui.txt
```

Install PyInstaller:

```powershell
python -m pip install pyinstaller
```

## 2) Build (GUI)
Run from the project root:

```powershell
.\build\build.ps1
```

Expected output:
- `dist/FilesGoThere/FilesGoThere.exe`

Notes:
- `--windowed` prevents a console window from opening.
- The `--add-data` option bundles the `config/` folder next to the executable (as a starting point).
- The project uses a `src/` layout, so the build includes `src/` in PyInstaller paths (handled by the script).

Alternative (single command in PowerShell):

```powershell
pyinstaller --noconfirm --clean --windowed --name FilesGoThere --paths "src" --add-data "config;config" main.py
```

## 3) Run the build
From the project root:

```powershell
.\dist\FilesGoThere\FilesGoThere.exe
```

## 4) Build (CLI only)
If you prefer a console app:

```powershell
.\build\build.ps1 -Console
```

## 5) Clean artifacts
```powershell
Remove-Item -Recurse -Force .\build, .\dist
```

## Known limitations (current phase)
- Runtime paths (queue/logs) should be set in `config/config.json` (recommended: `%LOCALAPPDATA%\FilesGoThere\...`).
- A later step can add built-in expansion of `%LOCALAPPDATA%` inside JSON config for portability.
