<#
.SYNOPSIS
    下载并解压 Android platform-tools（adb / fastboot / sqlite3）到 tools\platform-tools。
.DESCRIPTION
    官方下载源：https://dl.google.com/android/repository/platform-tools-latest-windows.zip
    不需要管理员权限，只写入项目目录。已存在时默认跳过，用 -Force 强制重新下载。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\get-platform-tools.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\get-platform-tools.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $repoRoot 'tools'
$adbExe   = Join-Path $toolsDir 'platform-tools\adb.exe'
$url      = 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip'

if ((Test-Path -LiteralPath $adbExe) -and -not $Force) {
    Write-Host "[跳过] platform-tools 已存在：$adbExe" -ForegroundColor Green
    & $adbExe version | Select-Object -First 1
    exit 0
}

New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$zipPath = Join-Path $toolsDir 'platform-tools-latest-windows.zip'

Write-Host '[1/3] 下载 platform-tools ...'
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curl) {
    throw '找不到 curl.exe（Windows 10 1809+ 自带；也可手动下载后解压到 tools\platform-tools）。'
}
& curl.exe -L --fail --retry 3 -o $zipPath $url
if ($LASTEXITCODE -ne 0) { throw "下载失败，curl 退出码 $LASTEXITCODE" }

Write-Host '[2/3] 解压 ...'
Expand-Archive -Path $zipPath -DestinationPath $toolsDir -Force
Remove-Item -LiteralPath $zipPath -Force

Write-Host '[3/3] 校验 ...'
& $adbExe version

Write-Host ''
Write-Host "完成：$adbExe" -ForegroundColor Green
Write-Host '下一步：powershell -ExecutionPolicy Bypass -File scripts\check-connection.ps1'
