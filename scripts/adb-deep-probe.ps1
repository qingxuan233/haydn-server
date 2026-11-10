# 安卓/小米深度 ADB 能力探查（只读，不修改设备状态）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\adb-deep-probe.ps1 [-Serial <serial>] [-OutDir <dir>]
# 输出：inventory\deep-probe-<timestamp>.md
param(
    [string]$Serial = '',
    [string]$OutDir = ''
)

$ErrorActionPreference = 'Continue'
$adb = Join-Path $PSScriptRoot '..\tools\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { Write-Host "找不到 adb: $adb"; exit 1 }
$serialArgs = @()
if ($Serial) { $serialArgs = @('-s', $Serial) }
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot '..\inventory' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function A([string]$cmd) { (& $adb @serialArgs shell $cmd 2>&1) -join "`n" }
function Section([System.Text.StringBuilder]$sb, [string]$title, [string]$cmd) {
    [void]$sb.AppendLine("## $title"); [void]$sb.AppendLine('```text')
    $body = A $cmd
    if ($body.Length -gt 8000) { $body = $body.Substring(0, 8000) + "`n... (truncated)" }
    [void]$sb.AppendLine($body.TrimEnd()); [void]$sb.AppendLine('```'); [void]$sb.AppendLine('')
}

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('# 安卓深度 ADB 能力探查报告'); [void]$sb.AppendLine('')
[void]$sb.AppendLine(('- 时间：' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')))
[void]$sb.AppendLine(('- ADB 设备：' + ((& $adb @serialArgs get-serialno 2>&1) -join '').Trim()))
[void]$sb.AppendLine('')

Section $sb '1. 设备基础信息' 'getprop ro.product.model; getprop ro.product.device; getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.miui.build.region; getprop ro.build.version.incremental'
Section $sb '2. `cmd -l`（可用的系统服务命令入口）' 'cmd -l'
Section $sb '3. `dpm`（DevicePolicyManager）能力' 'dpm 2>&1 | head -40; echo ---LIST-OWNERS---; dpm list-owners'
Section $sb '4. `pm list users` / 多用户' 'pm list users'
Section $sb '5. `pm` 关键子命令' 'cmd package 2>&1 | grep -E "compile|suspend|unsuspend|install-existing|list packages" -A2 | head -40'
Section $sb '6. `cmd appops` 能力' 'cmd appops 2>&1 | head -30'
Section $sb '7. `device_config` 可调命名空间（只读）' 'device_config list 2>&1 | head -80'
Section $sb '8. `cmd overlay`（RRO 覆盖层）' 'cmd overlay list 2>&1 | head -40'
Section $sb '9. 显示密度/尺寸（可写，测试后已恢复）' 'wm density; wm size'
Section $sb '10. 关键系统设置（ADB/安装/安全相关）' 'settings list global | grep -iE "adb|install|verifier|package" | head -20'
Section $sb '11. 包统计' 'echo -n "total="; pm list packages --user 0 | wc -l; echo -n "thirdparty="; pm list packages -3 --user 0 | wc -l; echo -n "disabled="; pm list packages -d --user 0 | wc -l'
Section $sb '12. 典型 AppOps 状态' 'cmd appops get com.termux RUN_ANY_IN_BACKGROUND; cmd appops get com.miui.analytics RUN_ANY_IN_BACKGROUND'
Section $sb '13. service list（Binder 服务，前 60 行）' 'service list 2>&1 | head -60'

$out = Join-Path $OutDir ('deep-probe-' + (Get-Date).ToString('yyyyMMdd-HHmmss') + '.md')
[System.IO.File]::WriteAllText($out, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Host ("报告已写入: " + $out)
