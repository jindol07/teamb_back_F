# A01 예약 후 네 칸을 자유롭게 점유하고 출차한 뒤 A/B 불꽃 시험으로 이어집니다.
param(
    [string]$Config = (Join-Path $PSScriptRoot 'results\parking_runtime\demo_current_20261028\runtime.local.json'),
    [switch]$CheckOnly
)
$ErrorActionPreference='Stop'
$options=@{Config=$Config;FreeParking=$true}
if ($CheckOnly) {$options.CheckOnly=$true}
& (Join-Path $PSScriptRoot 'run_deployed_integration.ps1') @options
