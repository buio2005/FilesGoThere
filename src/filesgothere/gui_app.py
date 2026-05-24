from __future__ import annotations

import json
import sys
from pathlib import Path

from filesgothere.config import ConfigError, load_config


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

    app = QApplication(sys.argv)

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
    app.aboutToQuit.connect(window.shutdown)
    window.show()
    return app.exec()
