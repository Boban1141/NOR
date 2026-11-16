param(
    [switch]$Enable,
    [ValidateRange(1024, 65535)][int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\PrivateAccess.ps1')
$norCli = Get-Command tailscale -ErrorAction SilentlyContinue
if ($norCli) { $norCliPath = $norCli.Source }
elseif (Test-Path -LiteralPath 'C:\Program Files\Tailscale\tailscale.exe') { $norCliPath = 'C:\Program Files\Tailscale\tailscale.exe' }
else { throw 'Install Tailscale on Windows, sign in, then run this script again. See docs/IPHONE_CONNEXION.md.' }
$norStatusText = & $norCliPath status --json
if ($LASTEXITCODE -ne 0) { throw 'Tailscale status unavailable. Start Tailscale and sign in.' }
$norStatus = ($norStatusText -join "`n") | ConvertFrom-Json
if ($norStatus.BackendState -ne 'Running') { throw 'Sign in to Tailscale on this PC first.' }
$norDns = ([string]$norStatus.Self.DNSName).TrimEnd('.')
if ($norDns -notmatch '^[a-zA-Z0-9.-]+\.ts\.net$') { throw 'A Tailscale DNS name is required. Enable MagicDNS in your tailnet.' }
$norHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5
if ($norHealth.status -ne 'ok') { throw 'Start the NOR server before configuring iPhone access.' }
$norServeText = & $norCliPath serve status --json
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect Tailscale Serve. No configuration changed.' }
$norServe = ($norServeText -join "`n") | ConvertFrom-Json
$norState = Get-NorServeState -Configuration $norServe -HostName $norDns -Port $Port
if ($norState -eq 'conflict') { throw 'Existing Tailscale Serve/Funnel configuration detected. No configuration changed. Inspect it with tailscale serve status.' }
if ($Enable -and $norState -eq 'empty') {
    & $norCliPath serve --bg --https=443 "http://127.0.0.1:$Port"
    if ($LASTEXITCODE -ne 0) { throw 'Serve could not start. Follow the Tailscale HTTPS instructions displayed above, then retry.' }
    $norCheck = & $norCliPath serve status --json
    if ($LASTEXITCODE -ne 0) { throw 'Serve verification failed.' }
    $norState = Get-NorServeState -Configuration (($norCheck -join "`n") | ConvertFrom-Json) -HostName $norDns -Port $Port
    if ($norState -ne 'nor') { throw 'Serve configuration could not be confirmed. Inspect tailscale serve status.' }
}
if ($norState -eq 'nor') {
    Write-Output "NOR private address: https://$norDns"
    Write-Output "From your iPhone with Tailscale connected, open: https://$norDns/health"
    Write-Output 'Keep the NOR server running. Enter the address and access token separately in the app settings.'
} else {
    Write-Output 'Checks passed. Run .\Connect-NOR-iPhone.ps1 -Enable in an Administrator PowerShell to enable private HTTPS access.'
}
