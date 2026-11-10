# 研究平台环境验证（只读，不改设备）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\verify-research-env.ps1 [-Serial <serial>]
# 输出：inventory\env-verify-<timestamp>.md（inventory 不入库）
param(
    [string]$Serial = '',
    [string]$SshKey = '',
    [string]$OutDir = ''
)

$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$adb = Join-Path $root 'tools\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { Write-Host "找不到 adb: $adb"; exit 1 }
if (-not $SshKey) { $SshKey = Join-Path $root 'backup\ssh\id_haydn' }
if (-not $OutDir) { $OutDir = Join-Path $root 'inventory' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$serialArgs = @()
if ($Serial) { $serialArgs = @('-s', $Serial) }
function A([string[]]$cmdArgs) { & $adb @serialArgs @cmdArgs 2>&1 }
function AShell([string]$cmd) { (A @('shell', $cmd)) -join "`n" }

$rows = New-Object 'System.Collections.Generic.List[object]'
function Check([string]$name, [string]$expect, [string]$actual, [bool]$ok) {
    $rows.Add([pscustomobject]@{ Item = $name; Expected = $expect; Actual = $actual; Result = $(if ($ok) { 'PASS' } else { 'FAIL' }) }) | Out-Null
}

Write-Host '=== 1) ADB 设备 ==='
$devices = (A @('devices')) -join "`n"
$okDev = $devices -match '\tdevice'
Check 'ADB 设备在线' 'device' ($(if ($okDev) { 'device' } else { '未连接/unauthorized' })) $okDev
if (-not $okDev) { Write-Host $devices }

Write-Host '=== 2) Android 基础属性/包 ==='
$boot = AShell 'getprop sys.boot_completed'
Check 'boot_completed' '1' $boot.Trim() ($boot.Trim() -eq '1')
$model = AShell 'getprop ro.product.model'
$sdk = AShell 'getprop ro.build.version.sdk'
Check '设备型号' 'M2012K11C' $model.Trim() ($model.Trim() -eq 'M2012K11C')
Check 'SDK' '34' $sdk.Trim() ($sdk.Trim() -eq '34')

$pkgs = AShell 'pm list packages --user 0'
$mustPkgs = @(
    @{ p = 'com.termux'; name = 'Termux' },
    @{ p = 'com.termux.boot'; name = 'Termux:Boot' },
    @{ p = 'moe.shizuku.privileged.api'; name = 'Shizuku' },
    @{ p = 'io.github.samolego.canta'; name = 'Canta' },
    @{ p = 'com.aistra.hail'; name = 'Hail' },
    @{ p = 'io.github.muntashirakon.AppManager'; name = 'AppManager' }
)
foreach ($m in $mustPkgs) {
    $present = $pkgs -match ('package:' + [regex]::Escape($m.p))
    Check ('包 ' + $m.name) '已安装' ($(if ($present) { '已安装' } else { '缺失' })) ([bool]$present)
}

Write-Host '=== 3) Shizuku 运行状态 ==='
$ps = AShell 'ps -A'
$sh = $ps -match 'shizuku_server'
Check 'Shizuku server' '运行' ($(if ($sh) { '运行' } else { '未运行（重启后需启动）' })) ([bool]$sh)

Write-Host '=== 4) 网络/服务器入口 ==='
$ipRaw = AShell 'ip -4 addr show wlan0'
$ip = $null
if ($ipRaw -match 'inet (\d+\.\d+\.\d+\.\d+)/') { $ip = $Matches[1] }
Check 'LAN IP' '可用' ($(if ($ip) { $ip } else { 'WiFi 未连接' })) ([bool]$ip)

$lan8080 = if ($ip) { (curl.exe -s -o NUL -w '%{http_code}' --max-time 8 ("http://" + $ip + ":8080/health") 2>$null) } else { '000' }
Check 'LAN 8080 health' '200' $lan8080 ($lan8080 -eq '200')
$lan8443 = if ($ip) { (curl.exe -k -s -o NUL -w '%{http_code}' --max-time 8 ("https://" + $ip + ":8443/health") 2>$null) } else { '000' }
Check 'LAN 8443 health' '200' $lan8443 ($lan8443 -eq '200')

$pubA = (curl.exe -s -o NUL -w '%{http_code}' --max-time 12 'http://47.97.70.99:48108/health' 2>$null)
Check '公网 48104 health' '200' $pubA ($pubA -eq '200')
$pubB = (curl.exe -k -s -o NUL -w '%{http_code}' --max-time 12 'https://47.97.70.99:44904/health' 2>$null)
Check '公网 44904 health' '200' $pubB ($pubB -eq '200')

Write-Host '=== 5) SSH / supervisor / DSH ==='
$sshOk = $false; $supCount = 'n/a'; $dshUrl = 'n/a'
if ($ip -and (Test-Path $SshKey)) {
    $sshOut = (& ssh -i $SshKey -p 2222 -o StrictHostKeyChecking=no -o ConnectTimeout=10 "root@$ip" "echo SSH_OK; supervisorctl -c /root/server/etc/supervisord.conf status 2>&1 | grep -c RUNNING; server-dsh url 2>/dev/null | head -1" 2>&1) -join "`n"
    $sshOk = $sshOut -match 'SSH_OK'
    if ($sshOut -match 'SSH_OK\s*(\d+)') { $supCount = $Matches[1] }
    if ($sshOut -match '(https://[^\s]+token=[A-Za-z0-9_-]+)') { $dshUrl = $Matches[1] }
}
Check 'SSH 2222' '可登录' ($(if ($sshOk) { 'SSH_OK' } else { '失败（检查 IP/key）' })) $sshOk
Check 'supervisor RUNNING 数' '>=10' $supCount ($supCount -match '^\d+' -and [int]$supCount -ge 10)
Check 'DSH token URL' '可取到' ($(if ($dshUrl -ne 'n/a') { '已取到（不落盘显示）' } else { '未取到' })) ($dshUrl -ne 'n/a')

Write-Host '=== 6) 研究物料 ==='
$uad = Join-Path $root 'tools\uad_lists.json'
Check 'UAD 清单' '存在' ($(if (Test-Path $uad) { '存在' } else { '缺失' })) (Test-Path $uad)
$backup1 = Join-Path $root 'backup\dsh\ubuntu-base.tar.gz'
Check 'ubuntu-base 备份' '存在' ($(if (Test-Path $backup1) { '存在' } else { '缺失' })) (Test-Path $backup1)

$outFile = Join-Path $OutDir ('env-verify-' + (Get-Date).ToString('yyyyMMdd-HHmmss') + '.md')
$md = New-Object System.Text.StringBuilder
[void]$md.AppendLine('# 研究平台环境验证报告'); [void]$md.AppendLine('')
[void]$md.AppendLine(('- 时间：' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')))
[void]$md.AppendLine(('- LAN IP：' + $(if ($ip) { $ip } else { '未知' })))
[void]$md.AppendLine(''); [void]$md.AppendLine('| 检查项 | 期望 | 实际 | 结果 |'); [void]$md.AppendLine('|---|---|---|---|')
foreach ($r in $rows) { [void]$md.AppendLine(('| ' + $r.Item + ' | ' + $r.Expected + ' | ' + ($r.Actual -replace '|', '\\|') + ' | ' + $r.Result + ' |')) }
[void]$md.AppendLine(''); [void]$md.AppendLine('> 只读验证；不修改设备。')
[System.IO.File]::WriteAllText($outFile, $md.ToString(), (New-Object System.Text.UTF8Encoding($false)))

Write-Host ''
$rows | Format-Table -AutoSize
$fail = @($rows | Where-Object { $_.Result -eq 'FAIL' })
Write-Host ("报告: " + $outFile)
Write-Host ("结果: " + $rows.Count + " 项，失败 " + $fail.Count)
if ($fail.Count -gt 0) { exit 1 } else { exit 0 }
