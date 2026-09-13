# Changelog

All notable changes to FilesGoThere are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-13

### Added
- **Optional update check.** FilesGoThere can tell you when a newer release is
  published on GitHub. It is **off by default** (`app.check_updates`): the first
  time you enable it, the app explains that this is its only outgoing connection
  and asks for confirmation. When enabled it runs once per startup, in a
  background thread, and fails silently when offline. No data is sent and the
  request is unauthenticated.
- **Open the releases page** button in the Settings tab, so you can check for new
  versions by hand without enabling the automatic check: the browser makes the
  connection, not FilesGoThere.
- **Update banner** shown in the main window when a newer version is found, with
  step-by-step instructions covering what the installer replaces and what it
  leaves untouched.

### Changed
- **The window now opens on the tab where the new file actually appeared**:
  History in `auto` mode, Pending in `manual` mode, scrolled to the top. If you
  are working in the Settings tab it is left alone.
- **Newest first.** Both the Pending and History tables are now sorted with the
  most recent entry at the top, so long lists no longer need scrolling. Rows keep
  carrying their real queue index, so Apply / Preview / Undo still act on the
  right file.
- **Single source of truth for the version number.** `src/filesgothere/__init__.py`
  is now the only place the version is written: `pyproject.toml` reads it
  dynamically and the Inno Setup installer receives it from
  `build/build_installer.ps1`, which also verifies that the expected Setup file
  was produced.

### Fixed
- **Zero-byte files left behind by Firefox downloads.** Browsers create an empty
  placeholder next to the growing `.part` file; the watcher considered that
  placeholder "stable" and moved it, so the finished download later landed beside
  it renamed to `name (1).ext`. The watcher now never treats a zero-byte file or
  one with a `.part`/`.crdownload` twin as ready, and tolerates the brief moment
  when the browser swaps one for the other.
- **The window did not come to the front when a download completed.** The trigger
  only watched the pending queue, which is always empty in `auto` mode, so the
  option never fired there. Detection is now based on new entries appearing in
  the history or the queue, which works in both modes.
- **A window minimized to the tray stayed hidden** when asked to come to the
  front: it was hidden rather than minimized, and was never shown again.
- **Windows focus restrictions.** Bringing the window to the front now works
  while another application is in the foreground, falling back to highlighting
  the taskbar button when Windows refuses the request.

## [1.0.0] - 2026-07-11

### Added
- **First stable public release.** FilesGoThere is now released as `1.0.0` with
  the full local-first desktop workflow ready for daily use.
- **Refined desktop UI.** The GUI now offers a clearer layout, grouped actions,
  better visual hierarchy, tray behavior, focus options, and improved readability
  for the main workflow.
- **Release-ready Windows packaging.** Bundled assets/config handling was aligned
  for GitHub distribution, including sanitized defaults and proper runtime paths.

### Changed
- The app and package version are now aligned to `1.0.0`.
- README and release-facing project files were updated to match the stable release.

### Fixed
- Improved taskbar/application icon handling on Windows by setting the application
  icon at app level and providing an explicit AppUserModelID.

## [0.2.0] - 2026-07-11

### Added
- **Auto mode now moves files for real.** In `auto` mode files are organized as
  soon as they settle, and every move is recorded in the History tab.
- **Undo.** Any applied move (auto or manual) can be reverted from the History
  tab, restoring the file to its original location. Actions are matched by a
  stable signature, so Undo is safe even with filters active.
- **System/junk file ignore-list** (`watch.ignore_globs`): the watcher now skips
  `desktop.ini`, `thumbs.db`, `.ds_store`, Office lock files (`~$*`), dot-files
  and (on Windows) hidden/system files. The list is configurable.
- **Settle safety cap** (`watch.settle_max_seconds`, `0` = no cap) with a warning
  log when reached.

### Changed
- **Robust settle for large/slow downloads.** The watcher now keeps waiting while
  the file is still growing instead of giving up after a fixed deadline, so big
  downloads are no longer dropped silently.
- Failed apply/undo operations now show a readable, localized message instead of
  a raw result dictionary.
- Configuration writing in the GUI was refactored into shared helpers
  (`_apply_app_section` / `_save_config`) to avoid duplicated logic.

### Fixed
- **Queue index misalignment with active filters.** Pending/History rows now
  carry their real queue index, so Apply / Preview / Undo / Open act on the
  correct action even when a text or extension filter is applied.
- **Selection and scroll position were lost every ~1.5s** on the auto-refresh.
  Tables are now rebuilt only when their data actually changes, and the current
  selection and scroll position are preserved.

## [0.1.0-beta.5] and earlier
- Initial backend + minimal PySide6 GUI: multi-folder watchdog monitoring,
  extension-based rule engine, manual queue with preview/apply, duplicate
  handling (`rename | skip | overwrite`), rotating logs, IT/EN i18n,
  light/dark theme.
