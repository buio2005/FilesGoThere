from __future__ import annotations

from pathlib import Path

from filesgothere.config import LibraryConfig, RulesConfig


class RuleEngine:
    def __init__(self, rules: RulesConfig, library: LibraryConfig) -> None:
        self._rules = rules
        self._library = library

    def destination_dir_for(self, file_path: Path) -> Path:
        ext = file_path.suffix.lower()
        relative = self._rules.by_extension.get(ext, self._rules.default_folder)
        relative_path = Path(relative)

        if self._library.root:
            return self._library.root / relative_path

        return file_path.parent / relative_path

    def on_file_ready(self, file_path: Path) -> Path:
        return self.destination_dir_for(file_path)
