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
- The build script bundles a sanitized `config/` (JSON files + presets only) to avoid shipping any local runtime artifacts (logs/queue).
- The project uses a `src/` layout, so the build includes `src/` in PyInstaller paths (handled by the script).

Alternative: use the build script (recommended) to ensure a clean bundle.

## 3) Run the build
From the project root:

```powershell
.\dist\FilesGoThere\FilesGoThere.exe
```

Notes:
- On first start, the executable creates a user config at `%LOCALAPPDATA%\FilesGoThere\config\config.json` (copied from the bundled default) and uses it afterwards.
- You can override the config path with: `.\FilesGoThere.exe --config <path>\config.json`

## 4) Build the installer (Inno Setup)
If you want a classic Windows installer (`Setup.exe`) instead of only the portable folder/ZIP:

1. Make sure Inno Setup 6 is installed.
2. Build the application bundle first:

```powershell
.\build\build.ps1
```

3. Compile the installer:

```powershell
.\build\build_installer.ps1
```

Expected output:
- `dist/FilesGoThere-Setup-v1.0.0.exe`

The installer packages the entire `dist/FilesGoThere/` folder and creates shortcuts for normal Windows users.

### SmartScreen
Because the installer is not code-signed, Windows SmartScreen may show a warning.

To continue:
1. Click `More info`
2. Click `Run anyway`

## 5) Build (CLI only)
If you prefer a console app:

```powershell
.\build\build.ps1 -Console
```

## 6) Clean artifacts
```powershell
Remove-Item -Recurse -Force .\build, .\dist
```

## Known limitations (current phase)
- If you use `%LOCALAPPDATA%` in `config/config.json`, FilesGoThere expands it automatically on Windows.
