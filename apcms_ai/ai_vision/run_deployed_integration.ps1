# 기존 지하 3층 A01 예약·주차와 A/B 공유 불꽃 감지의 실제 AWS 통합 시험입니다.
param(
    [string]$Config = (Join-Path $PSScriptRoot 'results\parking_runtime\demo_current_20261028\runtime.local.json'),
    [switch]$CheckOnly,
    [switch]$NoReservation,
    [switch]$FreeParking
)
$ErrorActionPreference='Stop'
$aiRoot=Split-Path -Parent $PSScriptRoot
$python=Join-Path $aiRoot '.venv\Scripts\python.exe'
$oldPath=$env:PYTHONPATH
$oldEncoding=$env:PYTHONIOENCODING
$oldUnbuffered=$env:PYTHONUNBUFFERED
try {
    $env:PYTHONPATH=$aiRoot
    $env:PYTHONIOENCODING='utf-8'
    $env:PYTHONUNBUFFERED='1'
    $arguments=@('-u','-m','ai_vision.parking.demo_tools.run_deployed_integration','--config',$Config)
    if ($CheckOnly) {$arguments+='--check-only'}
    if ($NoReservation) {$arguments+='--no-reservation'}
    if ($FreeParking) {$arguments+='--free-parking'}
    & $python @arguments
    $testExit=$LASTEXITCODE
    if ($testExit -eq 130) {
        Write-Host '시험을 취소했습니다. 카메라 종료는 차량 출차 처리를 뜻하지 않습니다.'
    }
    elseif ($testExit -eq 2) {Write-Host '시작 조건을 확인할 항목이 있어 시험을 보류했습니다. 위 원인 안내를 확인하세요.'}
    elseif ($testExit -ne 0) {throw '통합 시험이 완료되지 않았습니다. 위 TEST_STOPPED 원인과 결과 파일을 확인하세요.'}
}
finally {
    $env:PYTHONPATH=$oldPath
    $env:PYTHONIOENCODING=$oldEncoding
    $env:PYTHONUNBUFFERED=$oldUnbuffered
}
