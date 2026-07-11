# Changelog

All notable changes to FilesGoThere are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
