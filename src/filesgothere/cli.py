from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from filesgothere.app import run
from filesgothere.queue_cli import queue_command
from filesgothere.gui_app import gui_main


def _user_config_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "FilesGoThere" / "config" / "config.json"
    return Path.home() / ".config" / "FilesGoThere" / "config.json"


def _default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        embedded_base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        embedded_config = embedded_base / "config" / "config.json"
        user_config = _user_config_path()
        try:
            if not user_config.exists() and embedded_config.exists():
                user_config.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(embedded_config, user_config)
            if user_config.exists():
                return user_config
        except Exception:
            return embedded_config
        return embedded_config
    return Path("config/config.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="filesgothere")
    default_config = str(_default_config_path())
    parser.add_argument(
        "--config",
        default=default_config,
        help="Percorso al file di configurazione JSON",
    )

    subparsers = parser.add_subparsers(dest="command")
    gui_parser = subparsers.add_parser("gui")
    gui_parser.add_argument(
        "--config",
        dest="gui_config",
        default=None,
        help="Percorso al file di configurazione JSON (override per GUI)",
    )
    queue_parser = subparsers.add_parser("queue")
    queue_sub = queue_parser.add_subparsers(dest="queue_command")
    queue_list = queue_sub.add_parser("list")
    queue_list.add_argument(
        "--config",
        dest="queue_config",
        default=None,
        help="Percorso al file di configurazione JSON (override per comandi queue)",
    )
    queue_list.add_argument("--tail", type=int, default=None)
    queue_list.add_argument("--ext", default=None)
    queue_list.add_argument("--contains", default=None)
    queue_list.add_argument(
        "--source",
        choices=["pending", "done"],
        default="pending",
    )
    queue_archive = queue_sub.add_parser("archive")
    queue_archive.add_argument(
        "--config",
        dest="queue_config",
        default=None,
        help="Percorso al file di configurazione JSON (override per comandi queue)",
    )
    queue_apply = queue_sub.add_parser("apply")
    queue_apply.add_argument("--index", type=int, required=True)
    queue_apply.add_argument("--yes", action="store_true")
    queue_apply.add_argument("--require-same-size", action="store_true")
    queue_apply.add_argument(
        "--config",
        dest="queue_config",
        default=None,
        help="Percorso al file di configurazione JSON (override per comandi queue)",
    )

    args = parser.parse_args(argv)

    if args.command == "queue":
        if not args.queue_command:
            queue_parser.print_help()
            return 2
        config_path = Path(args.queue_config or args.config)
        options = {
            "tail": getattr(args, "tail", None),
            "ext": getattr(args, "ext", None),
            "contains": getattr(args, "contains", None),
            "source": getattr(args, "source", "pending"),
            "index": getattr(args, "index", None),
            "yes": getattr(args, "yes", False),
            "require_same_size": getattr(args, "require_same_size", False),
        }
        return queue_command(config_path, args.queue_command, options)
    if args.command == "gui":
        config_path = Path(args.gui_config or args.config)
        return gui_main(config_path)

    if getattr(sys, "frozen", False):
        return gui_main(Path(args.config))
    return run(Path(args.config))
