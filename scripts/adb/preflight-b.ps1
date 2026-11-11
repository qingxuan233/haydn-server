<#
.SYNOPSIS
    B 路线（解锁 + Root + chroot）前置条件检查。
.DESCRIPTION
    只读检查，不修改设备。输出 PASS/WARN/FAIL 清单与 Gate B0 提示：
      - 设备连接、区域（CN 国行政策风险）、解锁状态、OEM 解锁开关
      - 电量、存储
      - Mi Unlock / Magisk 工具是否就绪（含 SHA256 校验）
      - 固件包是否存在（backup\firmware）
      - A 方案备份是否存在（backup\）
    退出码：0 = 无阻断项；1 = 存在 FAIL（阻断项）。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\adb\preflight-b.ps1
#>
[CmdletBinding()]
param(
    [string]$AdbPath
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$results = New-Object 'System.Collections.Generic.List[string]'
$hasFail = $false

function Add-Item {
    param([string]$Level, [string]$Text)
    $line = "[$Level] $Text"
    [void]$script:results.Add($line)
    if ($Level -eq 'FAIL') { $script:hasFail = $true }
    Write-Host $line -ForegroundColor $(if ($Level -eq 'PASS') { 'Green' } elseif ($Level -eq 'FAIL') { 'Red' } elseif ($Level -eq 'WARN') { 'Yellow' } else { 'Cyan' })
}
function Resolve-Adb {
    param([string]$Explicit)
    foreach ($candidate in @($Explicit, $env:ADB_PATH, (Join-Path $repoRoot 'tools\platform-tools\adb.exe'))) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw '找不到 adb'
}
function Get-DevProp {
    param([string]$Adb, [string]$Name)
    $v = (& $Adb shell getprop $Name) -join ''
    return $v.Trim()
}

Write-Host '=== B 路线前置检查（只读） ===' -ForegroundColor Cyan

# 1. adb
try { $adb = Resolve-Adb -Explicit $AdbPath; Add-Item 'PASS' "adb: $adb" } catch { Add-Item 'FAIL' $_.Exception.Message; Write-Host ("汇总：" + $results.Count + " 项，含阻断项"); exit 1 }

# 2. 设备
& $adb start-server 2>$null | Out-Null
$devices = ((& $adb devices -l) -join "`n")
$serial = $null
foreach ($line in ($devices -split "`r?`n")) { if ($line -match '^([0-9A-Za-z]+)\s+device') { $serial = $Matches[1]; break } }
if (-not $serial) {
    Add-Item 'FAIL' '未检测到已授权设备（检查数据线/USB 调试/授权）'
    Write-Host ("汇总：" + $results.Count + " 项，含阻断项"); exit 1
}
Add-Item 'PASS' "设备连接：$serial"

# 3. 关键属性
$model   = Get-DevProp $adb 'ro.product.model'
$device  = Get-DevProp $adb 'ro.product.device'
$rom     = Get-DevProp $adb 'ro.build.version.incremental'
$region  = Get-DevProp $adb 'ro.miui.region'
$hwc     = Get-DevProp $adb 'ro.boot.hwc'
$locked  = Get-DevProp $adb 'ro.boot.flash.locked'
$vbmeta  = Get-DevProp $adb 'ro.boot.vbmeta.device_state'
$vbs     = Get-DevProp $adb 'ro.boot.verifiedbootstate'
$oemAllw = Get-DevProp $adb 'sys.oem_unlock_allowed'
$slot    = Get-DevProp $adb 'ro.boot.slot_suffix'

Add-Item 'INFO' "机型：$model ($device) / 固件 $rom / slot $slot"
if ($region -eq 'CN') {
    Add-Item 'WARN' "区域 = CN（国行）：2026 年官方解锁政策可能已关闭，必须先做 Gate B0 验证（docs/05 §1）"
} else { Add-Item 'INFO' "区域 = $region（非国行，政策风险较低）" }

if ($locked -eq '0') {
    Add-Item 'PASS' "Bootloader 已解锁（flash.locked=0 / vbmeta=$vbmeta）→ 可跳过解锁，直接做 Root"
} else {
    Add-Item 'INFO' "Bootloader 锁定（flash.locked=$locked / vbmeta=$vbmeta / $vbs）→ 需 Gate B0 + 解锁"
}

if ($oemAllw -eq '1') { Add-Item 'PASS' 'OEM 解锁开关：允许（sys.oem_unlock_allowed=1）' }
else { Add-Item 'WARN' "OEM 解锁开关：$oemAllw（可能需在开发者选项打开）" }

# 4. 电量与存储
$battery = (& $adb shell dumpsys battery) -join "`n"
$level = $null
if ($battery -match '(?m)^\s*level:\s*(\d+)') { $level = [int]$Matches[1] }
if ($level -ge 50) { Add-Item 'PASS' "电量：$level%（解锁门槛 > 50%）" }
else { Add-Item 'FAIL' "电量：$level%（低于 50%，先充电再解锁）" }

$df = (& $adb shell df /data) -join "`n"
if ($df -match '(\d+)%') {
    $pct = [int]$Matches[1]
    if ($pct -lt 80) { Add-Item 'PASS' "/data 使用率 $pct%（< 80%）" } else { Add-Item 'WARN' "/data 使用率 $pct%（偏高，先清理）" }
}

# 5. 工具就绪
$unlockExe = Join-Path $repoRoot 'tools\mi-unlock\miflash_unlock.exe'
if (Test-Path -LiteralPath $unlockExe) { Add-Item 'PASS' 'Mi Unlock 工具：已就绪（tools\mi-unlock\miflash_unlock.exe）' }
else { Add-Item 'FAIL' 'Mi Unlock 工具缺失：请运行 tools 下载或检查 tools\mi-unlock' }

$magiskApk = Join-Path $repoRoot 'tools\magisk\Magisk-v31.1.apk'
if (Test-Path -LiteralPath $magiskApk) {
    $hash = (Get-FileHash -LiteralPath $magiskApk -Algorithm SHA256).Hash.ToLower()
    $expected = '89cefac0a318afa39fb3880c45c87b036c05bc1ebf02a7a715b7f8d7c26ac6e7'
    if ($hash -eq $expected) { Add-Item 'PASS' 'Magisk APK：SHA256 校验通过' }
    else { Add-Item 'FAIL' "Magisk APK SHA256 不匹配（实际 $hash）" }
} else { Add-Item 'FAIL' 'Magisk APK 缺失：tools\magisk\Magisk-v31.1.apk' }

# 6. 固件与备份
$firmware = @(Get-ChildItem -Path (Join-Path $repoRoot 'backup\firmware'), (Join-Path $repoRoot 'tools\firmware') -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '\.(tgz|zip)$' })
if ($firmware.Count -gt 0) { Add-Item 'PASS' ("固件包：已找到 " + $firmware.Count + " 个 → " + $firmware[0].Name) }
else { Add-Item 'WARN' '未找到原厂固件包（backup\firmware\*.tgz）：Root 前必须获取，解锁后可继续' }

$backupDir = Join-Path $repoRoot 'backup'
$backupFiles = @(Get-ChildItem -Path $backupDir -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\firmware\\' })
if ($backupFiles.Count -gt 0) { Add-Item 'PASS' ("A 方案备份：backup\ 下有 " + $backupFiles.Count + " 个文件") }
else { Add-Item 'FAIL' 'A 方案备份缺失：解锁会清空所有数据，必须先备份（docs/05 §2.2）' }

Write-Host ''
Write-Host '=== 结果汇总 ===' -ForegroundColor Cyan
Write-Host ("检查项：" + $results.Count + "，阻断项：" + $(if ($hasFail) { '有（见 FAIL）' } else { '无' }))
Write-Host ''
Write-Host '下一步：'
Write-Host '  1) 若 Bootloader 锁定 → 先执行 Gate B0 验证（docs\05-B路线执行手册.md §1）'
Write-Host '  2) 若 Gate B0 通过 → 完成备份与固件准备后，按 §3 解锁'
Write-Host '  3) 若 Gate B0 失败（国行受限）→ 按 §9 转 A+ 无 Root 优化方案'
if ($hasFail) { exit 1 } else { exit 0 }
