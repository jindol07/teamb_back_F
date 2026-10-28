# 주차 A/B + 공유 화재의 로컬 관찰 실행기
param(
    [Parameter(Mandatory=$true)][string]$Config,
    [ValidateRange(1024,65535)][int]$Port=8002,
    [switch]$CheckOnly
)
$ErrorActionPreference='Stop'
$aiRoot=Split-Path -Parent $PSScriptRoot
$pythonExe=Join-Path $aiRoot '.venv\Scripts\python.exe'
$configPath=[System.IO.Path]::GetFullPath($Config)
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) { throw '프로젝트 .venv Python이 없습니다.' }
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { throw '주차 런타임 설정 파일이 없습니다.' }
$settings=@{
    PYTHONPATH=$aiRoot
    PYTHONIOENCODING='utf-8'
    PYTHONUNBUFFERED='1'
    PARKING_RUNTIME_ENABLED='true'
    PARKING_RUNTIME_CONFIG=$configPath
    SAFETY_CAMERA_AUTOSTART='false'
    SAFETY_SHARED_AUTOSTART='true'
    SAFETY_SHARED_SEND_ENABLED='false'
}
$previous=@{}
foreach ($name in $settings.Keys) { $previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process') }
try {
    foreach ($name in $settings.Keys) { [Environment]::SetEnvironmentVariable($name,$settings[$name],'Process') }
    Push-Location $aiRoot
    try {
        & $pythonExe -m ai_vision.safety.shared_monitor_preflight
        if ($LASTEXITCODE -ne 0) { throw '사전점검 실패. 카메라를 열지 않았습니다.' }
        if ($CheckOnly) { return }
        # 모델·카메라 중복 프로세스를 만드는 reload/복수 worker는 사용하지 않습니다.
        & $pythonExe -m uvicorn ai_vision.app:app --host 127.0.0.1 --port $Port --workers 1 --no-access-log
        if ($LASTEXITCODE -ne 0) { throw '공유 감시 서버가 오류로 종료됐습니다.' }
    } finally { Pop-Location }
} finally {
    foreach ($name in $settings.Keys) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
}
