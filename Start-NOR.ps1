param([switch]$CheckOnly, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$norPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $norPython)) {
    $norPython = (Get-Command python -ErrorAction Stop).Source
}
$norManager = Join-Path $PSScriptRoot 'backend\manage.py'
if ($CheckOnly) {
    & $norPython $norManager doctor
} else {
    & $norPython $norManager serve --port $Port
}
exit $LASTEXITCODE
