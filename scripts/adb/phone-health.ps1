<#
.SYNOPSIS
    手机服务器健康检查：温度/负载/内存/磁盘/服务状态，输出报告并保存到 inventory\。
.DESCRIPTION
    通过 adb 读取 Android 侧指标（电池、温度、load、df），通过 SSH 读取 proot 侧
    supervisord 服务状态。默认参数对应本项目环境，可用参数覆盖。
    只读操作，不修改任何配置。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\adb\phone-health.ps1
#>
[CmdletBinding()]
param(
    [string]$AdbPath,
    [string]$HostName = '192.168.10.143',
    [int]$SshPort = 2222,
    [string]$SshUser = 'root',
    [string]$KeyPath = '',
    [string]$SupervisorConf = '/root/server/etc/supervisord.conf'
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$invDir = Join-Path $repoRoot 'inventory'
New-Item -ItemType Directory -Force -Path $invDir | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$report = New-Object 'System.Collections.Generic.List[string]'
$fail = $false

function Add-Line {
    param([string]$Text, [string]$Color = 'Gray')
    [void]$report.Add($Text)
    Write-Host $Text -ForegroundColor $Color
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

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Add-Line ("# 手机健康报告 " + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) 'Cyan'

# ---------- Android 侧 ----------
try { $adb = Resolve-Adb -Explicit $AdbPath } catch { Add-Line ("[FAIL] " + $_.Exception.Message) 'Red'; Write-Host '无法继续'; exit 1 }
$devices = ((& $adb devices -l) -join "`n")
if (-not ($devices -match '(?m)^([0-9A-Za-z]+)\s+device')) { Add-Line '[FAIL] 设备未连接/未授权' 'Red'; exit 1 }
Add-Line "[PASS] adb 设备在线" 'Green'

$batteryText = ((& $adb shell dumpsys battery) -join "`n")
$level = if ($batteryText -match '(?m)^\s*level:\s*(\d+)') { $Matches[1] } else { '?' }
$tempDeci = if ($batteryText -match '(?m)^\s*temperature:\s*(\d+)') { $Matches[1] } else { '' }
$battTempC = if ($tempDeci) { [math]::Round([double]$tempDeci / 10, 1) } else { '?' }
$acPowered = if ($batteryText -match '(?m)^\s*AC powered:\s*(true|false)') { $Matches[1] } else { '?' }
Add-Line "[INFO] 电池：$level%，$battTempC °C，AC 供电=$acPowered"

$load = ((& $adb shell cat /proc/loadavg) -join '').Trim()
Add-Line "[INFO] Android loadavg：$load"
$mem = ((& $adb shell cat /proc/meminfo) -join "`n")
$memAvail = if ($mem -match '(?m)^MemAvailable:\s*(\d+)\s*kB') { [math]::Round([int64]$Matches[1] / 1048576, 2) } else { '?' }
Add-Line "[INFO] MemAvailable：$memAvail GiB"

$df = ((& $adb shell df /data) -join "`n")
$dfLine = ($df -split "`r?`n" | Where-Object { $_ -match '%' } | Select-Object -Last 1)
if ($dfLine -and $dfLine -match '(\d+)%') {
    $pct = [int]$Matches[1]
    if ($pct -lt 80) { Add-Line "[PASS] /data 使用率 $pct% （$($dfLine.Trim())）" 'Green' } else { Add-Line "[WARN] /data 使用率 $pct%（≥80%）" 'Yellow'; $fail = $true }
} else { Add-Line '[WARN] 无法解析 /data 使用率' 'Yellow' }

# 关键热区（按 zone 索引配对 type/temp，避免 glob 顺序错位）
$thermalMap = @{}
$thermalRaw = ((& $adb shell 'z=0; for t in /sys/class/thermal/thermal_zone*/type; do echo $z $(cat $t) $(cat /sys/class/thermal/thermal_zone$z/temp); z=$((z+1)); done') -join "`n")
foreach ($line in ($thermalRaw -split "`r?`n")) {
    if ($line -match '^\s*(\d+)\s+([a-z0-9_\-]+)\s+(-?\d+)') {
        $thermalMap[$Matches[2]] = [math]::Round([double]$Matches[3] / 1000, 1)
    }
}
$want = @('cpu-1-0-usr', 'cpu-0-0-usr', 'gpuss-0-usr', 'ddr-usr', 'battery', 'quiet_therm', 'xo_therm')
foreach ($w in $want) {
    if ($thermalMap.ContainsKey($w)) {
        $t = $thermalMap[$w]
        $color = if ($w -like 'cpu*' -and $t -gt 70) { 'Red' } elseif ($w -eq 'battery' -and $t -gt 40) { 'Red' } else { 'Gray' }
        Add-Line "  [TEMP] $w = $t °C" $color
        if (($w -like 'cpu*' -and $t -gt 70) -or ($w -eq 'battery' -and $t -gt 40)) { $fail = $true }
    }
}

# ---------- proot 侧（SSH） ----------
if (-not $KeyPath) {
    $KeyPath = Join-Path $repoRoot 'backup\ssh\id_haydn'
}
if (Test-Path -LiteralPath $KeyPath) {
    $sshBase = @('-i', $KeyPath, '-p', "$SshPort", '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', '-o', 'StrictHostKeyChecking=accept-new', "$SshUser@$HostName")
    $supOut = (& ssh @sshBase "supervisorctl -c $SupervisorConf status 2>&1 | head -20") -join "`n"
    if ($LASTEXITCODE -eq 0 -and $supOut.Trim()) {
        Add-Line "[INFO] supervisord 服务状态："
        $running = 0; $total = 0
        foreach ($line in ($supOut -split "`r?`n")) {
            if ($line -match '^\S+\s+\S+') {
                $total++
                if ($line -match 'RUNNING') { $running++ } else { Add-Line ("  [WARN] " + $line.Trim()) 'Yellow'; $fail = $true }
            }
        }
        Add-Line ("  → RUNNING " + $running + " / " + $total) $(if ($running -eq $total -and $total -gt 0) { 'Green' } else { 'Yellow' })
    } else { Add-Line '[WARN] 无法获取 supervisord 状态（SSH 失败或配置路径不符）' 'Yellow' }

    $sysInfo = (& ssh @sshBase "echo LOAD:`$(cat /proc/loadavg); echo UPTIME:`$(cat /proc/uptime | cut -d' ' -f1); df -h / | tail -1; free -m 2>/dev/null | head -2" 2>&1) -join "`n"
    Add-Line "[INFO] proot 侧：`n$sysInfo"
} else {
    Add-Line "[WARN] 未找到 SSH 私钥：$KeyPath，跳过 proot 侧检查" 'Yellow'
}

# ---------- 落盘 ----------
Add-Line ''
Add-Line $(if ($fail) { '结论：存在告警项（见 WARN/红色项）' } else { '结论：全部正常' }) $(if ($fail) { 'Yellow' } else { 'Green' })
$mdPath = Join-Path $invDir ("phone-health-$stamp.md")
[System.IO.File]::WriteAllLines($mdPath, $report, $utf8NoBom)
Copy-Item -LiteralPath $mdPath -Destination (Join-Path $invDir 'phone-health-latest.md') -Force
Write-Host ''
Write-Host ("已保存：$mdPath") -ForegroundColor Green
if ($fail) { exit 1 } else { exit 0 }
