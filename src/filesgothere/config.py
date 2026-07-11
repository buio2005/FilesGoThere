from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


# File "spazzatura" o di sistema che non devono mai essere organizzati.
DEFAULT_IGNORE_GLOBS: list[str] = [
    "desktop.ini",
    "thumbs.db",
    ".ds_store",
    "~$*",
    ".*",
]


Language = Literal["it", "en"]
Mode = Literal["auto", "manual"]
DuplicateStrategy = Literal["rename", "skip", "overwrite"]
Theme = Literal["light", "dark"]


@dataclass(frozen=True)
class AppConfig:
    language: Language = "it"
    mode: Mode = "auto"
    theme: Theme = "light"
    focus_on_startup: bool = False
    focus_on_download_complete: bool = False
    minimize_to_tray: bool = True


@dataclass(frozen=True)
class WatchConfig:
    paths: list[Path]
    recursive: bool = False
    settle_seconds: float = 2.0
    settle_max_seconds: float = 0.0
    ignore_globs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LibraryConfig:
    root: Path | None
    create_folders: bool = True
    duplicate_strategy: DuplicateStrategy = "rename"


@dataclass(frozen=True)
class RulesConfig:
    by_extension: dict[str, str]
    default_folder: str = "Altro"


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    file: Path = Path("logs/filesgothere.log")
    max_bytes: int = 1_048_576
    backups: int = 3


@dataclass(frozen=True)
class QueueConfig:
    enabled: bool = True
    file: Path = Path("data/queue.jsonl")


@dataclass(frozen=True)
class RootConfig:
    app: AppConfig
    watch: WatchConfig
    library: LibraryConfig
    rules: RulesConfig
    logging: LoggingConfig
    queue: QueueConfig


class ConfigError(Exception):
    pass


def load_config(path: Path) -> RootConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ConfigError(f"File non trovato: {path}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"JSON non valido: {e}") from e

    return _parse(raw, path)


def _parse(raw: dict[str, Any], source_path: Path) -> RootConfig:
    app_raw = _as_dict(raw.get("app"), "app")
    watch_raw = _as_dict(raw.get("watch"), "watch")
    library_raw = _as_dict(raw.get("library"), "library")
    rules_raw = _as_dict(raw.get("rules"), "rules")
    logging_raw = _as_dict(raw.get("logging"), "logging")
    queue_raw = _as_dict(raw.get("queue"), "queue")

    language = app_raw.get("language", "it")
    if language not in ("it", "en"):
        raise ConfigError("app.language deve essere 'it' o 'en'")

    mode = app_raw.get("mode", "auto")
    if mode not in ("auto", "manual"):
        raise ConfigError("app.mode deve essere 'auto' o 'manual'")

    theme = app_raw.get("theme", "light")
    if theme not in ("light", "dark"):
        raise ConfigError("app.theme deve essere 'light' o 'dark'")

    focus_on_startup = bool(app_raw.get("focus_on_startup", False))
    focus_on_download_complete = bool(app_raw.get("focus_on_download_complete", False))
    minimize_to_tray = bool(app_raw.get("minimize_to_tray", True))

    paths_raw = watch_raw.get("paths", [])
    if not isinstance(paths_raw, list):
        raise ConfigError("watch.paths deve essere una lista")

    watch_paths = [Path(_expand_vars(str(p))).expanduser() for p in paths_raw]
    recursive = bool(watch_raw.get("recursive", False))
    settle_seconds = float(watch_raw.get("settle_seconds", 2.0))
    if settle_seconds < 0.0:
        raise ConfigError("watch.settle_seconds deve essere >= 0")

    settle_max_seconds = float(watch_raw.get("settle_max_seconds", 0.0))
    if settle_max_seconds < 0.0:
        raise ConfigError("watch.settle_max_seconds deve essere >= 0")

    ignore_globs_raw = watch_raw.get("ignore_globs", None)
    if ignore_globs_raw is None:
        ignore_globs = list(DEFAULT_IGNORE_GLOBS)
    elif isinstance(ignore_globs_raw, list):
        ignore_globs = [str(x) for x in ignore_globs_raw]
    else:
        raise ConfigError("watch.ignore_globs deve essere una lista")

    raw_library_root = str(library_raw.get("root", "")).strip()
    library_root: Path | None
    if not raw_library_root or raw_library_root == ".":
        library_root = None
    else:
        library_root = Path(_expand_vars(raw_library_root)).expanduser()
    duplicate_strategy = library_raw.get("duplicate_strategy", "rename")
    if duplicate_strategy not in ("rename", "skip", "overwrite"):
        raise ConfigError("library.duplicate_strategy deve essere rename|skip|overwrite")

    by_extension_raw = rules_raw.get("by_extension", {})
    if not isinstance(by_extension_raw, dict):
        raise ConfigError("rules.by_extension deve essere un oggetto")
    by_extension = {str(k).lower(): str(v) for k, v in by_extension_raw.items()}

    default_folder = str(rules_raw.get("default_folder", "Altro"))

    log_level = str(logging_raw.get("level", "INFO")).upper()
    log_file_raw = _expand_vars(str(logging_raw.get("file", "logs/filesgothere.log")))
    max_bytes = int(logging_raw.get("max_bytes", 1_048_576))
    backups = int(logging_raw.get("backups", 3))
    if max_bytes < 0 or backups < 0:
        raise ConfigError("logging.max_bytes/backups devono essere >= 0")

    queue_enabled = bool(queue_raw.get("enabled", True))
    queue_file_raw = _expand_vars(str(queue_raw.get("file", "data/queue.jsonl")))

    base_dir = source_path.parent
    log_file = Path(log_file_raw)
    if not log_file.is_absolute():
        log_file = (base_dir / log_file).resolve()

    queue_file = Path(queue_file_raw)
    if not queue_file.is_absolute():
        queue_file = (base_dir / queue_file).resolve()

    if library_root and not library_root.is_absolute():
        library_root = (base_dir / library_root).resolve()

    return RootConfig(
        app=AppConfig(
            language=language,
            mode=mode,
            theme=theme,
            focus_on_startup=focus_on_startup,
            focus_on_download_complete=focus_on_download_complete,
            minimize_to_tray=minimize_to_tray,
        ),
        watch=WatchConfig(
            paths=watch_paths,
            recursive=recursive,
            settle_seconds=settle_seconds,
            settle_max_seconds=settle_max_seconds,
            ignore_globs=ignore_globs,
        ),
        library=LibraryConfig(
            root=library_root,
            create_folders=bool(library_raw.get("create_folders", True)),
            duplicate_strategy=duplicate_strategy,
        ),
        rules=RulesConfig(by_extension=by_extension, default_folder=default_folder),
        logging=LoggingConfig(level=log_level, file=log_file, max_bytes=max_bytes, backups=backups),
        queue=QueueConfig(enabled=queue_enabled, file=queue_file),
    )


def _as_dict(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"Sezione '{name}' deve essere un oggetto")
    return value


_UNRESOLVED_ENV_RE = re.compile(r"%[^%]+%")


def _expand_vars(value: str) -> str:
    expanded = os.path.expandvars(value)
    if _UNRESOLVED_ENV_RE.search(expanded):
        raise ConfigError(f"Variabile d'ambiente non risolta nel path: {value}")
    return expanded
