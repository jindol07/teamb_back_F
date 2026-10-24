# Windows 현장 한 대 시연 진입점. 준비/사전점검은 카메라·HTTP·DB를 사용하지 않습니다.
param(
    [string]$ProfileDir = (Join-Path $PSScriptRoot 'results\parking_demo\local'),
    [string]$PythonExe = "",
    [switch]$VerifyHandoffPlate,
    [switch]$Prepare,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$repoDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$aiRoot = Join-Path $repoDir 'apcms_ai'
$baseDir = [System.IO.Path]::GetFullPath($ProfileDir)
$toolsDir = Join-Path $PSScriptRoot 'parking\demo_tools'
# 기본 환경을 보존하면서 별도로 검증한 Python 환경도 선택할 수 있습니다.
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $aiRoot '.venv312\Scripts\python.exe'
}
$pythonExe = [System.IO.Path]::GetFullPath($PythonExe)
$helperDir = Join-Path $baseDir '.demo_helper'
$classpathFile = Join-Path $helperDir 'classpath.txt'
$required = @($pythonExe, (Join-Path $toolsDir 'controller.py'), (Join-Path $toolsDir 'gate_runner.py'),
    (Join-Path $toolsDir 'parking_runner.py'), (Join-Path $toolsDir 'CameraE2EFixture.java'),
    (Join-Path $toolsDir 'classpath.init.gradle'), (Join-Path $baseDir 'demo.local.json'))
foreach ($file in $required) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required demo file is missing: $file" }
}
$mutex = New-Object System.Threading.Mutex($false, 'Local\APCMS_AI_CAMERA_E2E')
$ownsMutex = $false
$oldPythonPath = $env:PYTHONPATH
$oldProfile = $env:PARKING_DEMO_PROFILE_DIR
$oldRun = $env:PARKING_DEMO_RUN_DIR
$oldVerifyIdentity = $env:PARKING_DEMO_VERIFY_HANDOFF_PLATE
try {
    try { $ownsMutex = $mutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $ownsMutex = $true }
    if (-not $ownsMutex) { throw 'Another demo is running. Close it before retrying.' }
    $env:PYTHONPATH = $aiRoot
    $env:PARKING_DEMO_PROFILE_DIR = $baseDir
    $env:PARKING_DEMO_VERIFY_HANDOFF_PLATE = if ($VerifyHandoffPlate) { '1' } else { '0' }
    $preflight = & $pythonExe -m ai_vision.parking.demo_session --status $baseDir --check-profile
    if ($LASTEXITCODE -ne 0) {
        Write-Host $preflight
        throw 'Profile validation failed or an earlier fixture needs recovery. No cameras were opened.'
    }
    if (-not (Get-Command java -ErrorAction SilentlyContinue)) { throw 'Java is required.' }
    if ($Prepare) {
        if (-not (Get-Command javac -ErrorAction SilentlyContinue)) { throw 'JDK javac is required for preparation.' }
        $wrapperSettings = Get-Content -LiteralPath (Join-Path $repoDir 'apcms_a\gradle\wrapper\gradle-wrapper.properties') -Raw
        $distributionMatch = [regex]::Match($wrapperSettings, 'gradle-([0-9.]+)-(bin|all)\.zip')
        if (-not $distributionMatch.Success) { throw 'Unsupported local Gradle distribution setting.' }
        $gradleCacheRoot = if ($env:GRADLE_USER_HOME) { $env:GRADLE_USER_HOME } else { Join-Path $env:USERPROFILE '.gradle' }
        $distributionName = $distributionMatch.Value -replace '\.zip$', ''
        $distributionDir = Join-Path $gradleCacheRoot ('wrapper\dists\' + $distributionName)
        $gradleCommands = @(Get-ChildItem -LiteralPath $distributionDir -Filter 'gradle.bat' -File -Recurse -ErrorAction SilentlyContinue)
        if ($gradleCommands.Count -lt 1) { throw 'Gradle is not cached locally. Preparation does not download it automatically.' }
        $gradleExe = $gradleCommands[0].FullName
        New-Item -ItemType Directory -Path $helperDir -Force | Out-Null
        Push-Location (Join-Path $repoDir 'apcms_a')
        try {
            # 기존 Gradle 캐시만 사용합니다. 설치/온라인 다운로드/Boot 소스 컴파일은 하지 않습니다.
            $classpathOutput = & $gradleExe --offline --console=plain --quiet -I (Join-Path $toolsDir 'classpath.init.gradle') parkingVerificationClasspath
            $gradleExit = $LASTEXITCODE
        }
        finally { Pop-Location }
        if ($gradleExit -ne 0) { throw 'Offline Gradle dependency resolution failed. No camera or DB action.' }
        $classpathLine = @($classpathOutput | Where-Object { $_ -match '\.jar' -and $_ -match [regex]::Escape([IO.Path]::PathSeparator) })
        if ($classpathLine.Count -ne 1) { throw 'Could not resolve exactly one runtime classpath.' }
        $classpath = $classpathLine[0].Trim()
        & javac -encoding UTF-8 -cp $classpath -d $helperDir (Join-Path $toolsDir 'CameraE2EFixture.java')
        if ($LASTEXITCODE -ne 0) { throw 'Fixture helper compilation failed.' }
        [IO.File]::WriteAllText($classpathFile,$classpath,(New-Object Text.UTF8Encoding($false)))
        Write-Host 'PREPARED: fixture helper rebuilt offline; no camera, HTTP or DB action'
    }
    if (-not (Test-Path -LiteralPath $classpathFile) -or -not (Test-Path -LiteralPath (Join-Path $helperDir 'CameraE2EFixture.class'))) {
        throw 'Local fixture helper is not prepared. Run this script with -Prepare first.'
    }
    $helperSource = Get-Item -LiteralPath (Join-Path $toolsDir 'CameraE2EFixture.java')
    $helperClass = Get-Item -LiteralPath (Join-Path $helperDir 'CameraE2EFixture.class')
    if ($helperClass.LastWriteTimeUtc -lt $helperSource.LastWriteTimeUtc) {
        throw 'Fixture helper source changed. Run -Prepare before opening cameras.'
    }
    foreach ($entry in ((Get-Content -LiteralPath $classpathFile -Raw).Trim() -split [regex]::Escape([IO.Path]::PathSeparator))) {
        if ($entry.EndsWith('.jar') -and -not (Test-Path -LiteralPath $entry -PathType Leaf)) {
            throw 'A cached dependency is missing. Run -Prepare with the local Gradle dependencies available.'
        }
    }
    if ($Prepare -or $CheckOnly) { Write-Host 'PREFLIGHT_OK: no camera, HTTP or DB action'; return }
    $runDir = Join-Path $baseDir ('e2e_manual_' + [guid]::NewGuid().ToString('N').Substring(0,8))
    New-Item -ItemType Directory -Path $runDir | Out-Null
    $env:PARKING_DEMO_RUN_DIR = $runDir
    Push-Location $repoDir
    try { & $pythonExe -m ai_vision.parking.demo_tools.controller; $exitCode = $LASTEXITCODE }
    finally { Pop-Location }
    Write-Host "RESULT DIRECTORY: $runDir"
    $resultFile = Join-Path $runDir 'http_e2e_result.json'
    if (Test-Path -LiteralPath $resultFile) {
        $result = Get-Content -LiteralPath $resultFile -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-Host "TEST_SUCCESS: $($result.success)"
        Write-Host "CLEANUP: $($result.cleanup)"
    }
    if ($exitCode -ne 0) { throw 'Demo stopped with an error. Inspect the saved result and cleanup before retrying.' }
}
finally {
    $env:PYTHONPATH = $oldPythonPath
    $env:PARKING_DEMO_PROFILE_DIR = $oldProfile
    $env:PARKING_DEMO_RUN_DIR = $oldRun
    $env:PARKING_DEMO_VERIFY_HANDOFF_PLATE = $oldVerifyIdentity
    if ($ownsMutex) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
