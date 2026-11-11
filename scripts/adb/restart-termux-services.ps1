<#
.SYNOPSIS
    远程恢复 Termux/proot 服务（不依赖手动解锁屏幕，不需要 Root）。
.DESCRIPTION
    场景：重启/被清理后 Termux 进程消失、SSH 2222 与 supervisord 服务不可达，
    但 adb 仍在线且 Termux 为 debuggable 时，用 `run-as com.termux` 在应用上下文执行
    Termux:Boot 的开机脚本（.termux/boot/00-server.sh），拉起 proot + supervisord。
    注意：Android FBE 锁屏状态下 BOOT_COMPLETED 不会下发，因此重启后自动恢复需要解锁一次；
    本脚本是"不解锁也能救回来"的兜底手段。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\adb\restart-termux-services.ps1
#>
[CmdletBinding()]
param(
    [string]$AdbPath,
    [string]$TermuxPkg = 'com.termux',
    [string]$BootScript = '/data/data/com.termux/files/home/.termux/boot/00-server.sh',
    [int]$WaitSeconds = 30
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
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

$Adb = Resolve-Adb -Explicit $AdbPath
& $Adb start-server 2>$null | Out-Null
$devices = ((& $Adb devices -l) -join "`n")
if (-not ($devices -match '(?m)^([0-9A-Za-z]+)\s+device')) { throw '设备未连接/未授权' }
Write-Host '[1/4] 设备在线' -ForegroundColor Green

# 1) 确保 Termux App 进程存在（app 未运行则 run-as 仍可用，但 wake-lock 需 app 进程）
$ps = ((& $Adb shell ps -A) -join "`n")
if (-not ($ps -match 'com\.termux')) {
    Write-Host '[2/4] 启动 Termux App ...'
    & $Adb shell monkey -p $TermuxPkg -c android.intent.category.LAUNCHER 1 2>$null | Out-Null
    Start-Sleep -Seconds 4
} else {
    Write-Host '[2/4] Termux App 已在运行'
}

# 2) 构造启动脚本并推送
$sh = @'
#!/system/bin/sh
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:$PATH
export LD_LIBRARY_PATH=$PREFIX/lib
export TMPDIR=$PREFIX/tmp
export TERM=xterm-256color
cd $HOME
if command -v setsid >/dev/null 2>&1; then
  setsid sh "BOOTSCRIPT" >> "$HOME/server.log" 2>&1 < /dev/null &
else
  nohup sh "BOOTSCRIPT" >> "$HOME/server.log" 2>&1 < /dev/null &
fi
echo "STARTED pid=$!"
'@
$content = $sh -replace 'BOOTSCRIPT', $BootScript
$content = $content -replace "`r`n", "`n"
$tmp = Join-Path $env:TEMP 'restart-termux.sh'
[System.IO.File]::WriteAllText($tmp, $content, $utf8NoBom)
& $Adb push $tmp '/data/local/tmp/restart-termux.sh' 2>$null | Out-Null
& $Adb shell chmod 644 /data/local/tmp/restart-termux.sh | Out-Null
Write-Host '[3/4] 通过 run-as 执行启动脚本 ...'
& $Adb shell ("run-as {0} sh /data/local/tmp/restart-termux.sh" -f $TermuxPkg)

# 3) 等待并验证
Start-Sleep -Seconds $WaitSeconds
$ps2 = ((& $Adb shell ps -A) -join "`n")
$procs = @(($ps2 -split "`r?`n") | Where-Object { $_ -match 'proot|sshd -D|supervisor' })
$tcp = ((& $Adb shell cat /proc/net/tcp) -join "`n")
$ports = @()
foreach ($line in ($tcp -split "`r?`n")) {
    if ($line -match '^\s*\d+:\s+[0-9A-F]{8}:([0-9A-F]{4})\s+[0-9A-F]{8}:[0-9A-F]{4}\s+0A') { $ports += [Convert]::ToInt32($Matches[1], 16) }
}
$ports = $ports | Sort-Object -Unique
Write-Host '[4/4] 恢复结果：' -ForegroundColor Cyan
Write-Host ("  相关进程数：" + $procs.Count)
Write-Host ("  监听端口：" + ($ports -join ', '))
if ($ports -contains 2222) { Write-Host '  [OK] SSH 2222 已恢复' -ForegroundColor Green; exit 0 }
Write-Host '  [WARN] 2222 未监听，请检查 server.log 或手动打开 Termux 执行 ~/.termux/boot/00-server.sh' -ForegroundColor Yellow
exit 1
