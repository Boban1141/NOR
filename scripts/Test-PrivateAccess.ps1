$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PrivateAccess.ps1')
$norHostName = 'nor.example.ts.net'
$norFixture = '{"TCP":{"443":{"HTTPS":true}},"Web":{"nor.example.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:8000"}}}}}'
if ((Get-NorServeState ($norFixture | ConvertFrom-Json) $norHostName 8000) -ne 'nor') { throw 'NOR configuration rejected' }
if ((Get-NorServeState ('{}' | ConvertFrom-Json) $norHostName 8000) -ne 'empty') { throw 'Empty configuration rejected' }
foreach ($norBad in @(
    $norFixture.Replace('8000','9000'),
    $norFixture.Replace('127.0.0.1','external.example'),
    $norFixture.Replace('"HTTPS":true','"HTTPS":true,"TCPForward":"external:22"'),
    $norFixture.Replace('"Proxy":','"Path":"C:/private","Proxy":'),
    $norFixture.Replace('"TCP":','"AllowFunnel":{"nor.example.ts.net:443":true},"TCP":'),
    $norFixture.Replace('"TCP":','"Foreground":{},"TCP":')
)) {
    if ((Get-NorServeState ($norBad | ConvertFrom-Json) $norHostName 8000) -ne 'conflict') { throw 'Unsafe configuration accepted' }
}
Write-Output '8 private-access configuration checks passed.'
