# ADB 为服务器让资源：Status / Quiet / Restore（机器本地）
param(
    [switch]$Status,
    [switch]$Quiet,
    [switch]$Restore,
    [string]$Serial = ''
)

$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$adb = Join-Path $root 'tools\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { Write-Host "找不到 adb: $adb"; exit 1 }
$serialArgs = @()
if ($Serial) { $serialArgs = @('-s', $Serial) }
function A([string]$cmd) { (& $adb @serialArgs shell $cmd 2>&1) -join "`n" }

$researchApps = @(
    'com.aistra.hail',
    'io.github.samolego.canta',
    'io.github.muntashirakon.AppManager'
)
$keepServer = 'moe.shizuku.privileged.api'
$termuxUid = '10250'

function ShowStatus {
    Write-Host '=== 服务器保护状态 ==='
    $wl = A 'cmd deviceidle whitelist 2>/dev/null'
    ($wl -split "`r?`n") | Where-Object { $_ -match 'termux' } | Write-Host
    Write-Host ('  netpolicy whitelist: ' + ((A 'cmd netpolicy list restrict-background-whitelist 2>/dev/null') -join ' '))
    Write-Host ('  Termux appops: ' + (A 'cmd appops get com.termux RUN_ANY_IN_BACKGROUND 2>/dev/null | tail -1'))
    Write-Host ('  Termux bucket: ' + (A 'am get-standby-bucket com.termux 2>/dev/null'))
    Write-Host '=== 资源 ==='
    Write-Host (A 'cat /proc/meminfo | head -3')
    Write-Host (A 'cat /proc/loadavg')
    Write-Host ('  freezer=' + (A 'settings get global cached_apps_freezer') + '  low_power=' + (A 'settings get global low_power') + '  wifi_sleep=' + (A 'settings get global wifi_sleep_policy'))
    Write-Host ('  logcat: ' + ((A 'logcat -g 2>/dev/null') -split "`r?`n" | Select-Object -First 1))
    Write-Host '=== 研究 App / 关键进程 ==='
    $mi = A 'dumpsys meminfo 2>/dev/null'
    ($mi -split "`r?`n") | Where-Object { $_ -match 'K: (moe\.shizuku|com\.aistra\.hail|io\.github\.samolego\.canta|io\.github\.muntashirakon|shizuku_server|node|com\.termux)' } | Select-Object -First 10 | Write-Host
}

function SetQuiet {
    Write-Host '· 重放 P0 设置'
    A 'settings put global cached_apps_freezer enabled' | Out-Null
    A 'logcat -G 1M; logcat -c' | Out-Null
    A 'settings put global low_power 0' | Out-Null
    A 'cmd power set-adaptive-power-saver-enabled false' | Out-Null
    A ('cmd netpolicy add restrict-background-whitelist ' + $termuxUid) | Out-Null
    A 'settings put global wifi_sleep_policy 2' | Out-Null
    Write-Host '· 静默研究 App（保留 shizuku_server）'
    foreach ($p in $researchApps) {
        $exists = A ('pm path ' + $p) -match 'package:'
        if ($exists) {
            Write-Host ('  force-stop ' + $p)
            A ('am force-stop ' + $p) | Out-Null
        }
    }
    Write-Host ('  force-stop ' + $keepServer + '（只停 UI，服务端独立运行）')
    A ('am force-stop ' + $keepServer) | Out-Null
}

function SetRestore {
    Write-Host '· 恢复辅助设置（不恢复已静默 App）'
    A 'settings put global cached_apps_freezer disabled' | Out-Null
    A 'logcat -G 2M' | Out-Null
    Write-Host '· 研究 App 需要时手动打开（Shizuku 需重新 start）'
}

if ($Status -or (-not $Quiet -and -not $Restore)) { ShowStatus }
if ($Quiet) { SetQuiet; Start-Sleep -Seconds 5; ShowStatus }
if ($Restore) { SetRestore; ShowStatus }
