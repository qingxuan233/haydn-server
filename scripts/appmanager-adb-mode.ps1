# AppManager ADB 特权模式（librun_server）启停脚本
# 原理：AppManager 自带 librun_server.so，用 ADB shell 执行后以 shell(UID 2000) 启动本地特权服务端，
#       AppManager 再切到「操作模式 → 网络调试（ADB）」连接；无需 Shizuku/Root。
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\appmanager-adb-mode.ps1 -Start
#   powershell -ExecutionPolicy Bypass -File scripts\appmanager-adb-mode.ps1 -Status
#   powershell -ExecutionPolicy Bypass -File scripts\appmanager-adb-mode.ps1 -Stop
# 注意：端口 60001/token 由 AppManager 当前安装实例生成；若重装/清数据，请在 App 内重新复制命令并用 -Command 覆盖。
param(
    [switch]$Start,
    [switch]$Stop,
    [switch]$Status,
    [string]$Serial = '',
    [int]$Port = 60001,
    [string]$Token = 'jolly-fit-dove',
    [string]$Command = ''
)

$ErrorActionPreference = 'Continue'
$adb = Join-Path $PSScriptRoot '..\tools\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { Write-Host "找不到 adb: $adb"; exit 1 }
$serialArgs = @()
if ($Serial) { $serialArgs = @('-s', $Serial) }
function A([string[]]$cmdArgs) { & $adb @serialArgs @cmdArgs 2>&1 }

$pkg = 'io.github.muntashirakon.AppManager'

function Get-ServerPid {
    $ps = (A @('shell', 'ps -A')) -join "`n"
    foreach ($line in ($ps -split "`r?`n")) {
        if ($line -match '^shell\s+(\d+)\s+.*am_local_server') { return [int]$Matches[1] }
        if ($line -match '\sam_local_server') { if ($line -match '^\S+\s+(\d+)') { return [int]$Matches[1] } }
    }
    return $null
}

if ($Stop) {
    $pidServer = Get-ServerPid
    if ($pidServer) { A @('shell', ("kill " + $pidServer)) | Out-Null; Write-Host ("· 已停止 am_local_server pid=" + $pidServer) }
    else { Write-Host '· 未发现 am_local_server' }
    A @('shell', ('am force-stop ' + $pkg)) | Out-Null
    Write-Host '· 已 force-stop AppManager'
    exit 0
}

if ($Status) {
    $pidServer = Get-ServerPid
    if ($pidServer) { Write-Host ("· am_local_server 运行中 pid=" + $pidServer) } else { Write-Host '· am_local_server 未运行' }
    $net = (A @('shell', 'netstat -tln')) -join "`n"
    $line = ($net -split "`r?`n") | Where-Object { $_ -match ("60001|" + $Port) } | Select-Object -First 1
    if ($line) { Write-Host ("· 端口: " + $line.Trim()) } else { Write-Host '· 端口未监听' }
    exit 0
}

if ($Start) {
    $pidServer = Get-ServerPid
    if ($pidServer) { Write-Host ("· 已在运行 pid=" + $pidServer + "（如需重启先 -Stop）"); exit 0 }

    if (-not $Command) {
        $pathLine = (A @('shell', ('pm path ' + $pkg))) -join ''
        $path = $pathLine.Trim() -replace '^package:', ''
        if (-not $path) { Write-Host '未安装 AppManager'; exit 1 }
        $lib = $path -replace 'base\.apk$', 'lib/arm64/librun_server.so'
        $Command = "$lib $Port $Token am.jar main.jar $pkg 0 0"
    }
    Write-Host ("· 启动命令: " + $Command)
    # 用独立进程启动 adb shell（脚本退出后服务端仍可存活；AppManager 自身 bgrun=1）
    $job = Start-Job -ScriptBlock {
        param($a, $s, $c)
        & $a @s shell $c 2>&1
    } -ArgumentList $adb, $serialArgs, $Command
    Start-Sleep -Seconds 5
    Receive-Job -Id $job.Id -Keep 2>&1 | Select-Object -First 8
    # 注意：脚本退出时 Start-Job 可能结束，但 librun_server 以 bgrun=1 运行，服务端会继续存活（可用 -Status 验证）
    if (Get-ServerPid) { Write-Host '· 成功：am_local_server 已启动（AppManager 内选 操作模式→网络调试→应用）' }
    else { Write-Host '· 失败：未发现 am_local_server（可重试 -Start）' }
    exit 0
}

Write-Host '用法: -Start | -Status | -Stop （可加 -Serial / -Port / -Token / -Command）'
