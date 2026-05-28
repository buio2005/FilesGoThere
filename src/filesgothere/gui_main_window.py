from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
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
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor
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
            QCheckBox,
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
        self._theme = config.app.theme
        self._mode = config.app.mode
        self._focus_on_startup = config.app.focus_on_startup
        self._focus_on_download_complete = config.app.focus_on_download_complete
        self._watch_paths = [Path(p) for p in config.watch.paths]
        self._watch_recursive = config.watch.recursive
        self._watch_settle = config.watch.settle_seconds
        self._last_pending_sizes: dict[str, int] = {}
        self._notified_complete: set[str] = set()
        self._first_run_hint_shown = False
        self._Qt = Qt
        self._QColor = QColor

        self._window = QMainWindow()
        self._window.setWindowTitle(t("gui.title", self._lang))
        self._apply_theme()

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
        self._lang_combo.addItem(t("gui.it", self._lang), "it")
        self._lang_combo.addItem(t("gui.en", self._lang), "en")

        self._btn_start = QPushButton()
        self._btn_stop = QPushButton()
        self._btn_refresh = QPushButton()
        self._btn_preview = QPushButton()
        self._btn_open_src = QPushButton()
        self._btn_open_dst = QPushButton()
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
        header.addWidget(self._btn_open_src)
        header.addWidget(self._btn_open_dst)
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
        self._pending_table.setAlternatingRowColors(True)

        self._history_table = QTableWidget(0, 6)
        self._history_table.setSelectionBehavior(self._history_table.SelectionBehavior.SelectRows)
        self._history_table.setSelectionMode(self._history_table.SelectionMode.SingleSelection)
        self._history_table.setEditTriggers(self._history_table.EditTrigger.NoEditTriggers)
        self._history_table.setAlternatingRowColors(True)

        self._tabs.addTab(self._pending_table, "")
        self._tabs.addTab(self._history_table, "")

        settings_page = QWidget()
        settings_root = QVBoxLayout()
        settings_box = QGroupBox()
        settings_layout = QVBoxLayout()

        mode_row = QHBoxLayout()
        self._mode_label = QLabel()
        self._mode_combo = QComboBox()
        self._mode_combo.addItem(t("gui.mode.manual", self._lang), "manual")
        self._mode_combo.addItem(t("gui.mode.auto", self._lang), "auto")
        mode_row.addWidget(self._mode_label)
        mode_row.addWidget(self._mode_combo, 1)
        settings_layout.addLayout(mode_row)

        theme_row = QHBoxLayout()
        self._theme_label = QLabel()
        self._theme_combo = QComboBox()
        self._theme_combo.addItem(t("gui.theme.light", self._lang), "light")
        self._theme_combo.addItem(t("gui.theme.dark", self._lang), "dark")
        theme_row.addWidget(self._theme_label)
        theme_row.addWidget(self._theme_combo, 1)
        settings_layout.addLayout(theme_row)

        self._chk_focus_startup = QCheckBox()
        self._chk_focus_download = QCheckBox()
        settings_layout.addWidget(self._chk_focus_startup)
        settings_layout.addWidget(self._chk_focus_download)
        settings_layout.addStretch(1)

        settings_box.setLayout(settings_layout)
        settings_root.addWidget(settings_box)
        settings_page.setLayout(settings_root)
        self._tabs.addTab(settings_page, "")
        root.addWidget(self._tabs)

        central.setLayout(root)
        self._window.setCentralWidget(central)

        self._btn_watch_add.clicked.connect(self.watch_add)
        self._btn_watch_remove.clicked.connect(self.watch_remove)
        self._btn_watch_suggest.clicked.connect(self.watch_suggest_downloads)
        self._btn_watch_save.clicked.connect(self.watch_save)
        self._btn_watch_reload.clicked.connect(self.reload_config)

        self._lang_combo.currentIndexChanged.connect(self.on_language_changed)
        self._theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        self._chk_focus_startup.stateChanged.connect(self.on_focus_changed)
        self._chk_focus_download.stateChanged.connect(self.on_focus_changed)
        self._mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self._btn_start.clicked.connect(self.start_watcher)
        self._btn_stop.clicked.connect(self.stop_watcher)
        self._btn_refresh.clicked.connect(self.refresh)
        self._btn_preview.clicked.connect(self.preview_selected)
        self._btn_open_src.clicked.connect(self.open_source)
        self._btn_open_dst.clicked.connect(self.open_destination)
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
        self._sync_theme_combo()
        self._sync_focus_checkboxes()
        self._sync_mode_combo()
        self._apply_language()
        self._refresh_watch_list()
        self.refresh()

    def show(self) -> None:
        self._window.show()
        if self._focus_on_startup:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(200, self._bring_to_front)
        self._maybe_show_first_run_hint()

    def shutdown(self) -> None:
        try:
            self._save_app_settings_silent()
        except Exception:
            pass
        self.stop_watcher()

    def _maybe_show_first_run_hint(self) -> None:
        if self._first_run_hint_shown:
            return
        self._first_run_hint_shown = True
        if self._watcher is not None:
            return
        if self._watch_paths:
            return

        box = self._QMessageBox(self._window)
        box.setIcon(self._QMessageBox.Icon.Information)
        box.setWindowTitle(t("gui.first_run.title", self._lang))
        box.setText(t("gui.first_run.text", self._lang))
        btn_suggest = box.addButton(t("gui.suggest_downloads", self._lang), self._QMessageBox.ButtonRole.ActionRole)
        btn_add = box.addButton(t("gui.add", self._lang), self._QMessageBox.ButtonRole.ActionRole)
        btn_later = box.addButton(t("gui.first_run.later", self._lang), self._QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_suggest)
        box.exec()

        clicked = box.clickedButton()
        if clicked == btn_suggest:
            self.watch_suggest_downloads()
        elif clicked == btn_add:
            self.watch_add()
        elif clicked == btn_later:
            return

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
        self._btn_open_src.setText(t("gui.open_source", self._lang))
        self._btn_open_dst.setText(t("gui.open_destination", self._lang))
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
        self._tabs.setTabText(2, t("gui.tab.settings", self._lang))

        self._mode_label.setText(t("gui.mode", self._lang))
        self._theme_label.setText(t("gui.theme", self._lang))
        self._chk_focus_startup.setText(t("gui.focus_on_startup", self._lang))
        self._chk_focus_download.setText(t("gui.focus_on_download_complete", self._lang))

        self._btn_preview.setToolTip(t("gui.tip.preview", self._lang))
        self._btn_apply.setToolTip(t("gui.tip.apply", self._lang))
        self._btn_archive.setToolTip(t("gui.tip.archive", self._lang))
        self._btn_open_src.setToolTip(t("gui.tip.open_source", self._lang))
        self._btn_open_dst.setToolTip(t("gui.tip.open_destination", self._lang))

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

        self._update_language_combo_labels()
        self._update_mode_combo_labels()
        self._update_theme_combo_labels()
        self.refresh()

    def clear_filters(self) -> None:
        self._filter_text.setText("")
        self._filter_ext.setText("")
        self.refresh()

    def on_tab_changed(self) -> None:
        tab = self._tabs.currentIndex()
        is_pending = tab == 0
        is_actions = tab in (0, 1)
        self._btn_preview.setEnabled(is_actions)
        self._btn_open_src.setEnabled(is_actions)
        self._btn_open_dst.setEnabled(is_actions)
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
            self._save_app_settings()

    def _sync_mode_combo(self) -> None:
        for i in range(self._mode_combo.count()):
            if self._mode_combo.itemData(i) == self._mode:
                self._mode_combo.setCurrentIndex(i)
                break

    def _update_mode_combo_labels(self) -> None:
        self._mode_combo.blockSignals(True)
        try:
            for i in range(self._mode_combo.count()):
                v = self._mode_combo.itemData(i)
                if v == "manual":
                    self._mode_combo.setItemText(i, t("gui.mode.manual", self._lang))
                elif v == "auto":
                    self._mode_combo.setItemText(i, t("gui.mode.auto", self._lang))
        finally:
            self._mode_combo.blockSignals(False)

    def on_mode_changed(self) -> None:
        if self._watcher is not None:
            self._mode_combo.blockSignals(True)
            try:
                self._sync_mode_combo()
            finally:
                self._mode_combo.blockSignals(False)
            self._QMessageBox.information(self._window, t("gui.title", self._lang), t("gui.msg.stop_before_mode", self._lang))
            return

        mode = self._mode_combo.currentData()
        if mode in ("manual", "auto"):
            self._mode = mode
            self._save_app_settings()

    def _sync_theme_combo(self) -> None:
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == self._theme:
                self._theme_combo.setCurrentIndex(i)
                break

    def _sync_focus_checkboxes(self) -> None:
        self._chk_focus_startup.setChecked(bool(self._focus_on_startup))
        self._chk_focus_download.setChecked(bool(self._focus_on_download_complete))

    def _update_language_combo_labels(self) -> None:
        self._lang_combo.blockSignals(True)
        try:
            for i in range(self._lang_combo.count()):
                v = self._lang_combo.itemData(i)
                if v == "it":
                    self._lang_combo.setItemText(i, t("gui.it", self._lang))
                elif v == "en":
                    self._lang_combo.setItemText(i, t("gui.en", self._lang))
        finally:
            self._lang_combo.blockSignals(False)

    def _update_theme_combo_labels(self) -> None:
        self._theme_combo.blockSignals(True)
        try:
            for i in range(self._theme_combo.count()):
                v = self._theme_combo.itemData(i)
                if v == "light":
                    self._theme_combo.setItemText(i, t("gui.theme.light", self._lang))
                elif v == "dark":
                    self._theme_combo.setItemText(i, t("gui.theme.dark", self._lang))
        finally:
            self._theme_combo.blockSignals(False)

    def on_theme_changed(self) -> None:
        theme = self._theme_combo.currentData()
        if theme in ("light", "dark"):
            self._theme = theme
            self._apply_theme()
            self._save_app_settings()

    def on_focus_changed(self) -> None:
        self._focus_on_startup = bool(self._chk_focus_startup.isChecked())
        self._focus_on_download_complete = bool(self._chk_focus_download.isChecked())
        self._save_app_settings()

    def _save_app_settings(self) -> None:
        try:
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}

        if not isinstance(raw, dict):
            raw = {}

        app = raw.get("app")
        if not isinstance(app, dict):
            app = {}
            raw["app"] = app
        app["language"] = self._lang
        app["mode"] = self._mode
        app["theme"] = self._theme
        app["focus_on_startup"] = bool(self._focus_on_startup)
        app["focus_on_download_complete"] = bool(self._focus_on_download_complete)

        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self._QMessageBox.warning(self._window, t("gui.tab.settings", self._lang), f"{t('gui.msg.write_error', self._lang)}: {e}")
            return

    def _save_app_settings_silent(self) -> None:
        try:
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}

        if not isinstance(raw, dict):
            raw = {}

        app = raw.get("app")
        if not isinstance(app, dict):
            app = {}
            raw["app"] = app
        app["language"] = self._lang
        app["mode"] = self._mode
        app["theme"] = self._theme
        app["focus_on_startup"] = bool(self._focus_on_startup)
        app["focus_on_download_complete"] = bool(self._focus_on_download_complete)

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    def _apply_theme(self) -> None:
        if self._theme == "dark":
            self._window.setStyleSheet(self._stylesheet_dark())
        else:
            self._window.setStyleSheet(self._stylesheet_light())

    def _stylesheet_light(self) -> str:
        return (
            "QWidget{font-family:Segoe UI;font-size:12px;color:#111827;background:#ffffff;}"
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
            "QCheckBox{padding:6px;}"
            "QTabWidget::pane{border:1px solid #e5e7eb;border-radius:10px;top:-1px;}"
            "QTabBar::tab{padding:8px 12px;border:1px solid #e5e7eb;border-top-left-radius:10px;border-top-right-radius:10px;background:#f9fafb;margin-right:4px;}"
            "QTabBar::tab:selected{background:#ffffff;}"
            "QHeaderView::section{background:#f3f4f6;padding:6px;border:0;border-bottom:1px solid #e5e7eb;}"
            "QTableWidget{gridline-color:#e5e7eb;border:1px solid #e5e7eb;border-radius:10px;}"
            "QTableWidget::item:alternate{background:#f9fafb;}"
            "QTableWidget::item:selected{background:#dbeafe;color:#111827;}"
        )

    def _stylesheet_dark(self) -> str:
        return (
            "QWidget{font-family:Segoe UI;font-size:12px;color:#e5e7eb;background:#0b1220;}"
            "QGroupBox{font-weight:600;margin-top:8px;border:1px solid #243146;border-radius:10px;padding:10px;background:#0f172a;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;}"
            "QPushButton{padding:7px 12px;border:1px solid #334155;border-radius:10px;background:#111827;color:#e5e7eb;}"
            "QPushButton:hover{background:#0b1220;}"
            "QPushButton:pressed{background:#020617;}"
            "QPushButton:disabled{color:#64748b;background:#0f172a;}"
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
            "QLineEdit{padding:7px 10px;border:1px solid #334155;border-radius:10px;background:#111827;color:#e5e7eb;}"
            "QComboBox{padding:6px 10px;border:1px solid #334155;border-radius:10px;background:#111827;color:#e5e7eb;}"
            "QCheckBox{padding:6px;}"
            "QTabWidget::pane{border:1px solid #243146;border-radius:10px;top:-1px;}"
            "QTabBar::tab{padding:8px 12px;border:1px solid #243146;border-top-left-radius:10px;border-top-right-radius:10px;background:#0f172a;margin-right:4px;}"
            "QTabBar::tab:selected{background:#111827;}"
            "QHeaderView::section{background:#0f172a;padding:6px;border:0;border-bottom:1px solid #243146;}"
            "QTableWidget{gridline-color:#243146;border:1px solid #243146;border-radius:10px;background:#111827;color:#e5e7eb;}"
            "QTableWidget::item:alternate{background:#0f172a;}"
            "QTableWidget::item:selected{background:#1d4ed8;color:#ffffff;}"
        )

    def _bring_to_front(self) -> None:
        from PySide6.QtCore import QTimer

        if self._window.isMinimized():
            self._window.showNormal()
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
        self._window.setWindowState((self._window.windowState() & ~self._Qt.WindowMinimized) | self._Qt.WindowActive)

        self._window.setWindowFlag(self._Qt.WindowStaysOnTopHint, True)
        self._window.show()

        def _unset() -> None:
            self._window.setWindowFlag(self._Qt.WindowStaysOnTopHint, False)
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()

        QTimer.singleShot(250, _unset)

    def start_watcher(self) -> None:
        if self._watcher is not None:
            return
        if not self._watch_paths:
            self._QMessageBox.information(self._window, t("gui.title", self._lang), t("gui.msg.watch_empty", self._lang))
            return

        queue_writer = None
        if self._mode == "manual" and self._config.queue.enabled:
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
                mode=self._mode,
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
            self._QMessageBox.warning(self._window, t("gui.reload", self._lang), str(e))
            return
        except Exception as e:
            self._QMessageBox.warning(self._window, t("gui.reload", self._lang), f"{t('gui.msg.error', self._lang)}: {e}")
            return

        self._config = config
        self._queue_path = config.queue.file
        self._done_path = config.queue.file.with_name("queue_done.jsonl")
        self._logger = setup_logging(config.logging)
        self._lang = config.app.language
        self._theme = config.app.theme
        self._mode = config.app.mode
        self._focus_on_startup = config.app.focus_on_startup
        self._focus_on_download_complete = config.app.focus_on_download_complete
        self._watch_paths = [Path(p) for p in config.watch.paths]
        self._watch_recursive = config.watch.recursive
        self._watch_settle = config.watch.settle_seconds
        self._sync_language_combo()
        self._sync_theme_combo()
        self._sync_focus_checkboxes()
        self._sync_mode_combo()
        self._apply_language()
        self._refresh_watch_list()
        self.refresh()

    def refresh(self) -> None:
        contains = self._filter_text.text().strip() or None
        ext = self._filter_ext.text().strip() or None
        pending_actions = read_actions(self._queue_path, ext=ext, contains=contains)
        done_actions = read_actions(self._done_path, tail=500, ext=ext, contains=contains)
        self._maybe_raise_on_download_complete(pending_actions)
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
            size_raw = a.get("size_bytes")
            size = int(size_raw) if isinstance(size_raw, int) else -1
            created_raw = a.get("created_at")
            created = str(created_raw) if created_raw is not None else ""
            src_raw = a.get("src_path")
            dst_raw = a.get("dst_dir")

            self._pending_table.setItem(i, 0, self._QTableWidgetItem(str(i)))
            self._pending_table.setItem(i, 1, self._QTableWidgetItem(self._fmt_dt(created)))
            self._pending_table.setItem(i, 2, self._QTableWidgetItem(str(a.get("extension", ""))))
            self._pending_table.setItem(i, 3, self._QTableWidgetItem(self._fmt_size(size)))
            self._pending_table.setItem(i, 4, self._QTableWidgetItem(str(src_raw or "")))
            self._pending_table.setItem(i, 5, self._QTableWidgetItem(str(dst_raw or "")))
            self._apply_pending_row_style(i, size)
        self._pending_table.resizeColumnsToContents()

        self._history_table.setRowCount(len(done_actions))
        for i, a in enumerate(done_actions):
            created_raw = a.get("created_at")
            applied_raw = a.get("applied_at")
            created = str(created_raw) if created_raw is not None else ""
            applied = str(applied_raw) if applied_raw is not None else ""
            self._history_table.setItem(i, 0, self._QTableWidgetItem(str(i)))
            self._history_table.setItem(i, 1, self._QTableWidgetItem(self._fmt_dt(created)))
            self._history_table.setItem(i, 2, self._QTableWidgetItem(self._fmt_dt(applied)))
            status_raw = a.get("status")
            status = str(status_raw) if status_raw is not None else ""
            self._history_table.setItem(i, 3, self._QTableWidgetItem(self._tr_status(status)))
            self._history_table.setItem(i, 4, self._QTableWidgetItem(str(a.get("src_path", ""))))
            self._history_table.setItem(i, 5, self._QTableWidgetItem(str(a.get("moved_to", ""))))
            self._apply_history_row_style(i, status)
        self._history_table.resizeColumnsToContents()
        self._update_settings_enabled()

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
            warnings_raw = preview.get("warnings")
            warnings_list = warnings_raw if isinstance(warnings_raw, list) else []
            warnings_text = ", ".join(self._tr_warning(str(w)) for w in warnings_list)
            duplicate_raw = preview.get("duplicate_strategy")
            duplicate = str(duplicate_raw) if duplicate_raw is not None else ""
            text = "\n".join(
                [
                    f"{t('gui.preview.field.index', self._lang)}: {preview.get('index')}",
                    f"{t('gui.preview.field.source', self._lang)}: {preview.get('src_path')}",
                    f"{t('gui.preview.field.dest_dir', self._lang)}: {preview.get('dst_dir')}",
                    f"{t('gui.preview.field.predicted', self._lang)}: {preview.get('predicted_moved_to')}",
                    f"{t('gui.preview.field.warnings', self._lang)}: {warnings_text}",
                    f"{t('gui.preview.field.duplicate_strategy', self._lang)}: {self._tr_duplicate_strategy(duplicate)}",
                    f"{t('gui.preview.field.will_create_dir', self._lang)}: {preview.get('will_create_dir')}",
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
        status_raw = a.get("status")
        status = str(status_raw) if status_raw is not None else ""
        text = "\n".join(
            [
                f"{t('gui.preview.field.index', self._lang)}: {index}",
                f"{t('gui.preview.field.source', self._lang)}: {a.get('src_path')}",
                f"{t('gui.preview.field.moved_to', self._lang)}: {a.get('moved_to')}",
                f"{t('gui.preview.field.status', self._lang)}: {self._tr_status(status)}",
                f"{t('gui.preview.field.created', self._lang)}: {self._fmt_dt(str(a.get('created_at') or ''))}",
                f"{t('gui.preview.field.applied_at', self._lang)}: {self._fmt_dt(str(a.get('applied_at') or ''))}",
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
            warnings=", ".join(self._tr_warning(str(w)) for w in (preview.get("warnings") or [])),
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
            self._QMessageBox.warning(self._window, t("gui.watch_folders", self._lang), f"{t('gui.msg.read_error', self._lang)}: {e}")
            return

        if not isinstance(raw, dict):
            self._QMessageBox.warning(self._window, t("gui.watch_folders", self._lang), t("gui.msg.config_invalid", self._lang))
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
        app["mode"] = self._mode
        app["theme"] = self._theme
        app["focus_on_startup"] = bool(self._focus_on_startup)
        app["focus_on_download_complete"] = bool(self._focus_on_download_complete)

        try:
            self._config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self._QMessageBox.warning(self._window, t("gui.watch_folders", self._lang), f"{t('gui.msg.write_error', self._lang)}: {e}")
            return

        self._QMessageBox.information(self._window, t("gui.watch_folders", self._lang), t("gui.msg.saved", self._lang))

    def _maybe_raise_on_download_complete(self, pending_actions: list[dict[str, object]]) -> None:
        current: dict[str, int] = {}
        for a in pending_actions:
            src_raw = a.get("src_path")
            size_raw = a.get("size_bytes")
            if not isinstance(src_raw, str):
                continue
            size = int(size_raw) if isinstance(size_raw, int) else -1
            key = src_raw.casefold()
            current[key] = size

        if self._focus_on_download_complete and not self._window.isActiveWindow():
            for key, size in current.items():
                prev = self._last_pending_sizes.get(key)
                if prev == 0 and size > 0 and key not in self._notified_complete:
                    self._notified_complete.add(key)
                    from PySide6.QtCore import QTimer

                    QTimer.singleShot(0, self._bring_to_front)
                    break

        removed = set(self._last_pending_sizes.keys()) - set(current.keys())
        for key in removed:
            self._notified_complete.discard(key)

        self._last_pending_sizes = current

    def _tr_warning(self, code: str) -> str:
        return t(f"queue.warning.{code}", self._lang)

    def _tr_status(self, code: str) -> str:
        return t(f"queue.status.{code}", self._lang)

    def _tr_duplicate_strategy(self, code: str) -> str:
        return t(f"queue.duplicate_strategy.{code}", self._lang)

    def _fmt_size(self, size: int) -> str:
        if size < 0:
            return ""
        if size == 0:
            return "0"
        units = ["B", "KB", "MB", "GB", "TB"]
        v = float(size)
        i = 0
        while v >= 1024.0 and i < (len(units) - 1):
            v /= 1024.0
            i += 1
        if i == 0:
            return f"{int(v)} {units[i]}"
        if v >= 100:
            return f"{v:.0f} {units[i]}"
        if v >= 10:
            return f"{v:.1f} {units[i]}"
        return f"{v:.2f} {units[i]}"

    def _fmt_dt(self, iso: str) -> str:
        s = iso.strip()
        if not s:
            return ""
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            return s
        try:
            if dt.tzinfo is None:
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            local = dt.astimezone()
            return local.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s

    def _apply_pending_row_style(self, row: int, size: int) -> None:
        if size != 0:
            return
        color = "#fef9c3" if self._theme != "dark" else "#3b2f0b"
        for col in range(self._pending_table.columnCount()):
            item = self._pending_table.item(row, col)
            if item is not None:
                item.setBackground(self._QColor(color))

    def _apply_history_row_style(self, row: int, status: str) -> None:
        if not status:
            return
        if status == "applied":
            color = "#dcfce7" if self._theme != "dark" else "#064e3b"
        elif status == "skipped_duplicate":
            color = "#f3f4f6" if self._theme != "dark" else "#0f172a"
        else:
            color = "#fee2e2" if self._theme != "dark" else "#3f1d1d"
        for col in range(self._history_table.columnCount()):
            item = self._history_table.item(row, col)
            if item is not None:
                item.setBackground(self._QColor(color))

    def _update_settings_enabled(self) -> None:
        running = self._watcher is not None
        self._mode_combo.setEnabled(not running)

    def _selected_history_index(self) -> int | None:
        if self._tabs.currentIndex() != 1:
            return None
        rows = self._history_table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(rows[0].row())

    def _open_in_explorer(self, path: Path, *, select: bool) -> None:
        try:
            if select:
                subprocess.run(["explorer.exe", "/select,", str(path)], check=False)
            else:
                os.startfile(str(path))
        except Exception as e:
            self._QMessageBox.warning(self._window, t("gui.title", self._lang), f"{t('gui.msg.error', self._lang)}: {e}")

    def open_source(self) -> None:
        if self._tabs.currentIndex() == 0:
            index = self._selected_index()
            if index is None:
                self._QMessageBox.information(self._window, t("gui.open_source", self._lang), t("gui.msg.select_row", self._lang))
                return
            actions = read_actions(self._queue_path)
            if index < 0 or index >= len(actions):
                return
            src_raw = actions[index].get("src_path")
            if not isinstance(src_raw, str) or not src_raw:
                return
            src = Path(src_raw)
            if src.exists():
                self._open_in_explorer(src, select=True)
            elif src.parent.exists():
                self._open_in_explorer(src.parent, select=False)
            return

        if self._tabs.currentIndex() == 1:
            index = self._selected_history_index()
            if index is None:
                self._QMessageBox.information(self._window, t("gui.open_source", self._lang), t("gui.msg.select_row", self._lang))
                return
            actions = read_actions(self._done_path, tail=500)
            if index < 0 or index >= len(actions):
                return
            src_raw = actions[index].get("src_path")
            if not isinstance(src_raw, str) or not src_raw:
                return
            src = Path(src_raw)
            if src.exists():
                self._open_in_explorer(src, select=True)
            elif src.parent.exists():
                self._open_in_explorer(src.parent, select=False)

    def open_destination(self) -> None:
        if self._tabs.currentIndex() == 0:
            index = self._selected_index()
            if index is None:
                self._QMessageBox.information(self._window, t("gui.open_destination", self._lang), t("gui.msg.select_row", self._lang))
                return
            actions = read_actions(self._queue_path)
            if index < 0 or index >= len(actions):
                return
            dst_raw = actions[index].get("dst_dir")
            if not isinstance(dst_raw, str) or not dst_raw:
                return
            dst = Path(dst_raw)
            if dst.exists():
                self._open_in_explorer(dst, select=False)
            elif dst.parent.exists():
                self._open_in_explorer(dst.parent, select=False)
            return

        if self._tabs.currentIndex() == 1:
            index = self._selected_history_index()
            if index is None:
                self._QMessageBox.information(self._window, t("gui.open_destination", self._lang), t("gui.msg.select_row", self._lang))
                return
            actions = read_actions(self._done_path, tail=500)
            if index < 0 or index >= len(actions):
                return
            moved_raw = actions[index].get("moved_to")
            if not isinstance(moved_raw, str) or not moved_raw:
                return
            moved = Path(moved_raw)
            if moved.exists():
                self._open_in_explorer(moved, select=True)
            elif moved.parent.exists():
                self._open_in_explorer(moved.parent, select=False)
