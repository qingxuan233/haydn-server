# Qingxuan Android Bridge（Bridge APK）

`android-bridge/` 是 **Android Bridge APK** 的源码与可重复构建目录：一个无 Root 的伴生 App，用 `specialUse` 前台服务常驻，在 `127.0.0.1:3099` 提供只读 HTTPS 状态接口，供 proot 服务器聚合手机状态（电池 / WiFi / 屏幕 / 用法 / 网络累计等）。

> **状态（2026-11-11）**：release 版已安装运行（`debuggable=false`，约 25KB）；5/5 debug 重启 + 1/1 release 重启通过；Phase 2 字段（display / usage / network bytes / uptime）已接入服务器 API 与 Console；**24h soak 未完成**。权威状态见 [当前状态](../docs/00-overview/当前状态.md)。

| 项 | 值 |
|---|---|
| 包名 | `com.qingxuan.bridge`（`versionName 1.0.0` / `versionCode 1`） |
| 平台 | `minSdk 29` / `targetSdk 34`（编译用 platforms android-35） |
| 监听 | 仅 `127.0.0.1:3099`（loopback，TLS 自签 + Bearer token） |
| 端点 | `/v1/health`（无 token）、`/v1/version`、`/v1/status`（需 token） |
| 构建 | 无 Gradle：`build.ps1`（aapt2 + javac + d8 + zipalign + apksigner） |
| 文档 | [27 架构调研](../docs/50-bridge/27-Android-Bridge-APK架构调研.md) · [33 MVP 实施记录](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) · [32 OEM 适配](../docs/10-device/32-多厂商Android适配与迁移指南.md) · [scripts 索引](../scripts/README.md) |

## 1. 目录组成

| 路径 | 作用 |
|---|---|
| `AndroidManifest.xml` | 声明 `BootReceiver`（BOOT_COMPLETED / MY_PACKAGE_REPLACED / QUICKBOOT）、`BridgeService`（`specialUse` FGS，不导出）、`MainActivity`；固定 `debuggable=false`、`allowBackup=false` |
| `src/com/qingxuan/bridge/` | Java 源码：`BootReceiver`（开机拉起 FGS）、`BridgeService`（前台通知 + 启动 HTTPS）、`LocalHttpsServer`（TLS + 路由）、`BridgeStatus`（字段采集）、`TokenStore`（首次运行生成 token）、`MainActivity`（启动/权限提示） |
| `assets/bridge.p12` | TLS keystore（自签证书 + **静态私钥**，随 APK 打包；**gitignored**，首次构建自动生成） |
| `certs/bridge.crt` | 导出的 TLS 证书，供服务器 pin（**gitignored**，首次构建自动生成） |
| `signing.p12` | APK 签名 keystore（release 签名用；**gitignored**，首次构建自动生成） |
| `build.ps1` | 无 Gradle 构建脚本（探测 JDK/SDK、校验 ASCII 路径、生成密钥、编译打包签名） |
| `build/` | 构建产物（**gitignored**，每次构建前清空重建） |
| `README.md` | 本文件 |

## 2. 前置

- **JDK 17+**（需要 `javac` / `jar` / `keytool`）。本机已装 JDK 17（`D:\Program Files\Microsoft\jdk-17.0.20.8-hotspot`）与 JDK 21；`build.ps1` 自动探测，两者均可构建（实测 JDK 21 构建通过）。
- **Android SDK**：`platforms;android-35`（或 34）+ `build-tools;35.0.0`。本机 SDK 在 `tools/android-sdk`（**gitignored**，可重装重建）。
- **不需要 Gradle**。
- **仓库路径与 SDK 路径必须是纯 ASCII**（见 §4）。
- Windows PowerShell 5.1+（无需 PowerShell 7）。

## 3. SDK / JDK 探测顺序

`build.ps1` 启动时自动探测，按顺序取第一个可用项：

```text
SDK: $env:ANDROID_HOME → $env:ANDROID_SDK_ROOT → <repo>\tools\android-sdk → %LOCALAPPDATA%\Android\Sdk
JDK: $env:JAVA_HOME → 常见安装目录（Program Files\Microsoft、Program Files\Java、
     Android Studio、JetBrains 等）→ PATH 中的 javac
```

build-tools 取 `$SDK\build-tools` 下版本号最高者，platform 取 `$SDK\platforms` 下最新的 `android-*`；缺 `aapt2/d8/zipalign/apksigner` 会直接报错退出。

## 4. ASCII 路径要求（重要）

- **aapt2 在 Windows 上不能可靠处理非 ASCII 路径**。这是 2026-11-11 把仓库从中文名 `手机优化` 改名为 `haydn-server` 的直接原因。
- `build.ps1` 启动即校验**仓库路径**与 **SDK 路径**，发现非 ASCII 字符直接报错退出（不再做任何绕行）。
- 旧的 ASCII junction（`D:\android-sdk` → `tools/android-sdk`、`D:\bridge-src` → `android-bridge`）**已删除、不再需要**；不要重新创建 junction，也不要把仓库放回中文路径。

## 5. 构建

```powershell
# 在仓库根目录执行
powershell -NoProfile -ExecutionPolicy Bypass -File android-bridge\build.ps1
```

产物（均在 `android-bridge/build/`，gitignored）：

| 产物 | 说明 |
|---|---|
| `build/bridge.apk` | **release 签名、`debuggable=false`**，约 25KB |
| `build/bridge.crt` | 服务器 TLS pin 用的证书 |

脚本内 5 步：`aapt2 link`（manifest + assets）→ `javac` → `jar` + `d8` → 加入 `classes.dex` → `zipalign` + `apksigner sign` + `apksigner verify`。

说明：

- `build/` 每次构建前会被清空（`unsigned.apk` / `aligned.apk` / 中间 `classes/`、`dex/` 都是临时文件）。
- 首次构建会**自动生成** `assets/bridge.p12`（TLS）、`certs/bridge.crt`（证书）、`signing.p12`（APK 签名）；口令默认值可在环境变量 `BRIDGE_TLS_PASS` / `BRIDGE_SIGN_PASS` 覆盖。**这些私钥与证书不要提交到 Git、不要外传。**
- 升级 APK 时用同一签名 key（`signing.p12`）原地 `install -r`，可保留 token 与权限。

## 6. 安装与授权

```bash
# 1) 安装（release 签名，可原地替换）
adb install -r android-bridge/build/bridge.apk

# 2) 运行时权限（按实际需要；release 下 MIUI 重启后可能被重置）
adb shell pm grant com.qingxuan.bridge android.permission.POST_NOTIFICATIONS
adb shell pm grant com.qingxuan.bridge android.permission.ACCESS_FINE_LOCATION

# 3) 后台存活相关（标准 Android；MIUI 仍需人工白名单）
adb shell cmd appops set com.qingxuan.bridge RUN_ANY_IN_BACKGROUND allow
adb shell dumpsys deviceidle whitelist +com.qingxuan.bridge

# 4) Phase 2 usage 字段（可选；也可在系统设置里手动授权"使用情况访问"）
adb shell cmd appops set com.qingxuan.bridge GET_USAGE_STATS allow
```

**MIUI / HyperOS 必做（一次性）**：设置 → 应用 → 自启动管理 → 允许 Qingxuan Bridge；电池 → 无限制；允许后台弹出 / 锁定后台。
仅 appops/deviceidle **不足以**绕过后台启动拦截；实测 5/5 重启成功是在自启动白名单打开之后。其他 OEM 路径见 [32 多厂商 Android 适配与迁移指南](../docs/10-device/32-多厂商Android适配与迁移指南.md)。

安装后首次启动（或开机）应自动拉起 FGS；也可点一次 App 图标确认。

## 7. token 与证书：生产/部署

- token 在**首次启动时生成**并保存在 App 私有目录 `files/bridge.token`（32 字节随机 → 43 字符 Base64URL）。
- **debug 构建**可用 `adb shell run-as com.qingxuan.bridge cat files/bridge.token` 提取（仅调试用途）。
- **release 构建（`debuggable=false`）`run-as` 不可用**；当前做法是升级 `install -r` **保留原 token**，服务器无需改配置。**全新安装的配对 / 自动下发 token 尚未实现（Phase 2 议题）。**
- 服务器侧固定读取：
  - `/root/server/etc/bridge.token`（权限 600）
  - `/root/server/etc/bridge.crt`（权限 644）
- 部署方式：把 `android-bridge/build/bridge.crt` 与 token 文件放（或复制）到服务器 proot 内上述路径；传输通道（ADB push / SSH / Termux 内复制）按当前环境选择，注意不要落到 Git。具体流程见 [03 操作手册](../docs/20-server/03-操作手册.md)。
- 服务器端消费方：`scripts/server/bridge_client.py` → `/api/sysinfo` 合并字段（`bridge_source` / `bridge_available` / `bridge_age_s` / `bridge_version` / `bridge_last_seen` / `bridge_error` 等）；`server-ops bridge status` 提供只读状态。

## 8. 测试（在 proot 服务器内执行）

```bash
# health 不需要 token
curl -sS --cacert /root/server/etc/bridge.crt https://127.0.0.1:3099/v1/health
# 期望：{"ok":true,...}

# status 需要 Bearer token
curl -sS --cacert /root/server/etc/bridge.crt \
  -H "Authorization: Bearer $(cat /root/server/etc/bridge.token)" \
  https://127.0.0.1:3099/v1/status

# 服务器聚合结果应为 source=bridge
curl -s http://127.0.0.1:8080/api/sysinfo | grep -o '"bridge_source":"[^"]*"'
server-ops bridge status
```

预期：`/v1/health` 返回 `ok:true`；`/v1/status` 含 device / battery / wifi / memory / disk / thermal / packages（Phase 2 还有 display / usage / network / uptime，字段可空）；不带 token 访问 `/v1/status` 返回 **401**；`https://<LAN-IP>:3099` **连不上**（只绑 loopback）。

## 9. 重启与自启验证

- 已通过：**5/5 debug 重启 + 1/1 release 重启**（2026-11-11）；每次重启后 `/v1/health` 200、API `source=bridge`、服务器 12/12。
- 启动日志链路：`BridgeBoot: bridge service start requested for BOOT_COMPLETED` → `BridgeService: startForeground returned` → `bridge https server started`；FGS `isForeground=true`。
- 回退验证：`adb shell am force-stop com.qingxuan.bridge` 后，`/api/sysinfo` 变为 `source=termux`；App 重新启动后回到 `source=bridge`。
- **24h soak 未完成**（待补；见 [33 §8.4](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)）。

## 10. 已知限制（必须知道）

1. **TLS 私钥是静态的**：证书/私钥构建时生成并打进 APK assets，仅适用于本机 MVP；Phase 2 迁移到运行时生成 / 证书轮换 / mTLS。
2. **24h soak 未完成**：稳定性结论目前只到"6h21m 连续 + 重启矩阵"，不代表长期无故障。
3. **Usage 权限重启后被重置**：`GET_USAGE_STATS` 重启后回到 default，`usage_foreground` 为空（需用户或 ADB 再次授权）；属于 Phase 2 可选字段，不影响主链路。
4. **POST_NOTIFICATIONS 重启后被 MIUI 重置为 ignore**：FGS 仍在运行，但通知不可见。
5. **无 Root 的能力边界**：全局 `/proc/stat`、`/proc/net/dev` 原始字节、`dumpsys` / `settings` / 冻结 / 停用等不可得；网络字节用 `TrafficStats` 累计（`since_boot=true`），不可得字段置 `null`。
6. **release 全新安装缺配对流程**：目前依赖升级保留 token；换机/清数据后需要重新拿到 token 再部署。
7. **只绑 loopback**：不要改监听地址、不要公网暴露、不要把 APK 或私钥上传到公网。

## 11. 故障排查

| 现象 | 先查 |
|---|---|
| 构建报路径含非 ASCII | 仓库/SDK 路径必须纯 ASCII（§4）；不要把仓库放回中文目录 |
| 构建找不到 SDK/JDK | 按 §3 顺序设置 `ANDROID_HOME`/`JAVA_HOME`，或确认 `tools/android-sdk` 存在 |
| `/v1/health` 失败 | App 是否在运行（`adb shell dumpsys activity services com.qingxuan.bridge`）；是否被 MIUI 清理 |
| `/v1/status` 401 | 服务器 `bridge.token` 与 App 内 token 是否一致（可能重装过 App） |
| TLS 校验失败 | 服务器 `bridge.crt` 是否为当前 APK 对应的证书（重建 APK 后证书会变） |
| `/api/sysinfo` 为 `source=termux` | Bridge 不可用（进程被杀 / 端口未起 / 证书 token 不匹配）；见 `bridge_error` |
