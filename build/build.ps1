param(
  [switch]$Console
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  throw "Virtualenv not found. Create it first: python -m venv .venv"
}

$py = ".\.venv\Scripts\python.exe"

& $py -m pip install --upgrade pip | Out-Host
& $py -m pip install -r requirements.txt | Out-Host

if (Test-Path ".\requirements-gui.txt") {
  & $py -m pip install -r requirements-gui.txt | Out-Host
}

& $py -m pip install pyinstaller | Out-Host

Get-Process FilesGoThere -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Remove-Item -Force -ErrorAction SilentlyContinue ".\dist\FilesGoThere.exe"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue ".\build\FilesGoThere", ".\dist\FilesGoThere"

$configStage = ".\build\config_stage"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $configStage
New-Item -ItemType Directory -Force -Path $configStage | Out-Null

Copy-Item -Force ".\config\config.json" $configStage
if (Test-Path ".\config\example_config.json") {
  Copy-Item -Force ".\config\example_config.json" $configStage
}
if (Test-Path ".\config\presets") {
  Copy-Item -Recurse -Force ".\config\presets" (Join-Path $configStage "presets")
}

$assetArgs = @()
if (Test-Path ".\assets") {
  $assetArgs += @("--add-data", ".\assets;assets")
}

if ($Console) {
  & $py -m PyInstaller --noconfirm --clean --console --name FilesGoThereConsole --paths "src" --add-data "$configStage;config" @assetArgs main.py | Out-Host
  exit 0
}

& $py -m PyInstaller --noconfirm --clean --windowed --name FilesGoThere --paths "src" --add-data "$configStage;config" @assetArgs main.py | Out-Host
