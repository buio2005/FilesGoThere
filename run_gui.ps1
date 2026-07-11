# ============================================================
#  FilesGoThere - avvio GUI (Windows / PowerShell)
#  Uso consigliato (da PowerShell nella cartella del progetto):
#     powershell -ExecutionPolicy Bypass -File .\run_gui.ps1
#  Aggiungi  -Cli  per avviare il watcher headless invece della GUI.
# ============================================================
param(
    [switch]$Cli
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# 1) Crea il virtualenv se manca
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "[FilesGoThere] Creo l'ambiente virtuale (.venv)..."
    python -m venv .venv
}

$py = ".\.venv\Scripts\python.exe"

# 2) Installa le dipendenze solo al primo avvio
if (-not (Test-Path ".\.venv\.deps_ok")) {
    Write-Host "[FilesGoThere] Installo le dipendenze (la prima volta puo' richiedere qualche minuto)..."
    & $py -m pip install --upgrade pip
    & $py -m pip install -r requirements.txt -r requirements-gui.txt
    New-Item -ItemType File -Path ".\.venv\.deps_ok" | Out-Null
}

# 3) Avvia GUI o CLI
if ($Cli) {
    Write-Host "[FilesGoThere] Avvio watcher (CLI headless)..."
    & $py main.py --config config\config.json
} else {
    Write-Host "[FilesGoThere] Avvio dell'interfaccia..."
    & $py main.py gui --config config\config.json
}
