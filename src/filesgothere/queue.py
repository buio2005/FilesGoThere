from __future__ import annotations

import json
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


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

        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(action), ensure_ascii=False)

        with self._lock:
            with self._path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(line)
                f.write("\n")
