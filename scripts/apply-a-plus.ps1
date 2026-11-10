<#
.SYNOPSIS
    A+ 无 Root 深度优化：应用可逆的系统设置与安全 debloat。
.DESCRIPTION
    默认 DryRun（只打印计划与原值，不修改）。使用 -Apply 执行；-Restore 按最近一次日志回滚。
    所有变更都会记录到 inventory\apply-a-plus-*.json 与 latest 副本，包含原值与恢复命令。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\apply-a-plus.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\apply-a-plus.ps1 -Apply
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\apply-a-plus.ps1 -Restore
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Restore,
    [string]$AdbPath
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$invDir = Join-Path $repoRoot 'inventory'
New-Item -ItemType Directory -Force -Path $invDir | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Resolve-Adb {
    param([string]$Explicit)
    foreach ($candidate in @($Explicit, $env:ADB_PATH, (Join-Path $repoRoot 'tools\platform-tools\adb.exe'))) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw '找不到 adb'
}
function Invoke-Adb {
    param([string[]]$AdbArgs)
    $out = & $script:Adb @AdbArgs 2>&1 | Out-String
    return $out.TrimEnd()
}
function Get-Setting {
    param([string]$Namespace, [string]$Key)
    $v = (Invoke-Adb @('shell', 'settings', 'get', $Namespace, $Key)) -replace "`r|`n", ''
    return $v.Trim()
}

$Adb = Resolve-Adb -Explicit $AdbPath
& $Adb start-server 2>$null | Out-Null
$devices = ((& $Adb devices -l) -join "`n")
$serial = $null
foreach ($line in ($devices -split "`r?`n")) { if ($line -match '^([0-9A-Za-z]+)\s+device') { $serial = $Matches[1]; break } }
if (-not $serial) { throw '未检测到已授权设备' }

$logJsonLatest = Join-Path $invDir 'apply-a-plus-latest.json'

# ---------- Restore ----------
if ($Restore) {
    if (-not (Test-Path -LiteralPath $logJsonLatest)) { throw "没有可用的回滚日志：$logJsonLatest" }
    $log = Get-Content -LiteralPath $logJsonLatest -Raw | ConvertFrom-Json
    Write-Host "=== 回滚：恢复设置 ===" -ForegroundColor Yellow
    foreach ($s in $log.settings) {
        $v = [string]$s.original
        if ($v) { Invoke-Adb @('shell', 'settings', 'put', $s.namespace, $s.key, $v) | Out-Null }
        Write-Host ("  settings put {0} {1} = {2}" -f $s.namespace, $s.key, $v)
    }
    Write-Host "=== 回滚：恢复被禁用应用 ===" -ForegroundColor Yellow
    foreach ($p in $log.packages) {
        if ($p.disabled) { Invoke-Adb @('shell', 'pm', 'enable', $p.package) | Out-Null; Write-Host ("  pm enable " + $p.package) }
    }
    Write-Host '回滚完成。' -ForegroundColor Green
    exit 0
}

# ---------- 计划 ----------
$settingsChanges = @(
    @{ ns = 'global'; key = 'window_animation_scale';    value = '0';    why = '动画归零，降低渲染开销' },
    @{ ns = 'global'; key = 'transition_animation_scale'; value = '0';   why = '同上' },
    @{ ns = 'global'; key = 'animator_duration_scale';    value = '0';   why = '同上' },
    @{ ns = 'system'; key = 'screen_off_timeout';         value = '15000'; why = '熄屏 15 秒，服务器场景省电降温' },
    @{ ns = 'system'; key = 'peak_refresh_rate';          value = '60';   why = '120Hz → 60Hz 省电（注：HyperOS 可能强制回 120）' },
    @{ ns = 'system'; key = 'user_refresh_rate';          value = '60';   why = '同上' },
    @{ ns = 'system'; key = 'screen_brightness_mode';     value = '0';    why = '关闭自动亮度，固定低亮度' },
    @{ ns = 'system'; key = 'screen_brightness';          value = '10';   why = '最低亮度（息屏为主）' },
    @{ ns = 'secure'; key = 'location_mode';             value = '0';    why = '关闭定位（服务器不需要，省电）' },
    @{ ns = 'global'; key = 'ble_scan_always_enabled';    value = '0';    why = '关闭常开蓝牙扫描' },
    @{ ns = 'global'; key = 'wifi_scan_always_enabled';   value = '0';    why = '关闭常开 WiFi 扫描' }
)

# 保守 debloat 清单（均为可 pm enable 恢复；避开系统核心组件）
$debloat = @(
    @{ pkg = 'com.miui.video';                 why = '视频 App' },
    @{ pkg = 'com.miui.newhome';               why = '内容中心' },
    @{ pkg = 'com.xiaomi.shop';                why = '小米商城' },
    @{ pkg = 'com.mfashiongallery.emag';       why = '壁纸画报/轮播' },
    @{ pkg = 'com.miui.miservice';             why = '服务反馈' },
    @{ pkg = 'com.miui.huanji';                why = '换机助手' },
    @{ pkg = 'com.xiaomi.gamecenter.sdk.service'; why = '游戏中心服务' },
    @{ pkg = 'com.baidu.carlife.xiaomi';       why = 'CarLife 车机' },
    @{ pkg = 'com.miui.newmidrive';            why = '车机互联' },
    @{ pkg = 'com.duokan.phone.remotecontroller'; why = '红外遥控器' },
    @{ pkg = 'com.miui.cleanmaster';           why = '清理大师' },
    @{ pkg = 'com.miui.compass';               why = '指南针' },
    @{ pkg = 'com.xiaomi.vipaccount';          why = '小米社区（B 路线已终止，不再需要）' }
)

Write-Host ('=== A+ 优化计划（设备 ' + $serial + '） ===') -ForegroundColor Cyan
Write-Host ''
Write-Host '--- 系统设置变更（含原值） ---'
$settingPlan = @()
foreach ($s in $settingsChanges) {
    $orig = Get-Setting $s.ns $s.key
    $settingPlan += [ordered]@{ namespace = $s.ns; key = $s.key; original = $orig; value = $s.value; why = $s.why }
    Write-Host ("  {0,-5} {1,-26} {2} -> {3}   ({4})" -f $s.ns, $s.key, $orig, $s.value, $s.why)
}

Write-Host ''
Write-Host '--- Debloat 清单（逐包可恢复） ---'
$installed = ((& $Adb shell pm list packages) -join "`n")
$disabledList = ((& $Adb shell pm list packages -d) -join "`n")
$pkgPlan = @()
foreach ($d in $debloat) {
    $isInstalled = $installed -match ('package:' + [regex]::Escape($d.pkg))
    $isDisabled = $disabledList -match ('package:' + [regex]::Escape($d.pkg))
    $pkgPlan += [ordered]@{ package = $d.pkg; why = $d.why; installed = [bool]$isInstalled; alreadyDisabled = [bool]$isDisabled; disabled = $false }
    $state = if ($isDisabled) { '已禁用' } elseif ($isInstalled) { '将禁用' } else { '未安装' }
    Write-Host ("  {0,-38} {1}   ({2})" -f $d.pkg, $state, $d.why)
}

if (-not $Apply) {
    Write-Host ''
    Write-Host 'DRY-RUN：未做任何修改。确认无误后加 -Apply 执行。' -ForegroundColor Yellow
    exit 0
}

# ---------- 执行 ----------
Write-Host ''
Write-Host '=== 执行系统设置 ===' -ForegroundColor Cyan
$appliedSettings = @()
foreach ($s in $settingsChanges) {
    $o = Get-Setting $s.ns $s.key
    Invoke-Adb @('shell', 'settings', 'put', $s.ns, $s.key, $s.value) | Out-Null
    $after = Get-Setting $s.ns $s.key
    $ok = ($after -eq $s.value)
    Write-Host ("  {0,-5} {1,-26} {2} -> {3}   [{4}]" -f $s.ns, $s.key, $o, $after, $(if ($ok) { 'OK' } else { '未生效' })) -ForegroundColor $(if ($ok) { 'Green' } else { 'Yellow' })
}

Write-Host ''
Write-Host '=== 执行 Debloat ===' -ForegroundColor Cyan
$failedPkgs = 0
foreach ($p in $pkgPlan) {
    if (-not $p.installed -or $p.alreadyDisabled) { continue }
    $out = Invoke-Adb @('shell', 'pm', 'disable-user', '--user', '0', $p.package)
    if ($out -match 'new state: disabled') { $p.disabled = $true }
    else { $failedPkgs++; Write-Host ("  [失败] " + $p.package + " -> " + $out) -ForegroundColor Yellow }
}

# 验证禁用结果
Write-Host ''
Write-Host '=== 验证 ===' -ForegroundColor Cyan
$disabledAfter = ((& $Adb shell pm list packages -d) -join "`n")
$verified = 0
foreach ($p in $pkgPlan) {
    if ($p.package -and $disabledAfter -match ('package:' + [regex]::Escape($p.package))) {
        $p.disabled = $true; $verified++
        Write-Host ("  [已禁用] " + $p.package)
    }
}
Write-Host ("  已禁用包数：" + $verified + "，失败：" + $failedPkgs)

# 稳定性抽查：系统是否仍响应 + 最近是否出现致命崩溃
$alive = Invoke-Adb @('shell', 'echo ALIVE')
if ($alive -match 'ALIVE') { Write-Host '  [OK] shell 响应正常' } else { Write-Host '  [WARN] shell 响应异常' -ForegroundColor Yellow }
$fatals = ((& $Adb shell logcat -d -t 300) -join "`n") | Select-String -Pattern 'FATAL EXCEPTION|AndroidRuntime.*FATAL' -SimpleMatch:$false
if ($fatals) { Write-Host '  [WARN] 最近日志出现 FATAL，请检查是否刚禁用应用导致：' -ForegroundColor Yellow; $fatals | Select-Object -First 5 } else { Write-Host '  [OK] 最近 300 行日志无 FATAL' }

# ---------- 写日志 ----------
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logObj = [ordered]@{
    schemaVersion = 1
    appliedAt   = (Get-Date).ToString('o')
    serial      = $serial
    mode        = 'apply'
    settings    = $settingPlan
    packages    = $pkgPlan
}
$jsonPath = Join-Path $invDir ("apply-a-plus-$stamp.json")
$jsonText = $logObj | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($jsonPath, $jsonText, $utf8NoBom)
Copy-Item -LiteralPath $jsonPath -Destination $logJsonLatest -Force

$mdPath = Join-Path $invDir ("apply-a-plus-$stamp.md")
$md = New-Object 'System.Collections.Generic.List[string]'
[void]$md.Add('# A+ 优化执行记录 ' + (Get-Date).ToString('yyyy-MM-dd HH:mm'))
[void]$md.Add(''); [void]$md.Add('设备：' + $serial)
[void]$md.Add(''); [void]$md.Add('## 系统设置')
foreach ($s in $settingPlan) { [void]$md.Add(('- `{0}` {1}: {2} -> {3}  （{4}）' -f $s.namespace, $s.key, $s.original, $s.value, $s.why)) }
[void]$md.Add(''); [void]$md.Add('## 被禁用应用')
foreach ($p in $pkgPlan) { if ($p.disabled) { [void]$md.Add(('- `' + $p.package + '` （' + $p.why + '）' )) } }
[void]$md.Add(''); [void]$md.Add('## 回滚命令')
[void]$md.Add('```powershell')
[void]$md.Add('powershell -ExecutionPolicy Bypass -File scripts\apply-a-plus.ps1 -Restore')
[void]$md.Add('# 或手动：')
foreach ($p in $pkgPlan) { if ($p.disabled) { [void]$md.Add('adb shell pm enable ' + $p.package) } }
foreach ($s in $settingPlan) { if ($s.original) { [void]$md.Add(('adb shell settings put {0} {1} {2}' -f $s.namespace, $s.key, $s.original)) } }
[void]$md.Add('```')
[System.IO.File]::WriteAllLines($mdPath, $md, $utf8NoBom)

Write-Host ''
Write-Host ("执行完成。日志：$jsonPath") -ForegroundColor Green
Write-Host ("回滚：powershell -ExecutionPolicy Bypass -File scripts\apply-a-plus.ps1 -Restore") -ForegroundColor Yellow
