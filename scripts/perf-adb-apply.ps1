# 性能优化 P0/P1 的 ADB 侧一键执行/回滚
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\perf-adb-apply.ps1 -Apply
#   powershell -ExecutionPolicy Bypass -File scripts\perf-adb-apply.ps1 -Status
#   powershell -ExecutionPolicy Bypass -File scripts\perf-adb-apply.ps1 -Restore
# 说明：不卸载任何应用；suspend/appops 全部可逆；重启后 cached_apps_freezer/logcat 会被 MIUI 重置，需重放。

param(
    [switch]$Apply,
    [switch]$Restore,
    [switch]$Status
)

$ErrorActionPreference = 'Continue'
$adb = Join-Path $PSScriptRoot '..\tools\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { Write-Host "找不到 adb: $adb"; exit 1 }

# 非关键预装应用（可随时 unsuspend / 恢复 appops）
$apps = @(
    'com.miui.analytics',
    'com.milink.service',
    'com.xiaomi.mi_connect_service',
    'com.miui.mishare.connectivity',
    'com.miui.tsmclient',
    'com.miui.personalassistant',
    'com.miui.voiceassist',
    'com.miui.bugreport',
    'com.google.android.marvin.talkback',
    'com.android.printspooler',
    'com.sohu.inputmethod.sogou.xiaomi'
)

function Invoke-Adb([string]$cmd) {
    & $adb shell $cmd 2>&1 | Out-Null
}

if ($Status) {
    Write-Host '=== P0 设置 ==='
    & $adb shell 'settings get global cached_apps_freezer'
    & $adb shell 'logcat -g' 2>&1 | Select-Object -First 1
    & $adb shell 'settings get secure default_input_method'
    Write-Host '=== 应用状态（suspended / RUN_ANY_IN_BACKGROUND）==='
    foreach ($p in $apps) {
        $s = (& $adb shell "dumpsys package $p 2>/dev/null | grep -m1 'suspended='") -join ''
        $op = (& $adb shell "cmd appops get $p RUN_ANY_IN_BACKGROUND 2>/dev/null | tail -1") -join ''
        Write-Host ("{0,-42} {1}  {2}" -f $p, $s.Trim(), $op.Trim())
    }
    exit 0
}

if ($Apply) {
    Write-Host '=== P0：缓存冻结 + 日志缓冲 ==='
    & $adb shell 'settings put global cached_apps_freezer enabled'
    & $adb shell 'logcat -G 1M; logcat -c'
    & $adb shell 'settings get global cached_apps_freezer'
    Write-Host '=== P1：appops 后台限制 + suspend + force-stop ==='
    foreach ($p in $apps) {
        $exists = (& $adb shell "pm path $p" 2>&1) -join ''
        if ($exists -match 'package:') {
            Invoke-Adb "cmd appops set $p RUN_ANY_IN_BACKGROUND ignore"
            Invoke-Adb "cmd deviceidle whitelist -$p"
            Invoke-Adb "cmd package suspend --user 0 $p"
            Invoke-Adb "am force-stop $p"
            Write-Host ("  applied: " + $p)
        } else {
            Write-Host ("  skip(not installed): " + $p)
        }
    }
    Write-Host '完成。重启后如需保持 freezer/logcat，重跑本脚本 -Apply 或仅执行前两条 settings/logcat 命令。'
    exit 0
}

if ($Restore) {
    Write-Host '=== 恢复 apps ==='
    foreach ($p in $apps) {
        $exists = (& $adb shell "pm path $p" 2>&1) -join ''
        if ($exists -match 'package:') {
            Invoke-Adb "cmd package unsuspend --user 0 $p"
            Invoke-Adb "cmd appops set $p RUN_ANY_IN_BACKGROUND default"
            Write-Host ("  restored: " + $p)
        }
    }
    Write-Host '=== 恢复 P0 设置 ==='
    & $adb shell 'settings put global cached_apps_freezer disabled'
    & $adb shell 'logcat -G 2M'
    Write-Host '完成。IME 若需恢复：settings put secure default_input_method com.sohu.inputmethod.sogou.xiaomi/.SogouIME'
    exit 0
}

Write-Host '用法: -Apply | -Status | -Restore'
