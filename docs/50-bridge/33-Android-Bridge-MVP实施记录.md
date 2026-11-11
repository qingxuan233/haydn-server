# 33 · Android Bridge MVP 实施记录（Phase 0/1）

> **历史记录（2026-11-11）**：本文记录 Phase 0/1 MVP、release 加固与仓库改名后的构建路径修复；当前状态以 [当前状态](../00-overview/当前状态.md) 为准。

| 文档 ID | `HB-BRIDGE-002` |
|---|---|
| 版本 | v1.2（2026-11-11 补 §9 仓库与构建路径修复） |
| 状态 | 历史记录（实施记录，含 release 加固） |
| 关联 | [27 Bridge 架构调研](27-Android-Bridge-APK架构调研.md) · [28 全栈整体方案规范](../00-overview/28-全栈整体方案规范.md) · [31 拍板事项](../10-device/31-拍板事项决策分析与Root升级路线.md) · [32 多厂商适配](../10-device/32-多厂商Android适配与迁移指南.md) |

> 实施时间：2026-11-11 00:30–01:15（Phase 0/1）、07:30–07:45（release 加固）、08:30 左右（仓库改名后的构建路径修复）。
> 范围：按用户批准的 D1–D10 推荐实施；无 Root、无外部服务。

---

## 1. 结论

**Phase 0/1 MVP 已落地（历史快照，2026-11-11 01:15）：**

- Bridge APK：`com.qingxuan.bridge`，debug 签名，约 25KB（release 加固见 §8）；
- BootReceiver + `specialUse` Foreground Service + loopback HTTPS + token；
- 端点 `/v1/health`、`/v1/version`、`/v1/status`；
- `Battery/WiFi/Build/Memory/Disk/Thermal/Packages` 已接入；
- 服务器 `bridge_client.py` + `/api/sysinfo` + `server-ops bridge status` 已接入；
- **5/5 次重启验证通过**：Bridge 自启、health 200、API `source=bridge`、服务器 12/12；
- 安全边界：status 无 token=401；仅 127.0.0.1；LAN IP 不可达；
- 回退：Bridge 停止时 API `source=termux`，恢复后回 `bridge`。

**2026-11-11 08:30 左右的现状（供引用，勿与上面的历史快照混淆）**：release 版已安装运行（`debuggable=false`）；5/5 debug 重启 + 1/1 release 重启通过；Phase 2 字段（display/usage/network bytes/uptime）已接入 API/UI；**24h soak 未完成**。完整状态见 [当前状态](../00-overview/当前状态.md)。

---

## 2. Phase 0：构建环境

- Android SDK：command-line tools + `platforms;android-35` + `build-tools;35.0.0`（装在 `tools/android-sdk`，gitignored）。
- JDK 17；**没有安装 Gradle**，使用 `aapt2 + javac + d8 + zipalign + apksigner` 的 `android-bridge/build.ps1`。
- 关键坑（2026-11-11 早晨遇到，同日已修复）：**aapt2 在 Windows 上不能处理含中文的路径**（当时仓库路径含“手机优化”）。
  - 当时的绕行：构建脚本创建 ASCII junction：`D:\android-sdk` → `tools/android-sdk`；`D:\bridge-src` → `android-bridge`。
  - 不建 junction 时 aapt2 会报 `Failed to stat ... android.jar`/assets 路径错误。
  - **2026-11-11 08:30 左右**：仓库改名为 `D:\CODE\haydn-server`，两个 junction 已删除，`build.ps1` 改为自动探测 JDK/SDK 并对非 ASCII 路径直接报错；详见 [§9](#9-2026-11-11-仓库与构建路径修复)。
- 构建材料（TLS p12、signing p12、certs）由 `build.ps1` 自动生成，已在 `.gitignore` 中排除私钥。

---

## 3. APK 结构

| 文件 | 作用 |
|---|---|
| `AndroidManifest.xml` | BootReceiver（BOOT_COMPLETED/MY_PACKAGE_REPLACED/QUICKBOOT）、BridgeService（specialUse FGS）、MainActivity |
| `BootReceiver.java` | 收到开机广播后 `startForegroundService` |
| `BridgeService.java` | 前台通知 + 启动 loopback HTTPS；`START_STICKY` |
| `LocalHttpsServer.java` | TLS 1.3、127.0.0.1:3099、Bearer token、只读 GET |
| `BridgeStatus.java` | 状态采集；`source=android`、`capabilities`、字段可空 |
| `TokenStore.java` | 首次运行生成 43 字符随机 token（app private） |

安全说明（MVP）：
- TLS 证书为**构建时自签**，私钥随 APK assets 打包（仅本机 MVP 可接受）；
- debug 构建用于 token 通过 `adb run-as` 提取；
- 正式发布需 Phase 2：release 签名 + 运行时证书/配对/mTLS。

---

## 4. 安装与服务器接入

### 4.1 Android 侧

```bash
adb install -r -t -g android-bridge/build/bridge.apk
adb shell pm grant com.qingxuan.bridge android.permission.POST_NOTIFICATIONS
adb shell pm grant com.qingxuan.bridge android.permission.ACCESS_FINE_LOCATION
adb shell cmd appops set com.qingxuan.bridge RUN_ANY_IN_BACKGROUND allow
adb shell dumpsys deviceidle whitelist +com.qingxuan.bridge
# MIUI/HyperOS：设置→应用→自启动管理，打开 Qingxuan Bridge（一次性）
```

> **MIUI 自启动是必需的**：仅设置 appops/deviceidle 时，BootReceiver 仍被 MIUI AutoStart 策略拦截；本次通过自启动管理 UI 将 Qingxuan Bridge 从“禁止”移入“允许”后，5/5 重启成功。
> 其他 OEM 对应步骤见 [32 多厂商 Android 适配与迁移指南 §3 OEM 适配矩阵](../10-device/32-多厂商Android适配与迁移指南.md)。

### 4.2 服务器侧

- 新增 `scripts/server/bridge_client.py`（HTTPS 127.0.0.1:3099，证书 pin、token、2s 超时、10s 缓存）。
- `console-api.py` 的 `/api/sysinfo` 合并 bridge 字段，并返回：
  `bridge_source` / `bridge_available` / `bridge_age_s` / `bridge_version` / `bridge_last_seen` / `bridge_error`。
- UI 顶部显示来源（`d-host`）与已有的设备/电池/WiFi 字段。
- `server-ops bridge status`（只读）新增。
- 凭据：
  - `/root/server/etc/bridge.token`（600）
  - `/root/server/etc/bridge.crt`（644）
  - 均随 `server-backup` 加密备份进入 `/root/server/etc`。

---

## 5. 验证记录

### 5.1 5 次重启（累计）

| 次 | Bridge 进程 | `/v1/health` | API source | 服务器 |
|---|---|---|---|---|
| 1（首次开启 MIUI 自启动后） | ✅ | 200 | bridge | 12/12 |
| 2 | ✅ | 200 | bridge | 12/12 |
| 3 | ✅ | 200 | bridge | 12/12 |
| 4 | ✅ | 200 | bridge | 12/12 |
| 5 | ✅ | 200 | bridge | 12/12 |

- Bridge 启动日志：`BridgeBoot: bridge service start requested for BOOT_COMPLETED` → `BridgeService: startForeground returned` → `bridge https server started`。
- FGS：`isForeground=true`，`startForegroundCount=1`；HOME 后服务不被立即回收。

### 5.2 安全/权限

- 无 token `/v1/status` → **401**；
- 仅 127.0.0.1；`https://192.168.10.159:3099` → 连接失败；
- `server-ops bridge status` 可读；DSH 不持 token。

### 5.3 回退

- `am force-stop com.qingxuan.bridge` → API `source=termux`、`available=false`；
- 重新启动后恢复 `source=bridge`。

### 5.4 API 样例

```text
source=bridge available=True battery=100% FULL PLUGGED_AC 25.0C
wifi_ip=192.168.10.159 rssi=-33 link=573
device=M2012K11C Xiaomi Android 14
package_count=359 thermal_battery=25.0
```

---

## 6. 已知限制 / 尚未做（2026-11-11 01:15 快照；§8 的 release 加固已改善其中部分）

1. **debug APK（历史）**：当时为 debug 签名；正式 release 签名、配对、token exchange、mTLS 未做。**08:00 左右已改 release 签名（见 §8.1）；配对/token exchange/mTLS 仍未做。**
2. **TLS 私钥静态**：MVP 可接受；Phase 2 改运行时证书/轮换。
3. **24h soak**：尚未连续跑满 24h；需补（截至 08:30 仍未完成）。
4. **UsageStats / NetworkStats**：按 D1 不进 MVP；Phase 2 已接入 display/usage/network bytes（§8.2），但 GET_USAGE_STATS 重启后需重新授权（§8.3），`usage_foreground` 可能为空。
5. **全局 CPU/网络原始字节/dumpsys**：无 Root 不可得。
6. **OEM 自启动**：MIUI 需人工自启动管理；其他 OEM profile 见 [32 多厂商 Android 适配与迁移指南](../10-device/32-多厂商Android适配与迁移指南.md)。
7. **MIUI 私有 appop** 不可靠；本次最终通过 UI 自启动白名单，而不是 appops。

---

## 7. 后续（按 [28 全栈整体方案规范](../00-overview/28-全栈整体方案规范.md)）

| 任务 | 说明 | 状态（2026-11-11 08:30） |
|---|---|---|
| 24h soak | Bridge/API/DSH/服务器持续监控；失败回退 termux | ⬜ 未完成 |
| release 构建 | 关闭 debuggable；token 配对；签名 key 管理 | ✅ release 已完成（§8.1）；配对/token exchange 仍未做 |
| Phase 2 | UsageStats/NetworkStats/Display/Keyguard、mTLS、证书轮换 | 🔶 display/usage/network/uptime 已接入；mTLS/证书轮换未做 |
| 文档 | 更新 [28 全栈规范](../00-overview/28-全栈整体方案规范.md)、[30 接手指南](../00-overview/30-新会话接手指南.md)、README 状态；补充 OEM profile | 🔶 2026-11-11 文档重构已更新结构 |
| 安全 | 运行时证书、token 轮换、审计/限流加严 | ⬜ 未做 |


---

## 8. Release 加固与 Phase 2（2026-11-11 07:30–07:45）

### 8.1 Release APK

- `android:debuggable=false`，同签名 key 原地 `install -r`；
- **token 保留**：升级后服务器 `/api/sysinfo` 仍 `source=bridge`；不再依赖 `run-as`；
- 验证：release 包无 `application-debuggable`；`/v1/health` 200。

### 8.2 Phase 2 新增字段

Bridge：
- `uptime_s`（elapsedRealtime）
- `display`：interactive / locked / refresh_hz / brightness
- `usage`：foreground / available（UsageStatsManager）
- `network`：rx_bytes / tx_bytes（TrafficStats 累计，since_boot=true）
- `capabilities` 增加 display/usage/network_bytes/uptime

服务器 `/api/sysinfo`：
- `bridge_uptime_s`、`display_*`、`usage_*`、`net_*_bytes`、`network_since_boot`、`bridge_capabilities`

Console 详情新增：屏幕/锁屏、前台应用、网络累计。

### 8.3 权限/自启现实

- **MIUI 自启动**在 release 更新/重启后仍保留，release 重启 `BOOT_COMPLETED` 成功；
- **POST_NOTIFICATION** 在 release 安装/重启后被 MIUI 重置为 ignore，但 FGS 仍工作（通知不可见）；
- **GET_USAGE_STATS** 在重启后回到 default：`usage_foreground` 为空；需用户/ADB 再授权（Phase 2 可选字段，不影响主链路）；
- 未实现“开机自动恢复 Usage 权限”；需要后续用 App 引导 Settings 或维护脚本。

### 8.4 稳定性

- 升级前 debug 版连续 **6h21m**：Bridge 无重启/错误，API source=bridge，服务器 12/12；
- release 升级后 **1/1 重启通过**；24h soak 仍待完成。

---

## 9. 2026-11-11 仓库与构建路径修复

### 9.1 问题：中文路径导致 aapt2 失败

- 现象：`aapt2` 在 Windows 上不能可靠处理含中文的路径（`Failed to stat ... android.jar` / assets 路径解析错误）；仓库当时名为 `D:\CODE\手机优化`。
- 当时的临时绕行：`build.ps1` 建两个 ASCII junction（`D:\android-sdk` → `tools/android-sdk`、`D:\bridge-src` → `android-bridge`）。副作用：依赖固定盘符、跨机器不可重现、易残留。
- 决定（2026-11-11 08:30 左右）：不再保留 junction。

### 9.2 修复：仓库改名 + 构建脚本自动探测

| 项 | 修复后 |
|---|---|
| 仓库路径 | `手机优化` → `haydn-server`（`D:\CODE\haydn-server`），文档与脚本内引用同步更新 |
| ASCII junction | 已删除（`D:\android-sdk`、`D:\bridge-src` 不再需要；发现残留可直接删除） |
| build.ps1 | 去掉 junction 逻辑；启动时校验仓库路径与 SDK 路径必须为 ASCII，否则直接报错；JDK/SDK 自动探测 |
| 产物 | 不变：`android-bridge\build\bridge.apk`（release 签名、`debuggable=false`，约 25KB）+ `build\bridge.crt` |

探测顺序：
- SDK：`$env:ANDROID_HOME` → `$env:ANDROID_SDK_ROOT` → 仓库 `tools\android-sdk` → `%LOCALAPPDATA%\Android\Sdk`；
- JDK：`$env:JAVA_HOME` → 常见安装目录（`Program Files\Microsoft` / `Java` / Android Studio / JetBrains 等）→ PATH 中的 `javac`。

构建命令、安装/授权与测试步骤见 [android-bridge/README.md](../../android-bridge/README.md)。

### 9.3 影响与验证

- 改名前构建失败；改名后 `build.ps1` 一次通过，产物 `bridge.apk` 为 release 签名、`debuggable=false`；
- 已安装运行并验证 1/1 release 重启（§8.4）；服务器 `/api/sysinfo` 仍 `source=bridge`；
- 结论：**ASCII 路径是硬性前提**，今后不要把仓库放回中文路径；构建脚本会在路径非 ASCII 时直接失败并提示。

---

## 10. 关联文档

- [27 Bridge 架构调研](27-Android-Bridge-APK架构调研.md)（历史调研，结论仍有效）
- [android-bridge/README.md](../../android-bridge/README.md)（构建/安装/测试的现行操作说明）
- [当前状态](../00-overview/当前状态.md) · [28 全栈整体方案规范](../00-overview/28-全栈整体方案规范.md)
