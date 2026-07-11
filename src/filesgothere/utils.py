from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path

from filesgothere.config import DuplicateStrategy


TEMP_EXTENSIONS = {".part", ".crdownload", ".tmp"}

_FILE_ATTRIBUTE_HIDDEN = 0x2
_FILE_ATTRIBUTE_SYSTEM = 0x4


def is_temporary_download(path: Path) -> bool:
    return path.suffix.lower() in TEMP_EXTENSIONS


def is_ignored(path: Path, patterns: list[str]) -> bool:
    """True se il file va ignorato: match su un glob della lista, oppure
    (solo su Windows) se ha l'attributo hidden/system."""
    name = path.name
    lname = name.lower()
    for pat in patterns:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(lname, pat.lower()):
            return True

    if os.name == "nt":
        try:
            attrs = getattr(path.stat(), "st_file_attributes", 0)
        except OSError:
            attrs = 0
        if attrs & (_FILE_ATTRIBUTE_HIDDEN | _FILE_ATTRIBUTE_SYSTEM):
            return True

    return False


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
