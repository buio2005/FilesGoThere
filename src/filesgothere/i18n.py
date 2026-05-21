from __future__ import annotations

from typing import Any


_MESSAGES: dict[str, dict[str, str]] = {
    "it": {
        "app.starting": "Avvio FilesGoThere…",
        "app.stopping": "Arresto FilesGoThere…",
        "config.loaded": "Configurazione caricata: {path}",
        "config.invalid": "Configurazione non valida: {reason}",
        "watch.start": "Monitoraggio attivo su {count} cartelle.",
        "watch.path": "- {path}",
        "event.detected": "Rilevato file: {path}",
        "event.skipped.temp": "Ignorato (download incompleto/temporaneo): {path}",
        "event.planned.manual": "Manuale (dry-run): {path} -> {dst_dir}",
        "event.planned.auto": "Auto (dry-run): {path} -> {dst_dir}",
        "event.moved": "Spostato: {src} -> {dst}",
        "event.duplicate.skipped": "Duplicato ignorato: {path}",
        "event.error": "Errore su {path}: {error}",
    },
    "en": {
        "app.starting": "Starting FilesGoThere…",
        "app.stopping": "Stopping FilesGoThere…",
        "config.loaded": "Configuration loaded: {path}",
        "config.invalid": "Invalid configuration: {reason}",
        "watch.start": "Watching {count} folder(s).",
        "watch.path": "- {path}",
        "event.detected": "Detected file: {path}",
        "event.skipped.temp": "Skipped (incomplete/temporary): {path}",
        "event.planned.manual": "Manual (dry-run): {path} -> {dst_dir}",
        "event.planned.auto": "Auto (dry-run): {path} -> {dst_dir}",
        "event.moved": "Moved: {src} -> {dst}",
        "event.duplicate.skipped": "Duplicate skipped: {path}",
        "event.error": "Error on {path}: {error}",
    },
}


def t(key: str, lang: str, **kwargs: Any) -> str:
    messages = _MESSAGES.get(lang) or _MESSAGES["en"]
    template = messages.get(key) or _MESSAGES["en"].get(key) or key
    try:
        return template.format(**kwargs)
    except Exception:
        return template

