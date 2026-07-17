[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$InputPath,

    [Parameter(Mandatory)]
    [string]$OutputDirectory,

    [ValidateSet('text', 'markdown', 'both')]
    [string]$Format = 'both',

    [string]$RhwpPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'RhwpPipeline.psm1') -Force

Invoke-RhwpExtraction `
    -InputPath $InputPath `
    -OutputDirectory $OutputDirectory `
    -Format $Format `
    -RhwpPath $RhwpPath |
    ConvertTo-Json -Depth 8
