# MIUI/HyperOS 下通过 ADB 安装 APK（自动点按安装确认弹窗）
# 背景：MIUI 拦截 adb install，返回 INSTALL_FAILED_USER_RESTRICTED，
#       实际是 com.miui.securitycenter/.permcenter.install.AdbInstallActivity 弹窗等待用户确认。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\adb\miui-adb-install.ps1 -Apk tools\apks\shizuku.apk
# 说明：脚本会临时延长亮屏、唤醒屏幕、轮询 UI 并点击「继续安装/安装/允许」等按钮，结束后恢复 15s 熄屏。
param(
    [Parameter(Mandatory = $true)][string]$Apk,
    [string]$Serial = ''
)

$ErrorActionPreference = 'Continue'
$adb = Join-Path $PSScriptRoot '..\tools\platform-tools\adb.exe'
if (-not (Test-Path $adb)) { Write-Host "找不到 adb: $adb"; exit 1 }
if (-not (Test-Path $Apk)) { Write-Host "找不到 APK: $Apk"; exit 1 }
$serialArgs = @()
if ($Serial) { $serialArgs = @('-s', $Serial) }

function A([string[]]$cmdArgs) { & $adb @serialArgs @cmdArgs 2>&1 }

Write-Host "· 唤醒屏幕 / 临时延长亮屏"
A @('shell', 'settings put system screen_off_timeout 1800000') | Out-Null
A @('shell', 'input keyevent KEYCODE_WAKEUP') | Out-Null
A @('shell', 'wm dismiss-keyguard') | Out-Null
Start-Sleep -Seconds 1

Write-Host "· 后台发起安装"
$uiPath = '/data/local/tmp/_miui_install_ui.xml'
$localUi = Join-Path $env:TEMP '_miui_install_ui.xml'
$job = Start-Job -ScriptBlock {
    param($a, $s, $apk)
    & $a @s install -r -t -g $apk 2>&1
} -ArgumentList $adb, $serialArgs, $Apk

$success = $false
for ($i = 1; $i -le 25; $i++) {
    Start-Sleep -Seconds 1
    $jobDone = (Get-Job -Id $job.Id).State -eq 'Completed'
    $jobText = ''
    if ($jobDone) { $jobText = (Receive-Job -Id $job.Id -Keep 2>&1 | Out-String) }
    if ($jobText -match 'Success') { $success = $true; Write-Host "  ✓ 安装成功（无需弹窗或已确认）"; break }

    Remove-Item $localUi -Force -ErrorAction SilentlyContinue
    A @('shell', "uiautomator dump $uiPath") | Out-Null
    A @('pull', $uiPath, $localUi) | Out-Null
    if (-not (Test-Path $localUi)) { continue }

    $xml = [System.IO.File]::ReadAllText($localUi)
    $hit = $null
    foreach ($m in [regex]::Matches($xml, '<node[^>]*clickable="true"[^>]*>')) {
        $n = $m.Value
        $text = if ($n -match 'text="([^"]*)"') { $Matches[1] } else { '' }
        $desc = if ($n -match 'content-desc="([^"]*)"') { $Matches[1] } else { '' }
        $label = ($text + ' ' + $desc).Trim()
        if ($label -match '^继续安装$|^安装$|^允许$|^确定$|^同意$|^授权$|^开始安装$|^下一步$') {
            if ($n -match 'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"') {
                $hit = @{ label = $label; x = [int](([int]$Matches[1] + [int]$Matches[3]) / 2); y = [int](([int]$Matches[2] + [int]$Matches[4]) / 2) }
            }
        }
    }
    if ($hit) {
        Write-Host ("  · 点击按钮「" + $hit.label + "」@ " + $hit.x + "," + $hit.y)
        A @('shell', ("input tap " + $hit.x + " " + $hit.y)) | Out-Null
        Start-Sleep -Seconds 3
        if ($jobDone) {
            $jobText = (Receive-Job -Id $job.Id -Keep 2>&1 | Out-String)
            if ($jobText -match 'Success') { $success = $true; break }
        }
    }
}

A @('shell', 'settings put system screen_off_timeout 15000') | Out-Null
$out = Receive-Job -Id $job.Id -Keep 2>&1 | Out-String
Remove-Job -Id $job.Id -Force -ErrorAction SilentlyContinue
if ($success -or $out -match 'Success') { Write-Host '✓ APK 安装完成'; exit 0 }
Write-Host '✗ 安装未完成（可能弹窗未被识别或已被取消）'
Write-Host $out
exit 1
