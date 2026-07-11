from __future__ import annotations

import json
import shutil
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from filesgothere.config import LibraryConfig
from filesgothere.utils import move_with_duplicates


@dataclass(frozen=True)
class PlannedAction:
    created_at: str
    mode: str
    src_path: str
    dst_dir: str
    extension: str
    size_bytes: int


class QueueWriter:
    def __init__(self, file_path: Path) -> None:
        self._path = file_path
        self._lock = threading.Lock()

    def append_planned_action(self, *, mode: str, src_path: Path, dst_dir: Path) -> None:
        try:
            size = src_path.stat().st_size
        except OSError:
            size = -1

        action = PlannedAction(
            created_at=datetime.now(timezone.utc).isoformat(),
            mode=mode,
            src_path=str(src_path),
            dst_dir=str(dst_dir),
            extension=src_path.suffix.lower(),
            size_bytes=size,
        )

        with self._lock:
            entries = _read_entries(self._path)
            action_obj: dict[str, Any] = asdict(action)
            src_key = str(action_obj.get("src_path", "")).casefold()

            match_index: int | None = None
            for i, (_, obj) in enumerate(entries):
                src_existing = obj.get("src_path")
                if isinstance(src_existing, str) and src_existing.casefold() == src_key and "status" not in obj:
                    match_index = i

            if match_index is None:
                line = json.dumps(action_obj, ensure_ascii=False)
                entries.append((line, action_obj))
            else:
                _, existing = entries[match_index]
                merged = dict(action_obj)
                created_at = existing.get("created_at")
                if isinstance(created_at, str) and created_at:
                    merged["created_at"] = created_at
                existing_mode = existing.get("mode")
                if isinstance(existing_mode, str) and existing_mode:
                    merged["mode"] = existing_mode

                existing_size = existing.get("size_bytes")
                if (
                    isinstance(existing_size, int)
                    and existing_size >= 0
                    and isinstance(merged.get("size_bytes"), int)
                    and merged["size_bytes"] < 0
                ):
                    merged["size_bytes"] = existing_size

                line = json.dumps(merged, ensure_ascii=False)
                entries[match_index] = (line, merged)

            _write_entries(self._path, entries)


class AutoApplier:
    """Sposta i file immediatamente (modalità auto) e registra l'esito nello storico."""

    def __init__(self, done_path: Path, library: LibraryConfig) -> None:
        self._done_path = done_path
        self._library = library
        self._lock = threading.Lock()

    def apply(self, *, mode: str, src_path: Path, dst_dir: Path) -> tuple[str | None, str]:
        try:
            size = src_path.stat().st_size
        except OSError:
            size = -1

        action: dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "src_path": str(src_path),
            "dst_dir": str(dst_dir),
            "extension": src_path.suffix.lower(),
            "size_bytes": size,
        }

        with self._lock:
            moved = move_with_duplicates(
                src_path,
                dst_dir,
                self._library.duplicate_strategy,
                create_folders=self._library.create_folders,
            )
            if moved is None:
                status = "skipped_duplicate"
                moved_to: str | None = None
            else:
                status = "applied"
                moved_to = str(moved)
            _append_done(self._done_path, action, status=status, moved_to=moved_to)

        return moved_to, status


def undo_action(
    done_path: Path,
    *,
    created_at: Any,
    src_path: Any,
    applied_at: Any,
    moved_to: Any = None,
) -> dict[str, Any]:
    """Riporta un file spostato alla sua posizione originale.

    L'azione viene individuata nello storico tramite la sua firma
    (created_at + src_path + applied_at) per evitare disallineamenti di indice.
    """
    if not isinstance(src_path, str) or not src_path:
        return {"undone": False, "reason": "invalid_action"}

    entries = _read_entries(done_path)
    match_index: int | None = None
    for i, (_, obj) in enumerate(entries):
        if (
            obj.get("src_path") == src_path
            and obj.get("created_at") == created_at
            and obj.get("applied_at") == applied_at
            and obj.get("status") == "applied"
        ):
            match_index = i

    if match_index is None:
        return {"undone": False, "reason": "not_found", "src_path": src_path}

    _, obj = entries[match_index]
    moved_raw = obj.get("moved_to")
    if not isinstance(moved_raw, str) or not moved_raw:
        return {"undone": False, "reason": "no_moved_to", "src_path": src_path}

    moved = Path(moved_raw)
    original = Path(src_path)

    if not moved.exists():
        return {"undone": False, "reason": "moved_missing", "moved_to": moved_raw}
    if original.exists():
        return {"undone": False, "reason": "source_exists", "src_path": src_path}

    try:
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(moved), str(original))
    except Exception as e:
        return {"undone": False, "reason": "move_failed", "error": str(e), "src_path": src_path}

    updated = dict(obj)
    updated["status"] = "undone"
    updated["undone_at"] = datetime.now(timezone.utc).isoformat()
    entries[match_index] = (json.dumps(updated, ensure_ascii=False), updated)
    _write_entries(done_path, entries)

    return {"undone": True, "restored_to": src_path, "from": moved_raw}


def read_actions(
    path: Path,
    *,
    tail: int | None = None,
    ext: str | None = None,
    contains: str | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    raw_lines = path.read_text(encoding="utf-8").splitlines()
    lines: Iterable[str] = raw_lines
    if tail is not None and tail >= 0:
        lines = raw_lines[-tail:]

    ext_norm = ext.lower() if isinstance(ext, str) and ext else None
    if ext_norm and not ext_norm.startswith("."):
        ext_norm = f".{ext_norm}"
    contains_norm = contains if isinstance(contains, str) and contains else None

    actions: list[dict[str, Any]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            if ext_norm:
                v = obj.get("extension")
                if not isinstance(v, str) or v.lower() != ext_norm:
                    continue
            if contains_norm:
                src = obj.get("src_path")
                dst = obj.get("dst_dir")
                text = f"{src} {dst}"
                if contains_norm.lower() not in text.lower():
                    continue
            actions.append(obj)
    return actions


def archive_queue(queue_path: Path, done_path: Path) -> dict[str, Any]:
    if not queue_path.exists():
        return {"archived": 0, "queue_file": str(queue_path), "done_file": str(done_path)}

    raw_lines = queue_path.read_text(encoding="utf-8").splitlines()
    lines = [line for line in (l.strip() for l in raw_lines) if line]
    if not lines:
        return {"archived": 0, "queue_file": str(queue_path), "done_file": str(done_path)}

    done_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        f = done_path.open("a", encoding="utf-8", newline="\n")
    except FileNotFoundError:
        done_path.parent.mkdir(parents=True, exist_ok=True)
        f = done_path.open("a", encoding="utf-8", newline="\n")

    with f:
        for line in lines:
            f.write(line)
            f.write("\n")

    queue_path.write_text("", encoding="utf-8")
    return {"archived": len(lines), "queue_file": str(queue_path), "done_file": str(done_path)}


def apply_action_by_index(
    queue_path: Path,
    done_path: Path,
    index: int,
    library: LibraryConfig,
    *,
    require_same_size: bool = False,
) -> dict[str, Any]:
    entries = _read_entries(queue_path)
    if not entries:
        return {"applied": False, "reason": "queue_empty", "index": index}
    if index < 0 or index >= len(entries):
        return {"applied": False, "reason": "index_out_of_range", "index": index, "count": len(entries)}

    raw_line, action = entries[index]
    src_raw = action.get("src_path")
    dst_raw = action.get("dst_dir")
    if not isinstance(src_raw, str) or not isinstance(dst_raw, str):
        return {"applied": False, "reason": "invalid_action", "index": index}

    src = Path(src_raw)
    dst_dir = Path(dst_raw)

    if not src.exists():
        return {"applied": False, "reason": "source_missing", "index": index, "src_path": src_raw}

    if require_same_size:
        queued_size = action.get("size_bytes")
        if isinstance(queued_size, int) and queued_size >= 0:
            try:
                current_size = src.stat().st_size
            except OSError:
                return {
                    "applied": False,
                    "reason": "stat_failed",
                    "index": index,
                    "src_path": src_raw,
                }
            if current_size != queued_size:
                return {
                    "applied": False,
                    "reason": "size_changed",
                    "index": index,
                    "src_path": src_raw,
                    "queued_size": queued_size,
                    "current_size": current_size,
                }

    moved_to: str | None = None
    status = "applied"
    try:
        moved = move_with_duplicates(
            src,
            dst_dir,
            library.duplicate_strategy,
            create_folders=library.create_folders,
        )
        if moved is None:
            status = "skipped_duplicate"
        else:
            moved_to = str(moved)
    except Exception as e:
        return {
            "applied": False,
            "reason": "move_failed",
            "index": index,
            "error": str(e),
            "src_path": src_raw,
            "dst_dir": dst_raw,
        }

    _append_done(done_path, action, status=status, moved_to=moved_to)

    remaining = entries[:index] + entries[index + 1 :]
    _write_entries(queue_path, remaining)

    return {
        "applied": True,
        "index": index,
        "status": status,
        "src_path": src_raw,
        "dst_dir": dst_raw,
        "moved_to": moved_to,
        "queue_file": str(queue_path),
        "done_file": str(done_path),
    }


def preview_action_by_index(
    queue_path: Path,
    index: int,
    library: LibraryConfig,
) -> dict[str, Any]:
    entries = _read_entries(queue_path)
    if not entries:
        return {"applied": False, "reason": "queue_empty", "index": index}
    if index < 0 or index >= len(entries):
        return {"applied": False, "reason": "index_out_of_range", "index": index, "count": len(entries)}

    _, action = entries[index]
    src_raw = action.get("src_path")
    dst_raw = action.get("dst_dir")
    if not isinstance(src_raw, str) or not isinstance(dst_raw, str):
        return {"applied": False, "reason": "invalid_action", "index": index}

    src = Path(src_raw)
    dst_dir = Path(dst_raw)
    dst = dst_dir / src.name

    warnings: list[str] = []
    if not src.exists():
        warnings.append("source_missing")
    else:
        try:
            current_size = src.stat().st_size
            queued_size = action.get("size_bytes")
            if isinstance(queued_size, int) and queued_size >= 0 and current_size != queued_size:
                warnings.append("size_changed")
        except OSError:
            warnings.append("stat_failed")

    will_create_dir = library.create_folders and not dst_dir.exists()

    status = "applied"
    predicted_moved_to: str | None = str(dst)
    if dst.exists():
        if library.duplicate_strategy == "skip":
            status = "skipped_duplicate"
            predicted_moved_to = None
        elif library.duplicate_strategy == "rename":
            candidate = dst
            i = 1
            while True:
                candidate = dst_dir / f"{dst.stem} ({i}){dst.suffix}"
                if not candidate.exists():
                    break
                i += 1
            predicted_moved_to = str(candidate)
        elif library.duplicate_strategy == "overwrite":
            predicted_moved_to = str(dst)

    return {
        "applied": False,
        "preview": True,
        "index": index,
        "src_path": src_raw,
        "dst_dir": dst_raw,
        "predicted_moved_to": predicted_moved_to,
        "duplicate_strategy": library.duplicate_strategy,
        "will_create_dir": will_create_dir,
        "warnings": warnings,
        "queue_file": str(queue_path),
        "count": len(entries),
    }


def _read_entries(path: Path) -> list[tuple[str, dict[str, Any]]]:
    if not path.exists():
        return []

    out: list[tuple[str, dict[str, Any]]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append((line, obj))
    return out


def _write_entries(path: Path, entries: list[tuple[str, dict[str, Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for raw_line, _ in entries:
            f.write(raw_line)
            f.write("\n")
    tmp.replace(path)


def _append_done(
    done_path: Path,
    action: dict[str, Any],
    *,
    status: str,
    moved_to: str | None,
) -> None:
    obj = dict(action)
    obj["status"] = status
    obj["applied_at"] = datetime.now(timezone.utc).isoformat()
    if moved_to is not None:
        obj["moved_to"] = moved_to

    done_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False)
    with done_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line)
        f.write("\n")
