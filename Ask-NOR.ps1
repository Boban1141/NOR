param(
    [Parameter(Mandatory = $true)][ValidateLength(2, 2000)][string]$Question,
    [ValidateSet('fr', 'en')][string]$Language = 'fr',
    [ValidateRange(1024, 65535)][int]$Port = 8000,
    [switch]$Refresh,
    [switch]$Deep,
    [switch]$NoCache,
    [switch]$Details
)
$ErrorActionPreference = 'Stop'
$norTokenPath = Join-Path $PSScriptRoot '.runtime\access-token'
$norAccess = (Get-Content -LiteralPath $norTokenPath -Raw).Trim()
if ($norAccess.Length -lt 32) { throw 'Configure NOR before asking a question.' }
$norBody = @{
    question = $Question
    language = $Language
    refresh = [bool]$Refresh
    profile = $(if ($Deep) { 'deep' } else { 'balanced' })
    use_cache = -not [bool]$NoCache
} | ConvertTo-Json
$norHttp = Invoke-WebRequest -UseBasicParsing `
    -Uri "http://127.0.0.1:$Port/research" `
    -Method Post `
    -Headers @{ Authorization = "Bearer $norAccess" } `
    -ContentType 'application/json; charset=utf-8' `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($norBody)) `
    -TimeoutSec 600
# Decode the raw bytes explicitly, including when using an older running
# server that did not yet advertise charset=utf-8 in its JSON response.
$norStream = $norHttp.RawContentStream
if ($norStream.CanSeek) { $norStream.Position = 0 }
$norReader = [System.IO.StreamReader]::new($norStream, [System.Text.UTF8Encoding]::new($false, $true), $true, 1024, $true)
try { $norDecoded = $norReader.ReadToEnd() | ConvertFrom-Json }
finally { $norReader.Dispose(); $norStream.Dispose() }
if ($Details) { $norDecoded | ConvertTo-Json -Depth 12 }
else {
    if ($norDecoded.cache -and $norDecoded.cache.hit) {
        if ($Language -eq 'fr') { Write-Host 'Réponse récente réutilisée ; sources inchangées.' }
        else { Write-Host 'Recent answer reused; sources unchanged.' }
    }
    $norDecoded.answer
}
