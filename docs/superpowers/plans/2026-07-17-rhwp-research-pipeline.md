# rhwp 조사 파이프라인 구현 계획

> **에이전트 작업자용:** 구현 시 작업별 테스트-구현-검증-커밋 순서를 지킨다.
> **REQUIRED SUB-SKILL:** 인라인 구현에는 `superpowers:executing-plans`와
> `superpowers:test-driven-development`를 사용한다.

**목표:** 공식 `edwardkim/rhwp` `v0.7.18` 배포물을 체크섬으로 검증하고, HWP를 임시로
텍스트·Markdown으로 추출하면서 입력·도구·출력 SHA-256 매니페스트를 남기는 fail-closed
조사 도구를 만든다.

**아키텍처:** `RhwpPipeline.psm1`이 릴리스 메타데이터, 검증된 임시 도구 세션, 추출과
매니페스트 생성의 단일 구현을 제공한다. 두 개의 얇은 `.ps1` 진입점은 모듈을 호출하며,
단위 테스트는 네트워크와 실행기를 주입해 격리하고 통합 테스트만 공식 GitHub 릴리스와
`rhwp gen-table`이 생성한 임시 HWP를 사용한다.

**기술 스택:** Windows PowerShell 5.1 호환 PowerShell, `rhwp v0.7.18`, SHA-256,
JSON, GitHub Releases, 프레임워크 비의존 PowerShell 테스트 하네스

## 전역 제약

- `rhwp` 버전은 `v0.7.18`로 고정한다.
- 공식 릴리스 URL은 `https://github.com/edwardkim/rhwp/releases/download/v0.7.18/`만
  시작점으로 허용한다.
- Windows x86_64 자산명은 `rhwp-v0.7.18-windows-x86_64.zip`이고 공식
  `SHA256SUMS.txt` 기준 SHA-256은
  `BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD`다.
- 자동 리디렉션을 끄고 각 hop을 요청하기 전에 `github.com`,
  `objects.githubusercontent.com`, `release-assets.githubusercontent.com`인지 검사한다.
- 체크섬, 버전, 파싱, 빈 출력, 페이지 연속성, 임시 정리 중 하나라도 실패하면 성공
  매니페스트를 만들지 않는다.
- `.hwpx` 텍스트 추출은 `v0.7.18`의 고정 통합 테스트가 별도로 통과하기 전까지
  비활성화한다.
- 사용자 입력 원문은 도구가 삭제하지 않는다.
- 원문 권리 승인 전 추출물 보존 상태는 `TEMPORARY_NOT_RETAINED`다.
- 저장소에 정부기관 HWP 원문이나 추출 전문을 fixture로 커밋하지 않는다.
- 생성·수정하는 Markdown은 한국어 설명을 먼저 두고, 마지막에 `English AI Context`를 둔다.

## 승인 후 코드 검토 보완

2026-07-17 코드 검토에서 입력 증거와 게시 경계를 더 엄격하게 만들었다. 입력 크기와
SHA-256은 도구 실행 전에 고정하고 실행 후 다시 대조한다. 허용한 페이지 이외의 파일·하위
디렉터리는 게시하지 않으며 내부 소유권 표식도 최종 출력에서 제거한다. 출력 디렉터리는
동일 경로 경쟁 상태를 덮어쓰지 않는 원자 이동으로 게시한다. GitHub 리디렉션은 각 hop을
요청하기 전에 허용 호스트인지 검사한다. 이 보완은 단위 테스트 25건과 공식 릴리스 기반
18페이지 text·Markdown 통합 테스트로 검증했다.
성공 명령의 도구 진단 메시지도 매니페스트에 기록하며, 실행 중 생성한 손상 HWP가 결과를
게시하지 않는 실제 `v0.7.18` 경로를 같은 통합 테스트에서 확인했다.
Windows PowerShell 5.1 단위 테스트와 로컬 302 기본 HTTP 경로는 필수 CI에 연결하고,
공식 GitHub 릴리스 통합 테스트는 `workflow_dispatch`에서 실행하는 비필수 작업으로 분리했다.

아래 작업별 코드 블록은 RED 테스트를 만들 당시의 시작점 기록이다. 코드 검토 보완 이후의
보안 경계는 이 절과 실제 `scripts/research/RhwpPipeline.psm1`을 기준으로 하며, 특히 아래
Step 3의 자동 리디렉션 예시는 사용하지 않는다.

## 파일 구조

| 경로 | 책임 |
|---|---|
| `scripts/research/RhwpPipeline.psm1` | 릴리스 선택, 다운로드·체크섬·버전 검증, 안전한 임시 세션, 추출·매니페스트 |
| `scripts/research/rhwp-tool.ps1` | 공식 도구를 검증한 뒤 메타데이터 JSON을 출력하고 임시 파일을 정리하는 진입점 |
| `scripts/research/extract-hwp.ps1` | 입력·출력·형식을 받아 원자적 추출을 수행하는 진입점 |
| `scripts/research/tests/Invoke-RhwpPipelineTests.ps1` | 외부 테스트 프레임워크 없이 실행하는 격리 단위 테스트 |
| `scripts/research/tests/Invoke-RhwpIntegrationTest.ps1` | 공식 릴리스와 `gen-table` 임시 HWP를 이용한 네트워크 통합 테스트 |
| `THIRD_PARTY_NOTICES.md` | `rhwp` 버전·저작권·MIT 라이선스·사용 범위 고지 |
| `specs/001-real-estate-policy-dashboard/source-register.md` | 조사 도구 버전·배포물/실행 파일 해시와 임시 추출 증거 |
| `specs/001-real-estate-policy-dashboard/research-data/README.md` | HWP 조사 실행법과 보존 상태 해석 |
| `specs/001-real-estate-policy-dashboard/checklists/research-readiness.md` | 자동 무결성 검증과 사람 검수의 분리된 게이트 |

---

### Task 1: 릴리스 계약과 체크섬 검증

**Files:**

- Create: `scripts/research/RhwpPipeline.psm1`
- Create: `scripts/research/tests/Invoke-RhwpPipelineTests.ps1`

**Interfaces:**

- Produces: `Get-RhwpReleaseDescriptor -Platform <windows|linux|macos> -Architecture
  <x86_64|aarch64> -> PSCustomObject`
- Produces: `Test-RhwpAllowedHost -Uri <uri> -> bool`
- Produces: `Get-RhwpExpectedChecksum -ChecksumPath <path> -AssetName <name> -> string`
- Produces: `Assert-RhwpArchiveChecksum -ArchivePath <path> -ExpectedSha256 <hash> -> void`

- [ ] **Step 1: 실패하는 릴리스 계약 테스트 작성**

`scripts/research/tests/Invoke-RhwpPipelineTests.ps1`에 자체 assertion과 다음 테스트를 작성한다.

```powershell
[CmdletBinding()]
param([switch]$Integration)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\RhwpPipeline.psm1') -Force

$script:Passed = 0
$script:Failed = 0

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -cne $Expected) {
        throw "$Message; expected='$Expected', actual='$Actual'"
    }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-ThrowsLike {
    param([scriptblock]$Action, [string]$Pattern)
    try { & $Action }
    catch {
        if ($_.Exception.Message -notlike $Pattern) {
            throw "Expected '$Pattern', received '$($_.Exception.Message)'"
        }
        return
    }
    throw "Expected exception matching '$Pattern'"
}

function Invoke-Test {
    param([string]$Name, [scriptblock]$Body)
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

Invoke-Test 'Windows release descriptor is pinned' {
    $release = Get-RhwpReleaseDescriptor -Platform windows -Architecture x86_64
    Assert-Equal $release.Version 'v0.7.18' 'Version must be pinned'
    Assert-Equal $release.AssetName 'rhwp-v0.7.18-windows-x86_64.zip' 'Wrong asset'
    Assert-Equal $release.ArchiveType 'zip' 'Wrong archive type'
}

Invoke-Test 'Only GitHub release hosts are accepted' {
    Assert-True (Test-RhwpAllowedHost -Uri 'https://github.com/a') 'github.com rejected'
    Assert-True (Test-RhwpAllowedHost -Uri 'https://release-assets.githubusercontent.com/a') 'release asset host rejected'
    Assert-True (-not (Test-RhwpAllowedHost -Uri 'https://example.com/a')) 'Untrusted host accepted'
}

Invoke-Test 'Exact asset checksum is selected' {
    $dir = Join-Path ([IO.Path]::GetTempPath()) ('rhwp-unit-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
        $sum = Join-Path $dir 'SHA256SUMS.txt'
        Set-Content -LiteralPath $sum -Encoding Ascii -Value (
            'bd0b3280c0b87580bfc8c86af337609acf939c5f8f1da6ab3ee73955064420fd  rhwp-v0.7.18-windows-x86_64.zip'
        )
        $actual = Get-RhwpExpectedChecksum -ChecksumPath $sum -AssetName 'rhwp-v0.7.18-windows-x86_64.zip'
        Assert-Equal $actual 'BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD' 'Checksum parsing failed'
    }
    finally { Remove-Item -LiteralPath $dir -Recurse -Force }
}

Invoke-Test 'Modified archive is rejected' {
    $file = [IO.Path]::GetTempFileName()
    try {
        Set-Content -LiteralPath $file -Encoding Ascii -Value 'modified'
        Assert-ThrowsLike {
            Assert-RhwpArchiveChecksum -ArchivePath $file -ExpectedSha256 ('0' * 64)
        } '*checksum mismatch*'
    }
    finally { Remove-Item -LiteralPath $file -Force }
}
```

- [ ] **Step 2: 테스트를 실행해 모듈 부재 실패 확인**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/research/tests/Invoke-RhwpPipelineTests.ps1
```

Expected: exit code `1`, `RhwpPipeline.psm1` 또는 함수가 없다는 오류.

- [ ] **Step 3: 최소 릴리스·체크섬 구현 작성**

`scripts/research/RhwpPipeline.psm1`에 고정 릴리스 계약과 순수 검증 함수를 구현한다.

```powershell
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
        [Parameter(Mandatory)] [ValidateSet('windows', 'linux', 'macos')] [string]$Platform,
        [Parameter(Mandatory)] [ValidateSet('x86_64', 'aarch64')] [string]$Architecture
    )

    if ($Platform -eq 'linux' -and $Architecture -eq 'aarch64') {
        throw 'rhwp v0.7.18 has no official linux-aarch64 release asset.'
    }
    if ($Platform -eq 'windows' -and $Architecture -eq 'aarch64') {
        throw 'rhwp v0.7.18 has no official windows-aarch64 release asset.'
    }

    $extension = if ($Platform -eq 'windows') { 'zip' } else { 'tar.gz' }
    $assetName = "rhwp-$($script:RhwpVersion)-$Platform-$Architecture.$extension"
    [pscustomobject]@{
        Version = $script:RhwpVersion
        AssetName = $assetName
        ArchiveType = $extension
        AssetUrl = "$($script:RhwpReleaseBase)/$assetName"
        ChecksumUrl = "$($script:RhwpReleaseBase)/SHA256SUMS.txt"
    }
}

function Test-RhwpAllowedHost {
    [CmdletBinding()]
    param([Parameter(Mandatory)] [uri]$Uri)
    return $Uri.Scheme -eq 'https' -and $Uri.Host -cin $script:RhwpAllowedHosts
}

function Get-RhwpExpectedChecksum {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$ChecksumPath,
        [Parameter(Mandatory)] [string]$AssetName
    )

    $matches = @(Get-Content -LiteralPath $ChecksumPath -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^(?<hash>[0-9a-fA-F]{64})\s+\*?(?<name>.+)$' -and $Matches.name -ceq $AssetName) {
            $Matches.hash.ToUpperInvariant()
        }
    })
    if ($matches.Count -ne 1) {
        throw "Expected exactly one checksum for $AssetName; found $($matches.Count)."
    }
    return $matches[0]
}

function Assert-RhwpArchiveChecksum {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$ArchivePath,
        [Parameter(Mandatory)] [ValidatePattern('^[0-9A-Fa-f]{64}$')] [string]$ExpectedSha256
    )

    $actual = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash
    if ($actual -cne $ExpectedSha256.ToUpperInvariant()) {
        throw "rhwp archive checksum mismatch: expected $ExpectedSha256, actual $actual"
    }
}

Export-ModuleMember -Function @(
    'Get-RhwpReleaseDescriptor',
    'Test-RhwpAllowedHost',
    'Get-RhwpExpectedChecksum',
    'Assert-RhwpArchiveChecksum'
)
```

- [ ] **Step 4: 단위 테스트 통과 확인**

Run: 위와 같은 테스트 명령.

Expected: `PASS` 4개, `Failed=0`, exit code `0`. 테스트 파일 끝에는 다음 집계를 추가한다.

```powershell
Write-Output "RESULT Passed=$script:Passed Failed=$script:Failed"
if ($script:Failed -gt 0) { exit 1 }
```

- [ ] **Step 5: Task 1 커밋**

```powershell
git add scripts/research/RhwpPipeline.psm1 scripts/research/tests/Invoke-RhwpPipelineTests.ps1
git commit -m "test: define pinned rhwp release contract"
```

---

### Task 2: 검증된 임시 도구 세션

**Files:**

- Modify: `scripts/research/RhwpPipeline.psm1`
- Modify: `scripts/research/tests/Invoke-RhwpPipelineTests.ps1`
- Create: `scripts/research/rhwp-tool.ps1`

**Interfaces:**

- Consumes: Task 1의 릴리스 descriptor와 체크섬 함수
- Produces: `New-RhwpToolSession [-RhwpPath <path>] [-DownloadFile <scriptblock>] -> PSCustomObject`
- Produces: `Remove-RhwpToolSession -Session <object> -> void`
- Session fields: `Path`, `Version`, `ExecutableSha256`, `ArchiveSha256`, `ReleaseUrl`,
  `ChecksumUrl`, `WorkspacePath`, `Temporary`

- [ ] **Step 1: 도구 세션의 실패 테스트 작성**

다음 테스트를 단위 테스트 파일의 결과 집계 전에 추가한다. fake downloader는 실제 네트워크를
사용하지 않으며, 변조된 archive가 압축 해제 전에 차단되는지 검증한다.

```powershell
Invoke-Test 'Tool session rejects archive before expansion' {
    $download = {
        param([uri]$Uri, [string]$Destination)
        if ($Destination -like '*SHA256SUMS.txt') {
            Set-Content -LiteralPath $Destination -Encoding Ascii -Value (
                ('0' * 64) + '  rhwp-v0.7.18-windows-x86_64.zip'
            )
        }
        else {
            Set-Content -LiteralPath $Destination -Encoding Ascii -Value 'tampered archive'
        }
        return [uri]'https://release-assets.githubusercontent.com/fake'
    }

    Assert-ThrowsLike {
        New-RhwpToolSession -Platform windows -Architecture x86_64 -DownloadFile $download
    } '*checksum mismatch*'
}

Invoke-Test 'Local executable must report pinned version' {
    $fake = Join-Path ([IO.Path]::GetTempPath()) ('fake-rhwp-' + [Guid]::NewGuid().ToString('N') + '.exe')
    try {
        Set-Content -LiteralPath $fake -Encoding Ascii -Value 'not executable'
        Assert-ThrowsLike { New-RhwpToolSession -RhwpPath $fake } '*version*'
    }
    finally { Remove-Item -LiteralPath $fake -Force }
}
```

- [ ] **Step 2: 새 테스트가 실패하는지 확인**

Run: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
scripts/research/tests/Invoke-RhwpPipelineTests.ps1`

Expected: `New-RhwpToolSession` 미정의로 새 테스트 2개 실패.

- [ ] **Step 3: 안전한 다운로드·압축 해제·버전 검증 구현**

모듈에 다음 동작을 구현한다.

```powershell
function Invoke-RhwpDownload {
    param([uri]$Uri, [string]$Destination)
    # 실제 구현은 System.Net.Http의 자동 리디렉션을 끈다.
    # 최초 URL과 각 Location을 다음 요청 전에 허용목록으로 검사한다.
    # 최대 10 hop, 비허용 호스트, 비정상 HTTP 상태와 부분 파일은 fail-closed 처리한다.
    # 정확한 승인 구현은 scripts/research/RhwpPipeline.psm1을 기준으로 한다.
    if (-not (Test-RhwpAllowedHost -Uri $Uri)) {
        throw "Untrusted rhwp download URI: $Uri"
    }
}

function New-RhwpToolSession {
    [CmdletBinding()]
    param(
        [string]$RhwpPath,
        [ValidateSet('windows', 'linux', 'macos')] [string]$Platform = 'windows',
        [ValidateSet('x86_64', 'aarch64')] [string]$Architecture = 'x86_64',
        [scriptblock]$DownloadFile = ${function:Invoke-RhwpDownload}
    )

    if ($RhwpPath) {
        $resolved = (Resolve-Path -LiteralPath $RhwpPath -ErrorAction Stop).Path
        $version = (& $resolved --version 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $version -cne 'rhwp v0.7.18') {
            throw "Local rhwp version must be exactly rhwp v0.7.18; received '$version'."
        }
        return [pscustomobject]@{
            Path = $resolved
            Version = 'v0.7.18'
            ExecutableSha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
            ArchiveSha256 = $null
            ReleaseUrl = $null
            ChecksumUrl = $null
            WorkspacePath = $null
            Temporary = $false
        }
    }

    $release = Get-RhwpReleaseDescriptor -Platform $Platform -Architecture $Architecture
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $leaf = 'rhwp-tool-' + [Guid]::NewGuid().ToString('N')
    $workspace = Join-Path $tempRoot $leaf
    New-Item -ItemType Directory -Path $workspace | Out-Null
    Set-Content -LiteralPath (Join-Path $workspace '.rhwp-owned') -Encoding Ascii -NoNewline -Value $leaf

    try {
        $checksumPath = Join-Path $workspace 'SHA256SUMS.txt'
        $archivePath = Join-Path $workspace $release.AssetName
        & $DownloadFile ([uri]$release.ChecksumUrl) $checksumPath | Out-Null
        & $DownloadFile ([uri]$release.AssetUrl) $archivePath | Out-Null
        $expected = Get-RhwpExpectedChecksum -ChecksumPath $checksumPath -AssetName $release.AssetName
        Assert-RhwpArchiveChecksum -ArchivePath $archivePath -ExpectedSha256 $expected

        $expanded = Join-Path $workspace 'expanded'
        New-Item -ItemType Directory -Path $expanded | Out-Null
        if ($release.ArchiveType -eq 'zip') {
            Expand-Archive -LiteralPath $archivePath -DestinationPath $expanded
        }
        else {
            & tar -xzf $archivePath -C $expanded
            if ($LASTEXITCODE -ne 0) { throw "tar extraction failed with exit code $LASTEXITCODE" }
        }

        $executableName = if ($Platform -eq 'windows') { 'rhwp.exe' } else { 'rhwp' }
        $executables = @(Get-ChildItem -LiteralPath $expanded -Recurse -File -Filter $executableName)
        if ($executables.Count -ne 1) { throw "Expected one $executableName; found $($executables.Count)." }
        $version = (& $executables[0].FullName --version 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $version -cne 'rhwp v0.7.18') {
            throw "Downloaded rhwp version check failed: '$version'."
        }

        return [pscustomobject]@{
            Path = $executables[0].FullName
            Version = $release.Version
            ExecutableSha256 = (Get-FileHash -LiteralPath $executables[0].FullName -Algorithm SHA256).Hash
            ArchiveSha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
            ReleaseUrl = $release.AssetUrl
            ChecksumUrl = $release.ChecksumUrl
            WorkspacePath = $workspace
            Temporary = $true
        }
    }
    catch {
        Remove-RhwpOwnedWorkspace -WorkspacePath $workspace -ExpectedPrefix 'rhwp-tool-'
        throw
    }
}
```

같은 모듈에 `Remove-RhwpOwnedWorkspace`를 작성한다. 삭제 전에는 정규화한 경로가 OS 임시
디렉터리 바로 아래인지, leaf가 `^rhwp-tool-[0-9a-f]{32}$`인지, `.rhwp-owned`의 내용이
leaf와 일치하는지를 모두 확인한다. 하나라도 다르면 삭제하지 않고 예외를 발생시킨다.

- [ ] **Step 4: 검증 전용 진입점 작성**

`scripts/research/rhwp-tool.ps1`은 세션 메타데이터만 JSON으로 출력하고 `finally`에서 반드시
임시 세션을 정리한다.

```powershell
[CmdletBinding()]
param([string]$RhwpPath)

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
    if ($null -ne $session) { Remove-RhwpToolSession -Session $session }
}
```

- [ ] **Step 5: 단위 테스트와 로컬 진입점 구문 검증**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/research/tests/Invoke-RhwpPipelineTests.ps1
[void][scriptblock]::Create((Get-Content scripts/research/rhwp-tool.ps1 -Raw -Encoding UTF8))
```

Expected: 모든 단위 테스트 통과, 구문 예외 없음, fake 변조 archive는 압축 해제 전에 거부.

- [ ] **Step 6: Task 2 커밋**

```powershell
git add scripts/research/RhwpPipeline.psm1 scripts/research/rhwp-tool.ps1 scripts/research/tests/Invoke-RhwpPipelineTests.ps1
git commit -m "feat: verify official rhwp tool sessions"
```

---

### Task 3: 원자적 HWP 추출과 매니페스트

**Files:**

- Modify: `scripts/research/RhwpPipeline.psm1`
- Modify: `scripts/research/tests/Invoke-RhwpPipelineTests.ps1`
- Create: `scripts/research/extract-hwp.ps1`

**Interfaces:**

- Consumes: `New-RhwpToolSession`, `Remove-RhwpToolSession`
- Produces: `Invoke-RhwpExtraction -InputPath <hwp> -OutputDirectory <new-dir> -Format
  <text|markdown|both> [-RhwpPath <exe>] -> manifest object`
- Manifest: `schema_version`, `executed_at_utc`, `tool`, `input`, `commands`, `outputs`,
  `retention_status`, `warnings`, `manual_review_required`

- [ ] **Step 1: 입력 선검증과 성공 매니페스트 테스트 작성**

테스트에서 `ToolResolver`와 `CommandRunner`를 주입한다. 이 계약으로 네트워크 접근 전에 확장자를
거부하고, 성공 시 페이지 연속성과 해시가 기록되는지 검증한다.

```powershell
Invoke-Test 'Unsupported extension is rejected before tool resolution' {
    $script:ToolResolverCalled = $false
    $input = [IO.Path]::GetTempFileName()
    $output = Join-Path ([IO.Path]::GetTempPath()) ('rhwp-out-' + [Guid]::NewGuid().ToString('N'))
    try {
        Assert-ThrowsLike {
            Invoke-RhwpExtraction -InputPath $input -OutputDirectory $output -ToolResolver {
                $script:ToolResolverCalled = $true
                throw 'must not run'
            }
        } '*.hwp*'
        Assert-True (-not $script:ToolResolverCalled) 'Tool resolver ran before extension validation'
    }
    finally { Remove-Item -LiteralPath $input -Force }
}

Invoke-Test 'HWPX stays disabled before compatibility evidence' {
    $script:ToolResolverCalled = $false
    $root = Join-Path ([IO.Path]::GetTempPath()) ('rhwp-hwpx-gate-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $root | Out-Null
    $input = Join-Path $root 'sample.hwpx'
    $output = Join-Path $root 'result'
    Set-Content -LiteralPath $input -Encoding UTF8 -Value 'fixture bytes'
    try {
        Assert-ThrowsLike {
            Invoke-RhwpExtraction -InputPath $input -OutputDirectory $output -ToolResolver {
                $script:ToolResolverCalled = $true
                throw 'must not run'
            }
        } '*.hwpx extraction is disabled*'
        Assert-True (-not $script:ToolResolverCalled) 'HWPX gate ran after tool resolution'
    }
    finally { Remove-Item -LiteralPath $root -Recurse -Force }
}

Invoke-Test 'Successful extraction writes an auditable manifest' {
    $root = Join-Path ([IO.Path]::GetTempPath()) ('rhwp-extract-test-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $root | Out-Null
    $input = Join-Path $root 'sample.hwp'
    $output = Join-Path $root 'result'
    Set-Content -LiteralPath $input -Encoding UTF8 -Value 'fixture bytes'
    try {
        $toolResolver = {
            [pscustomobject]@{
                Path = 'fake-rhwp'; Version = 'v0.7.18'; ExecutableSha256 = ('A' * 64)
                ArchiveSha256 = ('B' * 64); ReleaseUrl = 'https://github.com/edwardkim/rhwp'
                ChecksumUrl = 'https://github.com/edwardkim/rhwp/SHA256SUMS.txt'
                WorkspacePath = $null; Temporary = $false
            }
        }
        $runner = {
            param([string]$Executable, [string[]]$Arguments)
            $format = $Arguments[0]
            $destination = $Arguments[3]
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
            $extension = if ($format -eq 'export-text') { 'txt' } else { 'md' }
            Set-Content -LiteralPath (Join-Path $destination "sample_001.$extension") -Encoding UTF8 -Value 'page one'
            Set-Content -LiteralPath (Join-Path $destination "sample_002.$extension") -Encoding UTF8 -Value 'page two'
            [pscustomobject]@{ ExitCode = 0; Output = @('ok') }
        }

        $manifest = Invoke-RhwpExtraction -InputPath $input -OutputDirectory $output -Format both `
            -ToolResolver $toolResolver -CommandRunner $runner
        Assert-Equal $manifest.schema_version 1 'Wrong manifest schema'
        Assert-Equal $manifest.outputs.Count 4 'Expected two text and two markdown pages'
        Assert-Equal $manifest.retention_status 'TEMPORARY_NOT_RETAINED' 'Wrong retention state'
        Assert-True (Test-Path -LiteralPath (Join-Path $output 'rhwp-extraction-manifest.json')) 'Manifest missing'
        Assert-True (Test-Path -LiteralPath $input) 'Input was deleted'
    }
    finally { Remove-Item -LiteralPath $root -Recurse -Force }
}

Invoke-Test 'Page gaps fail closed without publishing output' {
    $root = Join-Path ([IO.Path]::GetTempPath()) ('rhwp-gap-test-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $root | Out-Null
    $input = Join-Path $root 'sample.hwp'
    $output = Join-Path $root 'result'
    Set-Content -LiteralPath $input -Encoding UTF8 -Value 'fixture bytes'
    try {
        $toolResolver = {
            [pscustomobject]@{
                Path = 'fake-rhwp'; Version = 'v0.7.18'; ExecutableSha256 = ('A' * 64)
                ArchiveSha256 = ('B' * 64); ReleaseUrl = 'https://github.com/edwardkim/rhwp'
                ChecksumUrl = 'https://github.com/edwardkim/rhwp/SHA256SUMS.txt'
                WorkspacePath = $null; Temporary = $false
            }
        }
        $runner = {
            param([string]$Executable, [string[]]$Arguments)
            $destination = $Arguments[3]
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
            Set-Content -LiteralPath (Join-Path $destination 'sample_001.txt') -Encoding UTF8 -Value 'page one'
            Set-Content -LiteralPath (Join-Path $destination 'sample_003.txt') -Encoding UTF8 -Value 'page three'
            [pscustomobject]@{ ExitCode = 0; Output = @('ok') }
        }
        Assert-ThrowsLike {
            Invoke-RhwpExtraction -InputPath $input -OutputDirectory $output -Format text `
                -ToolResolver $toolResolver -CommandRunner $runner
        } '*page sequence*'
        Assert-True (-not (Test-Path -LiteralPath $output)) 'Failed extraction published output'
    }
    finally { Remove-Item -LiteralPath $root -Recurse -Force }
}

function Invoke-FailClosedExtractionCase {
    param([scriptblock]$Runner, [string]$ExpectedError)
    $root = Join-Path ([IO.Path]::GetTempPath()) ('rhwp-fail-test-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $root | Out-Null
    $input = Join-Path $root 'sample.hwp'
    $output = Join-Path $root 'result'
    Set-Content -LiteralPath $input -Encoding UTF8 -Value 'fixture bytes'
    try {
        $toolResolver = {
            [pscustomobject]@{
                Path = 'fake-rhwp'; Version = 'v0.7.18'; ExecutableSha256 = ('A' * 64)
                ArchiveSha256 = ('B' * 64); ReleaseUrl = 'https://github.com/edwardkim/rhwp'
                ChecksumUrl = 'https://github.com/edwardkim/rhwp/SHA256SUMS.txt'
                WorkspacePath = $null; Temporary = $false
            }
        }
        Assert-ThrowsLike {
            Invoke-RhwpExtraction -InputPath $input -OutputDirectory $output -Format text `
                -ToolResolver $toolResolver -CommandRunner $Runner
        } $ExpectedError
        Assert-True (-not (Test-Path -LiteralPath $output)) 'Failed extraction published output'
        Assert-True (Test-Path -LiteralPath $input) 'Failed extraction deleted input'
    }
    finally { Remove-Item -LiteralPath $root -Recurse -Force }
}

Invoke-Test 'Parser command failure does not publish output' {
    Invoke-FailClosedExtractionCase -ExpectedError '*export-text failed with exit code 2*' -Runner {
        param([string]$Executable, [string[]]$Arguments)
        [pscustomobject]@{ ExitCode = 2; Output = @('parser error') }
    }
}

Invoke-Test 'Zero output files do not publish a manifest' {
    Invoke-FailClosedExtractionCase -ExpectedError '*produced no .txt output files*' -Runner {
        param([string]$Executable, [string[]]$Arguments)
        New-Item -ItemType Directory -Path $Arguments[3] -Force | Out-Null
        [pscustomobject]@{ ExitCode = 0; Output = @('no pages') }
    }
}
```

- [ ] **Step 2: 새 테스트의 실패 확인**

Run: 단위 테스트 명령.

Expected: `Invoke-RhwpExtraction` 미정의로 추출 테스트 실패.

- [ ] **Step 3: 추출·연속 페이지 검증·원자적 공개 구현**

모듈에 다음 계약을 구현한다.

```powershell
function Invoke-RhwpCommand {
    param([string]$Executable, [string[]]$Arguments)
    $output = @(& $Executable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
    return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $output }
}

function Get-RhwpPageOutputs {
    param([string]$Directory, [string]$Stem, [string]$Extension)
    $files = @(Get-ChildItem -LiteralPath $Directory -File | Where-Object {
        $_.Name -match ('^' + [regex]::Escape($Stem) + '_(?<page>[0-9]{3})\.' + $Extension + '$')
    } | Sort-Object Name)
    if ($files.Count -eq 0) { throw "rhwp produced no .$Extension output files." }
    for ($index = 0; $index -lt $files.Count; $index++) {
        $expected = '{0:D3}' -f ($index + 1)
        if ($files[$index].BaseName -notlike "*_$expected") {
            throw "rhwp page sequence is incomplete at $expected."
        }
        if ($files[$index].Length -le 0) { throw "rhwp produced empty output: $($files[$index].Name)" }
    }
    return $files
}

function Invoke-RhwpExtraction {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$InputPath,
        [Parameter(Mandatory)] [string]$OutputDirectory,
        [ValidateSet('text', 'markdown', 'both')] [string]$Format = 'both',
        [string]$RhwpPath,
        [scriptblock]$ToolResolver,
        [scriptblock]$CommandRunner = ${function:Invoke-RhwpCommand}
    )

    $input = Get-Item -LiteralPath $InputPath -ErrorAction Stop
    $extension = $input.Extension.ToLowerInvariant()
    if ($extension -eq '.hwpx' -and -not $script:RhwpHwpxCompatibilityEnabled) {
        throw '.hwpx extraction is disabled until the pinned compatibility test passes.'
    }
    if ($extension -ne '.hwp' -and $extension -ne '.hwpx') {
        throw 'InputPath must have the .hwp extension.'
    }
    if (Test-Path -LiteralPath $OutputDirectory) {
        throw "OutputDirectory must not already exist: $OutputDirectory"
    }

    $parent = Split-Path -Parent ([IO.Path]::GetFullPath($OutputDirectory))
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw "Output parent does not exist: $parent"
    }
    $staging = Join-Path $parent ('.rhwp-extract-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $staging | Out-Null
    Set-Content -LiteralPath (Join-Path $staging '.rhwp-owned') -Encoding Ascii -NoNewline -Value ([IO.Path]::GetFileName($staging))

    $session = $null
    try {
        $session = if ($ToolResolver) { & $ToolResolver } else { New-RhwpToolSession -RhwpPath $RhwpPath }
        $commands = @()
        $pageFiles = @()
        foreach ($kind in @('text', 'markdown')) {
            if ($Format -ne 'both' -and $Format -ne $kind) { continue }
            $command = if ($kind -eq 'text') { 'export-text' } else { 'export-markdown' }
            $fileExtension = if ($kind -eq 'text') { 'txt' } else { 'md' }
            $destination = Join-Path $staging $kind
            New-Item -ItemType Directory -Path $destination | Out-Null
            $arguments = @($command, $input.FullName, '--output', $destination)
            $result = & $CommandRunner $session.Path $arguments
            if ($result.ExitCode -ne 0) {
                throw "$command failed with exit code $($result.ExitCode): $($result.Output -join [Environment]::NewLine)"
            }
            $commands += [ordered]@{ name = $command; arguments = $arguments; exit_code = 0 }
            $pageFiles += @(Get-RhwpPageOutputs -Directory $destination -Stem $input.BaseName -Extension $fileExtension)
        }
        if ($Format -eq 'both') {
            $textCount = @($pageFiles | Where-Object Extension -eq '.txt').Count
            $markdownCount = @($pageFiles | Where-Object Extension -eq '.md').Count
            if ($textCount -ne $markdownCount) { throw 'rhwp text and markdown page counts differ.' }
        }

        $manifest = [ordered]@{
            schema_version = 1
            executed_at_utc = [DateTime]::UtcNow.ToString('o')
            tool = [ordered]@{
                version = $session.Version; executable_sha256 = $session.ExecutableSha256
                archive_sha256 = $session.ArchiveSha256; release_url = $session.ReleaseUrl
                checksum_url = $session.ChecksumUrl
            }
            input = [ordered]@{
                file_name = $input.Name; byte_count = $input.Length
                sha256 = (Get-FileHash -LiteralPath $input.FullName -Algorithm SHA256).Hash
            }
            commands = $commands
            outputs = @($pageFiles | ForEach-Object {
                [ordered]@{
                    relative_path = $_.FullName.Substring($staging.Length + 1).Replace('\', '/')
                    byte_count = $_.Length
                    sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
                }
            })
            retention_status = 'TEMPORARY_NOT_RETAINED'
            warnings = @('Extraction does not establish legal effect, source rights, tax correctness, or spatial correctness.')
            manual_review_required = $true
        }
        $manifestTemp = Join-Path $staging 'rhwp-extraction-manifest.json.tmp'
        $manifestPath = Join-Path $staging 'rhwp-extraction-manifest.json'
        $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestTemp -Encoding UTF8
        Move-Item -LiteralPath $manifestTemp -Destination $manifestPath

        if ($null -ne $session -and $session.Temporary) {
            Remove-RhwpToolSession -Session $session
            $session = $null
        }
        Move-Item -LiteralPath $staging -Destination $OutputDirectory
        return [pscustomobject]$manifest
    }
    catch {
        if (Test-Path -LiteralPath $staging) {
            Remove-RhwpOwnedWorkspace -WorkspacePath $staging -ExpectedPrefix '.rhwp-extract-' -AllowedParent $parent
        }
        throw
    }
    finally {
        if ($null -ne $session -and $session.Temporary) { Remove-RhwpToolSession -Session $session }
    }
}
```

- [ ] **Step 4: 추출 진입점 작성**

```powershell
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$InputPath,
    [Parameter(Mandatory)] [string]$OutputDirectory,
    [ValidateSet('text', 'markdown', 'both')] [string]$Format = 'both',
    [string]$RhwpPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'RhwpPipeline.psm1') -Force

Invoke-RhwpExtraction -InputPath $InputPath -OutputDirectory $OutputDirectory `
    -Format $Format -RhwpPath $RhwpPath | ConvertTo-Json -Depth 8
```

- [ ] **Step 5: 단위 테스트와 구문 검증**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/research/tests/Invoke-RhwpPipelineTests.ps1
[void][scriptblock]::Create((Get-Content scripts/research/extract-hwp.ps1 -Raw -Encoding UTF8))
```

Expected: 지원하지 않는 확장자는 resolver 호출 전 실패, 성공 fixture는 4개 출력과 매니페스트,
페이지 누락 fixture는 출력 디렉터리 없이 실패, 전체 테스트 exit code `0`.

- [ ] **Step 6: Task 3 커밋**

```powershell
git add scripts/research/RhwpPipeline.psm1 scripts/research/extract-hwp.ps1 scripts/research/tests/Invoke-RhwpPipelineTests.ps1
git commit -m "feat: extract HWP with auditable manifests"
```

---

### Task 4: 공식 통합검증과 조사 문서 반영

**Files:**

- Create: `scripts/research/tests/Invoke-RhwpIntegrationTest.ps1`
- Create: `THIRD_PARTY_NOTICES.md`
- Modify: `specs/001-real-estate-policy-dashboard/source-register.md:89`
- Modify: `specs/001-real-estate-policy-dashboard/research-data/README.md:30`
- Modify: `specs/001-real-estate-policy-dashboard/checklists/research-readiness.md:75`

**Interfaces:**

- Consumes: 공식 `New-RhwpToolSession`, `Invoke-RhwpExtraction`
- Produces: 공식 archive·실행 파일 hash, 18페이지 텍스트·Markdown 추출, 해시 재검산 결과

- [ ] **Step 1: 공식 생성 샘플 통합 테스트 작성**

`scripts/research/tests/Invoke-RhwpIntegrationTest.ps1`은 권리 문제가 없는 임시 샘플을 공식 CLI의
`gen-table`로 만들고 같은 CLI로 추출한다.

```powershell
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\RhwpPipeline.psm1') -Force

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar)
$leaf = 'rhwp-integration-' + [Guid]::NewGuid().ToString('N')
$workspace = Join-Path $tempRoot $leaf
New-Item -ItemType Directory -Path $workspace | Out-Null
$session = $null
try {
    $session = New-RhwpToolSession
    Push-Location -LiteralPath $workspace
    try { & $session.Path gen-table 2>&1 | Write-Output }
    finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "rhwp gen-table failed with exit code $LASTEXITCODE" }

    $input = Join-Path $workspace 'output\gen_table.hwp'
    $output = Join-Path $workspace 'extracted'
    $manifest = Invoke-RhwpExtraction -InputPath $input -OutputDirectory $output -Format both -RhwpPath $session.Path
    $textFiles = @(Get-ChildItem -LiteralPath (Join-Path $output 'text') -Filter '*.txt')
    $markdownFiles = @(Get-ChildItem -LiteralPath (Join-Path $output 'markdown') -Filter '*.md')
    if ($textFiles.Count -ne 18 -or $markdownFiles.Count -ne 18) {
        throw "Expected 18 text and 18 markdown pages; received $($textFiles.Count) and $($markdownFiles.Count)."
    }
    foreach ($record in $manifest.outputs) {
        $path = Join-Path $output $record.relative_path
        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($actual -cne $record.sha256) { throw "Output hash mismatch: $($record.relative_path)" }
    }
    [ordered]@{
        version = $session.Version
        archive_sha256 = $session.ArchiveSha256
        executable_sha256 = $session.ExecutableSha256
        text_pages = $textFiles.Count
        markdown_pages = $markdownFiles.Count
        input_preserved = (Test-Path -LiteralPath $input)
        manifest_hashes_verified = $true
    } | ConvertTo-Json -Depth 3
}
finally {
    if ($null -ne $session) { Remove-RhwpToolSession -Session $session }
    $resolved = [IO.Path]::GetFullPath($workspace)
    if (-not $resolved.StartsWith($tempRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($resolved) -notmatch '^rhwp-integration-[0-9a-f]{32}$') {
        throw "Unsafe integration cleanup target: $resolved"
    }
    if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
```

- [ ] **Step 2: 오프라인 단위 테스트 재실행**

Run: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
scripts/research/tests/Invoke-RhwpPipelineTests.ps1`

Expected: 네트워크 없이 전부 통과.

- [ ] **Step 3: 공식 통합 테스트 실행**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/research/tests/Invoke-RhwpIntegrationTest.ps1
```

Expected:

- version `v0.7.18`
- archive SHA-256
  `BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD`
- Windows 실행 파일 SHA-256
  `C92492674CD9B2BDEF7B550FD24591554F75FE391F6299F943B01B7AEEF4F859`
- text pages `18`, markdown pages `18`
- `input_preserved=true`, `manifest_hashes_verified=true`
- 테스트 종료 후 `rhwp-tool-*`, `rhwp-integration-*` 임시 폴더가 남지 않음

- [ ] **Step 4: 제3자 고지 작성**

`THIRD_PARTY_NOTICES.md`는 한국어 섹션에 프로젝트명, `v0.7.18`, Edward Kim의
2025-2026 저작권, MIT License, 공식 저장소·릴리스·라이선스 링크, 조사 CLI 사용 범위를
기록한다. 마지막 `English AI Context`에는 다음 구조를 둔다.

```yaml
dependency: edwardkim/rhwp
version: v0.7.18
license: MIT
copyright: Copyright (c) 2025-2026 Edward Kim
usage: temporary_research_cli
source: https://github.com/edwardkim/rhwp
release: https://github.com/edwardkim/rhwp/releases/tag/v0.7.18
```

- [ ] **Step 5: 조사 문서에 검증 증거 반영**

- `source-register.md`의 임시 캡처 증거 앞에 `rhwp` 검증 버전, 공식 archive hash, 실행 파일
  hash, 실행일, 추출물 비보존과 법적 효력 비승격을 기록한다.
- `research-data/README.md`의 fail-closed 원칙 다음에 `extract-hwp.ps1` 실행 예와
  `TEMPORARY_NOT_RETAINED` 매니페스트 해석을 추가한다.
- `research-readiness.md`의 원문 권리·무결성 섹션에 공식 체크섬 검증, 입력·도구·출력 hash
  재계산, 임시 삭제 확인은 `[x]`로 기록하되 원문 권리·사람 승인 항목은 `[ ]`로 유지한다.
- 각 문서의 `English AI Context`에도 `rhwp_version`, `rhwp_archive_sha256`,
  `rhwp_executable_sha256`, `extraction_retention`을 같은 이름으로 추가한다.

- [ ] **Step 6: 전체 정적·동적 검증**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/research/tests/Invoke-RhwpPipelineTests.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/research/tests/Invoke-RhwpIntegrationTest.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/verify/repository-hygiene.ps1
git diff --check
rg -n "TO[D]O|TB[D]|PLACEHOLD[E]R|\?{3}" scripts/research THIRD_PARTY_NOTICES.md specs/001-real-estate-policy-dashboard docs/superpowers/plans/2026-07-17-rhwp-research-pipeline.md
```

Expected: 단위·통합·저장소 위생 검사 exit code `0`, whitespace 오류 없음, 미완성 표식 검색
결과 없음. 조사 원문·추출 전문·릴리스 archive·실행 파일이 Git 추적 대상에 없어야 한다.

- [ ] **Step 7: Task 4 커밋**

```powershell
git add scripts/research/tests/Invoke-RhwpIntegrationTest.ps1 THIRD_PARTY_NOTICES.md specs/001-real-estate-policy-dashboard/source-register.md specs/001-real-estate-policy-dashboard/research-data/README.md specs/001-real-estate-policy-dashboard/checklists/research-readiness.md
git commit -m "docs: record verified rhwp research workflow"
```

## 최종 완료 판정

- 오프라인 단위 테스트와 공식 네트워크 통합 테스트가 모두 통과한다.
- `rhwp v0.7.18`, 공식 archive와 실행 파일 SHA-256이 매니페스트·조사 문서에 일치한다.
- 체크섬 불일치, 지원하지 않는 확장자, 버전 불일치, 빈 출력, 페이지 누락, 정리 실패가
  모두 성공 매니페스트 없이 종료된다.
- 성공 추출은 원문 권리나 정책·세금·공간 사실을 자동 승인하지 않는다.
- 정부기관 원문과 추출 전문은 저장소에 남지 않는다.
- 기존 T001·T002·T003·T006의 사람·전수조사 게이트는 별도 미완료 상태를 유지한다.

---

## English AI Context

```yaml
plan_id: RHWP_RESEARCH_PIPELINE_IMPLEMENTATION
design: docs/superpowers/specs/2026-07-17-rhwp-research-pipeline-design.md
execution_mode: inline
required_skills:
  - superpowers:executing-plans
  - superpowers:test-driven-development
tasks:
  - id: RHWP-1
    deliverable: pinned_release_and_checksum_contract
  - id: RHWP-2
    deliverable: verified_temporary_tool_session
    depends_on: [RHWP-1]
  - id: RHWP-3
    deliverable: atomic_extraction_and_manifest
    depends_on: [RHWP-2]
  - id: RHWP-4
    deliverable: official_integration_evidence_and_docs
    depends_on: [RHWP-3]
fixed_tool:
  repository: https://github.com/edwardkim/rhwp
  version: v0.7.18
  windows_asset: rhwp-v0.7.18-windows-x86_64.zip
  windows_archive_sha256: BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD
  windows_executable_sha256: C92492674CD9B2BDEF7B550FD24591554F75FE391F6299F943B01B7AEEF4F859
test_policy:
  unit_network: disabled
  unit_tests_passed: 25
  integration_source: official_github_release
  integration_fixture: rhwp_gen_table_temporary_output
  integration_text_pages: 18
  integration_markdown_pages: 18
  corrupt_hwp_failed_closed: true
  government_document_fixture_commit: forbidden
  required_ci:
    runner: windows-2022
    powershell_major: 5
    offline_unit_tests: true
    local_default_http_redirect_smoke: true
  optional_ci:
    official_release_integration: workflow_dispatch
review_hardening:
  validate_redirect_before_each_request: true
  input_pre_and_post_hash: true
  reject_unexpected_output_tree: true
  ownership_sentinel_published: false
  atomic_directory_publish: true
human_gates_unchanged:
  - T001
  - T002
  - T003
  - T006
```
