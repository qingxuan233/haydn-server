<#
.SYNOPSIS
    检查 ADB 工具链与手机连接状态。
.DESCRIPTION
    退出码：0 = 已授权可用；2 = 找不到 adb；3 = 无设备 / 未授权。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\adb\check-connection.ps1
#>
[CmdletBinding()]
param(
    [string]$AdbPath
)

$repoRoot = Split-Path -Parent $PSScriptRoot

function Resolve-Adb {
    param([string]$Explicit)
    foreach ($candidate in @($Explicit, $env:ADB_PATH, (Join-Path $repoRoot 'tools\platform-tools\adb.exe'))) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw '找不到 adb。请先运行 scripts/adb/get-platform-tools.ps1，或设置 ADB_PATH 环境变量。'
}

try { $adb = Resolve-Adb -Explicit $AdbPath } catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 2
}

Write-Host "ADB: $adb"

& $adb start-server 2>$null | Out-Null
$out = (& $adb devices -l) -join "`n"
Write-Host '--- adb devices -l ---'
Write-Host $out

if ($out -match 'unauthorized') {
    Write-Host ''
    Write-Host '[需授权] 手机已连接，但未授权本机调试。' -ForegroundColor Yellow
    Write-Host '请在手机上勾选「一律允许使用这台计算机进行调试」并点「允许」。' -ForegroundColor Yellow
    Write-Host '若没有弹窗：重新插拔数据线；或到开发者选项关闭再打开「USB 调试」。' -ForegroundColor Yellow
    exit 3
}

$serial = $null
foreach ($line in ($out -split "`r?`n")) {
    if ($line -match '^([0-9A-Za-z]+)\s+device') { $serial = $Matches[1]; break }
}
if (-not $serial) {
    Write-Host ''
    Write-Host '[未连接] 没有检测到已授权的设备。' -ForegroundColor Red
    Write-Host '排查：数据线是否为数据线（非纯充电线）、USB 连接模式、开发者选项中的 USB 调试开关。' -ForegroundColor Red
    exit 3
}

$model  = ((& $adb shell getprop ro.product.model) -join '').Trim()
$device = ((& $adb shell getprop ro.product.device) -join '').Trim()
$rom    = ((& $adb shell getprop ro.mi.os.version.name) -join '').Trim()
$android = ((& $adb shell getprop ro.build.version.release) -join '').Trim()

Write-Host ''
Write-Host "[已连接] 序列号 $serial — $model ($device) / Android $android / HyperOS $rom" -ForegroundColor Green
exit 0
