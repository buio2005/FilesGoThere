param()

$ErrorActionPreference = "Stop"

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

& $iscc ".\build\FilesGoThere.iss" | Out-Host
