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

Invoke-Test 'Redirect host is rejected before a follow-up request' {
    $directory = New-TestDirectory -Prefix 'rhwp-redirect-test-'
    try {
        $destination = Join-Path $directory 'asset.zip'
        $calls = [Collections.Generic.List[string]]::new()
        $sender = {
            param([uri]$RequestUri, [string]$Destination)
            $calls.Add($RequestUri.AbsoluteUri)
            if ($calls.Count -gt 1) {
                throw 'An untrusted redirect target was requested.'
            }
            return [pscustomobject]@{
                StatusCode = 302
                Location = 'https://example.com/payload.zip'
            }
        }.GetNewClosure()
        $module = Get-Module RhwpPipeline
        Assert-ThrowsLike {
            & $module {
                param($TargetPath, $RequestSender)
                Invoke-RhwpDownload `
                    -Uri 'https://github.com/edwardkim/rhwp/releases/download/v0.7.18/asset.zip' `
                    -Destination $TargetPath `
                    -RequestSender $RequestSender
            } $destination $sender
        } '*Untrusted rhwp redirect host*'
        Assert-Equal $calls.Count 1 'Untrusted redirect target received a request'
        Assert-True (-not (Test-Path -LiteralPath $destination)) 'Rejected redirect left a download'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-redirect-test-'
    }
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

Invoke-Test 'Tool session rejects a modified archive and removes its workspace' {
    $before = @(Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Directory -Filter 'rhwp-tool-*' |
        Select-Object -ExpandProperty FullName)
    $download = {
        param([uri]$Uri, [string]$Destination)

        if ([IO.Path]::GetFileName($Destination) -ceq 'SHA256SUMS.txt') {
            Set-Content -LiteralPath $Destination -Encoding Ascii -Value (
                ('0' * 64) + '  rhwp-v0.7.18-windows-x86_64.zip'
            )
        }
        else {
            Set-Content -LiteralPath $Destination -Encoding Ascii -Value 'modified archive'
        }
        return [uri]'https://release-assets.githubusercontent.com/test-asset'
    }

    Assert-ThrowsLike {
        New-RhwpToolSession `
            -Platform windows `
            -Architecture x86_64 `
            -DownloadFile $download
    } '*checksum mismatch*'
    $after = @(Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Directory -Filter 'rhwp-tool-*' |
        Select-Object -ExpandProperty FullName)
    Assert-Equal ($after -join '|') ($before -join '|') 'Failed tool session leaked a workspace'
}

Invoke-Test 'Local tool session requires the pinned version' {
    $directory = New-TestDirectory -Prefix 'rhwp-local-version-'
    try {
        $fakeTool = Join-Path $directory 'rhwp.cmd'
        Set-Content -LiteralPath $fakeTool -Encoding Ascii -Value @(
            '@echo off',
            'echo rhwp v0.7.17'
        )
        Assert-ThrowsLike {
            New-RhwpToolSession -RhwpPath $fakeTool
        } '*version must be exactly*'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-local-version-'
    }
}

Invoke-Test 'Valid local tool session records version and executable hash' {
    $directory = New-TestDirectory -Prefix 'rhwp-local-success-'
    try {
        $fakeTool = Join-Path $directory 'rhwp.cmd'
        Set-Content -LiteralPath $fakeTool -Encoding Ascii -Value @(
            '@echo off',
            'echo rhwp v0.7.18'
        )
        $session = New-RhwpToolSession -RhwpPath $fakeTool
        Assert-Equal $session.Version 'v0.7.18' 'Local tool version was not recorded'
        Assert-Equal $session.Temporary $false 'Local tool was marked temporary'
        Assert-Equal `
            $session.ExecutableSha256 `
            (Get-FileHash -LiteralPath $fakeTool -Algorithm SHA256).Hash `
            'Local executable hash mismatch'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-local-success-'
    }
}

Invoke-Test 'Tool cleanup refuses a workspace without its ownership sentinel' {
    $directory = New-TestDirectory -Prefix 'rhwp-tool-'
    try {
        $session = [pscustomobject]@{
            Temporary = $true
            WorkspacePath = $directory
        }
        Assert-ThrowsLike {
            Remove-RhwpToolSession -Session $session
        } '*ownership sentinel*'
        Assert-True (Test-Path -LiteralPath $directory) 'Unsafe workspace was deleted'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-tool-'
    }
}

Invoke-Test 'Tool entrypoint emits verified local metadata as JSON' {
    $directory = New-TestDirectory -Prefix 'rhwp-entrypoint-test-'
    try {
        $fakeTool = Join-Path $directory 'rhwp.cmd'
        Set-Content -LiteralPath $fakeTool -Encoding Ascii -Value @(
            '@echo off',
            'echo rhwp v0.7.18'
        )
        $entrypoint = Join-Path $PSScriptRoot '..\rhwp-tool.ps1'
        $output = @(& powershell.exe `
                -NoProfile `
                -ExecutionPolicy Bypass `
                -File $entrypoint `
                -RhwpPath $fakeTool 2>&1 | ForEach-Object { $_.ToString() })
        $exitCode = $LASTEXITCODE
        Assert-Equal $exitCode 0 'Tool entrypoint failed'
        $metadata = ($output -join [Environment]::NewLine) | ConvertFrom-Json
        Assert-Equal $metadata.version 'v0.7.18' 'Entrypoint version mismatch'
        Assert-Equal $metadata.temporary $false 'Entrypoint temporary flag mismatch'
        Assert-Equal `
            $metadata.executable_sha256 `
            (Get-FileHash -LiteralPath $fakeTool -Algorithm SHA256).Hash `
            'Entrypoint executable hash mismatch'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-entrypoint-test-'
    }
}

function New-FakeRhwpSession {
    return [pscustomobject]@{
        Path = 'fake-rhwp'
        Version = 'v0.7.18'
        ExecutableSha256 = ('A' * 64)
        ArchiveSha256 = ('B' * 64)
        ReleaseUrl = 'https://github.com/edwardkim/rhwp/releases/download/v0.7.18/fake.zip'
        ChecksumUrl = 'https://github.com/edwardkim/rhwp/releases/download/v0.7.18/SHA256SUMS.txt'
        WorkspacePath = $null
        Temporary = $false
    }
}

function Assert-NoExtractionStaging {
    param([Parameter(Mandatory)] [string]$Parent)

    $staging = @(Get-ChildItem -LiteralPath $Parent -Directory -Filter '.rhwp-extract-*')
    Assert-Equal $staging.Count 0 "Extraction staging directory leaked below $Parent"
}

Invoke-Test 'Unsupported extension is rejected before tool resolution' {
    $directory = New-TestDirectory -Prefix 'rhwp-extension-test-'
    try {
        $inputPath = Join-Path $directory 'sample.txt'
        $output = Join-Path $directory 'result'
        Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'fixture bytes'
        $probe = [pscustomobject]@{ Called = $false }
        $resolver = {
            $probe.Called = $true
            throw 'resolver must not run'
        }.GetNewClosure()
        Assert-ThrowsLike {
            Invoke-RhwpExtraction `
                -InputPath $inputPath `
                -OutputDirectory $output `
                -ToolResolver $resolver
        } '*.hwp extension*'
        Assert-Equal $probe.Called $false 'Tool resolver ran before extension validation'
        Assert-True (Test-Path -LiteralPath $inputPath) 'Input was deleted'
        Assert-True (-not (Test-Path -LiteralPath $output)) 'Invalid input created output'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-extension-test-'
    }
}

Invoke-Test 'HWPX extraction stays disabled before compatibility evidence' {
    $directory = New-TestDirectory -Prefix 'rhwp-hwpx-test-'
    try {
        $inputPath = Join-Path $directory 'sample.hwpx'
        $output = Join-Path $directory 'result'
        Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'fixture bytes'
        $probe = [pscustomobject]@{ Called = $false }
        $resolver = {
            $probe.Called = $true
            throw 'resolver must not run'
        }.GetNewClosure()
        Assert-ThrowsLike {
            Invoke-RhwpExtraction `
                -InputPath $inputPath `
                -OutputDirectory $output `
                -ToolResolver $resolver
        } '*.hwpx extraction is disabled*'
        Assert-Equal $probe.Called $false 'Tool resolver ran before the HWPX gate'
        Assert-True (-not (Test-Path -LiteralPath $output)) 'Gated HWPX created output'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-hwpx-test-'
    }
}

Invoke-Test 'Zero-byte HWP is rejected before tool resolution' {
    $directory = New-TestDirectory -Prefix 'rhwp-empty-input-'
    try {
        $inputPath = Join-Path $directory 'sample.hwp'
        $output = Join-Path $directory 'result'
        [IO.File]::WriteAllBytes($inputPath, [byte[]]@())
        $probe = [pscustomobject]@{ Called = $false }
        $resolver = {
            $probe.Called = $true
            throw 'resolver must not run'
        }.GetNewClosure()
        Assert-ThrowsLike {
            Invoke-RhwpExtraction `
                -InputPath $inputPath `
                -OutputDirectory $output `
                -ToolResolver $resolver
        } '*must not be empty*'
        Assert-Equal $probe.Called $false 'Tool resolver ran before input size validation'
        Assert-True (-not (Test-Path -LiteralPath $output)) 'Empty input created output'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-empty-input-'
    }
}

Invoke-Test 'Successful extraction writes page hashes and an auditable manifest' {
    $directory = New-TestDirectory -Prefix 'rhwp-extract-success-'
    try {
        $inputPath = Join-Path $directory 'sample.hwp'
        $output = Join-Path $directory 'result'
        Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'fixture bytes'
        $session = New-FakeRhwpSession
        $resolver = { $session }.GetNewClosure()
        $runner = {
            param([string]$Executable, [string[]]$Arguments)

            $destination = $Arguments[3]
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
            $extension = if ($Arguments[0] -ceq 'export-text') { 'txt' } else { 'md' }
            Set-Content `
                -LiteralPath (Join-Path $destination "sample_001.$extension") `
                -Encoding UTF8 `
                -Value 'page one'
            Set-Content `
                -LiteralPath (Join-Path $destination "sample_002.$extension") `
                -Encoding UTF8 `
                -Value 'page two'
            return [pscustomobject]@{ ExitCode = 0; Output = @('ok') }
        }

        $manifest = Invoke-RhwpExtraction `
            -InputPath $inputPath `
            -OutputDirectory $output `
            -Format both `
            -ToolResolver $resolver `
            -CommandRunner $runner
        Assert-Equal $manifest.schema_version 1 'Wrong manifest schema'
        Assert-Equal $manifest.tool.version 'v0.7.18' 'Wrong tool version'
        Assert-Equal $manifest.outputs.Count 4 'Expected two text and two Markdown pages'
        Assert-Equal $manifest.commands[0].diagnostics[0] 'ok' 'Parser diagnostics were not recorded'
        Assert-Equal `
            $manifest.retention_status `
            'TEMPORARY_NOT_RETAINED' `
            'Wrong retention state'
        Assert-Equal $manifest.manual_review_required $true 'Manual review flag is missing'
        Assert-True (Test-Path -LiteralPath $inputPath) 'Input was deleted'

        $manifestPath = Join-Path $output 'rhwp-extraction-manifest.json'
        Assert-True (Test-Path -LiteralPath $manifestPath) 'Manifest file is missing'
        $persisted = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Assert-Equal $persisted.input.sha256 (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash 'Input hash mismatch'
        foreach ($record in $persisted.outputs) {
            $path = Join-Path $output ($record.relative_path -replace '/', '\')
            Assert-Equal `
                $record.sha256 `
                (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash `
                "Output hash mismatch for $($record.relative_path)"
        }
        $publishedFiles = @(Get-ChildItem -LiteralPath $output -Recurse -File)
        Assert-Equal $publishedFiles.Count 5 'Published output contains unaudited files'
        Assert-True `
            (-not (Test-Path -LiteralPath (Join-Path $output '.rhwp-owned'))) `
            'Internal ownership sentinel was published'
        Assert-NoExtractionStaging -Parent $directory
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-extract-success-'
    }
}

function Invoke-FailClosedExtractionTest {
    param(
        [Parameter(Mandatory)] [string]$Prefix,
        [Parameter(Mandatory)] [scriptblock]$Runner,
        [Parameter(Mandatory)] [string]$ExpectedError
    )

    $directory = New-TestDirectory -Prefix $Prefix
    try {
        $inputPath = Join-Path $directory 'sample.hwp'
        $output = Join-Path $directory 'result'
        Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'fixture bytes'
        $session = New-FakeRhwpSession
        $resolver = { $session }.GetNewClosure()
        Assert-ThrowsLike {
            Invoke-RhwpExtraction `
                -InputPath $inputPath `
                -OutputDirectory $output `
                -Format text `
                -ToolResolver $resolver `
                -CommandRunner $Runner
        } $ExpectedError
        Assert-True (Test-Path -LiteralPath $inputPath) 'Failed extraction deleted input'
        Assert-True (-not (Test-Path -LiteralPath $output)) 'Failed extraction published output'
        Assert-NoExtractionStaging -Parent $directory
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix $Prefix
    }
}

Invoke-Test 'Parser command failure does not publish output' {
    Invoke-FailClosedExtractionTest `
        -Prefix 'rhwp-parser-failure-' `
        -ExpectedError '*export-text failed with exit code 2*' `
        -Runner {
            param([string]$Executable, [string[]]$Arguments)
            return [pscustomobject]@{ ExitCode = 2; Output = @('parser error') }
        }
}

Invoke-Test 'Input mutation during extraction fails closed' {
    $directory = New-TestDirectory -Prefix 'rhwp-input-mutation-'
    try {
        $inputPath = Join-Path $directory 'sample.hwp'
        $output = Join-Path $directory 'result'
        Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'alpha fixture bytes'
        $session = New-FakeRhwpSession
        $resolver = { $session }.GetNewClosure()
        $runner = {
            param([string]$Executable, [string[]]$Arguments)
            $destination = $Arguments[3]
            Set-Content `
                -LiteralPath (Join-Path $destination 'sample_001.txt') `
                -Encoding UTF8 `
                -Value 'page one'
            Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'bravo fixture bytes'
            return [pscustomobject]@{ ExitCode = 0; Output = @('ok') }
        }.GetNewClosure()
        Assert-ThrowsLike {
            Invoke-RhwpExtraction `
                -InputPath $inputPath `
                -OutputDirectory $output `
                -Format text `
                -ToolResolver $resolver `
                -CommandRunner $runner
        } '*input changed during extraction*'
        Assert-True (-not (Test-Path -LiteralPath $output)) 'Mutated input published output'
        Assert-NoExtractionStaging -Parent $directory
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-input-mutation-'
    }
}

Invoke-Test 'Unexpected parser files fail closed' {
    Invoke-FailClosedExtractionTest `
        -Prefix 'rhwp-unexpected-output-' `
        -ExpectedError '*unexpected extraction output*' `
        -Runner {
            param([string]$Executable, [string[]]$Arguments)
            $destination = $Arguments[3]
            Set-Content -LiteralPath (Join-Path $destination 'sample_001.txt') -Encoding UTF8 -Value 'page one'
            Set-Content -LiteralPath (Join-Path $destination 'debug.log') -Encoding UTF8 -Value 'unaudited'
            return [pscustomobject]@{ ExitCode = 0; Output = @('ok') }
        }
}

Invoke-Test 'Zero output files do not publish a manifest' {
    Invoke-FailClosedExtractionTest `
        -Prefix 'rhwp-empty-output-' `
        -ExpectedError '*produced no .txt output files*' `
        -Runner {
            param([string]$Executable, [string[]]$Arguments)
            New-Item -ItemType Directory -Path $Arguments[3] -Force | Out-Null
            return [pscustomobject]@{ ExitCode = 0; Output = @('no pages') }
        }
}

Invoke-Test 'Page gaps do not publish a manifest' {
    Invoke-FailClosedExtractionTest `
        -Prefix 'rhwp-page-gap-' `
        -ExpectedError '*page sequence is incomplete*' `
        -Runner {
            param([string]$Executable, [string[]]$Arguments)
            $destination = $Arguments[3]
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
            Set-Content -LiteralPath (Join-Path $destination 'sample_001.txt') -Encoding UTF8 -Value 'page one'
            Set-Content -LiteralPath (Join-Path $destination 'sample_003.txt') -Encoding UTF8 -Value 'page three'
            return [pscustomobject]@{ ExitCode = 0; Output = @('gap') }
        }
}

Invoke-Test 'Existing output directory is rejected before tool resolution' {
    $directory = New-TestDirectory -Prefix 'rhwp-existing-output-'
    try {
        $inputPath = Join-Path $directory 'sample.hwp'
        $output = Join-Path $directory 'result'
        Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'fixture bytes'
        New-Item -ItemType Directory -Path $output | Out-Null
        $probe = [pscustomobject]@{ Called = $false }
        $resolver = {
            $probe.Called = $true
            throw 'resolver must not run'
        }.GetNewClosure()
        Assert-ThrowsLike {
            Invoke-RhwpExtraction `
                -InputPath $inputPath `
                -OutputDirectory $output `
                -ToolResolver $resolver
        } '*must not already exist*'
        Assert-Equal $probe.Called $false 'Tool resolver ran before output validation'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-existing-output-'
    }
}

Invoke-Test 'Concurrent output creation prevents atomic publication' {
    $directory = New-TestDirectory -Prefix 'rhwp-publish-race-'
    try {
        $inputPath = Join-Path $directory 'sample.hwp'
        $output = Join-Path $directory 'result'
        Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'fixture bytes'
        $session = New-FakeRhwpSession
        $resolver = { $session }.GetNewClosure()
        $runner = {
            param([string]$Executable, [string[]]$Arguments)
            Set-Content `
                -LiteralPath (Join-Path $Arguments[3] 'sample_001.txt') `
                -Encoding UTF8 `
                -Value 'page one'
            New-Item -ItemType Directory -Path $output | Out-Null
            return [pscustomobject]@{ ExitCode = 0; Output = @('ok') }
        }.GetNewClosure()
        Assert-ThrowsLike {
            Invoke-RhwpExtraction `
                -InputPath $inputPath `
                -OutputDirectory $output `
                -Format text `
                -ToolResolver $resolver `
                -CommandRunner $runner
        } '*atomically publish*'
        Assert-Equal @(Get-ChildItem -LiteralPath $output -Force).Count 0 'Pipeline modified the competing output directory'
        Assert-NoExtractionStaging -Parent $directory
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-publish-race-'
    }
}

Invoke-Test 'Zero-byte page output fails closed' {
    Invoke-FailClosedExtractionTest `
        -Prefix 'rhwp-zero-byte-' `
        -ExpectedError '*produced empty output*' `
        -Runner {
            param([string]$Executable, [string[]]$Arguments)
            $destination = $Arguments[3]
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
            [IO.File]::WriteAllBytes((Join-Path $destination 'sample_001.txt'), [byte[]]@())
            return [pscustomobject]@{ ExitCode = 0; Output = @('empty page') }
        }
}

Invoke-Test 'Text and Markdown page count mismatch fails closed' {
    $directory = New-TestDirectory -Prefix 'rhwp-page-count-'
    try {
        $inputPath = Join-Path $directory 'sample.hwp'
        $output = Join-Path $directory 'result'
        Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'fixture bytes'
        $session = New-FakeRhwpSession
        $resolver = { $session }.GetNewClosure()
        $runner = {
            param([string]$Executable, [string[]]$Arguments)
            $destination = $Arguments[3]
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
            $extension = if ($Arguments[0] -ceq 'export-text') { 'txt' } else { 'md' }
            Set-Content -LiteralPath (Join-Path $destination "sample_001.$extension") -Encoding UTF8 -Value 'page one'
            if ($Arguments[0] -ceq 'export-text') {
                Set-Content -LiteralPath (Join-Path $destination 'sample_002.txt') -Encoding UTF8 -Value 'page two'
            }
            return [pscustomobject]@{ ExitCode = 0; Output = @('ok') }
        }
        Assert-ThrowsLike {
            Invoke-RhwpExtraction `
                -InputPath $inputPath `
                -OutputDirectory $output `
                -Format both `
                -ToolResolver $resolver `
                -CommandRunner $runner
        } '*page counts differ*'
        Assert-True (-not (Test-Path -LiteralPath $output)) 'Mismatched pages published output'
        Assert-NoExtractionStaging -Parent $directory
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-page-count-'
    }
}

Invoke-Test 'Extraction entrypoint emits manifest JSON and preserves input' {
    $directory = New-TestDirectory -Prefix 'rhwp-extract-entrypoint-'
    try {
        $inputPath = Join-Path $directory 'sample.hwp'
        $output = Join-Path $directory 'result'
        $fakeTool = Join-Path $directory 'rhwp.cmd'
        Set-Content -LiteralPath $inputPath -Encoding UTF8 -Value 'fixture bytes'
        Set-Content -LiteralPath $fakeTool -Encoding Ascii -Value @(
            '@echo off',
            'if "%~1"=="--version" goto version',
            'if "%~1"=="export-text" goto text',
            'if "%~1"=="export-markdown" goto markdown',
            'exit /b 2',
            ':version',
            'echo rhwp v0.7.18',
            'exit /b 0',
            ':text',
            'echo text page>"%~4\sample_001.txt"',
            'exit /b 0',
            ':markdown',
            'echo markdown page>"%~4\sample_001.md"',
            'exit /b 0'
        )

        $entrypoint = Join-Path $PSScriptRoot '..\extract-hwp.ps1'
        $jsonLines = @(& powershell.exe `
                -NoProfile `
                -ExecutionPolicy Bypass `
                -File $entrypoint `
                -InputPath $inputPath `
                -OutputDirectory $output `
                -Format both `
                -RhwpPath $fakeTool 2>&1 | ForEach-Object { $_.ToString() })
        $exitCode = $LASTEXITCODE
        Assert-Equal $exitCode 0 'Extraction entrypoint failed'
        $manifest = ($jsonLines -join [Environment]::NewLine) | ConvertFrom-Json
        Assert-Equal $manifest.outputs.Count 2 'Entrypoint output count mismatch'
        Assert-Equal $manifest.tool.version 'v0.7.18' 'Entrypoint tool version mismatch'
        Assert-True (Test-Path -LiteralPath $inputPath) 'Entrypoint deleted input'
        Assert-True `
            (Test-Path -LiteralPath (Join-Path $output 'rhwp-extraction-manifest.json')) `
            'Entrypoint did not persist the manifest'
    }
    finally {
        Remove-TestDirectory -Path $directory -Prefix 'rhwp-extract-entrypoint-'
    }
}

Write-Output "RESULT Passed=$script:Passed Failed=$script:Failed"
if ($script:Failed -gt 0) {
    exit 1
}
