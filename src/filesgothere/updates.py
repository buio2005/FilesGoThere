"""Controllo aggiornamenti: verifica se su GitHub esiste una release più
recente di quella in esecuzione.

Il controllo è facoltativo (`app.check_updates`, spento di default), avviene
una sola volta per avvio e fallisce in silenzio: se il computer è offline non
succede nulla e non si riprova fino al riavvio successivo.
"""

from __future__ import annotations

import json
import re
import threading
import urllib.request
from dataclasses import dataclass

RELEASES_API = "https://api.github.com/repos/buio2005/FilesGoThere/releases/latest"
RELEASES_PAGE = "https://github.com/buio2005/FilesGoThere/releases"
TIMEOUT_SECONDS = 6.0

_VERSION_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    url: str


def parse_version(text: str) -> tuple[int, int, int, int] | None:
    """Trasforma "v1.2.3" in (1, 2, 3, 1).

    Il confronto va fatto sui numeri e non sul testo: come stringa "1.10.0"
    risulterebbe minore di "1.9.0".

    L'ultimo elemento distingue le pre-release: "v1.2.3-beta.1" diventa
    (1, 2, 3, 0), cioè vale meno della 1.2.3 definitiva.
    """
    if not isinstance(text, str):
        return None
    cleaned = text.strip().lstrip("vV")
    match = _VERSION_RE.match(cleaned)
    if not match:
        return None
    major, minor, patch = (int(part) if part else 0 for part in match.groups())
    remainder = cleaned[match.end():]
    is_final = 0 if remainder.startswith("-") else 1
    return (major, minor, patch, is_final)


def is_newer(candidate: str, current: str) -> bool:
    """True solo se `candidate` è una versione successiva a `current`.
    Di fronte a un numero che non si riesce a leggere risponde False: meglio
    nessun avviso che un avviso sbagliato."""
    parsed_candidate = parse_version(candidate)
    parsed_current = parse_version(current)
    if parsed_candidate is None or parsed_current is None:
        return False
    return parsed_candidate > parsed_current


def fetch_latest_release(timeout: float = TIMEOUT_SECONDS) -> UpdateInfo | None:
    """Interroga l'API pubblica di GitHub (nessuna autenticazione, nessun dato
    inviato). Restituisce None a ogni problema: rete assente, risposta
    inattesa, tempo scaduto."""
    request = urllib.request.Request(
        RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "FilesGoThere",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag.strip():
        return None

    url = payload.get("html_url")
    return UpdateInfo(
        version=tag.strip(),
        url=url if isinstance(url, str) and url else RELEASES_PAGE,
    )


class UpdateChecker:
    """Esegue il controllo in un thread separato per non ritardare l'avvio.

    Il thread di lavoro si limita a depositare l'esito; è l'interfaccia
    grafica a raccoglierlo con take_result() dal proprio thread. Così nessun
    widget viene toccato da fuori, che è la causa più comune di blocchi
    inspiegabili nelle applicazioni con interfaccia.
    """

    def __init__(self, current_version: str) -> None:
        self._current_version = current_version
        self._result: UpdateInfo | None = None
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Avvia il controllo. Chiamate successive non fanno nulla: una volta
        sola per avvio, come richiesto."""
        if self._started:
            return
        self._started = True
        threading.Thread(
            target=self._run, name="filesgothere-update-check", daemon=True
        ).start()

    def _run(self) -> None:
        try:
            latest = fetch_latest_release()
        except Exception:
            return
        if latest is None or not is_newer(latest.version, self._current_version):
            return
        with self._lock:
            self._result = latest

    def take_result(self) -> UpdateInfo | None:
        """Restituisce l'esito una volta sola, poi si azzera: chi chiama lo
        mostra e non deve preoccuparsi di ripresentarlo a ogni giro."""
        with self._lock:
            result, self._result = self._result, None
        return result
