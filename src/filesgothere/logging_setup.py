from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from filesgothere.config import LoggingConfig


def setup_logging(config: LoggingConfig) -> logging.Logger:
    logger = logging.getLogger("filesgothere")
    logger.setLevel(_coerce_level(config.level))
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    _ensure_parent_dir(config.file)
    file_handler = RotatingFileHandler(
        filename=str(config.file),
        maxBytes=config.max_bytes,
        backupCount=config.backups,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def _coerce_level(level: str) -> int:
    return logging._nameToLevel.get(level.upper(), logging.INFO)


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
