[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot '..\RhwpPipeline.psm1') -Force

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
    [IO.Path]::DirectorySeparatorChar,
    [IO.Path]::AltDirectorySeparatorChar
)
$workspaceLeaf = 'rhwp-integration-' + [Guid]::NewGuid().ToString('N')
$workspace = Join-Path $tempRoot $workspaceLeaf
New-Item -ItemType Directory -Path $workspace | Out-Null

$session = $null
$failure = $null
$evidence = $null
try {
    $session = New-RhwpToolSession
    Push-Location -LiteralPath $workspace
    try {
        $generatorOutput = @(& $session.Path gen-table 2>&1 | ForEach-Object { $_.ToString() })
        $generatorExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($generatorExitCode -ne 0) {
        throw "rhwp gen-table failed with exit code ${generatorExitCode}: $($generatorOutput -join [Environment]::NewLine)"
    }

    $inputPath = Join-Path $workspace 'output\gen_table.hwp'
    if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) {
        throw "rhwp gen-table did not create the expected input: $inputPath"
    }
    $inputHashBefore = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash
    $outputDirectory = Join-Path $workspace 'extracted'
    $extractionSession = [pscustomobject]@{
        Path = $session.Path
        Version = $session.Version
        ExecutableSha256 = $session.ExecutableSha256
        ArchiveSha256 = $session.ArchiveSha256
        ReleaseUrl = $session.ReleaseUrl
        ChecksumUrl = $session.ChecksumUrl
        WorkspacePath = $null
        Temporary = $false
    }
    $toolResolver = { $extractionSession }.GetNewClosure()
    $manifest = Invoke-RhwpExtraction `
        -InputPath $inputPath `
        -OutputDirectory $outputDirectory `
        -Format both `
        -ToolResolver $toolResolver

    $textFiles = @(Get-ChildItem -LiteralPath (Join-Path $outputDirectory 'text') -Filter '*.txt')
    $markdownFiles = @(
        Get-ChildItem -LiteralPath (Join-Path $outputDirectory 'markdown') -Filter '*.md'
    )
    if ($textFiles.Count -ne 18 -or $markdownFiles.Count -ne 18) {
        throw "Expected 18 text and 18 Markdown pages; received $($textFiles.Count) and $($markdownFiles.Count)."
    }
    if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) {
        throw 'The extraction deleted its input HWP.'
    }
    $inputHashAfter = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash
    if ($inputHashAfter -cne $inputHashBefore -or $manifest.input.sha256 -cne $inputHashBefore) {
        throw 'The input HWP hash changed or does not match the manifest.'
    }

    foreach ($record in $manifest.outputs) {
        $relativePath = [string]$record.relative_path -replace '/', '\'
        $outputPath = Join-Path $outputDirectory $relativePath
        $actualHash = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash
        if ($actualHash -cne $record.sha256) {
            throw "Output hash mismatch: $($record.relative_path)"
        }
    }
    if ($manifest.tool.executable_sha256 -cne $session.ExecutableSha256) {
        throw 'Extraction manifest executable hash does not match the verified session.'
    }
    if ($manifest.tool.archive_sha256 -cne $session.ArchiveSha256) {
        throw 'Extraction manifest archive hash does not match the verified session.'
    }

    $corruptInputPath = Join-Path $workspace 'corrupt.hwp'
    $corruptOutputDirectory = Join-Path $workspace 'corrupt-extracted'
    [IO.File]::WriteAllBytes($corruptInputPath, [byte[]]@(1, 2, 3, 4))
    $corruptFailure = $null
    try {
        Invoke-RhwpExtraction `
            -InputPath $corruptInputPath `
            -OutputDirectory $corruptOutputDirectory `
            -Format text `
            -ToolResolver $toolResolver | Out-Null
    }
    catch {
        $corruptFailure = $_
    }
    if ($null -eq $corruptFailure) {
        throw 'A corrupt HWP unexpectedly produced a successful extraction.'
    }
    if (Test-Path -LiteralPath $corruptOutputDirectory) {
        throw 'A corrupt HWP published an output directory.'
    }
    if (-not (Test-Path -LiteralPath $corruptInputPath -PathType Leaf)) {
        throw 'A failed corrupt-HWP extraction deleted its input.'
    }

    $evidence = [ordered]@{
        version = $session.Version
        archive_sha256 = $session.ArchiveSha256
        executable_sha256 = $session.ExecutableSha256
        text_pages = $textFiles.Count
        markdown_pages = $markdownFiles.Count
        input_preserved = $true
        input_hash_verified = $true
        manifest_hashes_verified = $true
        manifest_archive_hash_verified = $true
        corrupt_input_failed_closed = $true
        retention_status = $manifest.retention_status
    }
}
catch {
    $failure = $_
}
finally {
    $cleanupErrors = [System.Collections.Generic.List[string]]::new()
    if ($null -ne $session) {
        try {
            Remove-RhwpToolSession -Session $session
        }
        catch {
            $cleanupErrors.Add($_.Exception.Message)
        }
    }

    $resolvedWorkspace = [IO.Path]::GetFullPath($workspace).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    $actualParent = [IO.Path]::GetDirectoryName($resolvedWorkspace)
    $actualLeaf = [IO.Path]::GetFileName($resolvedWorkspace)
    if (-not $actualParent.Equals($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $actualLeaf -notmatch '^rhwp-integration-[0-9a-f]{32}$') {
        $cleanupErrors.Add("Unsafe integration cleanup target: $resolvedWorkspace")
    }
    elseif (Test-Path -LiteralPath $resolvedWorkspace) {
        try {
            Remove-Item -LiteralPath $resolvedWorkspace -Recurse -Force
        }
        catch {
            $cleanupErrors.Add($_.Exception.Message)
        }
    }

    if ($cleanupErrors.Count -gt 0) {
        $primaryMessage = if ($null -eq $failure) { 'none' } else { $failure.Exception.Message }
        throw "Integration cleanup failed: $($cleanupErrors -join '; '); primary failure: $primaryMessage"
    }
}

if ($null -ne $failure) {
    throw $failure
}
$evidence | ConvertTo-Json -Depth 3
