# FilesGoThere
Local-first automatic file organizer for Windows
Offline. Lightweight. Privacy-friendly.

## Avvio (backend)
1. Copia `config/example_config.json` in `config/config.json` e modifica percorsi.
2. Installa dipendenze:
   - `pip install -r requirements.txt`
3. Avvia:
   - `python main.py --config config/config.json`

## Avvio (GUI minimale)
1. Installa dipendenze GUI:
   - `pip install -r requirements-gui.txt`
2. Avvia:
   - `python main.py gui --config config/config.json`
