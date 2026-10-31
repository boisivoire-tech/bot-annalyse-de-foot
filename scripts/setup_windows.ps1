# Installation automatique de FOOTBALL INTELLIGENCE PRO sous Windows.
# Lancée par la tâche VS Code "1. Installation complète", ou manuellement :
#   powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

Write-Step "Recherche de Python 3.12 (64 bits)"
$pyExe = $null
$pyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -eq 0) { $pyExe = "py"; $pyArgs = @("-3.12") }
}
if (-not $pyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $version = & python --version 2>&1
    if ("$version" -match "Python 3\.1[0-3]") { $pyExe = "python" }
}
if (-not $pyExe) {
    Write-Host "Python 3.10 à 3.13 introuvable. Installez Python 3.12 : winget install -e --id Python.Python.3.12" -ForegroundColor Red
    exit 1
}
& $pyExe @pyArgs --version

Write-Step "Création de l'environnement virtuel .venv (si absent)"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "Création de .venv impossible." -ForegroundColor Red; exit 1 }
}
$venvPy = Join-Path $root ".venv\Scripts\python.exe"

Write-Step "Mise à jour de pip et installation des bibliothèques"
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements.txt
& $venvPy -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { Write-Host "Installation des bibliothèques échouée." -ForegroundColor Red; exit 1 }

Write-Step "Fichier .env (clé API)"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Fichier .env créé. Ouvrez-le et remplacez VOTRE_CLE_ICI par votre clé API-Football." -ForegroundColor Yellow
} else {
    Write-Host "Fichier .env déjà présent : conservé."
}

Write-Step "Vérification : tests automatiques"
& $venvPy -m unittest discover -s tests -t .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Des tests ont échoué. Copiez le message ci-dessus." -ForegroundColor Red
    exit 1
}

Write-Host "`nInstallation terminée. Lancez l'application avec la tâche '2. Lancer l'application' ou : python main.py" -ForegroundColor Green
