function Get-NorServeState {
    param($Configuration, [string]$HostName, [int]$Port)
    if ($null -eq $Configuration) { return 'empty' }
    $norProperties = @($Configuration.PSObject.Properties)
    if ($norProperties.Count -eq 0) { return 'empty' }
    # Refuse configurations we do not own, including public Funnel exposure.
    if (@($norProperties | Where-Object { $_.Name -notin @('TCP', 'Web', 'AllowFunnel') }).Count -gt 0) { return 'conflict' }
    if ($Configuration.AllowFunnel -and @($Configuration.AllowFunnel.PSObject.Properties | Where-Object { $_.Value -eq $true }).Count -gt 0) { return 'conflict' }
    $norWeb = @($Configuration.Web.PSObject.Properties)
    $norTcp = @($Configuration.TCP.PSObject.Properties)
    if ($norWeb.Count -ne 1 -or $norTcp.Count -ne 1) { return 'conflict' }
    if ($norWeb[0].Name -ne ($HostName + ':443') -or $norTcp[0].Name -ne '443' -or $norTcp[0].Value.HTTPS -ne $true) { return 'conflict' }
    if (@($norTcp[0].Value.PSObject.Properties | Where-Object { $_.Name -ne 'HTTPS' }).Count -gt 0) { return 'conflict' }
    $norHandlers = @($norWeb[0].Value.Handlers.PSObject.Properties)
    if ($norHandlers.Count -ne 1 -or $norHandlers[0].Name -ne '/') { return 'conflict' }
    if ($norHandlers[0].Value.Proxy -ne "http://127.0.0.1:$Port") { return 'conflict' }
    if (@($norHandlers[0].Value.PSObject.Properties | Where-Object { $_.Name -ne 'Proxy' }).Count -gt 0) { return 'conflict' }
    return 'nor'
}
