[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [Parameter(Mandatory = $true)]
    [string]$ModelLockPath,

    [Parameter(Mandatory = $true)]
    [string]$ModelHome
)

$ErrorActionPreference = "Stop"

function Get-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }

    return [System.IO.Path]::GetFullPath(
        (Join-Path (Get-Location).Path $PathValue)
    )
}

function Resolve-ExistingFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $resolved = (Resolve-Path -LiteralPath $PathValue -ErrorAction Stop).Path
    $item = Get-Item -LiteralPath $resolved -Force -ErrorAction Stop
    if ($item.PSIsContainer) {
        throw "$Description must be an existing file: $resolved"
    }
    return [System.IO.Path]::GetFullPath($item.FullName)
}

function Resolve-ExistingDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $resolved = (Resolve-Path -LiteralPath $PathValue -ErrorAction Stop).Path
    $item = Get-Item -LiteralPath $resolved -Force -ErrorAction Stop
    if (-not $item.PSIsContainer) {
        throw "$Description must be an existing directory: $resolved"
    }
    return [System.IO.Path]::GetFullPath($item.FullName)
}

function Test-ReparsePoint {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.FileSystemInfo]$Item
    )

    return [bool](
        $Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint
    )
}

function Test-ExactRecoveryReceipt {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ReceiptPath,

        [Parameter(Mandatory = $true)]
        [string]$RecoveryToken
    )

    try {
        $receipt = Get-Item -LiteralPath $ReceiptPath -Force -ErrorAction Stop
        if ($receipt.PSIsContainer -or (Test-ReparsePoint $receipt)) {
            return $false
        }
        $utf8 = [System.Text.UTF8Encoding]::new($false, $true)
        $actual = [System.IO.File]::ReadAllText($receipt.FullName, $utf8)
        return $actual.Equals(
            $RecoveryToken,
            [System.StringComparison]::Ordinal
        )
    }
    catch {
        return $false
    }
}

function Test-TreeWithoutReparsePoints {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootPath
    )

    try {
        $root = Get-Item -LiteralPath $RootPath -Force -ErrorAction Stop
        if (-not $root.PSIsContainer -or (Test-ReparsePoint $root)) {
            return $false
        }

        $pending = [System.Collections.Generic.Stack[System.IO.DirectoryInfo]]::new()
        $pending.Push([System.IO.DirectoryInfo]$root)
        while ($pending.Count -gt 0) {
            $directory = $pending.Pop()
            foreach ($entry in $directory.GetFileSystemInfos()) {
                if (Test-ReparsePoint $entry) {
                    return $false
                }
                if ($entry -is [System.IO.DirectoryInfo]) {
                    $pending.Push($entry)
                }
            }
        }
        return $true
    }
    catch {
        return $false
    }
}

function Remove-ExactRecoveryStaging {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AbsoluteOutputDirectory,

        [Parameter(Mandatory = $true)]
        [string]$StagingNonce,

        [Parameter(Mandatory = $true)]
        [string]$RecoveryToken,

        [Parameter(Mandatory = $true)]
        [string]$ExactStagingPath,

        [Parameter(Mandatory = $true)]
        [string]$ReceiptPath
    )

    try {
        $parentDirectory = [System.IO.Path]::GetDirectoryName(
            $AbsoluteOutputDirectory
        )
        $outputName = [System.IO.Path]::GetFileName(
            $AbsoluteOutputDirectory
        )
        $expectedStagingName = ".$outputName.tmp-$StagingNonce"
        $expectedStagingPath = [System.IO.Path]::GetFullPath(
            (Join-Path $parentDirectory $expectedStagingName)
        )
        $expectedReceiptPath = [System.IO.Path]::GetFullPath(
            (Join-Path $parentDirectory ".$outputName.recovery-$StagingNonce")
        )
        if (
            -not $expectedStagingPath.Equals(
                [System.IO.Path]::GetFullPath($ExactStagingPath),
                [System.StringComparison]::OrdinalIgnoreCase
            ) -or
            -not $expectedReceiptPath.Equals(
                [System.IO.Path]::GetFullPath($ReceiptPath),
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            return
        }

        $parent = Get-Item -LiteralPath $parentDirectory -Force -ErrorAction Stop
        if (-not $parent.PSIsContainer -or (Test-ReparsePoint $parent)) {
            return
        }
        if (-not (Test-ExactRecoveryReceipt $ReceiptPath $RecoveryToken)) {
            return
        }

        $staging = Get-Item -LiteralPath $ExactStagingPath -Force -ErrorAction Stop
        if (-not $staging.PSIsContainer -or (Test-ReparsePoint $staging)) {
            return
        }
        if (
            -not $staging.Name.Equals(
                $expectedStagingName,
                [System.StringComparison]::Ordinal
            ) -or
            -not $staging.Parent.FullName.Equals(
                $parent.FullName,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            return
        }

        $ownerMarker = Join-Path $ExactStagingPath ".pdf-ocr-staging-owner"
        $marker = Get-Item -LiteralPath $ownerMarker -Force -ErrorAction SilentlyContinue
        if ($null -ne $marker) {
            if ($marker.PSIsContainer -or (Test-ReparsePoint $marker)) {
                return
            }
            $utf8 = [System.Text.UTF8Encoding]::new($false, $true)
            $ownerValue = [System.IO.File]::ReadAllText(
                $marker.FullName,
                $utf8
            )
            if (
                -not $ownerValue.Equals(
                    $RecoveryToken,
                    [System.StringComparison]::Ordinal
                )
            ) {
                return
            }
        }

        if (-not (Test-TreeWithoutReparsePoints $ExactStagingPath)) {
            return
        }
        if (-not (Test-ExactRecoveryReceipt $ReceiptPath $RecoveryToken)) {
            return
        }
        Remove-Item -LiteralPath $ExactStagingPath -Recurse -Force
    }
    catch {
        return
    }
}

function New-RecoveryReceipt {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ReceiptPath,

        [Parameter(Mandatory = $true)]
        [string]$RecoveryToken
    )

    $utf8 = [System.Text.UTF8Encoding]::new($false, $true)
    $bytes = $utf8.GetBytes($RecoveryToken)
    $stream = [System.IO.File]::Open(
        $ReceiptPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    }
    finally {
        $stream.Dispose()
    }
}

function Remove-ExactRecoveryReceipt {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ReceiptPath,

        [Parameter(Mandatory = $true)]
        [string]$RecoveryToken
    )

    if (Test-ExactRecoveryReceipt $ReceiptPath $RecoveryToken) {
        Remove-Item -LiteralPath $ReceiptPath -Force
    }
}

$repositoryRoot = (
    Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
).Path
$absoluteInputPath = Resolve-ExistingFile $InputPath "input PDF"
$absoluteModelLockPath = Resolve-ExistingFile $ModelLockPath "model lock"
$absoluteModelHome = Resolve-ExistingDirectory $ModelHome "model home"
$absoluteUvLockPath = Resolve-ExistingFile (
    Join-Path $repositoryRoot "tools\pdf-ocr\uv.lock"
) "uv lock"
$absoluteOutputDirectory = Get-AbsolutePath $OutputDirectory
$outputParentPath = [System.IO.Path]::GetDirectoryName(
    $absoluteOutputDirectory
)
[System.IO.Directory]::CreateDirectory($outputParentPath) | Out-Null
$outputParent = Get-Item -LiteralPath $outputParentPath -Force
if (Test-ReparsePoint $outputParent) {
    throw "output parent must not be a reparse point: $outputParentPath"
}
$absoluteOutputDirectory = Join-Path (
    [System.IO.Path]::GetFullPath($outputParent.FullName)
) ([System.IO.Path]::GetFileName($absoluteOutputDirectory))

Get-Command uv -ErrorAction Stop | Out-Null

$stagingNonce = [System.Guid]::NewGuid().ToString("N")
$recoveryToken = (
    [System.Guid]::NewGuid().ToString("N") +
    [System.Guid]::NewGuid().ToString("N")
)
$outputName = [System.IO.Path]::GetFileName($absoluteOutputDirectory)
$exactStagingPath = Join-Path (
    [System.IO.Path]::GetDirectoryName($absoluteOutputDirectory)
) ".$outputName.tmp-$stagingNonce"
$recoveryReceiptPath = Join-Path (
    [System.IO.Path]::GetDirectoryName($absoluteOutputDirectory)
) ".$outputName.recovery-$stagingNonce"

New-RecoveryReceipt $recoveryReceiptPath $recoveryToken

$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:UV_OFFLINE = "1"
$env:PDF_OCR_MODEL_HOME = $absoluteModelHome
$env:DOCLING_ARTIFACTS_PATH = $absoluteModelHome
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PDF_OCR_RECOVERY_TOKEN = $recoveryToken
$env:PDF_OCR_STAGING_NONCE = $stagingNonce
$env:PDF_OCR_STAGING_PATH = $exactStagingPath
$env:PDF_OCR_RECOVERY_RECEIPT = $recoveryReceiptPath

$commandExitCode = 1
Push-Location $repositoryRoot
try {
    & uv run `
        --frozen `
        --project "tools/pdf-ocr" `
        python -m pdf_ocr.cli `
        --input $absoluteInputPath `
        --output $absoluteOutputDirectory `
        --model-lock $absoluteModelLockPath `
        --model-home $absoluteModelHome `
        --uv-lock $absoluteUvLockPath
    $commandExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($commandExitCode -ne 0 -and $commandExitCode -ne 1) {
    Remove-ExactRecoveryStaging `
        $absoluteOutputDirectory `
        $stagingNonce `
        $recoveryToken `
        $exactStagingPath `
        $recoveryReceiptPath
}
Remove-ExactRecoveryReceipt $recoveryReceiptPath $recoveryToken
exit $commandExitCode
