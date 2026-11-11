# toolkit/repurpose.ps1
# 用途：Windows 下的 PowerShell 包装，等价于 python -m toolkit.repurpose。
# 参数：全部原样转发（ValueFromRemainingArguments），例如：
#   powershell -NoProfile -ExecutionPolicy Bypass -File toolkit\repurpose.ps1 validate --strict
#   powershell -NoProfile -ExecutionPolicy Bypass -File toolkit\repurpose.ps1 assess --profile profiles\haydn.json --json
# 退出码：与 Python CLI 一致（0 成功 / 2 用法错误 / 3 无 adb 或设备 / 4 校验失败）。
param([Parameter(ValueFromRemainingArguments = $true)]$Args)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repoRoot
try {
    & python -m toolkit.repurpose @Args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
