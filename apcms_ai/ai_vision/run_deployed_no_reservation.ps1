# 예약 생성 없이 입차→A02→A01→출차→A 불꽃→B 불꽃을 실제 AWS에서 확인합니다.
param(
    [string]$Config = (Join-Path $PSScriptRoot 'results\parking_runtime\demo_current_20261028\runtime.local.json'),
    [switch]$CheckOnly
)
$ErrorActionPreference='Stop'
$options=@{Config=$Config;NoReservation=$true}
if ($CheckOnly) {$options.CheckOnly=$true}
& (Join-Path $PSScriptRoot 'run_deployed_integration.ps1') @options
