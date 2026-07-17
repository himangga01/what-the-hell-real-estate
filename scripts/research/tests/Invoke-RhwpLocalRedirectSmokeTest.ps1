[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot '..\RhwpPipeline.psm1') -Force

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
    [IO.Path]::DirectorySeparatorChar,
    [IO.Path]::AltDirectorySeparatorChar
)
$workspaceLeaf = 'rhwp-http-smoke-' + [Guid]::NewGuid().ToString('N')
$workspace = Join-Path $tempRoot $workspaceLeaf
New-Item -ItemType Directory -Path $workspace | Out-Null
$readyPath = Join-Path $workspace 'ready'
$requestPath = Join-Path $workspace 'request.txt'
$destination = Join-Path $workspace 'asset.zip'

$probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$probe.Start()
$port = ([Net.IPEndPoint]$probe.LocalEndpoint).Port
$probe.Stop()

$serverJob = Start-Job -ArgumentList $port, $readyPath, $requestPath -ScriptBlock {
    param([int]$Port, [string]$ReadyPath, [string]$RequestPath)

    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
    try {
        $listener.Start()
        Set-Content -LiteralPath $ReadyPath -Encoding Ascii -NoNewline -Value 'ready'
        $client = $listener.AcceptTcpClient()
        try {
            $stream = $client.GetStream()
            $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::ASCII, $false, 1024, $true)
            try {
                $requestLine = $reader.ReadLine()
                while (-not [string]::IsNullOrEmpty($reader.ReadLine())) {
                }
            }
            finally {
                $reader.Dispose()
            }
            Set-Content -LiteralPath $RequestPath -Encoding Ascii -NoNewline -Value $requestLine
            $responseText = "HTTP/1.1 302 Found`r`nLocation: http://127.0.0.1:$Port/blocked`r`nContent-Length: 0`r`nConnection: close`r`n`r`n"
            $responseBytes = [Text.Encoding]::ASCII.GetBytes($responseText)
            $stream.Write($responseBytes, 0, $responseBytes.Length)
            $stream.Flush()
        }
        finally {
            $client.Dispose()
        }
    }
    finally {
        $listener.Stop()
    }
}

try {
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    while (-not (Test-Path -LiteralPath $readyPath -PathType Leaf)) {
        if ($serverJob.State -in @('Failed', 'Stopped', 'Completed')) {
            Receive-Job -Job $serverJob -ErrorAction SilentlyContinue | Out-Null
            throw "Local redirect server stopped before becoming ready: $($serverJob.State)"
        }
        if ([DateTime]::UtcNow -ge $deadline) {
            throw 'Timed out waiting for the local redirect server.'
        }
        Start-Sleep -Milliseconds 50
    }

    $startUri = [uri]"http://127.0.0.1:$port/start"
    $validator = {
        param([uri]$Candidate)
        return $Candidate.Scheme -ceq 'http' -and
            $Candidate.Host -ceq '127.0.0.1' -and
            $Candidate.Port -eq $port -and
            $Candidate.AbsolutePath -ceq '/start'
    }.GetNewClosure()
    $module = Get-Module RhwpPipeline
    $failure = $null
    try {
        & $module {
            param($Uri, $TargetPath, $UriValidator)
            Invoke-RhwpDownload `
                -Uri $Uri `
                -Destination $TargetPath `
                -UriValidator $UriValidator
        } $startUri $destination $validator
    }
    catch {
        $failure = $_
    }
    if ($null -eq $failure -or $failure.Exception.Message -notlike '*Untrusted rhwp redirect host*') {
        $message = if ($null -eq $failure) { 'no failure' } else { $failure.Exception.Message }
        throw "Local redirect was not rejected before follow-up: $message"
    }

    Wait-Job -Job $serverJob -Timeout 10 | Out-Null
    if ($serverJob.State -ne 'Completed') {
        throw "Local redirect server did not complete: $($serverJob.State)"
    }
    Receive-Job -Job $serverJob -ErrorAction Stop | Out-Null
    $requestLine = (Get-Content -LiteralPath $requestPath -Raw -Encoding Ascii).Trim()
    if ($requestLine -notlike 'GET /start HTTP/*') {
        throw "Unexpected local request: $requestLine"
    }
    if (Test-Path -LiteralPath $destination) {
        throw 'Rejected local redirect left a download file.'
    }

    [ordered]@{
        powershell_major = $PSVersionTable.PSVersion.Major
        initial_request = $requestLine
        redirect_followed = $false
        result = 'PASS'
    } | ConvertTo-Json
}
finally {
    if ($serverJob.State -in @('NotStarted', 'Running')) {
        if (Test-Path -LiteralPath $readyPath -PathType Leaf) {
            try {
                $unblockClient = [Net.Sockets.TcpClient]::new()
                $unblockClient.Connect([Net.IPAddress]::Loopback, $port)
                $unblockStream = $unblockClient.GetStream()
                $unblockBytes = [Text.Encoding]::ASCII.GetBytes(
                    "GET /cleanup HTTP/1.1`r`nHost: 127.0.0.1`r`nConnection: close`r`n`r`n"
                )
                $unblockStream.Write($unblockBytes, 0, $unblockBytes.Length)
                $unblockStream.Flush()
                $unblockClient.Dispose()
            }
            catch {
            }
        }
        Wait-Job -Job $serverJob -Timeout 5 | Out-Null
        if ($serverJob.State -in @('NotStarted', 'Running')) {
            Stop-Job -Job $serverJob
        }
    }
    Remove-Job -Job $serverJob -Force -ErrorAction SilentlyContinue
    $resolvedWorkspace = [IO.Path]::GetFullPath($workspace)
    $actualParent = [IO.Path]::GetDirectoryName($resolvedWorkspace)
    $actualLeaf = [IO.Path]::GetFileName($resolvedWorkspace)
    if (-not $actualParent.Equals($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $actualLeaf -notmatch '^rhwp-http-smoke-[0-9a-f]{32}$') {
        throw "Unsafe local redirect cleanup target: $resolvedWorkspace"
    }
    if (Test-Path -LiteralPath $resolvedWorkspace) {
        Remove-Item -LiteralPath $resolvedWorkspace -Recurse -Force
    }
}
