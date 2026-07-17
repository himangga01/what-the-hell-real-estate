[CmdletBinding()]
param(
    [string]$RhwpPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'RhwpPipeline.psm1') -Force

$session = $null
try {
    $session = New-RhwpToolSession -RhwpPath $RhwpPath
    [ordered]@{
        version = $session.Version
        executable_sha256 = $session.ExecutableSha256
        archive_sha256 = $session.ArchiveSha256
        release_url = $session.ReleaseUrl
        checksum_url = $session.ChecksumUrl
        temporary = $session.Temporary
    } | ConvertTo-Json -Depth 3
}
finally {
    if ($null -ne $session) {
        Remove-RhwpToolSession -Session $session
    }
}
