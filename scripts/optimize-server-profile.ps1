<#
.SYNOPSIS
    重置后安全优化（分批）：第 1 批卸载预装第三方 + 禁用 UI/媒体；-IncludeServices 再加后台服务/GMS。
.DESCRIPTION
    安全原则（2026-11-10 bootloop 事故后制定）：
      1. 系统包只用 pm disable-user（保持"已安装"状态，避免 Required services extension package 缺失导致 system_server 崩溃循环）；
      2. 第三方预装 App 用 uninstall --user 0（可从系统分区 install-existing 恢复）；
      3. 硬编码保护名单：ext.services / providers / systemui / settings / packageinstaller / 网络栈 / 电话 / 安全中心等一律不动；
      4. 分批执行，每批后重启验证；默认 DryRun；-Apply 执行；-Restore 恢复。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\optimize-server-profile.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\optimize-server-profile.ps1 -Apply
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\optimize-server-profile.ps1 -IncludeServices -Apply
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\optimize-server-profile.ps1 -Restore
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Restore,
    [switch]$IncludeServices,
    [string]$AdbPath
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$invDir = Join-Path $repoRoot 'inventory'
New-Item -ItemType Directory -Force -Path $invDir | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$logLatest = Join-Path $invDir 'optimize-profile-latest.json'

function Resolve-Adb {
    param([string]$Explicit)
    foreach ($c in @($Explicit, $env:ADB_PATH, (Join-Path $repoRoot 'tools\platform-tools\adb.exe'))) {
        if ($c -and (Test-Path -LiteralPath $c)) { return (Resolve-Path -LiteralPath $c).Path }
    }
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw '找不到 adb'
}
$Adb = Resolve-Adb -Explicit $AdbPath
& $Adb start-server 2>$null | Out-Null
$devices = ((& $Adb devices -l) -join "`n")
if (-not ($devices -match '(?m)^([0-9A-Za-z]+)\s+device')) { throw '设备未连接/未授权' }

$protected = @(
    'com.google.android.ext.services', 'com.google.android.ext.shared', 'com.google.android.webview',
    'com.android.systemui', 'com.android.settings', 'com.android.settings.intelligence',
    'com.android.packageinstaller', 'com.miui.packageinstaller', 'com.android.shell', 'com.android.keychain',
    'com.android.providers.settings', 'com.android.providers.media', 'com.android.providers.media.module',
    'com.android.providers.downloads', 'com.android.providers.telephony', 'com.android.providers.contacts',
    'com.android.providers.calendar', 'com.android.providers.userdictionary', 'com.android.providers.blockednumber',
    'com.android.networkstack', 'com.android.networkstack.tethering', 'com.android.networkstack.overlay.miui',
    'com.android.phone', 'com.android.server.telecom', 'org.codeaurora.ims', 'com.qualcomm.qcrilmsgtunnel',
    'com.android.bluetooth', 'com.xiaomi.bluetooth', 'com.android.nfc',
    'com.android.permissioncontroller', 'com.android.certinstaller', 'com.android.externalstorage',
    'com.android.mtp', 'com.android.storagemanager', 'com.android.se', 'com.android.modulemetadata',
    'com.android.intentresolver', 'com.android.sdksandbox', 'com.android.credentialmanager',
    'com.android.carrierconfig', 'com.android.cellbroadcastreceiver', 'com.android.cellbroadcastservice',
    'com.android.wifi.resources', 'com.android.wifi.resources.xiaomi',
    'com.miui.core', 'com.miui.core.internal.services', 'com.miui.system', 'com.miui.rom', 'com.miui.wmsvc',
    'com.miui.securitycenter', 'com.miui.securitycore', 'com.miui.securityadd', 'com.lbe.security.miui',
    'com.miui.guardprovider', 'com.miui.powerkeeper', 'com.miui.daemon', 'com.xiaomi.joyose',
    'com.miui.home', 'com.miui.notification', 'com.miui.miwallpaper', 'com.miui.screenshot',
    'com.termux', 'com.termux.boot', 'com.iflytek.inputmethod.miui'
)

# 第 1 批：UI / 媒体 / 个人应用（安全）
$uiDisable = @(
    'com.android.browser', 'com.android.mms', 'com.android.incallui', 'com.android.calendar', 'com.android.camera',
    'com.android.fileexplorer', 'com.android.deskclock', 'com.android.printspooler', 'com.android.bips',
    'com.android.wallpapercropper', 'com.android.wallpaper.livepicker', 'com.android.dreams.basic',
    'com.android.apps.tag', 'com.android.emergency', 'com.android.quicksearchbox', 'com.android.calllogbackup',
    'com.android.traceur', 'com.android.musicfx', 'com.android.nearby.halfsheet', 'com.android.stk',
    'com.android.companiondevicemanager',
    'com.miui.video', 'com.miui.notes', 'com.miui.calculator', 'com.miui.screenrecorder', 'com.miui.weather2',
    'com.miui.compass', 'com.miui.gallery', 'com.miui.mediaeditor', 'com.miui.mediaviewer', 'com.miui.player',
    'com.miui.phrase', 'com.miui.extraphoto', 'com.miui.qr', 'com.miui.yellowpage', 'com.miui.userguide',
    'com.miui.cit', 'com.miui.bugreport', 'com.miui.miservice', 'com.miui.vipservice', 'com.miui.nextpay',
    'com.miui.touchassistant', 'com.miui.contentextension', 'com.miui.contentcatcher', 'com.miui.hybrid',
    'com.miui.personalassistant', 'com.miui.freeform', 'com.miui.carlink', 'com.miui.mishare.connectivity',
    'com.miui.tsmclient', 'com.miui.aod', 'com.miui.miwallpaper.moon', 'com.miui.miwallpaper.snowmountain',
    'com.miui.miwallpaper.mars', 'com.miui.miwallpaper.earth',
    'com.miui.voiceassist', 'com.miui.voicetrigger', 'com.miui.voiceassistoverlay', 'com.xiaomi.mibrain.speech',
    'com.xiaomi.aiasst.service', 'com.xiaomi.aiasst.vision', 'com.xiaomi.aicr', 'com.xiaomi.aireco'
)

# 第 2 批：后台服务 / 云 / 推送 / 统计 / Google（-IncludeServices 才执行；仅 disable）
$servicesDisable = @(
    'com.xiaomi.xmsf', 'com.xiaomi.xmsfkeeper', 'com.xiaomi.metoknlp', 'com.xiaomi.security.onetrack',
    'com.xiaomi.ab', 'com.xiaomi.barrage', 'com.xiaomi.market', 'com.xiaomi.finddevice', 'com.xiaomi.account',
    'com.xiaomi.registration', 'com.xiaomi.devauth', 'com.xiaomi.trustservice', 'com.xiaomi.mis',
    'com.xiaomi.ugd', 'com.xiaomi.otrpbroker', 'com.xiaomi.mtb', 'com.xiaomi.simactivate.service',
    'com.xiaomi.location.fused', 'com.xiaomi.gnss.polaris', 'com.xiaomi.mi_connect_service',
    'com.xiaomi.micloud.sdk', 'com.xiaomi.digitalkey', 'com.xiaomi.xaee',
    'com.miui.cloudservice', 'com.miui.cloudbackup', 'com.miui.micloudsync', 'com.miui.analytics',
    'com.miui.dmregservice', 'com.miui.face', 'com.miui.securityinputmethod', 'com.miui.findmy',
    'com.miui.virtualsim', 'com.xiaomi.macro', 'com.xiaomi.mirror', 'com.xiaomi.cameratools',
    'com.xiaomi.migameservice', 'com.xiaomi.gamecenter.sdk.service', 'com.xiaomi.scanner', 'com.xiaomi.mifisecurity',
    'com.xiaomi.mimobile.noti', 'com.xiaomi.shop', 'com.xiaomi.vipaccount', 'com.xiaomi.smarthome',
    'com.google.android.gms', 'com.android.vending', 'com.google.android.gsf',
    'com.google.android.gms.location.history', 'com.google.android.configupdater',
    'com.google.android.onetimeinitializer', 'com.google.android.safetycore', 'com.google.android.verifier',
    'com.google.android.printservice.recommendation', 'com.google.android.accessibility.switchaccess',
    'com.google.android.marvin.talkback',
    'com.android.ondevicepersonalization.services', 'com.android.adservices.api',
    'com.android.federatedcompute.services'
)

$keepThirdParty = @('com.iflytek.inputmethod.miui')
function IsDisabledPkg { param([string]$Pkg) return [bool](((& $script:Adb shell ("pm list packages -d --user 0 " + $Pkg) 2>&1) -join '') -match ('package:' + [regex]::Escape($Pkg))) }
function IsInstalledPkg { param([string]$Pkg) return [bool](((& $script:Adb shell ("pm list packages --user 0 " + $Pkg) 2>&1) -join '') -match ('package:' + [regex]::Escape($Pkg))) }

if ($Restore) {
    if (-not (Test-Path -LiteralPath $logLatest)) { throw "没有日志：$logLatest" }
    $log = Get-Content -LiteralPath $logLatest -Raw | ConvertFrom-Json
    foreach ($p in $log.packages) {
        if ($p.method -eq 'uninstall') {
            $o = (& $Adb shell ("cmd package install-existing --user 0 " + $p.package) 2>&1) -join ''
            Write-Host ("[install-existing] " + $p.package + " -> " + $o.Trim())
        } elseif ($p.method -eq 'disable') {
            & $Adb shell ("pm enable " + $p.package) | Out-Null
            Write-Host ("[enable] " + $p.package)
        }
    }
    Write-Host '回滚完成（第三方 App 若无法 install-existing，需要重装 APK）'
    exit 0
}

$thirdRaw = ((& $Adb shell 'pm list packages -3 --user 0') -join "`n")
$seen = @{}
$plan = @()
foreach ($line in ($thirdRaw -split "`r?`n")) {
    if ($line -match '^package:') {
        $pkg = $line -replace '^package:', ''
        if ($keepThirdParty -contains $pkg) { continue }
        if ($protected -contains $pkg) { continue }
        if (IsDisabledPkg $pkg) { continue }
        $seen[$pkg] = $true
        $plan += [ordered]@{ package = $pkg; kind = 'third-party'; action = 'uninstall'; done = $false; output = '' }
    }
}
$listToApply = @($uiDisable)
if ($IncludeServices) { $listToApply += $servicesDisable }
foreach ($pkg in $listToApply) {
    if ($protected -contains $pkg) { continue }
    if ($seen.ContainsKey($pkg)) { continue }
    if (-not (IsInstalledPkg $pkg)) { continue }
    if (IsDisabledPkg $pkg) { continue }
    $seen[$pkg] = $true
    $plan += [ordered]@{ package = $pkg; kind = 'system'; action = 'disable'; done = $false; output = '' }
}

Write-Host ("=== 优化计划：第三方移除 " + @($plan | Where-Object { $_.kind -eq 'third-party' }).Count + "，系统禁用 " + @($plan | Where-Object { $_.kind -eq 'system' }).Count + " ===") -ForegroundColor Cyan
if (-not $Apply) {
    foreach ($p in $plan) { Write-Host ("  [{0,-11}] {1,-42}" -f $p.kind, $p.package) }
    Write-Host 'DRY-RUN：未修改。确认后加 -Apply。' -ForegroundColor Yellow
    exit 0
}

$okUn = 0; $okDis = 0; $fail = 0
foreach ($p in $plan) {
    if ($p.action -eq 'uninstall') {
        $o = (& $Adb shell ("pm uninstall --user 0 " + $p.package) 2>&1) -join ''
        $p.output = $o.Trim()
        if ($o -match 'Success') { $p.done = $true; $okUn++ } else { $fail++ }
    } else {
        $o = (& $Adb shell ("pm disable-user --user 0 " + $p.package) 2>&1) -join ''
        $p.output = $o.Trim()
        if ($o -match 'new state: disabled') { $p.done = $true; $okDis++ } else { $fail++ }
    }
}
Write-Host ("结果：移除 " + $okUn + "，禁用 " + $okDis + "，失败 " + $fail)
& $Adb shell 'svc bluetooth disable 2>&1; svc data disable 2>&1; settings put global bluetooth_on 0; settings put global mobile_data 0' | Out-Null
& $Adb shell 'logcat -c 2>&1; logcat -G 1M 2>&1' | Out-Null
$mem = ((& $Adb shell 'cat /proc/meminfo') -join "`n")
if ($mem -match '(?m)^MemAvailable:\s*(\d+)') { $memAvail = [math]::Round([int64]$Matches[1]/1048576,2) } else { $memAvail = $null }
$load = ((& $Adb shell 'cat /proc/loadavg') -join '').Trim()
Write-Host ("MemAvailable=" + $memAvail + " GiB；load=" + $load)
$ext = ((& $Adb shell 'pm list packages --user 0 com.google.android.ext.services') -join '').Trim()
Write-Host ("关键包 ext.services: " + $(if ($ext -match 'package:') { 'OK 已安装' } else { '异常缺失！' }))
$fatal = ((& $Adb shell logcat -d -t 300) -join "`n") | Select-String 'FATAL EXCEPTION'
if ($fatal) { Write-Host '  最近 300 行有 FATAL！' -ForegroundColor Red } else { Write-Host '  最近 300 行无 FATAL' }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logObj = [ordered]@{ appliedAt = (Get-Date).ToString('o'); includeServices = [bool]$IncludeServices; packages = $plan; memAvailableGiB = $memAvail; load = $load }
$jsonPath = Join-Path $invDir ("optimize-profile-$stamp.json")
[System.IO.File]::WriteAllText($jsonPath, ($logObj | ConvertTo-Json -Depth 6), $utf8NoBom)
Copy-Item -LiteralPath $jsonPath -Destination $logLatest -Force
Write-Host ("日志：$jsonPath")
