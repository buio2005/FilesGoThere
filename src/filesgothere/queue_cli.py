from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from filesgothere.config import ConfigError, load_config
from filesgothere.queue import apply_action_by_index, archive_queue, preview_action_by_index, read_actions


def queue_command(config_path: Path, command: str, options: dict[str, Any] | None = None) -> int:
    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 2

    opts = options or {}
    if command == "list":
        source = str(opts.get("source") or "pending")
        file_path = config.queue.file
        if source == "done":
            file_path = config.queue.file.with_name("queue_done.jsonl")

        actions = read_actions(
            file_path,
            tail=opts.get("tail"),
            ext=opts.get("ext"),
            contains=opts.get("contains"),
        )
        print(json.dumps(actions, ensure_ascii=False, indent=2))
        return 0
    if command == "archive":
        done_file = config.queue.file.with_name("queue_done.jsonl")
        result = archive_queue(config.queue.file, done_file)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if command == "apply":
        index = opts.get("index")
        if not isinstance(index, int) or index < 0:
            print(json.dumps({"error": "Index non valido: usa --index >= 0"}, ensure_ascii=False, indent=2))
            return 2
        if not opts.get("yes", False):
            preview = preview_action_by_index(config.queue.file, index, config.library)
            preview["require_same_size"] = bool(opts.get("require_same_size", False))
            preview["confirm_required"] = True
            preview["hint"] = "Rilancia con --yes per applicare davvero."
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            return 0
        done_file = config.queue.file.with_name("queue_done.jsonl")
        result = apply_action_by_index(
            config.queue.file,
            done_file,
            index,
            config.library,
            require_same_size=bool(opts.get("require_same_size", False)),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps({"error": f"Comando non supportato: {command}"}, ensure_ascii=False))
    return 2
