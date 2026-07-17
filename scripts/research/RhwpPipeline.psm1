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

Export-ModuleMember -Function @(
    'Get-RhwpReleaseDescriptor',
    'Test-RhwpAllowedHost',
    'Get-RhwpExpectedChecksum',
    'Assert-RhwpArchiveChecksum'
)
