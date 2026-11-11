# 重启/重连后恢复 Android 侧技能环境（PC 侧一键脚本）
# 背景：Shizuku 用 ADB 启动，重启后失效；cached_apps_freezer / logcat 等 MIUI 也会重置。
# 前提：PC 已能 adb 连接手机（USB 或无线 5555）。
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\adb\after-reboot-android.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\adb\after-reboot-android.ps1 -Serial 192.168.10.159:5555 -EnableTcpip
param(
    [string]$Serial = '',
    [switch]$EnableTcpip,
    [switch]$AppManager
)

$ErrorActionPreference = 'Continue'
$adb = Join-Path $PSScriptRoot '..\tools\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { Write-Host "找不到 adb: $adb"; exit 1 }
$serialArgs = @()
if ($Serial) { $serialArgs = @('-s', $Serial) }

function A([string[]]$cmdArgs) { & $adb @serialArgs @cmdArgs 2>&1 }

Write-Host '=== 0) 连接检查 ==='
$devices = (& $adb devices) -join "`n"
Write-Host $devices
if ($devices -notmatch '\tdevice') {
    Write-Host '✗ 没有可用 ADB 设备：请插 USB / 先 adb connect，或重启后在开发者选项开启无线调试'
    exit 1
}

if ($EnableTcpip) {
    Write-Host '=== 1) 开启无线 ADB 5555（重启后需重新执行） ==='
    A @('tcpip', '5555') | ForEach-Object { Write-Host $_ }
    Start-Sleep -Seconds 2
}

$shizukuArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'shizuku-adb-start.ps1'), '-Start')
if ($Serial) { $shizukuArgs += @('-Serial', $Serial) }

Write-Host '=== 2) 启动 Shizuku（重启后必须） ==='
& powershell @shizukuArgs

Write-Host '=== 3) 重放 P0/P1 临时设置与 appops ==='
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'perf-adb-apply.ps1') -Apply

if ($AppManager) {
    Write-Host '=== 3.5) AppManager ADB 特权服务端 ==='
    $amArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'appmanager-adb-mode.ps1'), '-Start')
    if ($Serial) { $amArgs += @('-Serial', $Serial) }
    & powershell @amArgs
}

Write-Host '=== 4) 最终状态 ==='
A @('shell', 'ps -A') | Select-String -Pattern 'shizuku_server' | Select-Object -First 1
A @('shell', 'settings get global cached_apps_freezer')
A @('shell', 'logcat -g') | Select-Object -First 1
Write-Host '完成。若 Shizuku 未运行：确认开发者选项「USB 调试（安全设置）」已开启。'
