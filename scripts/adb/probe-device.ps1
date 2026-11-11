<#
.SYNOPSIS
    推送并执行设备能力探测脚本（scripts\adb\probe-device.sh），结果保存到 inventory\。
.DESCRIPTION
    探测内容：内核命名空间/cgroup/overlayfs/seccomp/netfilter、充电控制节点、
    zram 与调度器、温控服务、boot 分区信息。
    用于把 docs/02-可行性分析.md 中的"待验证"项变成实测结论。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\adb\probe-device.ps1
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
    throw '找不到 adb。请先运行 scripts/adb/get-platform-tools.ps1。'
}

$adb = Resolve-Adb -Explicit $AdbPath
if (-not $OutDir) { $OutDir = Join-Path $repoRoot 'inventory' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$scriptFile = Join-Path $PSScriptRoot 'probe-device.sh'
if (-not (Test-Path -LiteralPath $scriptFile)) { throw "缺少脚本：$scriptFile" }

# 设备端要求 LF 行尾
$text = [System.IO.File]::ReadAllText($scriptFile)
$textLf = $text -replace "`r`n", "`n"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) 'probe-device.sh'
[System.IO.File]::WriteAllText($tmp, $textLf, (New-Object System.Text.UTF8Encoding($false)))

& $adb start-server 2>$null | Out-Null
& $adb push $tmp '/data/local/tmp/probe-device.sh' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'push 探测脚本失败' }

$out = (& $adb shell 'sh /data/local/tmp/probe-device.sh' 2>&1 | Out-String).TrimEnd()
Remove-Item -LiteralPath $tmp -Force

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$path = Join-Path $OutDir ("capability-probe-$stamp.txt")
[System.IO.File]::WriteAllText($path, $out, (New-Object System.Text.UTF8Encoding($false)))
Copy-Item -LiteralPath $path -Destination (Join-Path $OutDir 'capability-probe-latest.txt') -Force

Write-Host $out
Write-Host ''
Write-Host "已保存：$path" -ForegroundColor Green
