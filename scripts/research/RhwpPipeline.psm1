Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:RhwpVersion = 'v0.7.18'
$script:RhwpReleaseBase = 'https://github.com/edwardkim/rhwp/releases/download/v0.7.18'
$script:RhwpAllowedHosts = @(
    'github.com',
    'objects.githubusercontent.com',
    'release-assets.githubusercontent.com'
)
$script:RhwpHwpxCompatibilityEnabled = $false

function Get-RhwpReleaseDescriptor {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateSet('windows', 'linux', 'macos')]
        [string]$Platform,

        [Parameter(Mandatory)]
        [ValidateSet('x86_64', 'aarch64')]
        [string]$Architecture
    )

    if ($Architecture -eq 'aarch64' -and $Platform -ne 'macos') {
        throw "rhwp $($script:RhwpVersion) has no official $Platform-$Architecture release asset."
    }

    $archiveType = if ($Platform -eq 'windows') { 'zip' } else { 'tar.gz' }
    $assetName = "rhwp-$($script:RhwpVersion)-$Platform-$Architecture.$archiveType"
    return [pscustomobject]@{
        Version = $script:RhwpVersion
        AssetName = $assetName
        ArchiveType = $archiveType
        AssetUrl = "$($script:RhwpReleaseBase)/$assetName"
        ChecksumUrl = "$($script:RhwpReleaseBase)/SHA256SUMS.txt"
    }
}

function Test-RhwpAllowedHost {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [uri]$Uri
    )

    return $Uri.Scheme -ceq 'https' -and $Uri.Host -cin $script:RhwpAllowedHosts
}

function Get-RhwpExpectedChecksum {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$ChecksumPath,

        [Parameter(Mandatory)]
        [string]$AssetName
    )

    $matchingHashes = [System.Collections.Generic.List[string]]::new()
    foreach ($line in Get-Content -LiteralPath $ChecksumPath -Encoding UTF8) {
        if ($line -notmatch '^(?<hash>[0-9a-fA-F]{64})\s+\*?(?<name>.+)$') {
            continue
        }
        if ($Matches.name -ceq $AssetName) {
            $matchingHashes.Add($Matches.hash.ToUpperInvariant())
        }
    }

    if ($matchingHashes.Count -ne 1) {
        throw "Expected exactly one checksum for $AssetName; found $($matchingHashes.Count)."
    }
    return $matchingHashes[0]
}

function Assert-RhwpArchiveChecksum {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$ArchivePath,

        [Parameter(Mandatory)]
        [ValidatePattern('^[0-9A-Fa-f]{64}$')]
        [string]$ExpectedSha256
    )

    $expected = $ExpectedSha256.ToUpperInvariant()
    $actual = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash
    if ($actual -cne $expected) {
        throw "rhwp archive checksum mismatch: expected $expected, actual $actual"
    }
}

function Get-RhwpRuntimeTarget {
    $runtimeInformation = [Runtime.InteropServices.RuntimeInformation]
    if ($runtimeInformation::IsOSPlatform([Runtime.InteropServices.OSPlatform]::Windows)) {
        $platform = 'windows'
    }
    elseif ($runtimeInformation::IsOSPlatform([Runtime.InteropServices.OSPlatform]::Linux)) {
        $platform = 'linux'
    }
    elseif ($runtimeInformation::IsOSPlatform([Runtime.InteropServices.OSPlatform]::OSX)) {
        $platform = 'macos'
    }
    else {
        throw 'The current operating system has no supported rhwp release target.'
    }

    $architecture = switch ($runtimeInformation::OSArchitecture.ToString()) {
        'X64' { 'x86_64' }
        'Arm64' { 'aarch64' }
        default { throw "The current architecture is not supported: $($runtimeInformation::OSArchitecture)" }
    }
    return [pscustomobject]@{
        Platform = $platform
        Architecture = $architecture
    }
}

function Get-RhwpExecutableVersion {
    param([Parameter(Mandatory)] [string]$Path)

    try {
        $output = @(& $Path --version 2>&1 | ForEach-Object { $_.ToString() })
        $exitCode = $LASTEXITCODE
    }
    catch {
        throw "Unable to verify rhwp version at ${Path}: $($_.Exception.Message)"
    }

    $versionOutput = ($output -join [Environment]::NewLine).Trim()
    if ($exitCode -ne 0 -or $versionOutput -cne 'rhwp v0.7.18') {
        throw "Local rhwp version must be exactly 'rhwp v0.7.18'; received '$versionOutput'."
    }
    return $script:RhwpVersion
}

function Invoke-RhwpDownload {
    param(
        [Parameter(Mandatory)] [uri]$Uri,
        [Parameter(Mandatory)] [string]$Destination
    )

    if (-not (Test-RhwpAllowedHost -Uri $Uri)) {
        throw "Untrusted rhwp download URI: $Uri"
    }

    $response = Invoke-WebRequest `
        -UseBasicParsing `
        -Uri $Uri `
        -OutFile $Destination `
        -PassThru
    $finalUri = if ($null -ne $response.BaseResponse.ResponseUri) {
        [uri]$response.BaseResponse.ResponseUri
    }
    elseif ($null -ne $response.BaseResponse.RequestMessage) {
        [uri]$response.BaseResponse.RequestMessage.RequestUri
    }
    else {
        $Uri
    }

    if (-not (Test-RhwpAllowedHost -Uri $finalUri)) {
        Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
        throw "Untrusted rhwp redirect host: $($finalUri.Host)"
    }
    return $finalUri
}

function Remove-RhwpOwnedWorkspace {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$WorkspacePath,
        [Parameter(Mandatory)] [string]$ExpectedPrefix,
        [string]$AllowedParent
    )

    $resolved = [IO.Path]::GetFullPath($WorkspacePath).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    $parent = [IO.Path]::GetDirectoryName($resolved)
    $expectedParent = if ([string]::IsNullOrWhiteSpace($AllowedParent)) {
        [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
            [IO.Path]::DirectorySeparatorChar,
            [IO.Path]::AltDirectorySeparatorChar
        )
    }
    else {
        [IO.Path]::GetFullPath($AllowedParent).TrimEnd(
            [IO.Path]::DirectorySeparatorChar,
            [IO.Path]::AltDirectorySeparatorChar
        )
    }
    if (-not $parent.Equals($expectedParent, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing unsafe cleanup outside the expected parent: $resolved"
    }

    $leaf = [IO.Path]::GetFileName($resolved)
    $leafPattern = '^' + [regex]::Escape($ExpectedPrefix) + '[0-9a-f]{32}$'
    if ($leaf -notmatch $leafPattern) {
        throw "Refusing unsafe cleanup for unexpected workspace name: $resolved"
    }

    $sentinel = Join-Path $resolved '.rhwp-owned'
    if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf)) {
        throw "Refusing unsafe cleanup because the ownership sentinel is missing: $resolved"
    }
    $ownership = (Get-Content -LiteralPath $sentinel -Raw -Encoding Ascii).Trim()
    if ($ownership -cne $leaf) {
        throw "Refusing unsafe cleanup because the ownership sentinel does not match: $resolved"
    }

    Remove-Item -LiteralPath $resolved -Recurse -Force
}

function New-RhwpToolSession {
    [CmdletBinding()]
    param(
        [string]$RhwpPath,
        [ValidateSet('windows', 'linux', 'macos')] [string]$Platform,
        [ValidateSet('x86_64', 'aarch64')] [string]$Architecture,
        [scriptblock]$DownloadFile = ${function:Invoke-RhwpDownload}
    )

    if (-not [string]::IsNullOrWhiteSpace($RhwpPath)) {
        $resolvedTool = (Resolve-Path -LiteralPath $RhwpPath -ErrorAction Stop).Path
        [void](Get-RhwpExecutableVersion -Path $resolvedTool)
        return [pscustomobject]@{
            Path = $resolvedTool
            Version = $script:RhwpVersion
            ExecutableSha256 = (Get-FileHash -LiteralPath $resolvedTool -Algorithm SHA256).Hash
            ArchiveSha256 = $null
            ReleaseUrl = $null
            ChecksumUrl = $null
            WorkspacePath = $null
            Temporary = $false
        }
    }

    if ([string]::IsNullOrWhiteSpace($Platform) -or [string]::IsNullOrWhiteSpace($Architecture)) {
        $target = Get-RhwpRuntimeTarget
        if ([string]::IsNullOrWhiteSpace($Platform)) {
            $Platform = $target.Platform
        }
        if ([string]::IsNullOrWhiteSpace($Architecture)) {
            $Architecture = $target.Architecture
        }
    }
    $release = Get-RhwpReleaseDescriptor -Platform $Platform -Architecture $Architecture

    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    $workspaceLeaf = 'rhwp-tool-' + [Guid]::NewGuid().ToString('N')
    $workspace = Join-Path $tempRoot $workspaceLeaf
    New-Item -ItemType Directory -Path $workspace | Out-Null
    Set-Content `
        -LiteralPath (Join-Path $workspace '.rhwp-owned') `
        -Encoding Ascii `
        -NoNewline `
        -Value $workspaceLeaf

    try {
        $checksumPath = Join-Path $workspace 'SHA256SUMS.txt'
        $archivePath = Join-Path $workspace $release.AssetName
        $checksumFinalUri = & $DownloadFile ([uri]$release.ChecksumUrl) $checksumPath
        $archiveFinalUri = & $DownloadFile ([uri]$release.AssetUrl) $archivePath
        foreach ($finalUri in @($checksumFinalUri, $archiveFinalUri)) {
            if ($null -eq $finalUri -or -not (Test-RhwpAllowedHost -Uri ([uri]$finalUri))) {
                throw "Untrusted rhwp redirect result: $finalUri"
            }
        }

        $expectedHash = Get-RhwpExpectedChecksum `
            -ChecksumPath $checksumPath `
            -AssetName $release.AssetName
        Assert-RhwpArchiveChecksum -ArchivePath $archivePath -ExpectedSha256 $expectedHash

        $expanded = Join-Path $workspace 'expanded'
        New-Item -ItemType Directory -Path $expanded | Out-Null
        if ($release.ArchiveType -ceq 'zip') {
            Expand-Archive -LiteralPath $archivePath -DestinationPath $expanded
        }
        else {
            & tar -xzf $archivePath -C $expanded
            if ($LASTEXITCODE -ne 0) {
                throw "tar extraction failed with exit code $LASTEXITCODE"
            }
        }

        $executableName = if ($Platform -ceq 'windows') { 'rhwp.exe' } else { 'rhwp' }
        $executables = @(Get-ChildItem `
                -LiteralPath $expanded `
                -Recurse `
                -File `
                -Filter $executableName)
        if ($executables.Count -ne 1) {
            throw "Expected exactly one $executableName; found $($executables.Count)."
        }
        [void](Get-RhwpExecutableVersion -Path $executables[0].FullName)

        return [pscustomobject]@{
            Path = $executables[0].FullName
            Version = $release.Version
            ExecutableSha256 = (
                Get-FileHash -LiteralPath $executables[0].FullName -Algorithm SHA256
            ).Hash
            ArchiveSha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
            ReleaseUrl = $release.AssetUrl
            ChecksumUrl = $release.ChecksumUrl
            WorkspacePath = $workspace
            Temporary = $true
        }
    }
    catch {
        $primaryError = $_
        try {
            Remove-RhwpOwnedWorkspace `
                -WorkspacePath $workspace `
                -ExpectedPrefix 'rhwp-tool-'
        }
        catch {
            throw "rhwp tool setup failed and cleanup also failed: $($primaryError.Exception.Message); $($_.Exception.Message)"
        }
        throw $primaryError
    }
}

function Remove-RhwpToolSession {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [psobject]$Session
    )

    if (-not $Session.Temporary) {
        return
    }
    if ([string]::IsNullOrWhiteSpace([string]$Session.WorkspacePath)) {
        throw 'A temporary rhwp session is missing WorkspacePath.'
    }
    Remove-RhwpOwnedWorkspace `
        -WorkspacePath ([string]$Session.WorkspacePath) `
        -ExpectedPrefix 'rhwp-tool-'
}

Export-ModuleMember -Function @(
    'Get-RhwpReleaseDescriptor',
    'Test-RhwpAllowedHost',
    'Get-RhwpExpectedChecksum',
    'Assert-RhwpArchiveChecksum',
    'New-RhwpToolSession',
    'Remove-RhwpToolSession'
)
