from __future__ import annotations

import shutil
from pathlib import Path

from filesgothere.config import DuplicateStrategy


TEMP_EXTENSIONS = {".part", ".crdownload", ".tmp"}


def is_temporary_download(path: Path) -> bool:
    return path.suffix.lower() in TEMP_EXTENSIONS


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def move_with_duplicates(
    src: Path,
    dst_dir: Path,
    strategy: DuplicateStrategy,
    *,
    create_folders: bool,
) -> Path | None:
    if create_folders:
        ensure_directory(dst_dir)

    dst = dst_dir / src.name

    if dst.exists():
        if strategy == "skip":
            return None
        if strategy == "overwrite":
            if dst.is_file():
                dst.unlink()
            else:
                raise IsADirectoryError(str(dst))
        if strategy == "rename":
            dst = _next_available_name(dst)

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return dst


def _next_available_name(path: Path) -> Path:
    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1
