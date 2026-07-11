# FilesGoThere
FilesGoThere is a local-first Windows desktop utility that watches one or more folders (typically Downloads) and helps you organize files into the right destination folders using simple, customizable rules.

Offline. Lightweight. Privacy-friendly.

## Why it exists
- Keep your Downloads folders tidy without giving up control.
- Prefer “suggest + confirm” instead of silent automation.
- Work fully offline (no cloud, no telemetry).

## Current features
- Real-time multi-folder monitoring (watchdog).
- Download safety:
  - ignores temporary/incomplete files (`.part`, `.crdownload`, `.tmp`)
  - waits for downloads to finish (“settle”: file size stable for N seconds); keeps waiting while the file is still growing, so large/slow downloads are not dropped
  - skips system/junk files via a configurable ignore-list (`desktop.ini`, `thumbs.db`, `~$*`, dot-files, plus Windows hidden/system files)
- Rule engine (initial): extension → destination subfolder + default folder.
- Duplicate handling: `rename | skip | overwrite`.
- Two modes:
  - `manual`: generates a queue of proposed actions (JSON Lines); you apply the selected ones after a preview
  - `auto`: moves files automatically as soon as they are ready, recording every move in the history
- Undo: revert an applied move (auto or manual) back to its original location from the History tab.
- Logging: console + rotating log file (standard Python logging).
- Minimal GUI (PySide6, optional) to view/apply/undo actions, filter by text/extension, and manage watched folders.
- Settings in the GUI: language (Italian / English), mode, light/dark theme, focus options.

## Project status
FilesGoThere 1.0.0 is the first complete public release of the app.
The project already includes the full local workflow: monitoring, queue/manual mode,
real automatic mode, history, undo, tray support, and a polished desktop GUI.

Future versions may still refine the UI further, but the current release is intended
to be usable as a real day-to-day Windows utility.

## Requirements
- Windows 10/11
- Python 3.12+

Dependencies:
- `watchdog` (required)
- `PySide6` (optional, GUI)

## Quick start (CLI / backend)
1. Create and activate a virtual environment (recommended).
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Edit your configuration:
   - start from `config/example_config.json` or a preset in `config/presets/`
   - copy it into `config/config.json`
   - set:
     - `watch.paths` (folders to monitor)
     - `library.root` (base folder for organized output)
4. Run:
   - `python main.py --config config/config.json`

## Quick start (Minimal GUI)
1. Install GUI dependencies:
   - `pip install -r requirements-gui.txt`
2. Run:
   - `python main.py gui --config config/config.json`

## Configuration (JSON)
Configuration is stored as JSON and loaded at runtime.

Key sections:
- `app.language`: `it | en`
- `app.mode`: `manual | auto`
- `app.theme`: `light | dark`
- `watch.paths`: list of folders to monitor
- `watch.settle_seconds`: seconds of stable size before a file is considered ready
- `watch.settle_max_seconds`: safety cap on total wait time (`0` = no cap; the watcher keeps waiting while the file grows)
- `watch.ignore_globs`: filename globs to always skip (defaults to `desktop.ini`, `thumbs.db`, `.ds_store`, `~$*`, `.*`)
- `library.duplicate_strategy`: `rename | skip | overwrite`
- `rules.by_extension`: map of file extension → destination subfolder
- `rules.default_folder`: fallback subfolder
- `queue.file`: JSONL file storing proposed actions (manual mode)
- `logging.file`: rotating log file path

Note about `app.mode`:
- In `manual` mode files are only proposed in the queue and moved when you confirm.
- In `auto` mode files are moved as soon as they settle; each move is logged in the history and can be reverted with Undo.

Recommended (Windows) locations for runtime data:
- Queue: `%LOCALAPPDATA%\FilesGoThere\data\queue.jsonl`
- Logs: `%LOCALAPPDATA%\FilesGoThere\logs\filesgothere.log`

Windows executable config:
- On first start, `FilesGoThere.exe` creates `%LOCALAPPDATA%\FilesGoThere\config\config.json` (copied from the bundled default) and uses it afterwards.

Note about `library.root`:
- If `library.root` is empty, FilesGoThere uses the source file's folder as the base destination (i.e., it organizes inside the same Downloads folder).

## Presets
Presets are optional starting points you can copy into `config/config.json` and edit.
- `config/presets/common_it.json`: common extensions in Italian categories, designed for “organize in-place” (empty `library.root`).

## Queue commands (CLI)
All commands below print JSON to stdout (useful for automation and for the GUI).

- List pending actions:
  - `python main.py queue list --config config/config.json`
- List done (archived) actions:
  - `python main.py queue list --config config/config.json --source done`
- Filter:
  - `--tail 50`
  - `--ext .pdf`
  - `--contains "Downloads"`
- Preview an action (no changes):
  - `python main.py queue apply --config config/config.json --index 0`
- Apply an action (moves the file):
  - `python main.py queue apply --config config/config.json --index 0 --yes --require-same-size`
- Archive all pending actions:
  - `python main.py queue archive --config config/config.json`

## Minimal architecture
- Watcher: receives filesystem events and generates “file ready” events after settle.
- Rule engine: decides destination folder for a file.
- Queue: stores proposed actions (JSON Lines) for full user control.
- Apply: moves files when explicitly confirmed (CLI or GUI).

Code lives in `src/filesgothere/` and is intentionally kept simple and extendable.

## Build (Windows executable)
It is reasonable to start doing “dev builds” now, but a final distributable build is best done after:
- watcher behavior is stable across browsers
- config paths and defaults are finalized
- the GUI flow is finalized (tray icon, settings screen, etc.)

Build guide:
- See [build.md](docs/build.md)

After extracting the ZIP, you can start the GUI by double-clicking `FilesGoThere.exe`.

If you want to use a custom configuration file, pass it explicitly:
- `FilesGoThere.exe --config path\to\config.json`

## Windows installer
For end users, the recommended release assets are:
- `FilesGoThere-v1.0.0-windows.zip`: portable package
- `FilesGoThere-Setup-v1.0.0.exe`: installer created with Inno Setup

To create the installer locally:
1. Build the app bundle:
   - `.\build\build.ps1`
2. Compile the Inno Setup installer:
   - `.\build\build_installer.ps1`

This produces a standalone Windows installer in `dist/`.

## SmartScreen note
Because FilesGoThere is not code-signed yet, Windows SmartScreen may warn that the app is from an unknown publisher.

If that happens:
1. Click `More info`
2. Click `Run anyway`

This is expected for unsigned indie software builds distributed outside the Microsoft Store.
