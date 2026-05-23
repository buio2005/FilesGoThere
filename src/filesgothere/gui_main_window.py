from __future__ import annotations

import json
import os
from pathlib import Path

from filesgothere.config import RootConfig
from filesgothere.i18n import t
from filesgothere.logging_setup import setup_logging
from filesgothere.queue import apply_action_by_index, preview_action_by_index, read_actions
from filesgothere.queue import QueueWriter
from filesgothere.rules import RuleEngine
from filesgothere.config import WatchConfig
from filesgothere.watcher import FilesGoThereWatcher, WatchContext


class MainWindow:
    def __init__(self, *, config_path: Path, config: RootConfig) -> None:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import (
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
            QTabWidget,
            QVBoxLayout,
            QWidget,
            QListWidget,
            QAbstractItemView,
            QFileDialog,
            QGroupBox,
            QComboBox,
        )

        self._QMessageBox = QMessageBox
        self._QTableWidgetItem = QTableWidgetItem
        self._QFileDialog = QFileDialog
        self._config_path = config_path
        self._config = config
        self._queue_path = config.queue.file
        self._done_path = config.queue.file.with_name("queue_done.jsonl")
        self._watcher: FilesGoThereWatcher | None = None
        self._logger = setup_logging(config.logging)
        self._lang = config.app.language
        self._watch_paths = [Path(p) for p in config.watch.paths]
        self._watch_recursive = config.watch.recursive
        self._watch_settle = config.watch.settle_seconds

        self._window = QMainWindow()
        self._window.setWindowTitle(t("gui.title", self._lang))
        self._window.setStyleSheet(
            "QWidget{font-family:Segoe UI;font-size:12px;}"
            "QGroupBox{font-weight:600;margin-top:8px;border:1px solid #e5e7eb;border-radius:10px;padding:10px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;}"
            "QPushButton{padding:7px 12px;border:1px solid #d1d5db;border-radius:10px;background:#ffffff;}"
            "QPushButton:hover{background:#f3f4f6;}"
            "QPushButton:pressed{background:#e5e7eb;}"
            "QPushButton:disabled{color:#9ca3af;background:#f9fafb;}"
            "QPushButton#btnPrimary{background:#16a34a;color:#ffffff;border-color:#15803d;}"
            "QPushButton#btnPrimary:hover{background:#15803d;}"
            "QPushButton#btnPrimary:pressed{background:#166534;}"
            "QPushButton#btnDanger{background:#dc2626;color:#ffffff;border-color:#b91c1c;}"
            "QPushButton#btnDanger:hover{background:#b91c1c;}"
            "QPushButton#btnDanger:pressed{background:#991b1b;}"
            "QPushButton#btnAccent{background:#2563eb;color:#ffffff;border-color:#1d4ed8;}"
            "QPushButton#btnAccent:hover{background:#1d4ed8;}"
            "QPushButton#btnAccent:pressed{background:#1e40af;}"
            "QPushButton#btnSecondary{background:#6b7280;color:#ffffff;border-color:#4b5563;}"
            "QPushButton#btnSecondary:hover{background:#4b5563;}"
            "QPushButton#btnSecondary:pressed{background:#374151;}"
            "QLineEdit{padding:7px 10px;border:1px solid #d1d5db;border-radius:10px;background:#ffffff;}"
            "QComboBox{padding:6px 10px;border:1px solid #d1d5db;border-radius:10px;background:#ffffff;}"
            "QTabWidget::pane{border:1px solid #e5e7eb;border-radius:10px;top:-1px;}"
            "QTabBar::tab{padding:8px 12px;border:1px solid #e5e7eb;border-top-left-radius:10px;border-top-right-radius:10px;background:#f9fafb;margin-right:4px;}"
            "QTabBar::tab:selected{background:#ffffff;}"
            "QHeaderView::section{background:#f3f4f6;padding:6px;border:0;border-bottom:1px solid #e5e7eb;}"
            "QTableWidget{gridline-color:#e5e7eb;border:1px solid #e5e7eb;border-radius:10px;}"
        )

        central = QWidget()
        root = QVBoxLayout()

        watch_box = QGroupBox()
        watch_layout = QHBoxLayout()

        self._watch_list = QListWidget()
        self._watch_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        watch_layout.addWidget(self._watch_list, 1)

        watch_buttons = QVBoxLayout()
        self._btn_watch_add = QPushButton()
        self._btn_watch_remove = QPushButton()
        self._btn_watch_suggest = QPushButton()
        self._btn_watch_save = QPushButton()
        self._btn_watch_reload = QPushButton()

        self._btn_watch_save.setObjectName("btnPrimary")
        watch_buttons.addWidget(self._btn_watch_add)
        watch_buttons.addWidget(self._btn_watch_remove)
        watch_buttons.addWidget(self._btn_watch_suggest)
        watch_buttons.addWidget(self._btn_watch_save)
        watch_buttons.addWidget(self._btn_watch_reload)
        watch_buttons.addStretch(1)
        watch_layout.addLayout(watch_buttons)

        watch_box.setLayout(watch_layout)
        root.addWidget(watch_box)

        header = QHBoxLayout()
        self._status = QLabel()
        header.addWidget(self._status)
        header.addStretch(1)

        self._lang_label = QLabel()
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("Italiano", "it")
        self._lang_combo.addItem("English", "en")

        self._btn_start = QPushButton()
        self._btn_stop = QPushButton()
        self._btn_refresh = QPushButton()
        self._btn_preview = QPushButton()
        self._btn_apply = QPushButton()
        self._btn_archive = QPushButton()

        self._btn_start.setObjectName("btnPrimary")
        self._btn_stop.setObjectName("btnDanger")
        self._btn_apply.setObjectName("btnAccent")
        self._btn_archive.setObjectName("btnSecondary")

        header.addWidget(self._lang_label)
        header.addWidget(self._lang_combo)
        header.addWidget(self._btn_start)
        header.addWidget(self._btn_stop)
        header.addWidget(self._btn_refresh)
        header.addWidget(self._btn_preview)
        header.addWidget(self._btn_apply)
        header.addWidget(self._btn_archive)

        root.addLayout(header)

        filter_bar = QHBoxLayout()
        self._filter_text_label = QLabel()
        self._filter_text = QLineEdit()
        self._filter_ext_label = QLabel()
        self._filter_ext = QLineEdit()
        self._btn_search = QPushButton()
        self._btn_clear = QPushButton()

        self._filter_text.setMinimumWidth(260)
        self._filter_ext.setFixedWidth(120)

        filter_bar.addWidget(self._filter_text_label)
        filter_bar.addWidget(self._filter_text, 1)
        filter_bar.addWidget(self._filter_ext_label)
        filter_bar.addWidget(self._filter_ext)
        filter_bar.addWidget(self._btn_search)
        filter_bar.addWidget(self._btn_clear)
        root.addLayout(filter_bar)

        self._tabs = QTabWidget()

        self._pending_table = QTableWidget(0, 6)
        self._pending_table.setSelectionBehavior(self._pending_table.SelectionBehavior.SelectRows)
        self._pending_table.setSelectionMode(self._pending_table.SelectionMode.SingleSelection)
        self._pending_table.setEditTriggers(self._pending_table.EditTrigger.NoEditTriggers)

        self._history_table = QTableWidget(0, 6)
        self._history_table.setSelectionBehavior(self._history_table.SelectionBehavior.SelectRows)
        self._history_table.setSelectionMode(self._history_table.SelectionMode.SingleSelection)
        self._history_table.setEditTriggers(self._history_table.EditTrigger.NoEditTriggers)

        self._tabs.addTab(self._pending_table, "")
        self._tabs.addTab(self._history_table, "")
        root.addWidget(self._tabs)

        central.setLayout(root)
        self._window.setCentralWidget(central)

        self._btn_watch_add.clicked.connect(self.watch_add)
        self._btn_watch_remove.clicked.connect(self.watch_remove)
        self._btn_watch_suggest.clicked.connect(self.watch_suggest_downloads)
        self._btn_watch_save.clicked.connect(self.watch_save)
        self._btn_watch_reload.clicked.connect(self.reload_config)

        self._lang_combo.currentIndexChanged.connect(self.on_language_changed)
        self._btn_start.clicked.connect(self.start_watcher)
        self._btn_stop.clicked.connect(self.stop_watcher)
        self._btn_refresh.clicked.connect(self.refresh)
        self._btn_preview.clicked.connect(self.preview_selected)
        self._btn_apply.clicked.connect(self.apply_selected)
        self._btn_archive.clicked.connect(self.archive_all)
        self._tabs.currentChanged.connect(self.on_tab_changed)
        self._btn_search.clicked.connect(self.refresh)
        self._btn_clear.clicked.connect(self.clear_filters)
        self._filter_text.returnPressed.connect(self.refresh)
        self._filter_ext.returnPressed.connect(self.refresh)

        self._timer = QTimer()
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        self._sync_language_combo()
        self._apply_language()
        self._refresh_watch_list()
        self.refresh()

    def show(self) -> None:
        self._window.show()

    def shutdown(self) -> None:
        self.stop_watcher()

    def _apply_language(self) -> None:
        self._window.setWindowTitle(t("gui.title", self._lang))
        self._lang_label.setText(t("gui.language", self._lang))
        self._btn_watch_add.setText(t("gui.add", self._lang))
        self._btn_watch_remove.setText(t("gui.remove", self._lang))
        self._btn_watch_suggest.setText(t("gui.suggest_downloads", self._lang))
        self._btn_watch_save.setText(t("gui.save", self._lang))
        self._btn_watch_reload.setText(t("gui.reload", self._lang))

        self._btn_start.setText(t("gui.start", self._lang))
        self._btn_stop.setText(t("gui.stop", self._lang))
        self._btn_refresh.setText(t("gui.refresh", self._lang))
        self._btn_preview.setText(t("gui.preview", self._lang))
        self._btn_apply.setText(t("gui.apply", self._lang))
        self._btn_archive.setText(t("gui.archive_all", self._lang))

        self._filter_text_label.setText(t("gui.filter.text", self._lang))
        self._filter_text.setPlaceholderText(t("gui.filter.text.placeholder", self._lang))
        self._filter_ext_label.setText(t("gui.filter.ext", self._lang))
        self._filter_ext.setPlaceholderText(t("gui.filter.ext.placeholder", self._lang))
        self._btn_search.setText(t("gui.search", self._lang))
        self._btn_clear.setText(t("gui.clear", self._lang))

        self._tabs.setTabText(0, t("gui.tab.pending", self._lang))
        self._tabs.setTabText(1, t("gui.tab.history", self._lang))

        self._pending_table.setHorizontalHeaderLabels(
            [
                t("gui.table.index", self._lang),
                t("gui.table.created", self._lang),
                t("gui.table.ext", self._lang),
                t("gui.table.size", self._lang),
                t("gui.table.source", self._lang),
                t("gui.table.dest", self._lang),
            ]
        )
        self._history_table.setHorizontalHeaderLabels(
            [
                t("gui.table.index", self._lang),
                t("gui.table.created", self._lang),
                t("gui.table.applied_at", self._lang),
                t("gui.table.status", self._lang),
                t("gui.table.source", self._lang),
                t("gui.table.moved_to", self._lang),
            ]
        )

        parent = self._btn_watch_add.parentWidget()
        if parent is not None:
            watch_box = parent.parentWidget()
            if hasattr(watch_box, "setTitle"):
                watch_box.setTitle(t("gui.watch_folders", self._lang))

        self.refresh()

    def clear_filters(self) -> None:
        self._filter_text.setText("")
        self._filter_ext.setText("")
        self.refresh()

    def on_tab_changed(self) -> None:
        is_pending = self._tabs.currentIndex() == 0
        self._btn_apply.setEnabled(is_pending)
        self._btn_archive.setEnabled(is_pending)
        self.refresh()

    def _sync_language_combo(self) -> None:
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == self._lang:
                self._lang_combo.setCurrentIndex(i)
                break

    def on_language_changed(self) -> None:
        lang = self._lang_combo.currentData()
        if lang in ("it", "en"):
            self._lang = lang
            self._apply_language()

    def start_watcher(self) -> None:
        if self._watcher is not None:
            return
        if not self._watch_paths:
            self._QMessageBox.information(self._window, t("gui.title", self._lang), t("gui.msg.watch_empty", self._lang))
            return

        queue_writer = None
        if self._config.app.mode == "manual" and self._config.queue.enabled:
            queue_writer = QueueWriter(self._queue_path)

        rule_engine = RuleEngine(self._config.rules, self._config.library)
        watch_cfg = WatchConfig(
            paths=list(self._watch_paths),
            recursive=self._watch_recursive,
            settle_seconds=self._watch_settle,
        )
        watcher = FilesGoThereWatcher(
            WatchContext(
                lang=self._lang,
                watch=watch_cfg,
                mode=self._config.app.mode,
            ),
            rule_engine,
            self._logger,
            queue_writer=queue_writer,
        )
        watcher.start()
        self._watcher = watcher
        self.refresh()

    def stop_watcher(self) -> None:
        if self._watcher is None:
            return
        self._watcher.stop()
        self._watcher = None
        self.refresh()

    def reload_config(self) -> None:
        if self._watcher is not None:
            self._QMessageBox.information(self._window, t("gui.title", self._lang), t("gui.msg.stop_before_reload", self._lang))
            return

        from filesgothere.config import ConfigError, load_config

        try:
            config = load_config(self._config_path)
        except ConfigError as e:
            self._QMessageBox.warning(self._window, "Reload", str(e))
            return
        except Exception as e:
            self._QMessageBox.warning(self._window, "Reload", f"Errore: {e}")
            return

        self._config = config
        self._queue_path = config.queue.file
        self._done_path = config.queue.file.with_name("queue_done.jsonl")
        self._logger = setup_logging(config.logging)
        self._lang = config.app.language
        self._watch_paths = [Path(p) for p in config.watch.paths]
        self._watch_recursive = config.watch.recursive
        self._watch_settle = config.watch.settle_seconds
        self._sync_language_combo()
        self._apply_language()
        self._refresh_watch_list()
        self.refresh()

    def refresh(self) -> None:
        contains = self._filter_text.text().strip() or None
        ext = self._filter_ext.text().strip() or None
        pending_actions = read_actions(self._queue_path, ext=ext, contains=contains)
        done_actions = read_actions(self._done_path, tail=500, ext=ext, contains=contains)
        watcher_state = "gui.state.running" if self._watcher is not None else "gui.state.stopped"
        self._status.setText(
            t(
                "gui.queue.status",
                self._lang,
                state=t(watcher_state, self._lang),
                folders=str(len(self._watch_paths)),
                pending=str(len(pending_actions)),
                done=str(len(done_actions)),
            )
        )

        self._pending_table.setRowCount(len(pending_actions))
        for i, a in enumerate(pending_actions):
            self._pending_table.setItem(i, 0, self._QTableWidgetItem(str(i)))
            self._pending_table.setItem(i, 1, self._QTableWidgetItem(str(a.get("created_at", ""))))
            self._pending_table.setItem(i, 2, self._QTableWidgetItem(str(a.get("extension", ""))))
            self._pending_table.setItem(i, 3, self._QTableWidgetItem(str(a.get("size_bytes", ""))))
            self._pending_table.setItem(i, 4, self._QTableWidgetItem(str(a.get("src_path", ""))))
            self._pending_table.setItem(i, 5, self._QTableWidgetItem(str(a.get("dst_dir", ""))))
        self._pending_table.resizeColumnsToContents()

        self._history_table.setRowCount(len(done_actions))
        for i, a in enumerate(done_actions):
            self._history_table.setItem(i, 0, self._QTableWidgetItem(str(i)))
            self._history_table.setItem(i, 1, self._QTableWidgetItem(str(a.get("created_at", ""))))
            self._history_table.setItem(i, 2, self._QTableWidgetItem(str(a.get("applied_at", ""))))
            self._history_table.setItem(i, 3, self._QTableWidgetItem(str(a.get("status", ""))))
            self._history_table.setItem(i, 4, self._QTableWidgetItem(str(a.get("src_path", ""))))
            self._history_table.setItem(i, 5, self._QTableWidgetItem(str(a.get("moved_to", ""))))
        self._history_table.resizeColumnsToContents()

    def _selected_index(self) -> int | None:
        if self._tabs.currentIndex() != 0:
            return None
        rows = self._pending_table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(rows[0].row())

    def preview_selected(self) -> None:
        if self._tabs.currentIndex() == 0:
            index = self._selected_index()
            if index is None:
                self._QMessageBox.information(
                    self._window, t("gui.preview", self._lang), t("gui.msg.select_row", self._lang)
                )
                return

            preview = preview_action_by_index(self._queue_path, index, self._config.library)
            text = "\n".join(
                [
                    f"Index: {preview.get('index')}",
                    f"Source: {preview.get('src_path')}",
                    f"Dest dir: {preview.get('dst_dir')}",
                    f"Predicted: {preview.get('predicted_moved_to')}",
                    f"Warnings: {preview.get('warnings')}",
                    f"Duplicate strategy: {preview.get('duplicate_strategy')}",
                    f"Will create dir: {preview.get('will_create_dir')}",
                ]
            )
            self._QMessageBox.information(self._window, t("gui.preview", self._lang), text)
            return

        rows = self._history_table.selectionModel().selectedRows()
        if not rows:
            self._QMessageBox.information(
                self._window, t("gui.preview", self._lang), t("gui.msg.select_row", self._lang)
            )
            return
        index = int(rows[0].row())
        actions = read_actions(self._done_path, tail=500)
        if index < 0 or index >= len(actions):
            return
        a = actions[index]
        text = "\n".join(
            [
                f"Index: {index}",
                f"Source: {a.get('src_path')}",
                f"Moved to: {a.get('moved_to')}",
                f"Status: {a.get('status')}",
                f"Created: {a.get('created_at')}",
                f"Applied: {a.get('applied_at')}",
            ]
        )
        self._QMessageBox.information(self._window, t("gui.preview", self._lang), text)

    def apply_selected(self) -> None:
        if self._watcher is not None:
            self._QMessageBox.information(self._window, t("gui.apply", self._lang), t("gui.msg.stop_before_apply", self._lang))
            return

        index = self._selected_index()
        if index is None:
            self._QMessageBox.information(self._window, t("gui.apply", self._lang), t("gui.msg.select_row", self._lang))
            return

        preview = preview_action_by_index(self._queue_path, index, self._config.library)
        if preview.get("reason") == "queue_empty":
            self._QMessageBox.information(self._window, t("gui.apply", self._lang), t("gui.queue.pending", self._lang) + ": 0")
            return

        text = t(
            "gui.confirm.apply.text",
            self._lang,
            src=str(preview.get("src_path")),
            dst=str(preview.get("predicted_moved_to")),
            warnings=str(preview.get("warnings")),
        )
        answer = self._QMessageBox.question(self._window, t("gui.confirm.apply.title", self._lang), text)
        if answer != self._QMessageBox.StandardButton.Yes:
            return

        result = apply_action_by_index(
            self._queue_path,
            self._done_path,
            index,
            self._config.library,
            require_same_size=True,
        )
        if result.get("applied") is True:
            self._QMessageBox.information(self._window, t("gui.apply", self._lang), t("gui.info.applied", self._lang))
        else:
            self._QMessageBox.warning(self._window, t("gui.apply", self._lang), str(result))

        self.refresh()

    def archive_all(self) -> None:
        from filesgothere.queue import archive_queue

        if self._watcher is not None:
            self._QMessageBox.information(self._window, t("gui.archive_all", self._lang), t("gui.msg.stop_before_archive", self._lang))
            return

        answer = self._QMessageBox.question(self._window, t("gui.confirm.archive.title", self._lang), t("gui.confirm.archive.text", self._lang))
        if answer != self._QMessageBox.StandardButton.Yes:
            return

        result = archive_queue(self._queue_path, self._done_path)
        self._QMessageBox.information(self._window, t("gui.confirm.archive.title", self._lang), str(result))
        self.refresh()

    def _refresh_watch_list(self) -> None:
        self._watch_list.clear()
        for p in self._watch_paths:
            self._watch_list.addItem(str(p))

    def watch_add(self) -> None:
        if self._watcher is not None:
            self._QMessageBox.information(self._window, t("gui.watch_folders", self._lang), t("gui.msg.stop_before_edit", self._lang))
            return

        directory = self._QFileDialog.getExistingDirectory(self._window, t("gui.watch_folders", self._lang))
        if not directory:
            return
        path = Path(directory)
        if path not in self._watch_paths:
            self._watch_paths.append(path)
            self._refresh_watch_list()
            self.refresh()

    def watch_remove(self) -> None:
        if self._watcher is not None:
            self._QMessageBox.information(self._window, t("gui.watch_folders", self._lang), t("gui.msg.stop_before_edit", self._lang))
            return

        row = self._watch_list.currentRow()
        if row < 0:
            return
        self._watch_paths.pop(row)
        self._refresh_watch_list()
        self.refresh()

    def watch_suggest_downloads(self) -> None:
        if self._watcher is not None:
            self._QMessageBox.information(self._window, t("gui.watch_folders", self._lang), t("gui.msg.stop_before_edit", self._lang))
            return

        home = Path(os.path.expanduser("~"))
        candidate = home / "Downloads"
        if candidate.exists() and candidate.is_dir():
            if candidate not in self._watch_paths:
                self._watch_paths.append(candidate)
                self._refresh_watch_list()
                self.refresh()
            else:
                self._QMessageBox.information(self._window, t("gui.watch_folders", self._lang), t("gui.msg.downloads_already_present", self._lang))
        else:
            self._QMessageBox.information(self._window, t("gui.watch_folders", self._lang), t("gui.msg.not_found", self._lang, path=str(candidate)))

    def watch_save(self) -> None:
        if self._watcher is not None:
            self._QMessageBox.information(self._window, t("gui.watch_folders", self._lang), t("gui.msg.stop_before_save", self._lang))
            return

        try:
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
        except Exception as e:
            self._QMessageBox.warning(self._window, "Watch folders", f"Errore lettura config: {e}")
            return

        if not isinstance(raw, dict):
            self._QMessageBox.warning(self._window, "Watch folders", "Config non valida.")
            return

        watch = raw.get("watch")
        if not isinstance(watch, dict):
            watch = {}
            raw["watch"] = watch

        watch["paths"] = [str(p).replace("\\", "/") for p in self._watch_paths]
        app = raw.get("app")
        if not isinstance(app, dict):
            app = {}
            raw["app"] = app
        app["language"] = self._lang

        try:
            self._config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self._QMessageBox.warning(self._window, "Watch folders", f"Errore scrittura config: {e}")
            return

        self._QMessageBox.information(self._window, t("gui.watch_folders", self._lang), t("gui.msg.saved", self._lang))
