<#
.SYNOPSIS
    adb 包装器：自动定位项目内 tools/platform-tools/adb.exe。
.DESCRIPTION
    优先使用项目自带的 platform-tools；找不到时回退到 ADB_PATH 环境变量或 PATH 中的 adb。
    兼容 Windows PowerShell 5.1 与 PowerShell 7+。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\adb.ps1 devices -l
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\adb.ps1 shell getprop ro.product.model
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\adb.ps1 -Resolve
#>
[CmdletBinding()]
param(
    [switch]$Resolve,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AdbArgs = @()
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectAdb = Join-Path $repoRoot 'tools\platform-tools\adb.exe'
$adbPath = $null

foreach ($candidate in @($env:ADB_PATH, $projectAdb)) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
        $adbPath = (Resolve-Path -LiteralPath $candidate).Path
        break
    }
}
if (-not $adbPath) {
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { $adbPath = $cmd.Source }
}
if (-not $adbPath) {
    Write-Error '找不到 adb。请先运行 scripts/get-platform-tools.ps1 下载 platform-tools，或设置 ADB_PATH 环境变量。'
    exit 2
}

if ($Resolve) {
    Write-Output $adbPath
    exit 0
}

& $adbPath @AdbArgs
exit $LASTEXITCODE
