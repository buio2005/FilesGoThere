# Architettura (fase backend-only)

## Obiettivi
- Utility desktop Windows offline e privacy-friendly.
- Monitorare una o più cartelle (tipicamente Downloads).
- Applicare regole semplici per spostare i file in sottocartelle dedicate.

## Moduli
- `filesgothere.config`: carica/valida la configurazione JSON e la espone come dataclass.
- `filesgothere.logging_setup`: setup logging standard Python (console + file rotante).
- `filesgothere.rules`: risolve la cartella destinazione in base all’estensione.
- `filesgothere.watcher`: filesystem watcher con watchdog e “settle” per attendere il completamento del download.
- `filesgothere.i18n`: testi base IT/EN (per log e, in futuro, GUI).
- `filesgothere.app`: orchestration (carica config, avvia watcher, lifecycle).
- `filesgothere.gui`: placeholder per futura GUI PySide6.
