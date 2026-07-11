from __future__ import annotations

import json
import sys
from pathlib import Path

from filesgothere.config import ConfigError, load_config


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("tivustream.filesgothere")
    except Exception:
        pass


def _load_app_icon():
    try:
        from PySide6.QtGui import QIcon
    except Exception:
        return None

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        candidates.append(base / "assets" / "filesgothere.ico")
        candidates.append(base / "filesgothere.ico")
    here = Path(__file__).resolve()
    candidates.append(here.parents[2] / "assets" / "filesgothere.ico")

    for candidate in candidates:
        try:
            if candidate.exists():
                icon = QIcon(str(candidate))
                if not icon.isNull():
                    return icon
        except Exception:
            pass
    return None


def gui_main(config_path: Path) -> int:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except Exception:
        msg = "PySide6 non installato. Installa con: pip install -r requirements-gui.txt"
        if getattr(sys, "frozen", False):
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(0, msg, "FilesGoThere", 0x10)
            except Exception:
                pass
        else:
            print(json.dumps({"error": msg}, ensure_ascii=False, indent=2))
        return 2

    _set_windows_app_id()
    app = QApplication(sys.argv)
    # Keep the process alive when the main window is hidden to the tray.
    app.setQuitOnLastWindowClosed(False)
    app_icon = _load_app_icon()
    if app_icon is not None:
        app.setWindowIcon(app_icon)

    try:
        config = load_config(config_path)
    except ConfigError as e:
        QMessageBox.critical(None, "FilesGoThere", f"{e}\n\nConfig: {config_path}")
        return 2
    except Exception as e:
        QMessageBox.critical(None, "FilesGoThere", f"Errore: {e}\n\nConfig: {config_path}")
        return 2

    from filesgothere.gui_main_window import MainWindow

    window = MainWindow(config_path=config_path, config=config)
    if app_icon is not None:
        window._window.setWindowIcon(app_icon)
    app.aboutToQuit.connect(window.shutdown)
    window.show()
    return app.exec()
