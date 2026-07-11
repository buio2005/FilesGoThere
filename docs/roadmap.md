# Roadmap tecnica (iniziale)

## Fase 0 (ora)
- Struttura moduli backend.
- Watcher multi-cartella.
- Regole per estensione + cartella default.
- Attesa completamento download (settle su dimensione file).
- Logging su console e su file.
- Lingua base IT/EN per messaggi (i18n minimale).

## Fase 1 (in corso)
- [x] GUI PySide6 minimale: start/stop, coda azioni, storico, impostazioni, tema chiaro/scuro.
- [x] Modalità manuale: coda di "azioni suggerite" con anteprima e conferma.
- [x] Modalità auto: spostamento reale + Undo dell'ultima azione.
- [x] Filtri (testo/estensione) e messaggi di errore leggibili.
- [x] Ignore-list file di sistema + settle robusto per download grandi.
- [ ] Tray icon e notifiche toast (esperienza "PowerToys-like").
- [ ] Editor regole nella GUI.
- [ ] Regole avanzate (regex su nome file, mime, dimensione, priorità).

## Fase 2
- [ ] Gestione conflitti più ricca (hash, dedup).
- [ ] Import/export config, profili.
- [ ] Avvio automatico con Windows.
