# Qingxuan Android Bridge（MVP）

本目录是 Android Bridge APK 的源码与可重复构建脚本（Phase 0/1 MVP）。

## 组成

- `AndroidManifest.xml`：`BootReceiver` + `BridgeService`（`specialUse` FGS）+ `MainActivity`
- `src/com/qingxuan/bridge/`
  - `BootReceiver.java`：BOOT_COMPLETED / MY_PACKAGE_REPLACED 启动 FGS
  - `BridgeService.java`：前台服务、通知、启动 loopback HTTPS
  - `LocalHttpsServer.java`：127.0.0.1:3099，只读 `/v1/health`、`/v1/version`、`/v1/status`；Bearer token
  - `BridgeStatus.java`：Battery/WiFi/Build/Memory/Disk/Thermal/Packages
  - `TokenStore.java`：首次运行生成随机 token（app private files）
- `assets/bridge.p12`：TLS 自签证书/私钥（**gitignored**，构建时生成）
- `certs/bridge.crt`：服务端 pin 用的公钥证书（**gitignored**，构建时生成）
- `signing.p12`：APK 签名 keystore（**gitignored**，构建时生成）
- `build.ps1`：无 Gradle 构建（aapt2 + javac + d8 + zipalign + apksigner）

## 前置

- JDK 17（本机 `D:\Program Files\Microsoft\jdk-17.0.20.8-hotspot`）
- Android SDK command-line tools + `platforms;android-35` + `build-tools;35.0.0`
  - 本机 SDK 在 `tools/android-sdk`（gitignored）
- **aapt2 在 Windows 上不支持含中文的路径**：`build.ps1` 会创建 ASCII junction：
  - `D:\android-sdk` → 仓库 `tools/android-sdk`
  - `D:\bridge-src` → 本目录
  若 D: 不可用需自行改 junction 路径；不要把构建产物提交。

## 构建

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File android-bridge\build.ps1
```

输出：

- `android-bridge/build/bridge.apk`（debug 签名，约 25KB）
- `android-bridge/build/bridge.crt`（服务端 pin 证书）

## 安装/授权（MVP debug）

```bash
adb install -r -t -g android-bridge/build/bridge.apk
adb shell pm grant com.qingxuan.bridge android.permission.POST_NOTIFICATIONS
adb shell pm grant com.qingxuan.bridge android.permission.ACCESS_FINE_LOCATION
adb shell cmd appops set com.qingxuan.bridge RUN_ANY_IN_BACKGROUND allow
adb shell dumpsys deviceidle whitelist +com.qingxuan.bridge
# MIUI/HyperOS 还需在“自启动管理”中打开 Qingxuan Bridge（一次性；见 docs/32）
```

debug 构建 token 读取（仅开发）：

```bash
adb shell run-as com.qingxuan.bridge cat files/bridge.token
```

将 token 写入服务器 `/root/server/etc/bridge.token`（600），证书写到 `/root/server/etc/bridge.crt`（644）。

## 测试

```bash
# 在 proot 服务器内
curl -sS --cacert /root/server/etc/bridge.crt https://127.0.0.1:3099/v1/health
curl -sS --cacert /root/server/etc/bridge.crt \
  -H "Authorization: Bearer $(cat /root/server/etc/bridge.token)" \
  https://127.0.0.1:3099/v1/status | head
```

预期：health `ok:true`；status 有 device/battery/wifi/memory/disk/thermal/packages。
未带 token 访问 status 应 401；只监听 127.0.0.1，LAN IP 不可达。

## MVP 限制（必须知道）

1. **debug 构建**（`android:debuggable=true`），token 通过 adb run-as 读取；正式版需 release + 配对流程。
2. **TLS 私钥在 APK assets 中**（静态证书），仅适用于本机 MVP；Phase 2 改运行时生成/证书轮换/mTLS。
3. **MIUI 自启动需人工开启**（本机已设置；其他 OEM 见 docs/32），Android 标准 `BOOT_COMPLETED + specialUse FGS` 已验证 5 次重启。
4. **UsageStats/NetworkStats 未进 MVP**（Phase 2，需用户授权）；CPU/网络原始字节不可得。
5. 不要把这个 APK 上传或用于公网；服务只绑 loopback。

更多实施记录见 [docs/33](docs/33-Android-Bridge-MVP实施记录.md)。
