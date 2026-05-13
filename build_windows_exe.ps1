Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $repoRoot

$venvPython = Join-Path $repoRoot ".pythonenv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    $python = $venvPython
} else {
    throw "Python introuvable dans .pythonenv\Scripts\python.exe. Creez d'abord l'environnement virtuel du projet."
}

& $python -m PyInstaller --version | Out-Null

$buildDir = Join-Path $repoRoot "build"
$distDir = Join-Path $repoRoot "dist"
$exePath = Join-Path $distDir "WikisourceAssistant.exe"
$legacyZipPath = Join-Path $distDir "WikisourceAssistant-windows.zip"
$legacyAppDir = Join-Path $distDir "WikisourceAssistant"

foreach ($path in @($buildDir, $exePath, $legacyZipPath, $legacyAppDir)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

& $python -m PyInstaller --noconfirm --clean "$repoRoot\wikisource_assistant_gui.spec"

if (-not (Test-Path -LiteralPath $exePath)) {
    throw "L'executable de distribution n'a pas ete cree."
}

Write-Host ""
Write-Host "Build termine."
Write-Host "Executable autonome : $exePath"
