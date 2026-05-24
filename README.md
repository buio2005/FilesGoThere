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
  - waits for downloads to finish (“settle”: file size stable for N seconds)
- Rule engine (initial): extension → destination subfolder + default folder.
- Duplicate handling when applying actions: `rename | skip | overwrite`.
- Two modes:
  - `manual`: generates a queue of proposed actions (JSON Lines), user applies selected actions
  - `auto`: currently still dry-run in the watcher (actions happen via Apply)
- Logging: console + rotating log file (standard Python logging).
- Minimal GUI (PySide6, optional) to view/apply actions and manage watched folders.
- GUI language switch: Italian / English.

## Project status
This repository focuses on a clean and maintainable backend + a minimal GUI for early testing.
A full “PowerToys-like” tray experience is planned later.

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
- `watch.paths`: list of folders to monitor
- `watch.settle_seconds`: seconds of stable size before an action is produced
- `rules.by_extension`: map of file extension → destination subfolder
- `rules.default_folder`: fallback subfolder
- `queue.file`: JSONL file storing proposed actions (manual mode)
- `logging.file`: rotating log file path

Recommended (Windows) locations for runtime data:
- Queue: `%LOCALAPPDATA%\FilesGoThere\data\queue.jsonl`
- Logs: `%LOCALAPPDATA%\FilesGoThere\logs\filesgothere.log`

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
