from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from filesgothere.config import WatchConfig
from filesgothere.i18n import t
from filesgothere.queue import AutoApplier, QueueWriter
from filesgothere.rules import RuleEngine
from filesgothere.utils import is_ignored, is_temporary_download


@dataclass(frozen=True)
class WatchContext:
    lang: str
    watch: WatchConfig
    mode: str


class FilesGoThereWatcher:
    def __init__(
        self,
        ctx: WatchContext,
        rule_engine: RuleEngine,
        logger: logging.Logger,
        *,
        queue_writer: QueueWriter | None = None,
        auto_applier: AutoApplier | None = None,
    ) -> None:
        self._ctx = ctx
        self._rules = rule_engine
        self._log = logger
        self._queue = queue_writer
        self._auto = auto_applier
        self._observer = Observer()
        self._inflight: set[Path] = set()
        self._lock = threading.Lock()

    def start(self) -> None:
        handler = _Handler(self)
        for path in self._ctx.watch.paths:
            self._observer.schedule(handler, str(path), recursive=self._ctx.watch.recursive)
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=5)

    def on_candidate_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return

        if is_temporary_download(path):
            self._log.debug(t("event.skipped.temp", self._ctx.lang, path=str(path)))
            return

        if is_ignored(path, self._ctx.watch.ignore_globs):
            self._log.debug(t("event.skipped.ignored", self._ctx.lang, path=str(path)))
            return

        with self._lock:
            if path in self._inflight:
                return
            self._inflight.add(path)

        thread = threading.Thread(target=self._process_file, args=(path,), daemon=True)
        thread.start()

    def _process_file(self, path: Path) -> None:
        try:
            self._log.info(t("event.detected", self._ctx.lang, path=str(path)))
            if not _wait_for_settle(
                path,
                self._ctx.watch.settle_seconds,
                max_total_seconds=self._ctx.watch.settle_max_seconds,
                logger=self._log,
                lang=self._ctx.lang,
            ):
                return

            dst_dir = self._rules.on_file_ready(path)
            if self._ctx.mode == "auto":
                if self._auto is not None:
                    moved_to, status = self._auto.apply(
                        mode=self._ctx.mode, src_path=path, dst_dir=dst_dir
                    )
                    if status == "applied" and moved_to:
                        self._log.info(
                            t("event.moved", self._ctx.lang, src=str(path), dst=str(moved_to))
                        )
                    else:
                        self._log.info(
                            t("event.duplicate.skipped", self._ctx.lang, path=str(path))
                        )
                else:
                    self._log.info(
                        t("event.planned.auto", self._ctx.lang, path=str(path), dst_dir=str(dst_dir))
                    )
            else:
                self._log.info(
                    t("event.planned.manual", self._ctx.lang, path=str(path), dst_dir=str(dst_dir))
                )
                if self._queue is not None:
                    self._queue.append_planned_action(mode=self._ctx.mode, src_path=path, dst_dir=dst_dir)
        except Exception as e:
            self._log.exception(t("event.error", self._ctx.lang, path=str(path), error=str(e)))
        finally:
            with self._lock:
                self._inflight.discard(path)


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: FilesGoThereWatcher) -> None:
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def _handle(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        try:
            path = Path(str(getattr(event, "dest_path", None) or event.src_path))
        except Exception:
            return
        self._watcher.on_candidate_file(path)


def _wait_for_settle(
    path: Path,
    settle_seconds: float,
    *,
    max_total_seconds: float = 0.0,
    logger: logging.Logger | None = None,
    lang: str = "en",
) -> bool:
    """Attende che il file sia "stabile" (dimensione invariata per
    settle_seconds). Finché il file cresce continua ad attendere, così i
    download grandi/lenti non vengono scartati. max_total_seconds > 0 impone
    un tetto massimo di attesa (0 = nessun limite)."""
    if settle_seconds <= 0:
        return path.exists()

    start = time.time()
    last_size = -1
    stable_since: float | None = None

    while True:
        if max_total_seconds and (time.time() - start) >= max_total_seconds:
            if logger is not None:
                logger.warning(t("event.settle.timeout", lang, path=str(path)))
            return False

        if not path.exists():
            return False

        try:
            size = path.stat().st_size
        except OSError:
            time.sleep(0.2)
            continue

        if size == last_size:
            if stable_since is None:
                stable_since = time.time()
            if (time.time() - stable_since) >= settle_seconds:
                return True
        else:
            stable_since = None
            last_size = size

        time.sleep(0.3)
