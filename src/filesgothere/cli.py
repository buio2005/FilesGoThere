from __future__ import annotations

import argparse
from pathlib import Path

from filesgothere.app import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="filesgothere")
    parser.add_argument(
        "--config",
        default=str(Path("config/config.json")),
        help="Percorso al file di configurazione JSON",
    )
    args = parser.parse_args(argv)
    return run(Path(args.config))
