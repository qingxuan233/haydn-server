# Build the Qingxuan Android Bridge APK without Gradle (aapt2 + javac + d8 + zipalign + apksigner).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File android-bridge\build.ps1
#
# Requirements:
#   - JDK 17+ (javac / jar / keytool)
#   - Android SDK: platforms;android-35 (or 34) + build-tools;35.0.0
#     (accepted locations: $env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, <repo>\tools\android-sdk)
#   - Repository path MUST be ASCII: aapt2 cannot reliably handle non-ASCII paths on Windows.
#
# Artifacts (gitignored):
#   - android-bridge\build\bridge.apk   (release-signed, debuggable=false)
#   - android-bridge\build\bridge.crt   (certificate used by the server for TLS pinning)
#
# Local-only key material: assets\bridge.p12 (TLS), signing.p12 (APK signing) are generated
# on first build and MUST never be committed. Override passwords with env vars
# BRIDGE_TLS_PASS / BRIDGE_SIGN_PASS if you rotate the keystores.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProjectRoot = $PSScriptRoot
$RepoRoot = Split-Path $ProjectRoot -Parent

function Fail([string]$Message) { throw "[build] $Message" }

# ---------------------------------------------------------------- path guard
if ($RepoRoot -match '[^\x00-\x7F]') {
    Fail ("repository path contains non-ASCII characters: {0}. Rename/move the repository to an ASCII-only path (e.g. D:\CODE\haydn-server) and retry." -f $RepoRoot)
}

# ---------------------------------------------------------------- locate JDK
function Find-Jdk {
    $candidates = @()
    if ($env:JAVA_HOME) { $candidates += $env:JAVA_HOME }
    foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($base) { $candidates += (Join-Path $base 'Microsoft') }
        if ($base) { $candidates += (Join-Path $base 'Java') }
        if ($base) { $candidates += (Join-Path $base 'Android\Android Studio') }
        if ($base) { $candidates += (Join-Path $base 'JetBrains') }
    }
    $candidates += 'D:\Program Files\Microsoft'
    foreach ($c in $candidates) {
        if (-not (Test-Path $c)) { continue }
        $javac = Get-ChildItem -Path $c -Recurse -Filter 'javac.exe' -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($javac) { return $javac.DirectoryName | Split-Path -Parent }
    }
    $cmd = Get-Command javac.exe -ErrorAction SilentlyContinue
    if ($cmd) { return (Split-Path $cmd.Source -Parent | Split-Path -Parent) }
    return $null
}

$Jdk = Find-Jdk
if (-not $Jdk) { Fail 'JDK not found. Set JAVA_HOME to a JDK 17+ installation.' }
$Javac = Join-Path $Jdk 'bin\javac.exe'
$Jar = Join-Path $Jdk 'bin\jar.exe'
$Keytool = Join-Path $Jdk 'bin\keytool.exe'
foreach ($p in @($Javac, $Jar, $Keytool)) {
    if (-not (Test-Path $p)) { Fail "JDK is incomplete, missing: $p (JAVA_HOME=$Jdk)" }
}

# ---------------------------------------------------------------- locate SDK
function Find-Sdk {
    $roots = @()
    if ($env:ANDROID_HOME) { $roots += $env:ANDROID_HOME }
    if ($env:ANDROID_SDK_ROOT) { $roots += $env:ANDROID_SDK_ROOT }
    $roots += (Join-Path $RepoRoot 'tools\android-sdk')
    if ($env:LOCALAPPDATA) { $roots += (Join-Path $env:LOCALAPPDATA 'Android\Sdk') }
    foreach ($r in $roots) {
        if ($r -and (Test-Path (Join-Path $r 'build-tools')) -and (Test-Path (Join-Path $r 'platforms'))) { return $r }
    }
    return $null
}

$Sdk = Find-Sdk
if (-not $Sdk) { Fail 'Android SDK not found. Set ANDROID_HOME/ANDROID_SDK_ROOT or place it at <repo>\tools\android-sdk.' }
if ($Sdk -match '[^\x00-\x7F]') { Fail "Android SDK path contains non-ASCII characters: $Sdk" }

$buildToolsDir = Get-ChildItem (Join-Path $Sdk 'build-tools') -Directory |
    Sort-Object { [version]($_.Name -replace '-.*', '') } -Descending | Select-Object -First 1
if (-not $buildToolsDir) { Fail "no build-tools found under $Sdk\build-tools" }
$platformDir = Get-ChildItem (Join-Path $Sdk 'platforms') -Directory -Filter 'android-*' |
    Sort-Object Name -Descending | Select-Object -First 1
if (-not $platformDir) { Fail "no platforms found under $Sdk\platforms" }
$androidJar = Join-Path $platformDir.FullName 'android.jar'
if (-not (Test-Path $androidJar)) { Fail "android.jar missing under $($platformDir.FullName)" }

$BuildTools = $buildToolsDir.FullName
$Aapt2 = Join-Path $BuildTools 'aapt2.exe'
$D8 = Join-Path $BuildTools 'd8.bat'
$ZipAlign = Join-Path $BuildTools 'zipalign.exe'
$ApkSigner = Join-Path $BuildTools 'apksigner.bat'
foreach ($p in @($Aapt2, $D8, $ZipAlign, $ApkSigner)) {
    if (-not (Test-Path $p)) { Fail "build-tools is incomplete, missing: $p" }
}

Write-Host "[build] repo    = $RepoRoot"
Write-Host "[build] jdk     = $Jdk"
Write-Host "[build] sdk     = $Sdk"
Write-Host "[build] tools   = $BuildTools"
Write-Host "[build] platform= $($platformDir.Name)"

# ---------------------------------------------------------------- key material
$manifest = Join-Path $ProjectRoot 'AndroidManifest.xml'
$assets = Join-Path $ProjectRoot 'assets'
$certs = Join-Path $ProjectRoot 'certs'
$src = Join-Path $ProjectRoot 'src'
$build = Join-Path $ProjectRoot 'build'
$signing = Join-Path $ProjectRoot 'signing.p12'
$bridgeP12 = Join-Path $assets 'bridge.p12'
$certFile = Join-Path $certs 'bridge.crt'

$TlsPass = if ($env:BRIDGE_TLS_PASS) { $env:BRIDGE_TLS_PASS } else { 'BrdgTls2026!' }
$SignPass = if ($env:BRIDGE_SIGN_PASS) { $env:BRIDGE_SIGN_PASS } else { 'BrdgSign2026!' }

foreach ($p in @($manifest, $src)) { if (-not (Test-Path $p)) { Fail "project input missing: $p" } }
New-Item -ItemType Directory -Force -Path $assets, $certs | Out-Null

# TLS material for the loopback HTTPS server (self-signed, local MVP only).
if (-not (Test-Path $bridgeP12)) {
    Write-Host '[build] generating TLS keystore (assets\bridge.p12)'
    & $Keytool -genkeypair -alias bridge -keyalg RSA -keysize 2048 -validity 3650 `
        -storetype PKCS12 -keystore $bridgeP12 -storepass $TlsPass -keypass $TlsPass `
        -dname 'CN=com.qingxuan.bridge, OU=HaydnServer, O=Qingxuan' `
        -ext 'SAN=ip:127.0.0.1,dns:localhost' 2>&1 | Out-Null
}
if (-not (Test-Path $certFile)) {
    Write-Host '[build] exporting TLS certificate (certs\bridge.crt)'
    & $Keytool -exportcert -rfc -alias bridge -keystore $bridgeP12 -storepass $TlsPass `
        -file $certFile 2>&1 | Out-Null
}
# APK signing keystore (release-signed, debuggable=false).
if (-not (Test-Path $signing)) {
    Write-Host '[build] generating APK signing keystore (signing.p12)'
    & $Keytool -genkeypair -alias bridge-release -keyalg RSA -keysize 2048 -validity 10000 `
        -storetype PKCS12 -keystore $signing -storepass $SignPass -keypass $SignPass `
        -dname 'CN=Qingxuan Bridge, O=Qingxuan' 2>&1 | Out-Null
}

# ---------------------------------------------------------------- compile
if (Test-Path $build) { Remove-Item $build -Recurse -Force }
New-Item -ItemType Directory -Force -Path $build, (Join-Path $build 'classes'), (Join-Path $build 'dex') | Out-Null
$unsignedApk = Join-Path $build 'unsigned.apk'
$alignedApk = Join-Path $build 'aligned.apk'
$outApk = Join-Path $build 'bridge.apk'
$env:JAVA_HOME = $Jdk
$env:PATH = "$($Jdk)\bin;$BuildTools;$env:PATH"

Write-Host '=== 1/5 aapt2 link (manifest + assets) ==='
& $Aapt2 link -o $unsignedApk -I $androidJar --manifest $manifest -A $assets
if ($LASTEXITCODE -ne 0) { Fail "aapt2 link failed (exit $LASTEXITCODE)" }

Write-Host '=== 2/5 javac ==='
$srcFiles = (Get-ChildItem $src -Recurse -Filter *.java | ForEach-Object { $_.FullName })
& $Javac -source 8 -target 8 -Xlint:-options -nowarn -classpath $androidJar -d (Join-Path $build 'classes') $srcFiles
if ($LASTEXITCODE -ne 0) { Fail "javac failed (exit $LASTEXITCODE)" }

Write-Host '=== 3/5 jar + d8 ==='
& $Jar cf (Join-Path $build 'classes.jar') -C (Join-Path $build 'classes') .
if ($LASTEXITCODE -ne 0) { Fail "jar failed (exit $LASTEXITCODE)" }
& $D8 --min-api 29 --lib $androidJar --output (Join-Path $build 'dex') (Join-Path $build 'classes.jar')
if ($LASTEXITCODE -ne 0) { Fail "d8 failed (exit $LASTEXITCODE)" }

Write-Host '=== 4/5 add classes.dex ==='
Copy-Item (Join-Path $build 'dex\classes.dex') (Join-Path $build 'classes.dex') -Force
Push-Location $build
try {
    & $Jar uf $unsignedApk 'classes.dex'
    if ($LASTEXITCODE -ne 0) { Fail "adding classes.dex failed (exit $LASTEXITCODE)" }
} finally { Pop-Location }

Write-Host '=== 5/5 zipalign + sign ==='
& $ZipAlign -f 4 $unsignedApk $alignedApk
if ($LASTEXITCODE -ne 0) { Fail "zipalign failed (exit $LASTEXITCODE)" }
& $ApkSigner sign --ks $signing --ks-pass "pass:$SignPass" --key-pass "pass:$SignPass" --out $outApk $alignedApk
if ($LASTEXITCODE -ne 0) { Fail "apksigner sign failed (exit $LASTEXITCODE)" }
& $ApkSigner verify --print-certs $outApk
if ($LASTEXITCODE -ne 0) { Fail 'apksigner verify failed' }

Copy-Item $certFile (Join-Path $build 'bridge.crt') -Force

$apkInfo = Get-Item $outApk
Write-Host ''
Write-Host ("[build] APK : {0} ({1:N0} bytes)" -f $apkInfo.FullName, $apkInfo.Length)
Write-Host ("[build] CERT: {0}" -f (Join-Path $build 'bridge.crt'))
Write-Host '[build] OK'
