<#
.SYNOPSIS
    服务器模式 Debloat：无 Root 下通过 ADB 移除/禁用非必要组件（可回滚）。
.DESCRIPTION
    分两档：
      safe      —— 媒体/UI/预装第三方/个人助理类（不影响开机、网络、Termux）
      aggressive—— Google 服务框架(可选) / 小米云与统计 / 推送 / AI 识别 / 隐私计算等后台服务
    不触碰：systemui、settings、providers.*、networkstack、telephony、蓝牙、存储、权限、安全中心、
            Termux/Termux:Boot/Clash/ToDesk/MT 管理器、输入法、miui 核心服务（详见 NEVER 说明）。
    默认 DryRun（只列出计划）；-Apply 执行；-Restore 按最近日志恢复。
    所有操作记录到 inventory\debloat-*.json 与 latest 副本。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\debloat-server-mode.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\debloat-server-mode.ps1 -Tier safe -Apply
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\debloat-server-mode.ps1 -Tier aggressive -Apply
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\debloat-server-mode.ps1 -Restore
#>
[CmdletBinding()]
param(
    [ValidateSet('safe', 'aggressive', 'all')]
    [string]$Tier = 'safe',
    [switch]$Apply,
    [switch]$Restore,
    [string]$AdbPath
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$invDir = Join-Path $repoRoot 'inventory'
New-Item -ItemType Directory -Force -Path $invDir | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$logLatest = Join-Path $invDir 'debloat-latest.json'

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

$Adb = Resolve-Adb -Explicit $AdbPath
& $Adb start-server 2>$null | Out-Null
$devices = ((& $Adb devices -l) -join "`n")
$serial = $null
foreach ($line in ($devices -split "`r?`n")) { if ($line -match '^([0-9A-Za-z]+)\s+device') { $serial = $Matches[1]; break } }
if (-not $serial) { throw '未检测到已授权设备' }

# ---------- 回滚 ----------
if ($Restore) {
    if (-not (Test-Path -LiteralPath $logLatest)) { throw "没有可用的 debloat 日志：$logLatest" }
    $log = Get-Content -LiteralPath $logLatest -Raw | ConvertFrom-Json
    Write-Host '=== 回滚：恢复被移除/禁用的组件 ===' -ForegroundColor Yellow
    foreach ($p in $log.packages) {
        if ($p.method -eq 'uninstall') {
            $out = Invoke-Adb @('shell', 'cmd', 'package', 'install-existing', '--user', '0', $p.package)
            Write-Host ("  [install-existing] {0} -> {1}" -f $p.package, $out)
        } elseif ($p.method -eq 'disable') {
            $out = Invoke-Adb @('shell', 'pm', 'enable', $p.package)
            Write-Host ("  [pm enable] {0}" -f $p.package)
        }
    }
    foreach ($s in $log.settings) {
        if ($s.original) { Invoke-Adb @('shell', 'settings', 'put', $s.namespace, $s.key, [string]$s.original) | Out-Null; Write-Host ("  settings put {0} {1} = {2}" -f $s.namespace, $s.key, $s.original) }
    }
    Write-Host '回滚完成（第三方 App 若曾被彻底卸载，需要重新安装 APK）。' -ForegroundColor Green
    exit 0
}

# ---------- 清单 ----------
$safeList = @(
    # Android UI / 媒体 / 个人应用
    'com.android.browser', 'com.android.mms', 'com.android.incallui', 'com.android.calendar',
    'com.android.camera', 'com.android.fileexplorer', 'com.android.deskclock', 'com.android.soundrecorder',
    'com.android.printspooler', 'com.android.bips', 'com.android.wallpapercropper', 'com.android.wallpaper.livepicker',
    'com.android.dreams.basic', 'com.android.apps.tag', 'com.android.emergency', 'com.android.quicksearchbox',
    'com.android.calllogbackup', 'com.android.managedprovisioning', 'com.android.traceur', 'com.android.musicfx',
    'com.android.healthconnect.controller', 'com.android.health.connect.backuprestore', 'com.android.nearby.halfsheet',
    'com.android.stk', 'com.android.companiondevicemanager',
    # 小米媒体/工具/个性化
    'com.miui.video', 'com.miui.notes', 'com.miui.calculator', 'com.miui.screenrecorder', 'com.miui.weather2',
    'com.miui.compass', 'com.miui.gallery', 'com.miui.mediaeditor', 'com.miui.mediaviewer', 'com.miui.player',
    'com.miui.phrase', 'com.miui.extraphoto', 'com.miui.qr', 'com.miui.yellowpage', 'com.miui.userguide',
    'com.miui.cit', 'com.miui.bugreport', 'com.miui.miservice', 'com.miui.vipservice', 'com.miui.nextpay',
    'com.miui.touchassistant', 'com.miui.contentextension', 'com.miui.contentcatcher', 'com.miui.hybrid',
    'com.miui.personalassistant', 'com.miui.freeform', 'com.miui.carlink', 'com.miui.mishare.connectivity',
    'com.miui.tsmclient', 'com.miui.aod', 'com.miui.miwallpaper.moon', 'com.miui.miwallpaper.snowmountain',
    'com.miui.miwallpaper.mars', 'com.miui.miwallpaper.earth',
    # 语音/助手/AI
    'com.miui.voiceassist', 'com.miui.voicetrigger', 'com.miui.voiceassistoverlay', 'com.xiaomi.mibrain.speech',
    'com.xiaomi.aiasst.service', 'com.xiaomi.aiasst.vision', 'com.xiaomi.aicr', 'com.xiaomi.aireco',
    # 预装第三方 / 运营商
    'tv.twitch.android.app', 'cn.wps.moffice_eng.xiaomi.lite', 'com.layaboxhmhz.gamehmhz.okys',
    'com.google.ar.core', 'com.standardar.service', 'com.baidu.input_mi', 'com.google.android.ims',
    'mark.via', 'com.cmcc.simsecurity', 'com.cmcc.simauthn', 'com.xiaomi.scanner', 'com.miui.findmy',
    'com.xiaomi.mifisecurity', 'com.xiaomi.mimobile.noti', 'com.xiaomi.macro', 'com.xiaomi.mirror',
    'com.xiaomi.cameratools', 'com.xiaomi.migameservice', 'com.xiaomi.gamecenter.sdk.service'
)

$aggressiveList = @(
    # Google 服务框架与商店（移除后 Play 生态不可用；Termux 不受影响）
    'com.google.android.gms', 'com.android.vending', 'com.google.android.gsf',
    'com.google.android.gms.location.history', 'com.google.android.configupdater',
    'com.google.android.onetimeinitializer', 'com.google.android.ext.services',
    'com.google.android.ext.shared', 'com.google.android.safetycore',
    'com.google.android.printservice.recommendation', 'com.google.android.accessibility.switchaccess',
    'com.google.android.marvin.talkback',
    # 小米云/账号/推送/统计/设备注册
    'com.xiaomi.xmsf', 'com.xiaomi.xmsfkeeper', 'com.xiaomi.metoknlp', 'com.xiaomi.security.onetrack',
    'com.xiaomi.ab', 'com.xiaomi.barrage', 'com.xiaomi.market', 'com.xiaomi.finddevice', 'com.xiaomi.account',
    'com.xiaomi.registration', 'com.xiaomi.devauth', 'com.xiaomi.trustservice', 'com.xiaomi.mis',
    'com.xiaomi.ugd', 'com.xiaomi.otrpbroker', 'com.xiaomi.mtb', 'com.xiaomi.simactivate.service',
    'com.xiaomi.location.fused', 'com.xiaomi.gnss.polaris', 'com.xiaomi.mi_connect_service',
    'com.xiaomi.micloud.sdk', 'com.xiaomi.digitalkey', 'com.xiaomi.xaee',
    'com.miui.cloudservice', 'com.miui.cloudbackup', 'com.miui.micloudsync', 'com.miui.analytics',
    'com.miui.dmregservice', 'com.miui.face', 'com.miui.securityinputmethod',
    # Android 隐私计算/广告/联邦学习 与 NFC
    'com.android.ondevicepersonalization.services', 'com.android.adservices.api',
    'com.android.federatedcompute.services', 'com.android.nfc'
)

# ---------- 设备状态 ----------
$installedRaw = ((& $Adb shell pm list packages) -join "`n")
$disabledRaw  = ((& $Adb shell pm list packages -d) -join "`n")
$thirdRaw     = ((& $Adb shell pm list packages -3) -join "`n")
function Test-Installed { param([string]$Pkg) return [bool]($installedRaw -match ('package:' + [regex]::Escape($Pkg))) }
function Test-Disabled  { param([string]$Pkg) return [bool]($disabledRaw  -match ('package:' + [regex]::Escape($Pkg))) }
function Test-ThirdParty{ param([string]$Pkg) return [bool]($thirdRaw     -match ('package:' + [regex]::Escape($Pkg))) }

$targets = @()
if ($Tier -in @('safe', 'all')) { $targets += $safeList }
if ($Tier -in @('aggressive', 'all')) { $targets += $aggressiveList }
$targets = $targets | Select-Object -Unique

$plan = @()
foreach ($pkg in $targets) {
    $item = [ordered]@{ package = $pkg; installed = (Test-Installed $pkg); alreadyDisabled = (Test-Disabled $pkg); thirdParty = (Test-ThirdParty $pkg); method = $null; result = $null }
    $plan += $item
}

Write-Host ('=== 服务器模式 Debloat（设备 ' + $serial + '，档位 ' + $Tier + '，共 ' + $targets.Count + ' 个候选） ===') -ForegroundColor Cyan
$toAct = @($plan | Where-Object { $_.installed -and -not $_.alreadyDisabled })
Write-Host ("  - 将处理：" + $toAct.Count + " 个；已禁用/不存在：" + ($plan.Count - $toAct.Count) + " 个")

$memTextBefore = ((& $Adb shell cat /proc/meminfo) -join "`n"); $memBefore = if ($memTextBefore -match '(?m)^MemAvailable:\s*(\d+)') { [math]::Round([int64]$Matches[1] / 1048576, 2) } else { $null }
Write-Host ("  - 处理前 MemAvailable：" + $memBefore + " GiB")

if (-not $Apply) {
    Write-Host ''
    Write-Host '--- 计划清单 ---'
    foreach ($p in $plan) {
        $state = if (-not $p.installed) { '未安装' } elseif ($p.alreadyDisabled) { '已禁用' } else { '将移除' }
        $kind = if ($p.thirdParty) { '第三方' } else { '系统' }
        Write-Host ("  [{0}] {1,-42} {2,-8} {3}" -f $kind, $p.package, $state, $(if ($p.thirdParty -and $state -eq '将移除') { '（恢复需重装 APK）' } else { '' }))
    }
    Write-Host ''
    Write-Host 'DRY-RUN：未做修改。确认后加 -Apply。' -ForegroundColor Yellow
    exit 0
}

# ---------- 执行 ----------
Write-Host ''
Write-Host '=== 执行 ===' -ForegroundColor Cyan
$failed = 0; $done = 0
foreach ($p in @($plan | Where-Object { $_.installed -and -not $_.alreadyDisabled })) {
    $unOut = Invoke-Adb @('shell', 'pm', 'uninstall', '--user', '0', $p.package)
    if ($unOut -match 'Success') { $p.method = 'uninstall'; $p.result = 'removed'; $done++; Write-Host ("  [移除] " + $p.package) -ForegroundColor Green; continue }
    $disOut = Invoke-Adb @('shell', 'pm', 'disable-user', '--user', '0', $p.package)
    if ($disOut -match 'new state: disabled') { $p.method = 'disable'; $p.result = 'disabled'; $done++; Write-Host ("  [禁用] " + $p.package) -ForegroundColor Yellow; continue }
    $p.result = 'protected'; $failed++
    $brief = if ($unOut -match 'Cannot disable system packages') { '系统保护' } elseif ($unOut -match 'DELETE_FAILED') { '禁止删除' } else { ($unOut -split "`r?`n" | Select-Object -First 1) }
    Write-Host ("  [失败] {0} -> {1}" -f $p.package, $brief) -ForegroundColor DarkYellow
}

# Termux 保活：电池白名单 + 允许后台运行（防止 HyperOS 杀进程）
Invoke-Adb @('shell', 'cmd', 'deviceidle', 'whitelist', '+com.termux') | Out-Null
Invoke-Adb @('shell', 'cmd', 'deviceidle', 'whitelist', '+com.termux.boot') | Out-Null
Invoke-Adb @('shell', 'cmd', 'appops', 'set', 'com.termux', 'RUN_ANY_IN_BACKGROUND', 'allow') | Out-Null
# 缓存压缩：清理后台进程（临时动作，不改变配置）
# 注意：绝不能在此执行 am kill-all——2026-11-10 实测会连带杀掉 Termux/proot/supervisord 全部服务。
$freezerOrig = ((Invoke-Adb @('shell', 'settings', 'get', 'global', 'cached_apps_freezer')) -replace "`r|`n", '').Trim()
$settingsApplied = @()
if ($Apply) {
    Invoke-Adb @('shell', 'settings', 'put', 'global', 'cached_apps_freezer', 'enabled') | Out-Null
    $settingsApplied += [ordered]@{ namespace = 'global'; key = 'cached_apps_freezer'; original = $freezerOrig; value = 'enabled' }
}

# 验证
Write-Host ''
Write-Host '=== 验证 ===' -ForegroundColor Cyan
$alive = Invoke-Adb @('shell', 'echo ALIVE')
Write-Host ('  shell 响应：' + $(if ($alive -match 'ALIVE') { 'OK' } else { '异常' }))
$disabledAfter = ((& $Adb shell pm list packages -d) -join "`n")
$installedAfter = ((& $Adb shell pm list packages) -join "`n")
$removedCount = 0; $disabledCount = 0
foreach ($p in $plan) {
    if ($p.method) {
        if ($p.method -eq 'uninstall' -and -not ($installedAfter -match ('package:' + [regex]::Escape($p.package)))) { $removedCount++ }
        if ($p.method -eq 'disable' -and ($disabledAfter -match ('package:' + [regex]::Escape($p.package)))) { $disabledCount++ }
    }
}
Write-Host ("  已移除：" + $removedCount + "；已禁用：" + $disabledCount + "；受系统保护：" + $failed)
$fatal = ((& $Adb shell logcat -d -t 300) -join "`n") | Select-String -Pattern 'FATAL EXCEPTION' 
if ($fatal) { Write-Host '  [WARN] 最近 300 行日志出现 FATAL，疑似误删：' -ForegroundColor Yellow; $fatal | Select-Object -First 5 } else { Write-Host '  [OK] 最近 300 行日志无 FATAL' }

$memTextAfter = ((& $Adb shell cat /proc/meminfo) -join "`n"); $memAfter = if ($memTextAfter -match '(?m)^MemAvailable:\s*(\d+)') { [math]::Round([int64]$Matches[1] / 1048576, 2) } else { $null }
Write-Host ("  MemAvailable：" + $memBefore + " GiB -> " + $memAfter + " GiB")
$load = ((& $Adb shell cat /proc/loadavg) -join '').Trim()
Write-Host ("  loadavg：" + $load)

# ---------- 日志 ----------
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logObj = [ordered]@{
    schemaVersion = 1
    appliedAt = (Get-Date).ToString('o')
    serial = $serial
    tier = $Tier
    memBeforeGiB = $memBefore
    memAfterGiB = $memAfter
    removed = $removedCount
    disabled = $disabledCount
    protected = $failed
    packages = $plan
    settings = $settingsApplied
}
$jsonPath = Join-Path $invDir ("debloat-$Tier-$stamp.json")
$jsonText = $logObj | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($jsonPath, $jsonText, $utf8NoBom)
Copy-Item -LiteralPath $jsonPath -Destination $logLatest -Force

$md = New-Object 'System.Collections.Generic.List[string]'
[void]$md.Add('# Debloat 执行记录 ' + (Get-Date).ToString('yyyy-MM-dd HH:mm') + '（档位：' + $Tier + '）')
[void]$md.Add('')
[void]$md.Add('设备：' + $serial + '；MemAvailable ' + $memBefore + ' GiB -> ' + $memAfter + ' GiB')
[void]$md.Add('')
[void]$md.Add('## 已移除（uninstall --user 0）')
foreach ($p in $plan) { if ($p.method -eq 'uninstall') { [void]$md.Add('- `' + $p.package + '`') } }
[void]$md.Add('')
[void]$md.Add('## 已禁用（disable-user）')
foreach ($p in $plan) { if ($p.method -eq 'disable') { [void]$md.Add('- `' + $p.package + '`') } }
[void]$md.Add('')
[void]$md.Add('## 受系统保护（无 Root 无法处理）')
foreach ($p in $plan) { if ($p.result -eq 'protected') { [void]$md.Add('- `' + $p.package + '`') } }
[void]$md.Add('')
[void]$md.Add('## 回滚')
[void]$md.Add('```powershell')
[void]$md.Add('powershell -ExecutionPolicy Bypass -File scripts\debloat-server-mode.ps1 -Restore')
[void]$md.Add('```')
$mdPath = Join-Path $invDir ("debloat-$Tier-$stamp.md")
[System.IO.File]::WriteAllLines($mdPath, $md, $utf8NoBom)

Write-Host ''
Write-Host ("完成。日志：$jsonPath") -ForegroundColor Green
if ($failed -gt 0) { Write-Host ('注意：' + $failed + ' 个受系统保护，未处理（属正常）。') -ForegroundColor Yellow }
exit 0
