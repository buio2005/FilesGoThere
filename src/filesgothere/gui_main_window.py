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
from filesgothere.queue import AutoApplier, QueueWriter, undo_action
from filesgothere.rules import RuleEngine
from filesgothere.config import WatchConfig
from filesgothere.watcher import FilesGoThereWatcher, WatchContext


class MainWindow:
    def __init__(self, *, config_path: Path, config: RootConfig) -> None:
        from PySide6.QtCore import QTimer
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QIcon
        from PySide6.QtWidgets import (
            QGridLayout,
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
            QStyle,
            QSystemTrayIcon,
            QMenu,
            QSizePolicy,
            QHeaderView,
            QFrame,
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
        self._minimize_to_tray = config.app.minimize_to_tray
        self._watch_paths = [Path(p) for p in config.watch.paths]
        self._watch_recursive = config.watch.recursive
        self._watch_settle = config.watch.settle_seconds
        self._watch_settle_max = config.watch.settle_max_seconds
        self._watch_ignore_globs = list(config.watch.ignore_globs)
        self._last_pending_sizes: dict[str, int] = {}
        self._notified_complete: set[str] = set()
        self._first_run_hint_shown = False
        self._last_pending_sig: tuple | None = None
        self._last_done_sig: tuple | None = None
        self._tray = None
        self._tray_hint_shown = False
        self._force_quit = False
        self._QSystemTrayIcon = QSystemTrayIcon
        self._Qt = Qt
        self._QColor = QColor

        class _Shell(QMainWindow):
            def __init__(self, on_close):
                super().__init__()
                self._on_close = on_close

            def closeEvent(self, event):
                if self._on_close is not None:
                    self._on_close(event)
                else:
                    event.accept()

        self._app_icon_obj = self._load_app_icon(QIcon, QStyle)
        self._window = _Shell(self._handle_close)
        self._window.setWindowTitle(t("gui.title", self._lang))
        self._window.setWindowIcon(self._app_icon_obj)
        self._window.resize(1320, 840)
        self._window.setMinimumSize(1160, 760)
        self._apply_theme()

        central = QWidget()
        root = QHBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebarPanel")
        sidebar_widget.setMinimumWidth(360)
        sidebar_widget.setMaximumWidth(390)
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(10)

        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        overview_box = QGroupBox()
        self._overview_box = overview_box
        overview_layout = QVBoxLayout()
        overview_layout.setSpacing(8)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._status = QLabel()
        self._status.setObjectName("statusText")
        self._status.setWordWrap(True)
        self._status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        status_row.addWidget(self._status, 1)
        self._mode_badge = QLabel()
        status_row.addWidget(self._mode_badge, 0)
        overview_layout.addLayout(status_row)

        self._mode_hint = QLabel()
        self._mode_hint.setObjectName("modeHint")
        self._mode_hint.setWordWrap(True)
        overview_layout.addWidget(self._mode_hint)

        lang_row = QHBoxLayout()
        self._lang_label = QLabel()
        self._lang_combo = QComboBox()
        self._lang_combo.setMinimumWidth(120)
        self._lang_combo.addItem(t("gui.it", self._lang), "it")
        self._lang_combo.addItem(t("gui.en", self._lang), "en")
        lang_row.addWidget(self._lang_label)
        lang_row.addWidget(self._lang_combo, 1)
        overview_layout.addLayout(lang_row)
        overview_box.setLayout(overview_layout)
        sidebar_layout.addWidget(overview_box)

        watch_box = QGroupBox()
        self._watch_box = watch_box
        watch_layout = QVBoxLayout()
        watch_layout.setSpacing(8)

        self._watch_list = QListWidget()
        self._watch_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        watch_layout.addWidget(self._watch_list, 1)

        watch_buttons = QVBoxLayout()
        watch_buttons.setSpacing(6)
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
        watch_layout.addLayout(watch_buttons)

        watch_box.setLayout(watch_layout)
        sidebar_layout.addWidget(watch_box, 1)

        self._btn_start = QPushButton()
        self._btn_stop = QPushButton()
        self._btn_refresh = QPushButton()
        self._btn_preview = QPushButton()
        self._btn_open_src = QPushButton()
        self._btn_open_dst = QPushButton()
        self._btn_apply = QPushButton()
        self._btn_archive = QPushButton()
        self._btn_undo = QPushButton()

        self._btn_start.setObjectName("btnPrimary")
        self._btn_stop.setObjectName("btnDanger")
        self._btn_refresh.setObjectName("btnInfo")
        self._btn_preview.setObjectName("btnTeal")
        self._btn_open_src.setObjectName("btnSky")
        self._btn_open_dst.setObjectName("btnSky")
        self._btn_apply.setObjectName("btnAccent")
        self._btn_archive.setObjectName("btnSlate")
        self._btn_undo.setObjectName("btnViolet")
        self._btn_undo.setEnabled(False)

        actions_box = QGroupBox()
        self._actions_box = actions_box
        actions_layout = QGridLayout()
        actions_layout.setHorizontalSpacing(6)
        actions_layout.setVerticalSpacing(6)
        top_buttons = [self._btn_start, self._btn_stop, self._btn_refresh]
        bottom_buttons = [
            self._btn_preview,
            self._btn_apply,
            self._btn_open_src,
            self._btn_open_dst,
            self._btn_archive,
            self._btn_undo,
        ]
        for i, button in enumerate(top_buttons):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            actions_layout.addWidget(button, 0, i)
        self._actions_separator = QFrame()
        self._actions_separator.setObjectName("actionsSeparator")
        self._actions_separator.setFrameShape(QFrame.Shape.HLine)
        self._actions_separator.setFrameShadow(QFrame.Shadow.Plain)
        actions_layout.addWidget(self._actions_separator, 1, 0, 1, 3)
        middle_buttons = bottom_buttons[:3]
        lower_buttons = bottom_buttons[3:]
        for i, button in enumerate(middle_buttons):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            actions_layout.addWidget(button, 2, i)
        self._actions_separator_bottom = QFrame()
        self._actions_separator_bottom.setObjectName("actionsSeparator")
        self._actions_separator_bottom.setFrameShape(QFrame.Shape.HLine)
        self._actions_separator_bottom.setFrameShadow(QFrame.Shadow.Plain)
        actions_layout.addWidget(self._actions_separator_bottom, 3, 0, 1, 3)
        for i, button in enumerate(lower_buttons):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            actions_layout.addWidget(button, 4, i)
        actions_box.setLayout(actions_layout)
        main_layout.addWidget(actions_box)

        filter_box = QGroupBox()
        self._filter_box = filter_box
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(6)
        self._filter_text_label = QLabel()
        self._filter_text = QLineEdit()
        self._filter_ext_label = QLabel()
        self._filter_ext = QLineEdit()
        self._btn_search = QPushButton()
        self._btn_clear = QPushButton()

        self._filter_text.setMinimumWidth(180)
        self._filter_ext.setFixedWidth(120)

        filter_text_row = QVBoxLayout()
        filter_text_row.addWidget(self._filter_text_label)
        filter_text_row.addWidget(self._filter_text)
        filter_ext_row = QVBoxLayout()
        filter_ext_row.addWidget(self._filter_ext_label)
        filter_ext_row.addWidget(self._filter_ext)
        filter_buttons_row = QHBoxLayout()
        filter_buttons_row.setSpacing(6)
        filter_buttons_row.addWidget(self._btn_search)
        filter_buttons_row.addWidget(self._btn_clear)
        filter_layout.addLayout(filter_text_row)
        filter_layout.addLayout(filter_ext_row)
        filter_layout.addLayout(filter_buttons_row)
        filter_box.setLayout(filter_layout)
        sidebar_layout.addWidget(filter_box)

        self._tabs = QTabWidget()

        self._pending_table = QTableWidget(0, 6)
        self._pending_table.setSelectionBehavior(self._pending_table.SelectionBehavior.SelectRows)
        self._pending_table.setSelectionMode(self._pending_table.SelectionMode.SingleSelection)
        self._pending_table.setEditTriggers(self._pending_table.EditTrigger.NoEditTriggers)
        self._pending_table.setAlternatingRowColors(True)
        self._pending_table.setHorizontalScrollMode(self._pending_table.ScrollMode.ScrollPerPixel)

        self._history_table = QTableWidget(0, 6)
        self._history_table.setSelectionBehavior(self._history_table.SelectionBehavior.SelectRows)
        self._history_table.setSelectionMode(self._history_table.SelectionMode.SingleSelection)
        self._history_table.setEditTriggers(self._history_table.EditTrigger.NoEditTriggers)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.setHorizontalScrollMode(self._history_table.ScrollMode.ScrollPerPixel)

        pending_header = self._pending_table.horizontalHeader()
        pending_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        pending_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        pending_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        pending_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        pending_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        pending_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        history_header = self._history_table.horizontalHeader()
        history_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        history_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        history_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self._tabs.addTab(self._pending_table, "")
        self._tabs.addTab(self._history_table, "")

        settings_page = QWidget()
        settings_root = QVBoxLayout()

        settings_info_box = QGroupBox()
        self._settings_info_box = settings_info_box
        settings_info_layout = QVBoxLayout()
        self._settings_summary = QLabel()
        self._settings_summary.setWordWrap(True)
        self._settings_warning = QLabel()
        self._settings_warning.setWordWrap(True)
        settings_info_layout.addWidget(self._settings_summary)
        settings_info_layout.addWidget(self._settings_warning)
        settings_info_box.setLayout(settings_info_layout)
        settings_root.addWidget(settings_info_box)

        settings_box = QGroupBox()
        self._settings_box = settings_box
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
        self._chk_tray = QCheckBox()
        settings_layout.addWidget(self._chk_focus_startup)
        settings_layout.addWidget(self._chk_focus_download)
        settings_layout.addWidget(self._chk_tray)
        settings_layout.addStretch(1)

        settings_box.setLayout(settings_layout)
        settings_root.addWidget(settings_box)
        settings_page.setLayout(settings_root)
        self._tabs.addTab(settings_page, "")
        main_layout.addWidget(self._tabs, 1)

        sidebar_layout.addStretch(1)
        sidebar_widget.setLayout(sidebar_layout)
        main_widget.setLayout(main_layout)

        root.addWidget(sidebar_widget, 0)
        root.addWidget(main_widget, 1)
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
        self._chk_tray.stateChanged.connect(self.on_tray_changed)
        self._mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self._btn_start.clicked.connect(self.start_watcher)
        self._btn_stop.clicked.connect(self.stop_watcher)
        self._btn_refresh.clicked.connect(self.refresh)
        self._btn_preview.clicked.connect(self.preview_selected)
        self._btn_open_src.clicked.connect(self.open_source)
        self._btn_open_dst.clicked.connect(self.open_destination)
        self._btn_apply.clicked.connect(self.apply_selected)
        self._btn_archive.clicked.connect(self.archive_all)
        self._btn_undo.clicked.connect(self.undo_selected)
        self._tabs.currentChanged.connect(self.on_tab_changed)
        self._btn_search.clicked.connect(self.refresh)
        self._btn_clear.clicked.connect(self.clear_filters)
        self._filter_text.returnPressed.connect(self.refresh)
        self._filter_ext.returnPressed.connect(self.refresh)

        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                self._tray = QSystemTrayIcon(self._app_icon_obj, self._window)
                tray_menu = QMenu()
                self._act_tray_open = tray_menu.addAction(t("gui.tray.open", self._lang))
                self._act_tray_toggle = tray_menu.addAction(t("gui.start", self._lang))
                tray_menu.addSeparator()
                self._act_tray_quit = tray_menu.addAction(t("gui.tray.quit", self._lang))
                self._tray_menu = tray_menu
                self._tray.setContextMenu(tray_menu)
                self._tray.setToolTip(t("gui.tray.tooltip", self._lang, pending="0"))
                self._act_tray_open.triggered.connect(self._show_window)
                self._act_tray_toggle.triggered.connect(self._toggle_watcher)
                self._act_tray_quit.triggered.connect(self._quit_app)
                self._tray.activated.connect(self._on_tray_activated)
                self._tray.show()
        except Exception:
            self._tray = None

        self._timer = QTimer()
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        self._sync_language_combo()
        self._sync_theme_combo()
        self._sync_focus_checkboxes()
        self._sync_tray_checkbox()
        self._sync_mode_combo()
        self._apply_language()
        self._refresh_watch_list()
        self.refresh()

    def show(self) -> None:
        self._window.show()
        if self._focus_on_startup:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(250, self._bring_to_front)
        self._maybe_show_first_run_hint()

    def shutdown(self) -> None:
        try:
            self._save_app_settings_silent()
        except Exception:
            pass
        self.stop_watcher()

    def _load_app_icon(self, QIcon, QStyle):
        import sys

        candidates: list[Path] = []
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
            candidates.append(base / "assets" / "filesgothere.ico")
            candidates.append(base / "filesgothere.ico")
        here = Path(__file__).resolve()
        candidates.append(here.parents[2] / "assets" / "filesgothere.ico")
        candidates.append(here.parent / "assets" / "filesgothere.ico")

        for c in candidates:
            try:
                if c.exists():
                    icon = QIcon(str(c))
                    if not icon.isNull():
                        return icon
            except Exception:
                pass

        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None:
                return app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        except Exception:
            pass
        return QIcon()

    def _handle_close(self, event) -> None:
        if self._force_quit or not self._minimize_to_tray or self._tray is None or not self._tray.isVisible():
            event.accept()
            return
        event.ignore()
        self._window.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            try:
                self._tray.showMessage("FilesGoThere", t("gui.tray.minimized_hint", self._lang))
            except Exception:
                pass

    def _show_window(self) -> None:
        self._window.showNormal()
        self._window.raise_()
        self._window.activateWindow()

    def _on_tray_activated(self, reason) -> None:
        try:
            trigger = self._QSystemTrayIcon.ActivationReason.Trigger
            dbl = self._QSystemTrayIcon.ActivationReason.DoubleClick
            if reason in (trigger, dbl):
                self._show_window()
        except Exception:
            self._show_window()

    def _toggle_watcher(self) -> None:
        if self._watcher is not None:
            self.stop_watcher()
        else:
            self.start_watcher()

    def _quit_app(self) -> None:
        self._force_quit = True
        try:
            if self._tray is not None:
                self._tray.hide()
        except Exception:
            pass
        self._window.close()
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None:
                app.quit()
        except Exception:
            pass

    def _update_tray(self, pending_count: int) -> None:
        if self._tray is None:
            return
        try:
            self._tray.setToolTip(t("gui.tray.tooltip", self._lang, pending=str(pending_count)))
            running = self._watcher is not None
            self._act_tray_toggle.setText(
                t("gui.stop", self._lang) if running else t("gui.start", self._lang)
            )
            self._act_tray_open.setText(t("gui.tray.open", self._lang))
            self._act_tray_quit.setText(t("gui.tray.quit", self._lang))
        except Exception:
            pass

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
        self._btn_undo.setText(t("gui.undo", self._lang))

        self._filter_text_label.setText(t("gui.filter.text", self._lang))
        self._filter_text.setPlaceholderText(t("gui.filter.text.placeholder", self._lang))
        self._filter_ext_label.setText(t("gui.filter.ext", self._lang))
        self._filter_ext.setPlaceholderText(t("gui.filter.ext.placeholder", self._lang))
        self._btn_search.setText(t("gui.search", self._lang))
        self._btn_clear.setText(t("gui.clear", self._lang))

        self._tabs.setTabText(0, t("gui.tab.pending", self._lang))
        self._tabs.setTabText(1, t("gui.tab.history", self._lang))
        self._tabs.setTabText(2, t("gui.tab.settings", self._lang))
        tab_bar = self._tabs.tabBar()
        if self._theme == "dark":
            tab_bar.setTabTextColor(0, self._QColor("#cbd5e1"))
            tab_bar.setTabTextColor(1, self._QColor("#cbd5e1"))
            tab_bar.setTabTextColor(2, self._QColor("#bfdbfe"))
        else:
            tab_bar.setTabTextColor(0, self._QColor("#334155"))
            tab_bar.setTabTextColor(1, self._QColor("#334155"))
            tab_bar.setTabTextColor(2, self._QColor("#1d4ed8"))

        self._overview_box.setTitle(t("gui.overview", self._lang))
        self._watch_box.setTitle(t("gui.watch_folders", self._lang))
        self._filter_box.setTitle(t("gui.filters", self._lang))
        self._actions_box.setTitle(t("gui.actions", self._lang))
        self._settings_info_box.setTitle(t("gui.settings.how_it_works", self._lang))
        self._settings_box.setTitle(t("gui.settings.behavior", self._lang))
        self._mode_label.setText(t("gui.mode", self._lang))
        self._theme_label.setText(t("gui.theme", self._lang))
        self._chk_focus_startup.setText(t("gui.focus_on_startup", self._lang))
        self._chk_focus_download.setText(t("gui.focus_on_download_complete", self._lang))
        self._chk_tray.setText(t("gui.minimize_to_tray", self._lang))

        self._btn_preview.setToolTip(t("gui.tip.preview", self._lang))
        self._btn_apply.setToolTip(t("gui.tip.apply", self._lang))
        self._btn_archive.setToolTip(t("gui.tip.archive", self._lang))
        self._btn_undo.setToolTip(t("gui.tip.undo", self._lang))
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

        self._update_language_combo_labels()
        self._update_mode_combo_labels()
        self._update_theme_combo_labels()
        self._update_mode_ui()
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
        self._btn_undo.setEnabled(tab == 1)
        self.refresh()

    def _sync_language_combo(self) -> None:
        self._lang_combo.blockSignals(True)
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == self._lang:
                self._lang_combo.setCurrentIndex(i)
                break
        self._lang_combo.blockSignals(False)

    def on_language_changed(self) -> None:
        lang = self._lang_combo.currentData()
        if lang in ("it", "en"):
            self._lang = lang
            self._apply_language()
            self._save_app_settings()

    def _sync_mode_combo(self) -> None:
        self._mode_combo.blockSignals(True)
        for i in range(self._mode_combo.count()):
            if self._mode_combo.itemData(i) == self._mode:
                self._mode_combo.setCurrentIndex(i)
                break
        self._mode_combo.blockSignals(False)

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
            if mode == "auto" and self._mode != "auto":
                answer = self._QMessageBox.question(
                    self._window,
                    t("gui.confirm.auto_mode.title", self._lang),
                    t("gui.confirm.auto_mode.text", self._lang),
                )
                if answer != self._QMessageBox.StandardButton.Yes:
                    self._sync_mode_combo()
                    return
            self._mode = mode
            self._update_mode_ui()
            self._save_app_settings()

    def _sync_theme_combo(self) -> None:
        self._theme_combo.blockSignals(True)
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == self._theme:
                self._theme_combo.setCurrentIndex(i)
                break
        self._theme_combo.blockSignals(False)

    def _sync_focus_checkboxes(self) -> None:
        self._chk_focus_startup.blockSignals(True)
        self._chk_focus_download.blockSignals(True)
        try:
            self._chk_focus_startup.setChecked(bool(self._focus_on_startup))
            self._chk_focus_download.setChecked(bool(self._focus_on_download_complete))
        finally:
            self._chk_focus_startup.blockSignals(False)
            self._chk_focus_download.blockSignals(False)

    def _sync_tray_checkbox(self) -> None:
        self._chk_tray.blockSignals(True)
        try:
            self._chk_tray.setChecked(bool(self._minimize_to_tray))
        finally:
            self._chk_tray.blockSignals(False)

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
            self._update_mode_ui()
            self._save_app_settings()

    def on_focus_changed(self) -> None:
        self._focus_on_startup = bool(self._chk_focus_startup.isChecked())
        self._focus_on_download_complete = bool(self._chk_focus_download.isChecked())
        self._save_app_settings()

    def on_tray_changed(self) -> None:
        self._minimize_to_tray = bool(self._chk_tray.isChecked())
        self._save_app_settings()

    def _apply_app_section(self, raw: dict) -> None:
        app = raw.get("app")
        if not isinstance(app, dict):
            app = {}
            raw["app"] = app
        app["language"] = self._lang
        app["mode"] = self._mode
        app["theme"] = self._theme
        app["focus_on_startup"] = bool(self._focus_on_startup)
        app["focus_on_download_complete"] = bool(self._focus_on_download_complete)
        app["minimize_to_tray"] = bool(self._minimize_to_tray)

    def _save_config(self, *, silent: bool = False) -> bool:
        try:
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}

        self._apply_app_section(raw)

        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as e:
            if not silent:
                self._QMessageBox.warning(self._window, t("gui.tab.settings", self._lang), f"{t('gui.msg.write_error', self._lang)}: {e}")
            return False

    def _save_app_settings(self) -> None:
        self._save_config(silent=False)

    def _save_app_settings_silent(self) -> None:
        self._save_config(silent=True)

    def _apply_theme(self) -> None:
        if self._theme == "dark":
            self._window.setStyleSheet(self._stylesheet_dark())
        else:
            self._window.setStyleSheet(self._stylesheet_light())
        self._update_mode_ui()

    def _update_mode_ui(self) -> None:
        if not hasattr(self, "_mode_badge") or not hasattr(self, "_settings_summary"):
            return

        is_auto = self._mode == "auto"
        badge_key = "gui.mode.badge.auto" if is_auto else "gui.mode.badge.manual"
        hint_key = "gui.mode.hint.auto" if is_auto else "gui.mode.hint.manual"
        details_key = "gui.mode.details.auto" if is_auto else "gui.mode.details.manual"
        warning_key = "gui.mode.warning.auto" if is_auto else "gui.mode.warning.manual"

        self._mode_badge.setText(t(badge_key, self._lang))
        self._mode_hint.setText(t(hint_key, self._lang))
        self._settings_summary.setText(t(details_key, self._lang))
        self._settings_warning.setText(t(warning_key, self._lang))
        self._settings_warning.setVisible(bool(self._settings_warning.text().strip()))

        if is_auto:
            if self._theme == "dark":
                badge_style = (
                    "QLabel{background:#7c2d12;color:#ffedd5;border:1px solid #9a3412;"
                    "border-radius:12px;padding:6px 10px;font-weight:700;}"
                )
                hint_style = (
                    "QLabel{background:#1f2937;color:#fde68a;border:1px solid #92400e;"
                    "border-radius:12px;padding:10px 12px;}"
                )
                warning_style = "QLabel{color:#fdba74;font-weight:600;}"
            else:
                badge_style = (
                    "QLabel{background:#fff7ed;color:#9a3412;border:1px solid #fdba74;"
                    "border-radius:12px;padding:6px 10px;font-weight:700;}"
                )
                hint_style = (
                    "QLabel{background:#fffbeb;color:#92400e;border:1px solid #fcd34d;"
                    "border-radius:12px;padding:10px 12px;}"
                )
                warning_style = "QLabel{color:#c2410c;font-weight:600;}"
        else:
            if self._theme == "dark":
                badge_style = (
                    "QLabel{background:#0f3d2e;color:#dcfce7;border:1px solid #15803d;"
                    "border-radius:12px;padding:6px 10px;font-weight:700;}"
                )
                hint_style = (
                    "QLabel{background:#0f172a;color:#bfdbfe;border:1px solid #1d4ed8;"
                    "border-radius:12px;padding:10px 12px;}"
                )
                warning_style = "QLabel{color:#93c5fd;font-weight:600;}"
            else:
                badge_style = (
                    "QLabel{background:#f0fdf4;color:#166534;border:1px solid #86efac;"
                    "border-radius:12px;padding:6px 10px;font-weight:700;}"
                )
                hint_style = (
                    "QLabel{background:#eff6ff;color:#1d4ed8;border:1px solid #93c5fd;"
                    "border-radius:12px;padding:10px 12px;}"
                )
                warning_style = "QLabel{color:#1d4ed8;font-weight:600;}"

        self._mode_badge.setStyleSheet(badge_style)
        self._mode_hint.setStyleSheet(hint_style)
        self._settings_warning.setStyleSheet(warning_style)

    def _stylesheet_light(self) -> str:
        return (
            "QWidget{font-family:Segoe UI;font-size:12px;color:#111827;background:#ffffff;}"
            "QWidget#sidebarPanel{background:#f8fafc;border:1px solid #e5e7eb;border-radius:14px;}"
            "QGroupBox{font-weight:600;margin-top:8px;border:1px solid #e5e7eb;border-radius:10px;padding:10px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;}"
            "QPushButton{padding:5px 10px;min-height:30px;border:1px solid #d1d5db;border-radius:10px;background:#ffffff;}"
            "QPushButton:hover{background:#f3f4f6;}"
            "QPushButton:pressed{background:#e5e7eb;}"
            "QPushButton:disabled{color:#9ca3af;background:#f9fafb;}"
            "QPushButton#btnPrimary{background:#16a34a;color:#ffffff;border-color:#15803d;}"
            "QPushButton#btnPrimary:hover{background:#15803d;}"
            "QPushButton#btnPrimary:pressed{background:#166534;}"
            "QPushButton#btnDanger{background:#dc2626;color:#ffffff;border-color:#b91c1c;}"
            "QPushButton#btnDanger:hover{background:#b91c1c;}"
            "QPushButton#btnDanger:pressed{background:#991b1b;}"
            "QPushButton#btnInfo{background:#f59e0b;color:#ffffff;border-color:#d97706;}"
            "QPushButton#btnInfo:hover{background:#d97706;}"
            "QPushButton#btnInfo:pressed{background:#b45309;}"
            "QPushButton#btnTeal{background:#0f766e;color:#ffffff;border-color:#115e59;}"
            "QPushButton#btnTeal:hover{background:#115e59;}"
            "QPushButton#btnTeal:pressed{background:#134e4a;}"
            "QPushButton#btnSky{background:#0284c7;color:#ffffff;border-color:#0369a1;}"
            "QPushButton#btnSky:hover{background:#0369a1;}"
            "QPushButton#btnSky:pressed{background:#075985;}"
            "QPushButton#btnAccent{background:#2563eb;color:#ffffff;border-color:#1d4ed8;}"
            "QPushButton#btnAccent:hover{background:#1d4ed8;}"
            "QPushButton#btnAccent:pressed{background:#1e40af;}"
            "QPushButton#btnSlate{background:#64748b;color:#ffffff;border-color:#475569;}"
            "QPushButton#btnSlate:hover{background:#475569;}"
            "QPushButton#btnSlate:pressed{background:#334155;}"
            "QPushButton#btnViolet{background:#7c3aed;color:#ffffff;border-color:#6d28d9;}"
            "QPushButton#btnViolet:hover{background:#6d28d9;}"
            "QPushButton#btnViolet:pressed{background:#5b21b6;}"
            "QLineEdit{padding:7px 10px;border:1px solid #d1d5db;border-radius:10px;background:#ffffff;}"
            "QComboBox{padding:6px 10px;border:1px solid #d1d5db;border-radius:10px;background:#ffffff;}"
            "QCheckBox{padding:6px;}"
            "QListWidget{border:1px solid #e5e7eb;border-radius:10px;background:#ffffff;padding:4px;}"
            "QTabWidget::pane{border:1px solid #e5e7eb;border-radius:10px;top:-1px;}"
            "QTabBar::tab{padding:8px 12px;border:1px solid #e5e7eb;border-top-left-radius:10px;border-top-right-radius:10px;background:#f9fafb;margin-right:4px;}"
            "QTabBar::tab:selected{background:#ffffff;}"
            "QTabBar::tab:last{background:#dbeafe;border-color:#93c5fd;color:#1d4ed8;font-weight:700;}"
            "QTabBar::tab:last:selected{background:#bfdbfe;border-color:#60a5fa;color:#1e3a8a;}"
            "QHeaderView::section{background:#f3f4f6;padding:6px;border:0;border-bottom:1px solid #e5e7eb;}"
            "QTableWidget{gridline-color:#e5e7eb;border:1px solid #e5e7eb;border-radius:10px;}"
            "QTableWidget::item:alternate{background:#f9fafb;}"
            "QTableWidget::item:selected{background:#dbeafe;color:#111827;}"
            "QLabel#statusText{color:#475569;}"
            "QFrame#actionsSeparator{background:#cbd5e1;min-height:1px;max-height:1px;border:none;}"
        )

    def _stylesheet_dark(self) -> str:
        return (
            "QWidget{font-family:Segoe UI;font-size:12px;color:#e5e7eb;background:#0b1220;}"
            "QWidget#sidebarPanel{background:#0f172a;border:1px solid #243146;border-radius:14px;}"
            "QGroupBox{font-weight:600;margin-top:8px;border:1px solid #243146;border-radius:10px;padding:10px;background:#0f172a;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;}"
            "QPushButton{padding:5px 10px;min-height:30px;border:1px solid #334155;border-radius:10px;background:#111827;color:#e5e7eb;}"
            "QPushButton:hover{background:#0b1220;}"
            "QPushButton:pressed{background:#020617;}"
            "QPushButton:disabled{color:#64748b;background:#0f172a;}"
            "QPushButton#btnPrimary{background:#16a34a;color:#ffffff;border-color:#15803d;}"
            "QPushButton#btnPrimary:hover{background:#15803d;}"
            "QPushButton#btnPrimary:pressed{background:#166534;}"
            "QPushButton#btnDanger{background:#dc2626;color:#ffffff;border-color:#b91c1c;}"
            "QPushButton#btnDanger:hover{background:#b91c1c;}"
            "QPushButton#btnDanger:pressed{background:#991b1b;}"
            "QPushButton#btnInfo{background:#f59e0b;color:#ffffff;border-color:#d97706;}"
            "QPushButton#btnInfo:hover{background:#d97706;}"
            "QPushButton#btnInfo:pressed{background:#b45309;}"
            "QPushButton#btnTeal{background:#0f766e;color:#ffffff;border-color:#115e59;}"
            "QPushButton#btnTeal:hover{background:#115e59;}"
            "QPushButton#btnTeal:pressed{background:#134e4a;}"
            "QPushButton#btnSky{background:#0284c7;color:#ffffff;border-color:#0369a1;}"
            "QPushButton#btnSky:hover{background:#0369a1;}"
            "QPushButton#btnSky:pressed{background:#075985;}"
            "QPushButton#btnAccent{background:#2563eb;color:#ffffff;border-color:#1d4ed8;}"
            "QPushButton#btnAccent:hover{background:#1d4ed8;}"
            "QPushButton#btnAccent:pressed{background:#1e40af;}"
            "QPushButton#btnSlate{background:#64748b;color:#ffffff;border-color:#475569;}"
            "QPushButton#btnSlate:hover{background:#475569;}"
            "QPushButton#btnSlate:pressed{background:#334155;}"
            "QPushButton#btnViolet{background:#7c3aed;color:#ffffff;border-color:#6d28d9;}"
            "QPushButton#btnViolet:hover{background:#6d28d9;}"
            "QPushButton#btnViolet:pressed{background:#5b21b6;}"
            "QLineEdit{padding:7px 10px;border:1px solid #334155;border-radius:10px;background:#111827;color:#e5e7eb;}"
            "QComboBox{padding:6px 10px;border:1px solid #334155;border-radius:10px;background:#111827;color:#e5e7eb;}"
            "QCheckBox{padding:6px;}"
            "QListWidget{border:1px solid #243146;border-radius:10px;background:#111827;padding:4px;}"
            "QTabWidget::pane{border:1px solid #243146;border-radius:10px;top:-1px;}"
            "QTabBar::tab{padding:8px 12px;border:1px solid #243146;border-top-left-radius:10px;border-top-right-radius:10px;background:#0f172a;margin-right:4px;}"
            "QTabBar::tab:selected{background:#111827;}"
            "QTabBar::tab:last{background:#172554;border-color:#1d4ed8;color:#bfdbfe;font-weight:700;}"
            "QTabBar::tab:last:selected{background:#1e3a8a;border-color:#60a5fa;color:#eff6ff;}"
            "QHeaderView::section{background:#0f172a;padding:6px;border:0;border-bottom:1px solid #243146;}"
            "QTableWidget{gridline-color:#243146;border:1px solid #243146;border-radius:10px;background:#111827;color:#e5e7eb;}"
            "QTableWidget::item:alternate{background:#0f172a;}"
            "QTableWidget::item:selected{background:#1d4ed8;color:#ffffff;}"
            "QLabel#statusText{color:#94a3b8;}"
            "QFrame#actionsSeparator{background:#334155;min-height:1px;max-height:1px;border:none;}"
        )

    def _bring_to_front(self) -> None:
        if self._window.isActiveWindow():
            return
        if self._window.isMinimized():
            self._window.showNormal()
        self._window.raise_()
        self._window.activateWindow()
        self._window.setWindowState((self._window.windowState() & ~self._Qt.WindowMinimized) | self._Qt.WindowActive)

        if os.name == "nt":
            try:
                import ctypes

                hwnd = int(self._window.winId())
                ctypes.windll.user32.ShowWindow(hwnd, 9)
                ctypes.windll.user32.BringWindowToTop(hwnd)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

    def start_watcher(self) -> None:
        if self._watcher is not None:
            return
        if not self._watch_paths:
            self._QMessageBox.information(self._window, t("gui.title", self._lang), t("gui.msg.watch_empty", self._lang))
            return

        queue_writer = None
        auto_applier = None
        if self._mode == "manual" and self._config.queue.enabled:
            queue_writer = QueueWriter(self._queue_path)
        elif self._mode == "auto":
            auto_applier = AutoApplier(self._done_path, self._config.library)

        rule_engine = RuleEngine(self._config.rules, self._config.library)
        watch_cfg = WatchConfig(
            paths=list(self._watch_paths),
            recursive=self._watch_recursive,
            settle_seconds=self._watch_settle,
            settle_max_seconds=self._watch_settle_max,
            ignore_globs=list(self._watch_ignore_globs),
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
            auto_applier=auto_applier,
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
        self._minimize_to_tray = config.app.minimize_to_tray
        self._watch_paths = [Path(p) for p in config.watch.paths]
        self._watch_recursive = config.watch.recursive
        self._watch_settle = config.watch.settle_seconds
        self._watch_settle_max = config.watch.settle_max_seconds
        self._watch_ignore_globs = list(config.watch.ignore_globs)
        self._sync_language_combo()
        self._sync_theme_combo()
        self._sync_focus_checkboxes()
        self._sync_tray_checkbox()
        self._sync_mode_combo()
        self._apply_language()
        self._refresh_watch_list()
        self.refresh()

    def refresh(self) -> None:
        contains = self._filter_text.text().strip() or None
        ext = self._filter_ext.text().strip() or None

        all_pending = read_actions(self._queue_path)
        all_done = read_actions(self._done_path, tail=500)

        pending = self._filter_indexed(all_pending, ext, contains)
        done = self._filter_indexed(all_done, ext, contains)

        self._maybe_raise_on_download_complete([a for _, a in pending])

        watcher_state = "gui.state.running" if self._watcher is not None else "gui.state.stopped"
        self._status.setText(
            t(
                "gui.queue.status",
                self._lang,
                state=t(watcher_state, self._lang),
                mode=t("gui.mode.badge.auto", self._lang) if self._mode == "auto" else t("gui.mode.badge.manual", self._lang),
                folders=str(len(self._watch_paths)),
                pending=str(len(pending)),
                done=str(len(done)),
            )
        )
        self._update_tray(len(pending))

        pending_sig = (
            self._theme,
            self._lang,
            tuple(
                (
                    idx,
                    str(a.get("created_at", "")),
                    str(a.get("extension", "")),
                    int(a["size_bytes"]) if isinstance(a.get("size_bytes"), int) else -1,
                    str(a.get("src_path", "")),
                    str(a.get("dst_dir", "")),
                )
                for idx, a in pending
            ),
        )
        if pending_sig != self._last_pending_sig:
            self._rebuild_pending_table(pending)
            self._last_pending_sig = pending_sig

        done_sig = (
            self._theme,
            self._lang,
            tuple(
                (
                    idx,
                    str(a.get("created_at", "")),
                    str(a.get("applied_at", "")),
                    str(a.get("status", "")),
                    str(a.get("src_path", "")),
                    str(a.get("moved_to", "")),
                )
                for idx, a in done
            ),
        )
        if done_sig != self._last_done_sig:
            self._rebuild_history_table(done)
            self._last_done_sig = done_sig

        self._update_settings_enabled()

    def _filter_indexed(
        self, actions: list[dict[str, object]], ext: str | None, contains: str | None
    ) -> list[tuple[int, dict[str, object]]]:
        ext_norm = ext.lower() if ext else None
        if ext_norm and not ext_norm.startswith("."):
            ext_norm = f".{ext_norm}"
        contains_norm = contains.lower() if contains else None

        out: list[tuple[int, dict[str, object]]] = []
        for i, a in enumerate(actions):
            if ext_norm:
                v = a.get("extension")
                if not isinstance(v, str) or v.lower() != ext_norm:
                    continue
            if contains_norm:
                text = f"{a.get('src_path')} {a.get('dst_dir')} {a.get('moved_to')}".lower()
                if contains_norm not in text:
                    continue
            out.append((i, a))
        return out

    def _rebuild_pending_table(self, pending: list[tuple[int, dict[str, object]]]) -> None:
        table = self._pending_table
        prev = self._pending_selected_orig()
        scroll = table.verticalScrollBar().value()
        table.setRowCount(len(pending))
        select_row: int | None = None
        for row, (orig, a) in enumerate(pending):
            size_raw = a.get("size_bytes")
            size = int(size_raw) if isinstance(size_raw, int) else -1
            created = str(a.get("created_at") or "")
            idx_item = self._QTableWidgetItem(str(orig))
            idx_item.setData(self._Qt.ItemDataRole.UserRole, orig)
            table.setItem(row, 0, idx_item)
            table.setItem(row, 1, self._QTableWidgetItem(self._fmt_dt(created)))
            table.setItem(row, 2, self._QTableWidgetItem(str(a.get("extension", ""))))
            table.setItem(row, 3, self._QTableWidgetItem(self._fmt_size(size)))
            table.setItem(row, 4, self._QTableWidgetItem(str(a.get("src_path") or "")))
            table.setItem(row, 5, self._QTableWidgetItem(str(a.get("dst_dir") or "")))
            self._apply_pending_row_style(row, size)
            if prev is not None and orig == prev:
                select_row = row
        if select_row is not None:
            table.selectRow(select_row)
        table.verticalScrollBar().setValue(scroll)

    def _rebuild_history_table(self, done: list[tuple[int, dict[str, object]]]) -> None:
        table = self._history_table
        prev = self._history_selected_orig()
        scroll = table.verticalScrollBar().value()
        table.setRowCount(len(done))
        select_row: int | None = None
        for row, (orig, a) in enumerate(done):
            created = str(a.get("created_at") or "")
            applied = str(a.get("applied_at") or "")
            status = str(a.get("status") or "")
            idx_item = self._QTableWidgetItem(str(orig))
            idx_item.setData(self._Qt.ItemDataRole.UserRole, orig)
            table.setItem(row, 0, idx_item)
            table.setItem(row, 1, self._QTableWidgetItem(self._fmt_dt(created)))
            table.setItem(row, 2, self._QTableWidgetItem(self._fmt_dt(applied)))
            table.setItem(row, 3, self._QTableWidgetItem(self._tr_status(status)))
            table.setItem(row, 4, self._QTableWidgetItem(str(a.get("src_path", ""))))
            table.setItem(row, 5, self._QTableWidgetItem(str(a.get("moved_to", ""))))
            self._apply_history_row_style(row, status)
            if prev is not None and orig == prev:
                select_row = row
        if select_row is not None:
            table.selectRow(select_row)
        table.verticalScrollBar().setValue(scroll)

    def _pending_selected_orig(self) -> int | None:
        rows = self._pending_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self._pending_table.item(rows[0].row(), 0)
        if item is None:
            return None
        data = item.data(self._Qt.ItemDataRole.UserRole)
        return int(data) if isinstance(data, int) else None

    def _history_selected_orig(self) -> int | None:
        rows = self._history_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self._history_table.item(rows[0].row(), 0)
        if item is None:
            return None
        data = item.data(self._Qt.ItemDataRole.UserRole)
        return int(data) if isinstance(data, int) else None

    def _selected_index(self) -> int | None:
        if self._tabs.currentIndex() != 0:
            return None
        return self._pending_selected_orig()

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

        index = self._selected_history_index()
        if index is None:
            self._QMessageBox.information(
                self._window, t("gui.preview", self._lang), t("gui.msg.select_row", self._lang)
            )
            return
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
            self._QMessageBox.warning(self._window, t("gui.apply", self._lang), self._explain_result(result))

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

    def undo_selected(self) -> None:
        if self._watcher is not None:
            self._QMessageBox.information(self._window, t("gui.undo", self._lang), t("gui.msg.stop_before_undo", self._lang))
            return

        index = self._selected_history_index()
        if index is None:
            self._QMessageBox.information(self._window, t("gui.undo", self._lang), t("gui.msg.select_row", self._lang))
            return

        actions = read_actions(self._done_path, tail=500)
        if index < 0 or index >= len(actions):
            return
        a = actions[index]
        if a.get("status") != "applied":
            self._QMessageBox.information(self._window, t("gui.undo", self._lang), t("gui.msg.undo_not_applicable", self._lang))
            return

        text = t(
            "gui.confirm.undo.text",
            self._lang,
            moved=str(a.get("moved_to")),
            src=str(a.get("src_path")),
        )
        answer = self._QMessageBox.question(self._window, t("gui.confirm.undo.title", self._lang), text)
        if answer != self._QMessageBox.StandardButton.Yes:
            return

        result = undo_action(
            self._done_path,
            created_at=a.get("created_at"),
            src_path=a.get("src_path"),
            applied_at=a.get("applied_at"),
            moved_to=a.get("moved_to"),
        )
        if result.get("undone") is True:
            self._QMessageBox.information(self._window, t("gui.undo", self._lang), t("gui.info.undone", self._lang))
        else:
            self._QMessageBox.warning(self._window, t("gui.undo", self._lang), self._explain_result(result))

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
        self._apply_app_section(raw)

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

    _KNOWN_REASONS = (
        "queue_empty",
        "index_out_of_range",
        "invalid_action",
        "source_missing",
        "stat_failed",
        "size_changed",
        "move_failed",
        "moved_missing",
        "source_exists",
        "no_moved_to",
        "not_found",
    )

    def _explain_result(self, result: dict) -> str:
        reason = result.get("reason")
        if not isinstance(reason, str) or reason not in self._KNOWN_REASONS:
            return t("queue.reason.unknown", self._lang)
        error = result.get("error")
        return t(f"queue.reason.{reason}", self._lang, error=str(error) if error is not None else "")

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
        return self._history_selected_orig()

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
