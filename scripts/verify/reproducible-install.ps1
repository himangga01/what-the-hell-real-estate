[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-NormalizedFullPath {
    param([Parameter(Mandatory)] [string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd([char[]]@('\', '/'))
}

function Test-PathIsNested {
    param(
        [Parameter(Mandatory)] [string]$ParentPath,
        [Parameter(Mandatory)] [string]$ChildPath
    )

    $normalizedParent = Get-NormalizedFullPath -Path $ParentPath
    $normalizedChild = Get-NormalizedFullPath -Path $ChildPath
    $prefix = $normalizedParent + [System.IO.Path]::DirectorySeparatorChar

    return $normalizedChild.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [string[]]$Arguments,
        [Parameter(Mandatory)] [string]$WorkingDirectory
    )

    Push-Location -LiteralPath $WorkingDirectory
    try {
        & $FilePath @Arguments
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($exitCode -ne 0) {
        throw "Command failed with exit code ${exitCode}: $FilePath $($Arguments -join ' ')"
    }
}

function Resolve-ApplicationCommand {
    param([Parameter(Mandatory)] [string[]]$Candidates)

    foreach ($candidate in $Candidates) {
        $command = Get-Command -Name $candidate -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -ne $command) {
            return $command.Path
        }
    }

    throw "Required command was not found: $($Candidates -join ', ')"
}

function Assert-TemporaryWorkspace {
    param(
        [Parameter(Mandatory)] [string]$WorkspacePath,
        [Parameter(Mandatory)] [string]$ExpectedParent,
        [Parameter(Mandatory)] [string]$ExpectedLeaf,
        [Parameter(Mandatory)] [string]$SentinelPath,
        [Parameter(Mandatory)] [string]$OwnershipToken
    )

    $normalizedWorkspace = Get-NormalizedFullPath -Path $WorkspacePath
    $normalizedParent = Get-NormalizedFullPath -Path $ExpectedParent
    $actualParent = Get-NormalizedFullPath -Path ([System.IO.Directory]::GetParent($normalizedWorkspace).FullName)
    $actualLeaf = [System.IO.Path]::GetFileName($normalizedWorkspace)

    if (-not $actualParent.Equals($normalizedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing unsafe cleanup: temporary parent mismatch for $normalizedWorkspace"
    }
    if ($actualLeaf -cne $ExpectedLeaf) {
        throw "Refusing unsafe cleanup: temporary leaf mismatch for $normalizedWorkspace"
    }
    if ($actualLeaf -notmatch '^what-the-hell-real-estate-repro-[0-9a-f]{32}$') {
        throw "Refusing unsafe cleanup: temporary leaf is not an owned GUID workspace: $actualLeaf"
    }
    if (-not (Test-Path -LiteralPath $SentinelPath -PathType Leaf)) {
        throw "Refusing unsafe cleanup: ownership sentinel is missing from $normalizedWorkspace"
    }

    $actualToken = (Get-Content -LiteralPath $SentinelPath -Raw -Encoding UTF8).Trim()
    if ($actualToken -cne $OwnershipToken) {
        throw "Refusing unsafe cleanup: ownership sentinel does not match for $normalizedWorkspace"
    }
}

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

$repository = Get-NormalizedFullPath -Path $RepositoryRoot
if (-not (Test-Path -LiteralPath $repository -PathType Container)) {
    throw "Repository root does not exist: $repository"
}

$sourcePaths = [ordered]@{
    'backend/pyproject.toml'       = Join-Path $repository 'backend/pyproject.toml'
    'backend/uv.lock'             = Join-Path $repository 'backend/uv.lock'
    'frontend/package.json'       = Join-Path $repository 'frontend/package.json'
    'frontend/package-lock.json'  = Join-Path $repository 'frontend/package-lock.json'
}

$missingPaths = @($sourcePaths.GetEnumerator() | Where-Object {
        -not (Test-Path -LiteralPath $_.Value -PathType Leaf)
    } | ForEach-Object { $_.Key })
if ($missingPaths.Count -gt 0) {
    throw "Missing reproducibility input(s): $($missingPaths -join ', ')"
}

$sourceHashes = @{}
foreach ($entry in $sourcePaths.GetEnumerator()) {
    $sourceHashes[$entry.Key] = (Get-FileHash -LiteralPath $entry.Value -Algorithm SHA256).Hash
}

$uvExecutable = Resolve-ApplicationCommand -Candidates @('uv.exe', 'uv')
$npmExecutable = Resolve-ApplicationCommand -Candidates @('npm.cmd', 'npm')

$tempParent = Get-NormalizedFullPath -Path ([System.IO.Path]::GetTempPath())
$workspaceId = [System.Guid]::NewGuid().ToString('N')
$workspaceLeaf = "what-the-hell-real-estate-repro-$workspaceId"
$workspace = Join-Path $tempParent $workspaceLeaf
$ownershipToken = "what-the-hell-real-estate:$workspaceId"
$sentinel = Join-Path $workspace '.reproducible-install-owned'
$backendWorkspace = Join-Path $workspace 'backend'
$frontendWorkspace = Join-Path $workspace 'frontend'
$primaryFailure = $null

try {
    if (Test-Path -LiteralPath $workspace) {
        throw "Refusing to reuse an existing temporary workspace: $workspace"
    }
    if (-not (Test-PathIsNested -ParentPath $tempParent -ChildPath $workspace)) {
        throw "Temporary workspace is not nested below the OS temporary directory: $workspace"
    }
    if (Test-PathIsNested -ParentPath $repository -ChildPath $workspace) {
        throw "Temporary workspace must not be created below the repository: $workspace"
    }

    New-Item -ItemType Directory -Path $backendWorkspace -Force | Out-Null
    New-Item -ItemType Directory -Path $frontendWorkspace -Force | Out-Null
    Set-Content -LiteralPath $sentinel -Value $ownershipToken -Encoding UTF8 -NoNewline

    Assert-TemporaryWorkspace `
        -WorkspacePath $workspace `
        -ExpectedParent $tempParent `
        -ExpectedLeaf $workspaceLeaf `
        -SentinelPath $sentinel `
        -OwnershipToken $ownershipToken

    if (-not (Test-PathIsNested -ParentPath $workspace -ChildPath $backendWorkspace)) {
        throw "Backend workspace escaped the owned temporary directory: $backendWorkspace"
    }
    if (-not (Test-PathIsNested -ParentPath $workspace -ChildPath $frontendWorkspace)) {
        throw "Frontend workspace escaped the owned temporary directory: $frontendWorkspace"
    }

    Copy-Item -LiteralPath $sourcePaths['backend/pyproject.toml'] -Destination $backendWorkspace
    Copy-Item -LiteralPath $sourcePaths['backend/uv.lock'] -Destination $backendWorkspace
    Copy-Item -LiteralPath $sourcePaths['frontend/package.json'] -Destination $frontendWorkspace
    Copy-Item -LiteralPath $sourcePaths['frontend/package-lock.json'] -Destination $frontendWorkspace

    Invoke-CheckedCommand `
        -FilePath $uvExecutable `
        -Arguments @('lock', '--check', '--python', '3.14', '--no-python-downloads') `
        -WorkingDirectory $backendWorkspace
    Invoke-CheckedCommand `
        -FilePath $uvExecutable `
        -Arguments @('sync', '--locked', '--all-groups', '--python', '3.14', '--no-python-downloads') `
        -WorkingDirectory $backendWorkspace

    $pythonCandidates = @(
        (Join-Path $backendWorkspace '.venv/Scripts/python.exe'),
        (Join-Path $backendWorkspace '.venv/bin/python'),
        (Join-Path $backendWorkspace '.venv/bin/python3')
    )
    $backendPython = $pythonCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($backendPython)) {
        throw "uv did not create a supported temporary Python executable below $backendWorkspace/.venv"
    }
    Invoke-CheckedCommand `
        -FilePath $backendPython `
        -Arguments @(
            '-c',
            'import compileall, fastapi, sqlalchemy, pydantic, psycopg, alembic, pytest, hypothesis, check_jsonschema; assert compileall.compile_dir(fastapi.__path__[0], quiet=1, force=True); print(fastapi.__name__, pytest.__name__, hypothesis.__name__, check_jsonschema.__name__)'
        ) `
        -WorkingDirectory $backendWorkspace
    Invoke-CheckedCommand `
        -FilePath $uvExecutable `
        -Arguments @('run', '--locked', '--no-sync', 'ruff', '--version') `
        -WorkingDirectory $backendWorkspace
    Invoke-CheckedCommand `
        -FilePath $uvExecutable `
        -Arguments @('run', '--locked', '--no-sync', 'pyright', '--version') `
        -WorkingDirectory $backendWorkspace
    Invoke-CheckedCommand `
        -FilePath $uvExecutable `
        -Arguments @('run', '--locked', '--no-sync', 'check-jsonschema', '--version') `
        -WorkingDirectory $backendWorkspace

    Invoke-CheckedCommand `
        -FilePath $npmExecutable `
        -Arguments @('ci', '--ignore-scripts', '--no-audit', '--no-fund') `
        -WorkingDirectory $frontendWorkspace
    Invoke-CheckedCommand `
        -FilePath $npmExecutable `
        -Arguments @('ls', '--depth=0') `
        -WorkingDirectory $frontendWorkspace
}
catch {
    $primaryFailure = $_
}
finally {
    $cleanupFailure = $null
    if (Test-Path -LiteralPath $workspace) {
        try {
            Assert-TemporaryWorkspace `
                -WorkspacePath $workspace `
                -ExpectedParent $tempParent `
                -ExpectedLeaf $workspaceLeaf `
                -SentinelPath $sentinel `
                -OwnershipToken $ownershipToken
            Remove-Item -LiteralPath $workspace -Recurse -Force
        }
        catch {
            $cleanupFailure = $_
        }
    }

    $changedSources = @()
    foreach ($entry in $sourcePaths.GetEnumerator()) {
        if (-not (Test-Path -LiteralPath $entry.Value -PathType Leaf)) {
            $changedSources += $entry.Key
            continue
        }

        $currentHash = (Get-FileHash -LiteralPath $entry.Value -Algorithm SHA256).Hash
        if ($currentHash -cne $sourceHashes[$entry.Key]) {
            $changedSources += $entry.Key
        }
    }

    if ($changedSources.Count -gt 0) {
        $hashFailure = "Source reproducibility input changed during verification: $($changedSources -join ', ')"
        if ($null -ne $primaryFailure) {
            $hashFailure += "; original failure: $($primaryFailure.Exception.Message)"
        }
        $primaryFailure = [System.Management.Automation.RuntimeException]::new($hashFailure)
    }

    if ($null -ne $cleanupFailure) {
        $cleanupMessage = "Temporary workspace cleanup failed: $($cleanupFailure.Exception.Message)"
        if ($null -ne $primaryFailure) {
            $cleanupMessage += "; original failure: $($primaryFailure.Exception.Message)"
        }
        throw $cleanupMessage
    }
}

if ($null -ne $primaryFailure) {
    throw $primaryFailure
}

Write-Output 'Reproducible installation verified for backend and frontend; source hashes are unchanged.'
