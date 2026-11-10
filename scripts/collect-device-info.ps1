<#
.SYNOPSIS
    采集 Redmi K40 Pro (haydn / SM8350) 的设备档案。
.DESCRIPTION
    通过 adb 读取身份、构建、安全、硬件、内存、存储、电池、网络、包列表与温度信息。
    原始输出写入 inventory\device-raw-<时间戳>.txt，
    结构化信息写入 inventory\device-info-<时间戳>.json，
    同时生成 *-latest 副本供文档引用。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\collect-device-info.ps1
#>
[CmdletBinding()]
param(
    [string]$AdbPath,
    [string]$OutDir
)

$ErrorActionPreference = 'Continue'
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
    throw '找不到 adb。请先运行 scripts/get-platform-tools.ps1，或设置 ADB_PATH 环境变量。'
}
function Invoke-Adb {
    param([string[]]$AdbArgs)
    try {
        $out = & $script:AdbExe @AdbArgs 2>&1 | Out-String
        return $out.TrimEnd()
    } catch {
        return ('ERROR: ' + $_.Exception.Message)
    }
}
function Add-Raw {
    param([string]$Title, [string]$Body)
    [void]$script:Raw.Add('')
    [void]$script:Raw.Add('### ' + $Title)
    $lines = @($Body -split "`r?`n")
    foreach ($line in $lines) { [void]$script:Raw.Add([string]$line) }
}
function Get-DumpField {
    param([string]$Text, [string]$Field)
    if ($Text -match ('(?m)^\s*' + [regex]::Escape($Field) + '\s*:\s*(.+)$')) {
        return $Matches[1].Trim()
    }
    return $null
}

$AdbExe = Resolve-Adb -Explicit $AdbPath
if (-not $OutDir) { $OutDir = Join-Path $repoRoot 'inventory' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$rawPath = Join-Path $OutDir ("device-raw-$stamp.txt")
$jsonPath = Join-Path $OutDir ("device-info-$stamp.json")
$pkgPath = Join-Path $OutDir ("packages-$stamp.txt")

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Raw = New-Object 'System.Collections.Generic.List[string]'

$adbVersion = Invoke-Adb -AdbArgs @('version')
Add-Raw -Title 'adb version' -Body $adbVersion

$devices = Invoke-Adb -AdbArgs @('devices', '-l')
Add-Raw -Title 'adb devices -l' -Body $devices

$serial = $null
foreach ($line in ($devices -split "`r?`n")) {
    if ($line -match '^([0-9A-Za-z]+)\s+device') { $serial = $Matches[1]; break }
}
if (-not $serial) {
    [System.IO.File]::WriteAllLines($rawPath, $Raw, $utf8NoBom)
    if ($devices -match 'unauthorized') {
        throw '设备未授权：请在手机上勾选「一律允许使用这台计算机进行调试」并点「允许」，然后重试。'
    }
    throw '未找到已连接的 Android 设备：请检查数据线、USB 调试开关与驱动。'
}

$commands = [ordered]@{
    'uname -a'                             = @('shell', 'uname', '-a')
    '/proc/version'                        = @('shell', 'cat', '/proc/version')
    '/proc/cpuinfo'                        = @('shell', 'cat', '/proc/cpuinfo')
    '/proc/meminfo'                        = @('shell', 'cat', '/proc/meminfo')
    'df -h'                                = @('shell', 'df', '-h')
    'df'                                   = @('shell', 'df')
    'dumpsys battery'                      = @('shell', 'dumpsys', 'battery')
    'wm size'                              = @('shell', 'wm', 'size')
    'wm density'                           = @('shell', 'wm', 'density')
    'getenforce'                           = @('shell', 'getenforce')
    'id'                                   = @('shell', 'id')
    'which su'                             = @('shell', 'which', 'su')
    'which magisk'                         = @('shell', 'which', 'magisk')
    'ip -4 addr'                           = @('shell', 'ip', '-4', 'addr')
    'ip route'                             = @('shell', 'ip', 'route')
    'uptime'                               = @('shell', 'uptime')
    'cpu0 cpufreq governor'                = @('shell', 'cat', '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor')
    'cpu0 cpufreq available governors'     = @('shell', 'cat', '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors')
    'thermal zones'                        = @('shell', 'z=0; for t in /sys/class/thermal/thermal_zone*/type; do echo $z $(cat $t) $(cat /sys/class/thermal/thermal_zone$z/temp); z=$((z+1)); done')
}

$results = @{}
foreach ($key in $commands.Keys) {
    $body = Invoke-Adb -AdbArgs $commands[$key]
    $results[$key] = $body
    Add-Raw -Title $key -Body $body
}

$propsText = Invoke-Adb -AdbArgs @('shell', 'getprop')
Add-Raw -Title 'getprop (full)' -Body $propsText
$props = @{}
foreach ($line in ($propsText -split "`r?`n")) {
    if ($line -match '^\[([^\]]+)\]:\s*\[([^\]]*)\]') { $props[$Matches[1]] = $Matches[2] }
}
function Get-Prop {
    param([string]$Name)
    if ($script:props.ContainsKey($Name)) { return $script:props[$Name] }
    return $null
}

$pkgAll = Invoke-Adb -AdbArgs @('shell', 'pm', 'list', 'packages')
$pkg3   = Invoke-Adb -AdbArgs @('shell', 'pm', 'list', 'packages', '-3')
Add-Raw -Title 'pm list packages' -Body $pkgAll
Add-Raw -Title 'pm list packages -3' -Body $pkg3

$pkgFileLines = @('# 全部包 (pm list packages)')
$pkgFileLines += @($pkgAll -split "`r?`n")
$pkgFileLines += ''
$pkgFileLines += @('# 第三方包 (pm list packages -3)')
$pkgFileLines += @($pkg3 -split "`r?`n")
[System.IO.File]::WriteAllLines($pkgPath, $pkgFileLines, $utf8NoBom)

$pkgTotal = @($pkgAll -split "`r?`n" | Where-Object { $_ -match '^package:' }).Count
$pkgThird = @($pkg3   -split "`r?`n" | Where-Object { $_ -match '^package:' }).Count
$rootManagers = @($pkgAll -split "`r?`n" | Where-Object { $_ -match 'topjohnwu|kernelsu|apatch' } | ForEach-Object { $_ -replace '^package:', '' })

# ---- 解析关键字段 ----
$memTotalKb = $null
if ($results['/proc/meminfo'] -match '(?m)^MemTotal:\s*(\d+)\s*kB') { $memTotalKb = [int64]$Matches[1] }
$cpuCores = ([regex]::Matches([string]$results['/proc/cpuinfo'], '(?m)^processor\s*:')).Count

$batteryText = [string]$results['dumpsys battery']
$batteryLevel = Get-DumpField -Text $batteryText -Field 'level'
if ($batteryLevel) { $batteryLevel = [int]$batteryLevel }
$batteryTempDeci = Get-DumpField -Text $batteryText -Field 'temperature'
$batteryStatusRaw = Get-DumpField -Text $batteryText -Field 'status'
$batteryHealthRaw = Get-DumpField -Text $batteryText -Field 'health'
$batteryStatusMap = @{ '1' = 'UNKNOWN'; '2' = 'CHARGING'; '3' = 'DISCHARGING'; '4' = 'NOT_CHARGING'; '5' = 'FULL' }
$batteryHealthMap = @{ '1' = 'UNKNOWN'; '2' = 'GOOD'; '3' = 'OVERHEAT'; '4' = 'DEAD'; '5' = 'OVER_VOLTAGE'; '6' = 'UNSPECIFIED_FAILURE'; '7' = 'COLD' }
$batteryTempC = $null
if ($batteryTempDeci) { $batteryTempC = [math]::Round(([double]$batteryTempDeci) / 10, 1) }
$batteryStatus = $null
if ($batteryStatusRaw -and $batteryStatusMap.ContainsKey([string]$batteryStatusRaw)) { $batteryStatus = $batteryStatusMap[[string]$batteryStatusRaw] }
$batteryHealth = $null
if ($batteryHealthRaw -and $batteryHealthMap.ContainsKey([string]$batteryHealthRaw)) { $batteryHealth = $batteryHealthMap[[string]$batteryHealthRaw] }

$dataLine = @($results['df -h'] -split "`r?`n" | Where-Object { $_ -match ' /data$' } | Select-Object -First 1)[0]
$displaySize = @($results['wm size'] -split "`r?`n" | Where-Object { $_ -match 'Physical size|Override size' })

$osVersion = Get-Prop 'ro.mi.os.version.name'
$miuiVersion = Get-Prop 'ro.miui.ui.version.name'

$memTotalGiB = $null
if ($memTotalKb) { $memTotalGiB = [math]::Round($memTotalKb / 1048576, 2) }

# ---- 汇总 JSON ----
$info = [ordered]@{
    schemaVersion = 1
    collectedAt   = (Get-Date).ToString('o')
    tool          = [ordered]@{
        adbVersion = @(($adbVersion -split "`r?`n") | Where-Object { $_ -match 'Android Debug Bridge version' })[0]
        adbPath    = $AdbExe
    }
    transport = [ordered]@{
        serial        = $serial
        devicesOutput = $devices
    }
    identity = [ordered]@{
        model        = Get-Prop 'ro.product.model'
        device       = Get-Prop 'ro.product.device'
        productName  = Get-Prop 'ro.product.name'
        brand        = Get-Prop 'ro.product.brand'
        manufacturer = Get-Prop 'ro.product.manufacturer'
        marketName   = Get-Prop 'ro.product.marketname'
        fingerprint  = Get-Prop 'ro.build.fingerprint'
        characteristics = Get-Prop 'ro.build.characteristics'
    }
    build = [ordered]@{
        romVersion       = $osVersion
        miuiVersion      = $miuiVersion
        buildIncremental = Get-Prop 'ro.build.version.incremental'
        buildId          = Get-Prop 'ro.build.id'
        displayId        = Get-Prop 'ro.build.display.id'
        androidVersion   = Get-Prop 'ro.build.version.release'
        sdkVersion       = Get-Prop 'ro.build.version.sdk'
        securityPatch    = Get-Prop 'ro.build.version.security_patch'
        buildType        = Get-Prop 'ro.build.type'
        buildTags        = Get-Prop 'ro.build.tags'
    }
    security = [ordered]@{
        bootloader          = Get-Prop 'ro.bootloader'
        flashLocked         = Get-Prop 'ro.boot.flash.locked'
        verifiedBootState   = Get-Prop 'ro.boot.verifiedbootstate'
        verityMode          = Get-Prop 'ro.boot.veritymode'
        vbmetaDeviceState   = Get-Prop 'ro.boot.vbmeta.device_state'
        secure              = Get-Prop 'ro.secure'
        debuggable          = Get-Prop 'ro.debuggable'
        selinuxEnforce      = $results['getenforce']
        idOutput            = $results['id']
        suBinary            = $results['which su']
        magiskBinary        = $results['which magisk']
        rootManagerPackages = $rootManagers
    }
    hardware = [ordered]@{
        socModel      = Get-Prop 'ro.soc.model'
        socManufacturer = Get-Prop 'ro.soc.manufacturer'
        boardPlatform = Get-Prop 'ro.board.platform'
        bootHardware  = Get-Prop 'ro.boot.hardware'
        cpuAbi        = Get-Prop 'ro.product.cpu.abi'
        cpuAbiList    = Get-Prop 'ro.product.cpu.abilist'
        cpuCores      = $cpuCores
        kernelVersion = Get-Prop 'ro.kernel.version'
        kernel        = @(($results['uname -a'] -split "`r?`n") | Where-Object { $_ })[0]
        cpuGovernor   = $results['cpu0 cpufreq governor']
        cpuGovernors  = $results['cpu0 cpufreq available governors']
        displaySize   = $displaySize
        displayDensity = $results['wm density']
        thermalZones  = @($results['thermal zones'] -split "`r?`n" | Where-Object { $_ -match '^\d+' })
    }
    memory = [ordered]@{
        totalKb  = $memTotalKb
        totalGiB = $memTotalGiB
    }
    storage = [ordered]@{
        dataLine = $dataLine
        raw      = $results['df -h']
    }
    battery = [ordered]@{
        level        = $batteryLevel
        status       = $batteryStatus
        health       = $batteryHealth
        temperatureC = $batteryTempC
        acPowered    = Get-DumpField -Text $batteryText -Field 'AC powered'
        usbPowered   = Get-DumpField -Text $batteryText -Field 'USB powered'
        wirelessPowered = Get-DumpField -Text $batteryText -Field 'Wireless powered'
        raw          = $batteryText
    }
    network = [ordered]@{
        ipv4  = $results['ip -4 addr']
        route = $results['ip route']
    }
    packages = [ordered]@{
        total      = $pkgTotal
        thirdParty = $pkgThird
        listFile   = $pkgPath
    }
    artifacts = [ordered]@{
        rawFile  = $rawPath
        jsonFile = $jsonPath
    }
}

[void]$Raw.Add('')
[void]$Raw.Add('### artifacts')
[void]$Raw.Add("json: $jsonPath")
[void]$Raw.Add("packages: $pkgPath")
[System.IO.File]::WriteAllLines($rawPath, $Raw, $utf8NoBom)

$jsonText = $info | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($jsonPath, $jsonText, $utf8NoBom)

Copy-Item -LiteralPath $jsonPath -Destination (Join-Path $OutDir 'device-info-latest.json') -Force
Copy-Item -LiteralPath $rawPath  -Destination (Join-Path $OutDir 'device-raw-latest.txt') -Force

Write-Host ''
Write-Host '采集完成' -ForegroundColor Green
Write-Host ("  设备   : {0} ({1})  SoC {2}" -f $info.identity.model, $info.identity.device, $info.hardware.socModel)
Write-Host ("  系统   : Android {0} (SDK {1}) / HyperOS {2} / {3}" -f $info.build.androidVersion, $info.build.sdkVersion, $osVersion, $info.build.buildIncremental)
Write-Host ("  安全   : bootloaderLocked={0} selinux={1} su={2}" -f $info.security.flashLocked, $info.security.selinuxEnforce, $info.security.suBinary)
Write-Host ("  内存   : {0} GB (MemTotal {1} kB), CPU 核数 {2}" -f $info.memory.totalGiB, $info.memory.totalKb, $info.hardware.cpuCores)
Write-Host ("  电池   : {0}% {1} {2}C, AC={3} USB={4}" -f $info.battery.level, $info.battery.status, $info.battery.temperatureC, $info.battery.acPowered, $info.battery.usbPowered)
Write-Host ("  包数量 : 总共 {0} / 第三方 {1}" -f $info.packages.total, $info.packages.thirdParty)
Write-Host ''
Write-Host "  JSON: $jsonPath"
Write-Host "  RAW : $rawPath"
