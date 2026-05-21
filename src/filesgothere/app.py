from __future__ import annotations

import logging
import time
from pathlib import Path

from filesgothere.config import ConfigError, RootConfig, load_config
from filesgothere.i18n import t
from filesgothere.logging_setup import setup_logging
from filesgothere.queue import QueueWriter
from filesgothere.rules import RuleEngine
from filesgothere.watcher import FilesGoThereWatcher, WatchContext


def run(config_path: Path) -> int:
    config: RootConfig
    try:
        config = load_config(config_path)
    except ConfigError as e:
        logging.getLogger("filesgothere").error(t("config.invalid", "en", reason=str(e)))
        return 2

    logger = setup_logging(config.logging)
    logger.info(t("config.loaded", config.app.language, path=str(config_path)))
    logger.info(t("app.starting", config.app.language))

    if not config.watch.paths:
        logger.warning("watch.paths è vuoto: niente da monitorare.")
        return 0

    rule_engine = RuleEngine(config.rules, config.library)
    queue_writer = None
    if config.app.mode == "manual" and config.queue.enabled:
        queue_writer = QueueWriter(config.queue.file)
    watcher = FilesGoThereWatcher(
        WatchContext(lang=config.app.language, watch=config.watch, mode=config.app.mode),
        rule_engine,
        logger,
        queue_writer=queue_writer,
    )

    watcher.start()
    logger.info(t("watch.start", config.app.language, count=len(config.watch.paths)))
    for p in config.watch.paths:
        logger.info(t("watch.path", config.app.language, path=str(p)))

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info(t("app.stopping", config.app.language))
    finally:
        watcher.stop()

    return 0
