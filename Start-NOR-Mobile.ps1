$ErrorActionPreference = 'Stop'
$norPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $norPython)) { throw 'NOR Python environment not found.' }
Set-Location -LiteralPath $PSScriptRoot
$norRunning = $false
try {
    $norHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
    $norRunning = $norHealth.status -eq 'ok'
} catch {}
if ($norRunning) {
    try {
        $norManifest = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/manifest.webmanifest' -TimeoutSec 2
        if ($norManifest.short_name -ne 'NOR') { throw 'Unexpected application.' }
    } catch { throw 'The old NOR server is still running. Stop it with Ctrl+C in its window, then run Start-NOR-Mobile.ps1 again.' }
}
$norAddressFile = Join-Path $PSScriptRoot '.runtime\mobile-url'
if (Test-Path -LiteralPath $norAddressFile) {
    $norMobileUrl = (Get-Content -LiteralPath $norAddressFile -Raw).Trim()
    $norParsedUrl = $null
    if (-not [Uri]::TryCreate($norMobileUrl, [UriKind]::Absolute, [ref]$norParsedUrl) -or $norParsedUrl.Scheme -ne 'https' -or $norParsedUrl.UserInfo -or $norParsedUrl.Query -or $norParsedUrl.Fragment) { throw 'Invalid private mobile address.' }
    Write-Output ('NOR on iPhone: ' + $norMobileUrl)
} else { Write-Output 'Open the private HTTPS address shown by Connect-NOR-iPhone.ps1.' }
Write-Output 'Connect Tailscale on your iPhone, open the address in Safari and enter the pairing code below.'
& $norPython backend\manage.py pair
if ($LASTEXITCODE -ne 0) { throw 'Unable to generate the private pairing code. Verify NOR configuration.' }
Write-Output 'Keep this window open. Use Safari > Share > Add to Home Screen to install NOR.'
if ($norRunning) { Write-Output 'NOR is already running. A new pairing code has been generated.'; exit 0 }
& $norPython backend\manage.py serve
exit $LASTEXITCODE
