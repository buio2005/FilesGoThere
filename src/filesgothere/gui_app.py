from __future__ import annotations

import json
import sys
from pathlib import Path

from filesgothere.config import ConfigError, load_config


def gui_main(config_path: Path) -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        print(
            json.dumps(
                {
                    "error": "PySide6 non installato. Installa con: pip install -r requirements-gui.txt",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        return 2

    from filesgothere.gui_main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow(config_path=config_path, config=config)
    app.aboutToQuit.connect(window.shutdown)
    window.show()
    return app.exec()
