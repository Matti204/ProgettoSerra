# Avvio locale Windows, senza attivare manualmente l'ambiente virtuale.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $venvPython -c "import importlib.util, sys; sys.exit(not all(importlib.util.find_spec(name) for name in ('flask', 'waitress', 'dotenv', 'tzdata')))"
if ($LASTEXITCODE -ne 0) {
    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $venvPython app.py
exit $LASTEXITCODE
