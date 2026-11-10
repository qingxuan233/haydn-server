# Shizuku 安装/启动/状态（MIUI 无 Root 路线）
# 背景：
#   - MIUI 会拦截 adb install，需要用 miui-adb-install.ps1 自动确认弹窗。
#   - Shizuku v13.6 的 ADB 启动命令不是旧版 start.sh，而是直接执行 APK 内的
#     lib/arm64/libshizuku.so（App 内「查看指令」会显示完整路径）。
#   - Shizuku 用 adb 身份运行，权限受 Shell 限制；重启后需要重新执行启动命令。
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\shizuku-adb-start.ps1 -Install
#   powershell -ExecutionPolicy Bypass -File scripts\shizuku-adb-start.ps1 -Start
#   powershell -ExecutionPolicy Bypass -File scripts\shizuku-adb-start.ps1 -Status
param(
    [switch]$Install,
    [switch]$Start,
    [switch]$Status,
    [switch]$Stop,
    [string]$Serial = '',
    [string]$Apk = ''
)

$ErrorActionPreference = 'Continue'
$adb = Join-Path $PSScriptRoot '..\tools\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { Write-Host "找不到 adb: $adb"; exit 1 }
$serialArgs = @()
if ($Serial) { $serialArgs = @('-s', $Serial) }
function A([string[]]$cmdArgs) { & $adb @serialArgs @cmdArgs 2>&1 }

if ($Install) {
    if (-not $Apk) { $Apk = Join-Path $PSScriptRoot '..\tools\apks\shizuku.apk' }
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'miui-adb-install.ps1') -Apk $Apk -Serial $Serial
}

if ($Start) {
    $p = ((A @('shell', 'pm path moe.shizuku.privileged.api')) -join '').Trim() -replace '^package:', ''
    if (-not $p) { Write-Host '未安装 Shizuku，请先 -Install'; exit 1 }
    $so = $p -replace 'base\.apk$', 'lib/arm64/libshizuku.so'
    Write-Host ("· 启动: " + $so)
    A @('shell', $so) | ForEach-Object { Write-Host $_ }
}

if ($Stop) {
    $pidLine = (A @('shell', 'ps -A') | Select-String -Pattern 'shizuku_server').ToString()
    if ($pidLine -match '\s(\d+)\s+.*shizuku_server') {
        A @('shell', ("kill " + $Matches[1])) | Out-Null
        Write-Host ("· 已停止 shizuku_server pid=" + $Matches[1])
    } else { Write-Host '· 未发现 shizuku_server' }
}

if ($Status -or (-not $Install -and -not $Start -and -not $Stop)) {
    $lines = A @('shell', 'ps -A')
    $hit = $lines | Select-String -Pattern 'shizuku_server'
    if ($hit) { Write-Host '· Shizuku 正在运行:'; $hit | ForEach-Object { Write-Host ("  " + $_.Line.Trim()) } }
    else { Write-Host '· Shizuku 未运行（重启后需重新 -Start）' }
}
