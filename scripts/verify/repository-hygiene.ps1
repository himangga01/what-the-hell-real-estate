[CmdletBinding()]
param(
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
    throw 'Run this script inside the Git repository.'
}
$repoRoot = $repoRoot.Trim()

$issues = [System.Collections.Generic.List[string]]::new()

function Test-RequiredLines {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string[]]$RequiredLines
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        $issues.Add("Missing ignore file: $Path")
        return
    }

    $actual = @(Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object { $_.Trim() })
    foreach ($line in $RequiredLines) {
        if ($line -notin $actual) {
            $issues.Add("Missing required pattern '$line' in $Path")
        }
    }
}

function Test-GitIgnored {
    param([Parameter(Mandatory)] [string]$RelativePath)

    & git -C $repoRoot check-ignore -q --no-index -- $RelativePath
    return $LASTEXITCODE -eq 0
}

$gitIgnore = Join-Path $repoRoot '.gitignore'
$dockerIgnore = Join-Path $repoRoot '.dockerignore'

Test-RequiredLines -Path $gitIgnore -RequiredLines @(
    '.env',
    '.env.*',
    '**/.env',
    '**/.env.*',
    '!.env.example',
    '!**/.env.example',
    '__pycache__/',
    '*.py[cod]',
    '.venv/',
    '.pytest_cache/',
    '.ruff_cache/',
    '.mypy_cache/',
    '.pyright/',
    'htmlcov/',
    '*.egg-info/',
    'node_modules/',
    '.npm/',
    'dist/',
    'build/',
    'coverage/',
    'playwright-report/',
    'test-results/',
    'blob-report/',
    '*.log',
    '*.pem',
    '*.key',
    '*.p12',
    '*.pfx',
    'secrets/',
    '**/secrets/',
    '.worktrees/',
    'worktrees/',
    '.superpowers/'
)

Test-RequiredLines -Path $dockerIgnore -RequiredLines @(
    '.git',
    '**/.env',
    '**/.env.*',
    '!**/.env.example',
    '*.pem',
    '*.key',
    '*.p12',
    '*.pfx',
    'secrets/',
    '**/secrets/',
    '**/__pycache__',
    '**/.venv',
    '**/node_modules',
    '**/dist',
    '**/coverage'
)

$mustBeIgnored = @(
    '.env',
    'backend/.env',
    'frontend/.env.local',
    '.venv/pyvenv.cfg',
    'backend/__pycache__/module.pyc',
    'backend/.pytest_cache/v/cache/nodeids',
    'backend/.ruff_cache/cache.db',
    'backend/.mypy_cache/cache.json',
    'backend/.pyright/index.json',
    'backend/htmlcov/index.html',
    'backend/example.egg-info/PKG-INFO',
    'frontend/node_modules/package/index.js',
    'frontend/.npm/_cacache/index-v5/entry',
    'frontend/dist/assets/app.js',
    'coverage/index.html',
    'playwright-report/index.html',
    'test-results/result.json',
    'blob-report/report.zip',
    'backend/secrets/api-token',
    'certificate.pem',
    'private.key',
    'service.log',
    '.idea/workspace.xml',
    '.vscode/settings.json',
    '.worktrees/feature/file.txt',
    '.superpowers/sdd/progress.md'
)

foreach ($path in $mustBeIgnored) {
    if (-not (Test-GitIgnored -RelativePath $path)) {
        $issues.Add("Path is not ignored: $path")
    }
}

$mustRemainTrackable = @(
    'backend/.env.example',
    'frontend/.env.example',
    'backend/uv.lock',
    'frontend/package-lock.json'
)

foreach ($path in $mustRemainTrackable) {
    if (Test-GitIgnored -RelativePath $path) {
        $issues.Add("Required project file is ignored: $path")
    }
}

$ignoredTrackedPaths = @(& git -C $repoRoot ls-files -ci --exclude-standard)
foreach ($path in $ignoredTrackedPaths) {
    $issues.Add("Ignored path is already tracked: $path")
}

$trackedPaths = @(& git -C $repoRoot ls-files)
foreach ($path in $trackedPaths) {
    $isEnvironmentSecret = $path -match '(^|/)\.env($|\.)' -and $path -notmatch '(^|/)\.env\.example$'
    $isPrivateKey = $path -match '\.(pem|key|p12|pfx)$'
    $isGeneratedDirectory = $path -match '(^|/)(node_modules|__pycache__|\.venv|venv|dist|build|coverage|playwright-report|test-results)/'

    if ($isEnvironmentSecret -or $isPrivateKey -or $isGeneratedDirectory) {
        $issues.Add("Forbidden tracked path: $path")
    }
}

if ($issues.Count -gt 0) {
    $issues | ForEach-Object { Write-Error $_ -ErrorAction Continue }
    exit 1
}

if (-not $Quiet) {
    Write-Output "Repository hygiene check passed: $($mustBeIgnored.Count) ignored-path probes and $($mustRemainTrackable.Count) trackable-path probes."
}
