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

function Invoke-RhwpCommand {
    param(
        [Parameter(Mandatory)] [string]$Executable,
        [Parameter(Mandatory)] [string[]]$Arguments
    )

    $output = @(& $Executable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = $output
    }
}

function Get-RhwpPageOutputs {
    param(
        [Parameter(Mandatory)] [string]$Directory,
        [Parameter(Mandatory)] [string]$Stem,
        [Parameter(Mandatory)] [ValidateSet('txt', 'md')] [string]$Extension
    )

    $pattern = '^' + [regex]::Escape($Stem) + '_(?<page>[0-9]{3})\.' + $Extension + '$'
    $files = @(Get-ChildItem -LiteralPath $Directory -File | Where-Object {
            $_.Name -match $pattern
        } | Sort-Object Name)
    if ($files.Count -eq 0) {
        throw "rhwp produced no .$Extension output files."
    }

    for ($index = 0; $index -lt $files.Count; $index++) {
        $expectedPage = '{0:D3}' -f ($index + 1)
        if ($files[$index].BaseName -notlike "*_$expectedPage") {
            throw "rhwp page sequence is incomplete at $expectedPage."
        }
        if ($files[$index].Length -le 0) {
            throw "rhwp produced empty output: $($files[$index].Name)"
        }
    }
    return $files
}

function Invoke-RhwpExtraction {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$InputPath,

        [Parameter(Mandatory)]
        [string]$OutputDirectory,

        [ValidateSet('text', 'markdown', 'both')]
        [string]$Format = 'both',

        [string]$RhwpPath,
        [scriptblock]$ToolResolver,
        [scriptblock]$CommandRunner = ${function:Invoke-RhwpCommand}
    )

    $input = Get-Item -LiteralPath $InputPath -ErrorAction Stop
    if (-not $input.PSIsContainer -and $input.Extension.ToLowerInvariant() -eq '.hwpx') {
        if (-not $script:RhwpHwpxCompatibilityEnabled) {
            throw '.hwpx extraction is disabled until the pinned compatibility test passes.'
        }
    }
    elseif ($input.PSIsContainer -or $input.Extension.ToLowerInvariant() -ne '.hwp') {
        throw 'InputPath must have the .hwp extension.'
    }

    $outputFullPath = [IO.Path]::GetFullPath($OutputDirectory)
    if (Test-Path -LiteralPath $outputFullPath) {
        throw "OutputDirectory must not already exist: $outputFullPath"
    }
    $outputParent = [IO.Path]::GetDirectoryName($outputFullPath)
    if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) {
        throw "Output parent does not exist: $outputParent"
    }

    $stagingLeaf = '.rhwp-extract-' + [Guid]::NewGuid().ToString('N')
    $staging = Join-Path $outputParent $stagingLeaf
    New-Item -ItemType Directory -Path $staging | Out-Null
    Set-Content `
        -LiteralPath (Join-Path $staging '.rhwp-owned') `
        -Encoding Ascii `
        -NoNewline `
        -Value $stagingLeaf

    $session = $null
    try {
        $session = if ($null -ne $ToolResolver) {
            & $ToolResolver
        }
        else {
            New-RhwpToolSession -RhwpPath $RhwpPath
        }
        if ($null -eq $session -or [string]::IsNullOrWhiteSpace([string]$session.Path)) {
            throw 'The rhwp tool resolver did not return an executable path.'
        }

        $normalizedFormat = $Format.ToLowerInvariant()
        $requestedFormats = if ($normalizedFormat -ceq 'both') {
            @('text', 'markdown')
        }
        else {
            @($normalizedFormat)
        }
        $commands = [System.Collections.Generic.List[object]]::new()
        $pageFiles = [System.Collections.Generic.List[object]]::new()

        foreach ($kind in $requestedFormats) {
            $commandName = if ($kind -ceq 'text') { 'export-text' } else { 'export-markdown' }
            $fileExtension = if ($kind -ceq 'text') { 'txt' } else { 'md' }
            $destination = Join-Path $staging $kind
            New-Item -ItemType Directory -Path $destination | Out-Null
            $arguments = @($commandName, $input.FullName, '--output', $destination)
            $result = & $CommandRunner ([string]$session.Path) $arguments
            if ($null -eq $result -or $null -eq $result.ExitCode) {
                throw "$commandName returned no exit code."
            }
            if ([int]$result.ExitCode -ne 0) {
                $commandOutput = @($result.Output) -join [Environment]::NewLine
                throw "$commandName failed with exit code $($result.ExitCode): $commandOutput"
            }
            $commands.Add([ordered]@{
                    name = $commandName
                    arguments = $arguments
                    exit_code = 0
                })
            foreach ($file in @(Get-RhwpPageOutputs `
                        -Directory $destination `
                        -Stem $input.BaseName `
                        -Extension $fileExtension)) {
                $pageFiles.Add($file)
            }
        }

        if ($normalizedFormat -ceq 'both') {
            $textCount = @($pageFiles | Where-Object { $_.Extension -ceq '.txt' }).Count
            $markdownCount = @($pageFiles | Where-Object { $_.Extension -ceq '.md' }).Count
            if ($textCount -ne $markdownCount) {
                throw "rhwp text and markdown page counts differ: $textCount and $markdownCount."
            }
        }

        $manifestOutputs = @($pageFiles | ForEach-Object {
                [ordered]@{
                    relative_path = $_.FullName.Substring($staging.Length + 1).Replace('\', '/')
                    byte_count = $_.Length
                    sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
                }
            })
        $manifest = [ordered]@{
            schema_version = 1
            executed_at_utc = [DateTime]::UtcNow.ToString('o')
            tool = [ordered]@{
                version = $session.Version
                executable_sha256 = $session.ExecutableSha256
                archive_sha256 = $session.ArchiveSha256
                release_url = $session.ReleaseUrl
                checksum_url = $session.ChecksumUrl
            }
            input = [ordered]@{
                file_name = $input.Name
                byte_count = $input.Length
                sha256 = (Get-FileHash -LiteralPath $input.FullName -Algorithm SHA256).Hash
            }
            commands = @($commands)
            outputs = $manifestOutputs
            retention_status = 'TEMPORARY_NOT_RETAINED'
            warnings = @(
                'Extraction does not establish legal effect, source rights, tax correctness, or spatial correctness.'
            )
            manual_review_required = $true
        }

        $manifestTemporaryPath = Join-Path $staging 'rhwp-extraction-manifest.json.tmp'
        $manifestPath = Join-Path $staging 'rhwp-extraction-manifest.json'
        $manifest |
            ConvertTo-Json -Depth 8 |
            Set-Content -LiteralPath $manifestTemporaryPath -Encoding UTF8
        Move-Item -LiteralPath $manifestTemporaryPath -Destination $manifestPath

        if ($session.Temporary) {
            Remove-RhwpToolSession -Session $session
            $session = $null
        }
        Move-Item -LiteralPath $staging -Destination $outputFullPath
        return [pscustomobject]$manifest
    }
    catch {
        $primaryError = $_
        $cleanupErrors = [System.Collections.Generic.List[string]]::new()
        if (Test-Path -LiteralPath $staging) {
            try {
                Remove-RhwpOwnedWorkspace `
                    -WorkspacePath $staging `
                    -ExpectedPrefix '.rhwp-extract-' `
                    -AllowedParent $outputParent
            }
            catch {
                $cleanupErrors.Add($_.Exception.Message)
            }
        }
        if ($null -ne $session -and $session.Temporary) {
            try {
                Remove-RhwpToolSession -Session $session
            }
            catch {
                $cleanupErrors.Add($_.Exception.Message)
            }
        }
        if ($cleanupErrors.Count -gt 0) {
            throw "rhwp extraction failed and cleanup also failed: $($primaryError.Exception.Message); $($cleanupErrors -join '; ')"
        }
        throw $primaryError
    }
}

Export-ModuleMember -Function @(
    'Get-RhwpReleaseDescriptor',
    'Test-RhwpAllowedHost',
    'Get-RhwpExpectedChecksum',
    'Assert-RhwpArchiveChecksum',
    'New-RhwpToolSession',
    'Remove-RhwpToolSession',
    'Invoke-RhwpExtraction'
)
