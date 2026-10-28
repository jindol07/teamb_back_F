# APCMS 팀 AWS 테스트 서버 전용. 실제 운영 전송에는 사용하지 마세요.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path $python)) {
    $python = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
}
if (!(Test-Path $python)) {
    throw 'Python 가상환경(.venv 또는 venv)을 찾지 못했습니다.'
}

$source = Join-Path $PSScriptRoot 'ai_vision\safety\fire_alert_sender.py'
if (!(Test-Path $source)) {
    throw 'ai_vision\safety\fire_alert_sender.py 를 찾지 못했습니다. 이 스크립트를 apcms_ai 루트에 넣으세요.'
}

# 실행 전 로컬 검사만 수행합니다. 실제 네트워크 요청 없음.
& $python -m unittest test_aws_test_http_policy -q
if ($LASTEXITCODE -ne 0) { throw '보안 예외 정책 테스트가 실패했습니다. 실행하지 않습니다.' }

Write-Host 'AWS 관리자 Spring Boot에서 쓰는 FIRE_ALERT_API_KEY와 동일한 값을 입력하세요.'
Write-Host '키는 화면에 표시되지 않습니다. 공개 채팅/콘솔 로그에 입력하지 마세요.'
$secure = Read-Host '공유키' -AsSecureString
if ($null -eq $secure -or $secure.Length -eq 0) { throw '공유키가 비어 있습니다.' }
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:FIRE_ALERT_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
Remove-Variable secure -ErrorAction SilentlyContinue

$env:SAFETY_CAMERA_AUTOSTART = '1'
$env:SAFETY_CAMERA_SHOW = '1'
$env:SAFETY_CAMERA_SEND_ENABLED = '1'
$env:SAFETY_CAMERA_SEND_MODE = 'test'
$env:SAFETY_CAMERA_ALERT_URL = 'http://52.79.133.132:3000/admin-api/api/parking/ai/fire-alerts'
$env:SAFETY_TEST_AWS_HTTP = '1'
Remove-Item 'Env:SAFETY_CAMERA_ALLOW_PRODUCTION' -ErrorAction SilentlyContinue

Write-Host '[시험 모드] 팀 AWS HTTP 한 주소만 허용합니다.'
Write-Host '[알림] 테스트 성공 시 AWS Oracle에 시험 이벤트가 실제 저장될 수 있습니다.'
Write-Host '[종료] Ctrl+C 를 눌러 감시 종료. 본 PowerShell은 실행 후 닫으세요.'

try {
    & $python -m uvicorn main:app --host 127.0.0.1 --port 8001
} finally {
    foreach ($name in @('FIRE_ALERT_TOKEN','SAFETY_CAMERA_AUTOSTART','SAFETY_CAMERA_SHOW',
                         'SAFETY_CAMERA_SEND_ENABLED','SAFETY_CAMERA_SEND_MODE',
                         'SAFETY_CAMERA_ALERT_URL','SAFETY_TEST_AWS_HTTP')) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
}
