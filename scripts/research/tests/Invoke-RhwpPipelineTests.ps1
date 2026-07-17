[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot '..\RhwpPipeline.psm1') -Force

$script:Passed = 0
$script:Failed = 0

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [Parameter(Mandatory)] [string]$Message
    )

    if ($Actual -cne $Expected) {
        throw "$Message; expected='$Expected', actual='$Actual'"
    }
}

function Assert-True {
    param(
        [bool]$Condition,
        [Parameter(Mandatory)] [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-ThrowsLike {
    param(
        [Parameter(Mandatory)] [scriptblock]$Action,
        [Parameter(Mandatory)] [string]$Pattern
    )

    try {
        & $Action
    }
    catch {
        if ($_.Exception.Message -notlike $Pattern) {
            throw "Expected '$Pattern', received '$($_.Exception.Message)'"
        }
        return
    }

    throw "Expected exception matching '$Pattern'"
}

function Invoke-Test {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [scriptblock]$Body
    )

    try {
        & $Body
        $script:Passed++
        Write-Output "PASS $Name"
    }
    catch {
        $script:Failed++
        Write-Error "FAIL $Name`: $($_.Exception.Message)" -ErrorAction Continue
    }
}

function New-TestDirectory {
    param([Parameter(Mandatory)] [string]$Prefix)

    if ($Prefix -notmatch '^[a-z0-9-]+-$') {
        throw "Unsafe test prefix: $Prefix"
    }
    $path = Join-Path ([IO.Path]::GetTempPath()) ($Prefix + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $path | Out-Null
    return [IO.Path]::GetFullPath($path)
}

function Remove-TestDirectory {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Prefix
    )

    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    $resolved = [IO.Path]::GetFullPath($Path)
    $expectedParent = [IO.Path]::GetDirectoryName($resolved)
    $leaf = [IO.Path]::GetFileName($resolved)
    if (-not $expectedParent.Equals($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe test cleanup parent: $resolved"
    }
    if ($leaf -notmatch ('^' + [regex]::Escape($Prefix) + '[0-9a-f]{32}$')) {
        throw "Unsafe test cleanup leaf: $resolved"
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

Invoke-Test 'Windows release descriptor is pinned' {
    $release = Get-RhwpReleaseDescriptor -Platform windows -Architecture x86_64
    Assert-Equal $release.Version 'v0.7.18' 'Version must be pinned'
    Assert-Equal $release.AssetName 'rhwp-v0.7.18-windows-x86_64.zip' 'Wrong asset'
    Assert-Equal $release.ArchiveType 'zip' 'Wrong archive type'
    Assert-Equal `
        $release.AssetUrl `
        'https://github.com/edwardkim/rhwp/releases/download/v0.7.18/rhwp-v0.7.18-windows-x86_64.zip' `
        'Wrong official asset URL'
}

Invoke-Test 'Only approved GitHub release hosts are accepted' {
    Assert-True (Test-RhwpAllowedHost -Uri 'https://github.com/a') 'github.com rejected'
    Assert-True `
        (Test-RhwpAllowedHost -Uri 'https://objects.githubusercontent.com/a') `
        'objects.githubusercontent.com rejected'
    Assert-True `
        (Test-RhwpAllowedHost -Uri 'https://release-assets.githubusercontent.com/a') `
        'release-assets.githubusercontent.com rejected'
    Assert-True (-not (Test-RhwpAllowedHost -Uri 'http://github.com/a')) 'HTTP was accepted'
    Assert-True (-not (Test-RhwpAllowedHost -Uri 'https://example.com/a')) 'Untrusted host accepted'
}

Invoke-Test 'Exact asset checksum is selected' {
    $directory = New-TestDirectory -Prefix 'rhwp-checksum-test-'
    try {
        $checksumPath = Join-Path $directory 'SHA256SUMS.txt'
        Set-Content -LiteralPath $checksumPath -Encoding Ascii -Value @(
            '1111111111111111111111111111111111111111111111111111111111111111  another.zip',
            'bd0b3280c0b87580bfc8c86af337609acf939c5f8f1da6ab3ee73955064420fd  rhwp-v0.7.18-windows-x86_64.zip'
        )
        $actual = Get-RhwpExpectedChecksum `
            -ChecksumPath $checksumPath `
            -AssetName 'rhwp-v0.7.18-windows-x86_64.zip'
        Assert-Equal `
            $actual `
            'BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD' `
            'Checksum parsing failed'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-checksum-test-'
    }
}

Invoke-Test 'Missing or duplicate asset checksums are rejected' {
    $directory = New-TestDirectory -Prefix 'rhwp-checksum-cardinality-'
    try {
        $checksumPath = Join-Path $directory 'SHA256SUMS.txt'
        Set-Content -LiteralPath $checksumPath -Encoding Ascii -Value @(
            'bd0b3280c0b87580bfc8c86af337609acf939c5f8f1da6ab3ee73955064420fd  rhwp-v0.7.18-windows-x86_64.zip',
            'bd0b3280c0b87580bfc8c86af337609acf939c5f8f1da6ab3ee73955064420fd  rhwp-v0.7.18-windows-x86_64.zip'
        )
        Assert-ThrowsLike {
            Get-RhwpExpectedChecksum `
                -ChecksumPath $checksumPath `
                -AssetName 'rhwp-v0.7.18-windows-x86_64.zip'
        } '*exactly one checksum*'
        Assert-ThrowsLike {
            Get-RhwpExpectedChecksum -ChecksumPath $checksumPath -AssetName 'missing.zip'
        } '*exactly one checksum*'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-checksum-cardinality-'
    }
}

Invoke-Test 'Modified archive is rejected' {
    $directory = New-TestDirectory -Prefix 'rhwp-archive-test-'
    try {
        $archivePath = Join-Path $directory 'archive.zip'
        Set-Content -LiteralPath $archivePath -Encoding Ascii -Value 'modified'
        Assert-ThrowsLike {
            Assert-RhwpArchiveChecksum -ArchivePath $archivePath -ExpectedSha256 ('0' * 64)
        } '*checksum mismatch*'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-archive-test-'
    }
}

Write-Output "RESULT Passed=$script:Passed Failed=$script:Failed"
if ($script:Failed -gt 0) {
    exit 1
}
