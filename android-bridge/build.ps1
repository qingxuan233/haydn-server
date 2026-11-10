# Bootstrap Android Bridge APK without Gradle (aapt2 + javac + d8 + apksigner).
# Usage: powershell -ExecutionPolicy Bypass -File android-bridge\build.ps1
$ErrorActionPreference = 'Stop'
$base = Split-Path $PSScriptRoot -Parent
$asciiProject = 'D:\bridge-src'
$asciiSdk = 'D:\android-sdk'
# aapt2 on Windows cannot reliably handle non-ASCII paths; use ASCII junctions.
if (-not (Test-Path $asciiProject)) {
    cmd /c mklink /J "$asciiProject" "$PSScriptRoot" | Out-Null
}
if (-not (Test-Path $asciiSdk)) {
    cmd /c mklink /J "$asciiSdk" "$base\tools\android-sdk" | Out-Null
}
if (-not (Test-Path $asciiProject)) { throw 'cannot create ASCII junction D:\bridge-src' }
if (-not (Test-Path $asciiSdk)) { throw 'cannot create ASCII junction D:\android-sdk' }
$project = $asciiProject
$sdk = $asciiSdk
$buildTools = Join-Path $sdk 'build-tools\35.0.0'
$platform = Join-Path $sdk 'platforms\android-35\android.jar'
$jdk = 'D:\Program Files\Microsoft\jdk-17.0.20.8-hotspot'
$javac = Join-Path $jdk 'bin\javac.exe'
$jar = Join-Path $jdk 'bin\jar.exe'
$keytool = Join-Path $jdk 'bin\keytool.exe'
$d8 = Join-Path $buildTools 'd8.bat'
$aapt2 = Join-Path $buildTools 'aapt2.exe'
$zipalign = Join-Path $buildTools 'zipalign.exe'
$apksigner = Join-Path $buildTools 'apksigner.bat'
$manifest = Join-Path $project 'AndroidManifest.xml'
$assets = Join-Path $project 'assets'
$src = Join-Path $project 'src'
$certs = Join-Path $project 'certs'
$build = Join-Path $project 'build'
$signing = Join-Path $project 'signing.p12'
$env:JAVA_HOME = $jdk
$env:PATH = "$jdk\bin;$buildTools;$env:PATH"

# Generate local TLS/signing material if absent (gitignored; never commit private keys).
$bridgeP12 = Join-Path $assets 'bridge.p12'
$certFile = Join-Path $certs 'bridge.crt'
$signing = Join-Path $PSScriptRoot 'signing.p12'
New-Item -ItemType Directory -Force -Path $assets, $certs | Out-Null
if (-not (Test-Path $bridgeP12)) {
    & $keytool -genkeypair -alias bridge -keyalg RSA -keysize 2048 -validity 3650 `
        -storetype PKCS12 -keystore $bridgeP12 -storepass 'BrdgTls2026!' -keypass 'BrdgTls2026!' `
        -dname 'CN=com.qingxuan.bridge, OU=HaydnServer, O=Qingxuan' `
        -ext 'SAN=ip:127.0.0.1,dns:localhost' 2>&1 | Out-Null
}
if (-not (Test-Path $certFile)) {
    & $keytool -exportcert -rfc -alias bridge -keystore $bridgeP12 -storepass 'BrdgTls2026!' `
        -file $certFile 2>&1 | Out-Null
}
if (-not (Test-Path $signing)) {
    & $keytool -genkeypair -alias bridge-release -keyalg RSA -keysize 2048 -validity 10000 `
        -storetype PKCS12 -keystore $signing -storepass 'BrdgSign2026!' -keypass 'BrdgSign2026!' `
        -dname 'CN=Qingxuan Bridge, O=Qingxuan' 2>&1 | Out-Null
}

foreach ($p in @($javac, $jar, $keytool, $aapt2, $d8, $zipalign, $apksigner, $manifest, $platform)) {
    if (-not (Test-Path $p)) { throw "missing build dependency: $p" }
}
if (Test-Path $build) { Remove-Item $build -Recurse -Force }
New-Item -ItemType Directory -Force -Path $build, (Join-Path $build 'classes'), (Join-Path $build 'dex') | Out-Null

Write-Host '=== 1) aapt2 link (manifest + assets) ==='
& $aapt2 link -o (Join-Path $build 'unsigned.apk') -I $platform --manifest $manifest -A $assets
if ($LASTEXITCODE -ne 0) { throw "aapt2 link failed: $LASTEXITCODE" }

Write-Host '=== 2) javac ==='
$srcFiles = Get-ChildItem $src -Recurse -Filter *.java | ForEach-Object { $_.FullName }
& $javac -source 8 -target 8 -classpath $platform -d (Join-Path $build 'classes') $srcFiles
if ($LASTEXITCODE -ne 0) { throw "javac failed: $LASTEXITCODE" }

Write-Host '=== 3) jar + d8 ==='
& $jar cf (Join-Path $build 'classes.jar') -C (Join-Path $build 'classes') .
if ($LASTEXITCODE -ne 0) { throw "jar failed: $LASTEXITCODE" }
& $d8 --min-api 29 --lib $platform --output (Join-Path $build 'dex') (Join-Path $build 'classes.jar')
if ($LASTEXITCODE -ne 0) { throw "d8 failed: $LASTEXITCODE" }

Write-Host '=== 4) add classes.dex ==='
Copy-Item (Join-Path $build 'dex\classes.dex') (Join-Path $build 'classes.dex') -Force
Push-Location $build
& $jar uf unsigned.apk classes.dex
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "add classes.dex failed" }
Pop-Location

Write-Host '=== 5) zipalign + sign ==='
& $zipalign -f 4 (Join-Path $build 'unsigned.apk') (Join-Path $build 'aligned.apk')
if ($LASTEXITCODE -ne 0) { throw "zipalign failed" }
& $apksigner sign --ks $signing --ks-pass 'pass:BrdgSign2026!' --key-pass 'pass:BrdgSign2026!' --out (Join-Path $build 'bridge.apk') (Join-Path $build 'aligned.apk')
if ($LASTEXITCODE -ne 0) { throw "apksigner failed" }
& $apksigner verify --print-certs (Join-Path $build 'bridge.apk')

Copy-Item (Join-Path $certs 'bridge.crt') (Join-Path $build 'bridge.crt') -Force
Write-Host ''
Write-Host ('APK: ' + (Join-Path $build 'bridge.apk'))
Write-Host ('CERT: ' + (Join-Path $build 'bridge.crt'))
Get-Item (Join-Path $build 'bridge.apk') | Select-Object Name, Length
