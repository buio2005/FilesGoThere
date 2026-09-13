param()

$ErrorActionPreference = "Stop"

# Il numero di versione ha una sola fonte: src\filesgothere\__init__.py.
# Da qui viene letto e passato al compilatore Inno Setup, che lo usa sia per
# la versione dichiarata nell'installer sia per il nome del file Setup.
$versionFile = ".\src\filesgothere\__init__.py"
if (-not (Test-Path $versionFile)) {
  throw "Version file not found: $versionFile (run this script from the project root)."
}

$versionMatch = Select-String -Path $versionFile -Pattern '__version__\s*=\s*"([^"]+)"' |
  Select-Object -First 1
if (-not $versionMatch) {
  throw "Could not read __version__ from $versionFile."
}
$version = $versionMatch.Matches[0].Groups[1].Value
Write-Host "FilesGoThere version: $version"

$isccPaths = @(
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
  "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$iscc = $isccPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
  throw "Inno Setup Compiler (ISCC.exe) not found."
}

if (-not (Test-Path ".\dist\FilesGoThere\FilesGoThere.exe")) {
  throw "Build output not found. Run .\build\build.ps1 first."
}

& $iscc "/DAppVersion=$version" ".\build\FilesGoThere.iss" | Out-Host

$setup = ".\dist\FilesGoThere-Setup-v$version.exe"
if (Test-Path $setup) {
  Write-Host "Installer created: $setup"
} else {
  throw "Installer not found at $setup after compilation."
}
