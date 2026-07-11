# Architettura

## Obiettivi
- Utility desktop Windows offline e privacy-friendly.
- Monitorare una o più cartelle (tipicamente Downloads).
- Applicare regole semplici per spostare i file in sottocartelle dedicate.

## Moduli
- `filesgothere.config`: carica/valida la configurazione JSON e la espone come dataclass (incluse `settle_max_seconds` e `ignore_globs`).
- `filesgothere.logging_setup`: setup logging standard Python (console + file rotante).
- `filesgothere.rules`: risolve la cartella destinazione in base all’estensione.
- `filesgothere.utils`: helper filesystem (`move_with_duplicates`, `is_temporary_download`, `is_ignored`).
- `filesgothere.watcher`: filesystem watcher con watchdog e “settle” robusto (attende finché il file cresce); salta file temporanei e file di sistema.
- `filesgothere.queue`: coda azioni (JSONL) per la modalità manuale; `AutoApplier` per lo spostamento automatico e `undo_action` per l'annullamento.
- `filesgothere.i18n`: testi IT/EN per log e GUI.
- `filesgothere.app`: orchestration headless (carica config, avvia watcher, lifecycle).
- `filesgothere.gui_app` / `filesgothere.gui_main_window`: GUI PySide6 (coda, storico, impostazioni, undo).

## Flusso
1. Il watcher rileva un file, attende il "settle" e ignora temporanei/di sistema.
2. Il rule engine calcola la cartella destinazione.
3. In `manual` l'azione va in coda (anteprima + conferma → spostamento). In `auto` lo spostamento è immediato e registrato nello storico.
4. Ogni spostamento applicato può essere annullato (Undo), riportando il file alla posizione originale.
