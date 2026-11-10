# 27 · Android Bridge APK 架构调研与实施建议

> 日期：2026-11-10
> 目标：调研成熟开源项目，判断能否用一个 **Android Bridge APK** 替代当前“Termux 采集器 + Termux:API + 手工打开/ADB”的链路，实现 **无 Root 伴生自启、持久、安全可靠**；
> 范围：只做架构调研与实施建议，不接外部云服务。

---

## 1. 结论（Executive Summary）

**可以做得比现在更好，最优解是自建一个轻量 Android Bridge APK，而不是继续依赖 Termux:API。**

理由：
1. Termux:API 的 `TermuxApiReceiver` 是 `android:exported="false"`，且 `KeepAliveService` 也不导出；Termux 侧无法在后台把它拉起来。实测只有用 ADB 启动过 App 后，`termux-battery-status` 才能工作；这就是“重启后需手动打开一次”的根因。[Termux:API manifest]
2. Shizuku 官方明确：**非 root 设备每次开机都需要用 ADB 手动重启 Shizuku**；其 issue #248 “auto boot without root” 仍 open。[Shizuku API README][Shizuku #248]
3. Android 14/15 对“后台启动”和“前台服务类型”有明确规则，但 **BOOT_COMPLETED + Foreground Service** 是成熟可行的自启路径；Home Assistant Android 和 WallPanel 都是这么做的。[HA manifest][WallPanel BootUpReceiver][Android FGS]
4. 因此：**不依赖 PC ADB 的运行时自启，只能由我们自己的 APK 实现**；Termux:API 不适合作为长期伴生组件。

**推荐架构**：
```text
proot Ubuntu Server (Console/DSH/ops/存储/聚合)
        │  仅本机 loopback，HTTPS + token/mTLS
        ▼
Android Bridge APK（同机、普通 App、无 root）
  ├─ BootReceiver + Foreground Service（specialUse）
  ├─ 本地 HTTPS API：battery/wifi/network/display/usage/packages/thermal/build...
  ├─ 可选：Shizuku API（仅当 Shizuku 运行时，补特权字段）
  └─ 安全：Keystore、证书 pin、token、只读、限流
```

**边界承诺**：
- Bridge 可覆盖 **全部 App 可访问的实用状态**；
- **不能覆盖**：全局 `/proc/stat` 精确 CPU、`/proc/net/dev` 原始字节、`dumpsys`/`settings`/`appops`/冻结/停用等特权操作；这些只能靠 Shizuku/ADB/Root；
- “伴生系统自启”= BootReceiver + FGS + MIUI/电池白名单，**不是 system/priv-app**（本机 BL 锁、无 Root，装不了系统应用）。

---

## 1.5 服务器构建/运行是否包含在本方案内？

**结论：包含，但分成两条轨道，且不会把服务器塞进 APK 里。**

| 轨道 | 内容 | 构建 | 运行 |
|---|---|---|---|
| **A. 服务器栈** | Termux + proot Ubuntu + supervisord + nginx + DSH + Console + 备份/ops | 按 [docs/17](17-研究平台环境构建手册.md) Phase 0–6；脚本在 `scripts/server/` | Termux:Boot → `00-server.sh` → `ubuntu.sh` → `server-up` + `server-watch`；12 个服务常驻 |
| **B. Bridge APK** | Android 宿主侧采集/本地 HTTPS（本文方案） | 新建 `android-bridge/` Gradle 工程，产出 APK | BootReceiver + `specialUse` 前台服务常驻 |
| **C. 集成层** | `bridge_client.py` + Console 字段 + token/证书 pin | 随服务器代码部署 | 服务器轮询 Bridge；失败回退 Termux 采集器 |

**为什么不是把服务器打进 APK：**
- 那等于重做一个 Termux（Termux 运行时 + rootfs + 包管理 + 终端），工程量远大于 Bridge；
- 当前服务器已在 proot Ubuntu 内稳定运行，APK 只做“宿主桥”更轻、更安全；
- APK 若内嵌 Linux 用户空间，升级/备份/DSH 全部要重做，不符合“最小变更”。

**当前服务器基线（已实测）**：12/12 服务 RUNNING；ADB 32s、8080 45s、完整服务+DSH 111s；备份含 server+sessions；这些继续沿用，不在 Bridge 工程里重做。

**全栈部署顺序（重装/新机）**：
1. Android 宿主准备：ADB、Termux、Termux:Boot、权限/白名单；
2. 服务器构建：按 docs/17 装 proot Ubuntu、Node24、DSH、nginx、supervisor 服务、备份；
3. 服务器验收：12/12、DSH `/app-login`、Console、重启自启；
4. 安装/配置 Bridge APK：BootReceiver + FGS + token/证书 + ADB 白名单；
5. 部署 `bridge_client.py`，Console 切换数据源（Bridge 优先 / Termux 回退）；
6. 全栈验收：5 次重启、24h soak、Bridge 断开回退、DSH/服务可用。

> 因此：**“服务器构建运行”是本方案 Track A，已经包含在总体交付里；docs/27 只详细展开新增的 Track B（Bridge APK），不是遗漏。** 若目标是从零重装整机，按上面 1–6 执行；若服务器已在运行，只需做 3–6 的增量。
## 2. 当前实现路径回顾

| 数据 | 当前来源 | 问题 |
|---|---|---|
| 内存/磁盘/温度/服务 | proot `/proc`、`/sys`、supervisor | 原生，已内嵌 |
| uptime/load/top/getprop/package/热区 | Termux App 采集器写 `termux-status.txt` | 依赖 Termux 进程，文件轮询 |
| 电池/WiFi | Termux:API App（`termux-battery-status`/`wifi-connectioninfo`） | **App 不自动启动**；Termux 无法从后台拉起 |
| 特权控制（freeze/appops/settings/dumpsys） | PC ADB / Shizuku | 每次开机需 ADB；无 Root 不自包含 |
| 公网 | frp | 外部中继；可 LAN-only |

现有链路的问题不是“数据不准”，而是**宿主 App 的生命周期不可控**。

---

## 3. 开源项目调研

> 调研方法：GitHub API 拉取仓库 manifest/README/license（本环境 Web 搜索 API 不可用）；Android 官方文档经 `developer.android.google.cn` 镜像核实。

### 3.1 对比矩阵

| 项目 | 许可 | 自启/常驻 | 本地 API | 特权能力 | 对本项目的价值/问题 |
|---|---|---|---|---|---|
| **Termux:API** | GPLv3 | ❌ 无 boot receiver（有 `RECEIVE_BOOT_COMPLETED` 权限但 receiver `exported=false`） | 命令桥（am/socket） | ❌ | 设备 API 清单可参考；**不适合作为可自启 Bridge**；GPL 不宜直接抄 |
| **Termux:Boot** | GPL | ✅ 启动 Termux 脚本 | 无 | ❌ | 启动 proot 服务器用；不能启动其他 App |
| **Shizuku** | Apache-2.0（API MIT） | ❌ 非 root 每次开机 ADB 重启 | Binder API | ✅ shell/root 身份 | 可补特权字段；**不能做无 PC 自启** |
| **AppManager** | GPL | ❌ 依赖 ADB/Shizuku | ADB/Shizuku | ✅ | 特权操作参考；不适合做轻量 telemetry agent |
| **Home Assistant Android** | Apache-2.0 | ✅ BootReceiver + SensorWorker/FGS | 主要连 HA（非本地 bridge） | ❌ | **生命周期/传感器模式最佳参考** |
| **WallPanel** | Apache-2.0 | ✅ BootUpReceiver + service | HTTP/MQTT 控制+本地 Web | ❌ | 本地 HTTP server 模式参考；其 BootReceiver 直接 startActivity，Android 10+ 易被后台限制，我们应改成 FGS |
| **LocalSend** | Apache-2.0 | 传输期服务 | REST + **HTTPS** | ❌ | **本地 HTTPS/REST 安全模型参考** |
| **KDE Connect** | GPLv2/3 | ✅ 后台服务 | TLS + 配对/插件 | ❌ | **TLS 证书配对安全模型参考**；GPL 只借鉴思路 |
| **NanoHTTPD** | Modified BSD | 库 | 嵌入式 HTTP server | ❌ | 最小依赖的 HTTP server 候选（BSD 友好） |
| **AndServer** | Apache-2.0（需复核） | 库 | 注解式 HTTP/反向代理 | ❌ | 功能更多，依赖更重；可选 |

### 3.2 关键证据

- Termux:API manifest：`<receiver android:name=".TermuxApiReceiver" android:exported="false" />`；`KeepAliveService` 也 `exported=false`；没有 `BOOT_COMPLETED` intent-filter。[manifest]
- Shizuku API README 原文：*“On non-rooted devices, Shizuku needs to be manually restarted with adb every time on boot.”* [Shizuku API]
- Shizuku issue #248 “Feature request: auto boot without root” 仍 open；#1254 讨论 start-on-boot 标签。[Shizuku #248]
- HA Android manifest 明确注释：`<!-- Start things like SensorWorker on device boot -->`，`WebsocketBroadcastReceiver` 与 `SensorReceiver` 都监听 `BOOT_COMPLETED`。[HA manifest]
- WallPanel `BootUpReceiver.kt` 在 BOOT_COMPLETED 后 `startActivity(BrowserActivityNative)`；这展示了“自启”可行，但 Activity 启动在新系统上不如 FGS 稳。[WallPanel BootUpReceiver]
- LocalSend README：REST API + HTTPS 加密，无云。[LocalSend]
- KDE Connect README：Wi-Fi 局域网 + TLS 加密。[KDE Connect]
- NanoHTTPD README：可嵌入 Java 应用的轻量 HTTP server（BSD）。[NanoHTTPD]

---

## 4. Android 14/15 关键事实（官方文档核实）

1. **Android 14 起必须声明前台服务类型**，并申请对应 `FOREGROUND_SERVICE_*` 权限；否则 `startForeground()` 抛异常。[Android FGS types]
2. 可用类型包含：`camera / connectedDevice / dataSync / health / location / mediaPlayback / mediaProjection / microphone / phoneCall / remoteMessaging / shortService / specialUse / systemExempted`。
3. **Android 15 目标平台：不得从 BOOT_COMPLETED receiver 启动 `dataSync` 类型 FGS**；因此**不要用 dataSync 做常驻 Bridge**。选择 **`specialUse`**（需在 `<service>` 内声明 `<property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE" ...>`），或 `connectedDevice`（若定位为伴生设备）。[FGS service types]
4. **从后台启动 FGS 的豁免**包括：用户交互、精确闹钟、高优先级 FCM、**BOOT_COMPLETED / LOCKED_BOOT_COMPLETED / MY_PACKAGE_REPLACED**、设备管理、`SYSTEM_ALERT_WINDOW` 等；但 Android 14+ 对 `BOOT_COMPLETED` 启动某些 FGS 类型有限制。[FGS bg-start]
5. 电池温度：`Intent.ACTION_BATTERY_CHANGED` 的 `EXTRA_TEMPERATURE`（整数，0.1°C）；电压 `EXTRA_VOLTAGE`。[BatteryManager]
6. `UsageStatsManager` 多数方法需要 `PACKAGE_USAGE_STATS`，且用户必须在 Settings 中授权；仅查询自身包名不需要。[UsageStatsManager]
7. `NetworkStatsManager` 同样受使用情况访问权限约束；用它替代 `/proc/net/dev` 的原始字节统计。[NetworkStatsManager]
8. WiFi SSID：现代 Android 对普通 App 返回 `<unknown ssid>` 很常见，需要定位权限/系统限制，**不能保证**；可保证 IP/BSSID/RSSI/link speed（仍受厂商限制）。[WifiManager]

---

## 5. 推荐架构（详细）

### 5.1 组件与职责

```text
┌──────────────────────────────┐
│ Android Bridge APK           │
│  BootReceiver                │  BOOT_COMPLETED / MY_PACKAGE_REPLACED
│  BridgeService (FGS)         │  specialUse; START_STICKY; 低优先级通知
│  LocalHttpsServer (loopback) │  127.0.0.1:3099; TLS; only GET
│  Collectors                  │  Battery/Wifi/Network/Display/Usage/Packages/Thermal/Build
│  Auth/Pairing                │  Keystore token / cert pin / 限流
│  Optional Shizuku client     │  仅当 Shizuku 运行；补特权字段，不自启
└───────────────┬──────────────┘
                │ loopback HTTPS + token
┌───────────────▼──────────────┐
│ proot Ubuntu Server          │
│  bridge_client.py            │  2s timeout / 熔断 / 缓存
│  /api/sysinfo 合并字段       │  bridge 优先，Termux 回退
│  Console/DSH/ops/备份        │  单一数据聚合方
└──────────────────────────────┘
```

### 5.2 数据映射（Bridge 能提供的“全部实用状态”）

| 字段 | Android API | 权限/说明 |
|---|---|---|
| 机型/Android/build | `Build`, `PackageManager` | 无 |
| 电池电量/状态/健康/温度/电压/电流 | `BatteryManager` sticky `ACTION_BATTERY_CHANGED` + `EXTRA_*` | 无 |
| 充电状态 | `BatteryManager.isCharging()` / plugged | 无 |
| WiFi IP/BSSID/RSSI/link/frequency | `WifiManager.getConnectionInfo` / `ConnectivityManager` | `ACCESS_WIFI_STATE`、`ACCESS_FINE_LOCATION`（SSID best effort） |
| 网络用量 | `NetworkStatsManager`（推荐）/ `TrafficStats` | `PACKAGE_USAGE_STATS` + 用户授权 |
| 前台/使用统计 | `UsageStatsManager.queryEvents` | `PACKAGE_USAGE_STATS` + 用户 Settings 授权 |
| 屏幕状态/亮度/刷新率 | `PowerManager.isInteractive`、`KeyguardManager`、`DisplayManager`、`Settings.System` | 写亮度需 `WRITE_SETTINGS`（只读可尽力） |
| 内存 | `ActivityManager.MemoryInfo` | 无 |
| 磁盘 | `StatFs` | 无 |
| 热区/温度 | 电池温度、`PowerManager` 热状态、sysfs 尽力 | 无/部分厂商限制 |
| 应用包数 | `PackageManager.getInstalledPackages` | `QUERY_ALL_PACKAGES`（侧载可接受） |
| 全局 CPU | ❌ 普通 App 无 `/proc/stat`；可尝试 `/system/bin/top` 解析（近似） | 精确值需 Shizuku/root |
| 网络原始字节 | ❌ `/proc/net/dev`；用 `NetworkStatsManager` 替代 | 需用户授权 |
| 冻结/停用/settings/dumpsys | ❌ | 仅 Shizuku/ADB |

### 5.3 自启与常驻设计

- **BootReceiver**：
  - 监听 `BOOT_COMPLETED`、`LOCKED_BOOT_COMPLETED`（可选）、`MY_PACKAGE_REPLACED`、`QUICKBOOT_POWERON`（厂商）。
  - `onReceive` 中 `ContextCompat.startForegroundService(...)`；Android 12+ 注意后台启动限制，BOOT_COMPLETED 属豁免。
- **BridgeService**：
  - `startForeground(notificationId, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)`；
  - manifest：`android:foregroundServiceType="specialUse"` + `<property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE" android:value="device monitoring bridge"/>`；
  - `onStartCommand` return `START_STICKY`；
  - `onTaskRemoved` 用 `AlarmManager`/`JobScheduler` 触发复活（Doze 用 `setAndAllowWhileIdle`；避免精确闹钟权限依赖）。
- **Watchdog**：
  - 服务内部 30s 心跳；
  - Supervisor/Console 侧监控 bridge 200；连续失败告警；
  - `JobScheduler` 15 min 兜底；不依赖 `dataSync`。
- **ADB 一次性优化（Provisining）**：
  ```bash
  adb install -r bridge.apk
  adb shell pm grant <pkg> android.permission.POST_NOTIFICATIONS
  adb shell pm grant <pkg> android.permission.ACCESS_FINE_LOCATION
  adb shell cmd appops set <pkg> GET_USAGE_STATS allow
  adb shell cmd appops set <pkg> RUN_ANY_IN_BACKGROUND allow
  adb shell dumpsys deviceidle whitelist +<pkg>
  # MIUI/HyperOS 还需人工开启：自启动、无限制省电、允许后台弹出
  ```
  - 之后重启不再需要 PC；Bridge 由 BootReceiver 自启。
- **MIUI 专项**：
  - 自启动白名单、电池“无限制”、后台弹出界面、锁定后台；
  - 若被清理，`BOOT_COMPLETED`/FGS 仍应恢复；用 5 次重启验收。

### 5.4 安全设计（安全可靠）

- **只绑 loopback** `127.0.0.1`，不开 0.0.0.0；不提供公网监听。
- **TLS**：自签 CA + 服务端 pin 指纹；优先 **mTLS**（Bridge 只接受持有客户端证书的 server），至少 **token + pin**。
- **配对**：
  - 首次启动 Bridge Pairing Activity 显示 8 位配对码/二维码；server 输入后换 token；
  - 或 ADB provisioning 时传入一次性 token；token 存 **EncryptedSharedPreferences/Keystore**。
- **认证**：
  - `Authorization: Bearer <token>`；常量时间比较；
  - 限流（如 10 req/s）、body 上限 16KB、只允许 GET 白名单；
  - **不提供 shell/exec/任意 URL** endpoint。
- **组件暴露**：
  - 只导出 BootReceiver（系统 protected broadcast）+ 配对 Activity（可设 `android:exported=true` 但仅由本机 UI/ADB 调用）；
  - BridgeService/HTTP server 不导出；`debuggable=false`；`allowBackup=false`。
- **网络**：
  - `networkSecurityConfig` 禁止明文；证书 pin；HTTP 只在本机 loopback 使用 TLS。
  - 日志不打印 token；异常不泄露。
- **升级/回滚**：
  - 手动 ADB 安装/签名；Bridge 提供 `/v1/version`；server 记录版本；
  - 失败回退到旧 APK/旧 Termux 采集器。
- **审计**：server 记录 bridge 来源/版本/最后成功时间；异常面板。

### 5.5 服务端集成

- 新增 `scripts/server/bridge_client.py`：
  - 读取 `/root/server/etc/bridge.token`、`/root/server/etc/bridge.cert.sha256`；
  - `urllib`/`http.client` 请求 `https://127.0.0.1:3099/v1/status`；
  - 2s 超时、失败熔断 30s、成功缓存；
  - 合并到 `/api/sysinfo`：`bridge_source`、`bridge_version`；字段优先 bridge，失败回退 Termux 文件。
- Console 显示数据来源（Bridge/回退/Termux API 缺失），Battery/WiFi 缺失时提示“打开一次 Termux:API”改为“等待 Bridge 或检查自启”。
- 保留 Termux 采集器作为**只读回退**，Bridge 稳定后可移除其对 battery/wifi 的依赖。

---

## 6. 实施计划（分阶段）

### Phase 0：准备（0.5 天）
- 安装 Android SDK cmdline-tools + platform 34/35 + build-tools；`gradle wrapper`。
- 确认 JDK 17/21（本机已有 JDK 17/21，**无 Gradle/SDK**，需下载）。
- 创建 `android-bridge/` Gradle 工程；签名 keystore；包名 `com.qingxuan.bridge`（避免 Shizuku 保留名）。

### Phase 1：MVP（2–3 天）
- BootReceiver + BridgeService（specialUse FGS + 通知 + START_STICKY）。
- 本地 HTTP（NanoHTTPD/自写）绑 127.0.0.1；`/v1/health`、`/v1/status`。
- Collectors：Build、Battery、Wifi、Memory、Disk、Thermal、Packages。
- token 认证 + TLS 自签 + pin + 限流。
- Server `bridge_client.py` 合并字段；Console 显示。
- 5 次重启 + 强制停止测试。

### Phase 2：完整状态（2–4 天）
- UsageStats（前台/使用）、NetworkStats（用量）、Display/Keyguard、Package count。
- mTLS/配对流程完善；后台存活看门狗；MIUI 白名单指导。
- 安全性：请求日志脱敏、版本接口、回滚文档。
- 与 Termux collector 并行 2 天对比，确认字段一致。

### Phase 3：可选特权（按需）
- **Shizuku API**（MIT）接入：仅当 Shizuku 运行，补全局 CPU/网络/冻结等；**不承诺自启**，失败自动降级。
- 不引入 Root；不修改系统分区。

### Phase 4：验收（2–3 天）
- 5 次重启、24h soak、Doze、低电、WiFi 切换、锁屏、服务端重启、APK 升级/回滚；
- 验收指标：
  - 重启后 ≤30s Bridge 可用（不计系统启动）；
  - 24h 可用率 ≥99%，服务端无假数据；
  - 内存占用 <30MB，CPU 空闲影响 <1%；
  - 除 loopback 外无监听端口；无未授权 endpoint。

---

## 7. 风险与替代方案

### 7.1 风险
- **MIUI/HyperOS 后台清理**：BootReceiver/FGS 仍可能被杀；需自启动+电池白名单+服务端告警；无法 100% 保证。
- **Android 14/15 FGS 规则**：必须 specialUse/正确类型；dataSync 不能从 BOOT 启动且 Android 15 有 6h 限制。
- **构建/签名**：需要 Android SDK/Gradle；debug/release key；侧载无自动更新。
- **权限授予**：Usage/位置/通知需 ADB 或用户交互；MIUI Autostart 无标准 API。
- **安全暴露**：loopback 对同机其他 App 可见；必须 TLS/token/pin，不能裸 HTTP。
- **“全部功能”不可达**：全局 CPU/网络原始字节/系统级控制仍受沙箱；只有 Root/Shizuku（且 Shizuku 不自启）。
- **许可证**：不要复制 GPL 的 Termux:API/WallPanel/KDE 代码；使用 Apache/BSD 项目作为参考/库。

### 7.2 替代/更优解排序
1. **自建 Bridge APK（推荐）**：无 root、可自启、本地 HTTPS、安全可控、可长期维护；工作量中等。
2. **Bridge + 可选 Shizuku**：补特权，但 Shizuku 不自启；适合维护期，不适合作为运行时依赖。
3. **当前 Termux:API + 手动打开**：成本最低，但重启后人工；不满足“伴生自启”。
4. **Device Owner / priv-app / Root**：可真正系统级常驻，但需重置设备/解锁 BL/刷机；本机 BL 锁定，不现实。
5. **Fork Termux:API / WallPanel**：不推荐；GPL、Activity 自启、默认弱鉴权、与现有 server 集成差。

---

## 8. 参考资料

**Android 官方文档（CN 镜像可访问）**
- FGS 类型（Android 14）：https://developer.android.google.cn/about/versions/14/changes/fgs-types-required
- FGS 后台启动限制：https://developer.android.google.cn/develop/background-work/services/fgs/restrictions-bg-start
- FGS 服务类型（specialUse/dataSync/BOOT 限制）：https://developer.android.google.cn/develop/background-work/services/fgs/service-types
- BatteryManager：https://developer.android.google.cn/reference/android/os/BatteryManager
- UsageStatsManager：https://developer.android.google.cn/reference/android/app/usage/UsageStatsManager
- NetworkStatsManager：https://developer.android.google.cn/reference/android/app/usage/NetworkStatsManager
- WifiManager：https://developer.android.google.cn/reference/android/net/wifi/WifiManager
- Android 15 行为变更：https://developer.android.google.cn/about/versions/15/behavior-changes-15

**开源项目**
- Termux:API：https://github.com/termux/termux-api
- Termux:API manifest：https://github.com/termux/termux-api/blob/master/app/src/main/AndroidManifest.xml
- Termux:API license（GPLv3）：https://github.com/termux/termux-api#license
- Shizuku API：https://github.com/RikkaApps/Shizuku-API
- Shizuku issue #248（auto boot without root，open）：https://github.com/RikkaApps/Shizuku/issues/248
- Home Assistant Android manifest：https://github.com/home-assistant/android/blob/master/app/src/main/AndroidManifest.xml
- WallPanel：https://github.com/TheTimeWalker/wallpanel-android
- WallPanel BootUpReceiver：https://github.com/TheTimeWalker/wallpanel-android/blob/master/WallPanelApp/src/main/java/xyz/wallpanel/app/BootUpReceiver.kt
- LocalSend：https://github.com/localsend/localsend
- KDE Connect Android：https://github.com/KDE/kdeconnect-android
- NanoHTTPD：https://github.com/NanoHttpd/nanohttpd
- AndServer：https://github.com/yanzhenjie/AndServer
- AppManager：https://github.com/MuntashirAkon/AppManager

---

## 9. 下一步

- 若认可该架构：进入 Phase 0/1，先做 **MVP Bridge APK**（电池/WiFi/Build/内存/磁盘/热区 + Boot/FGS + 本地 HTTPS + token），替换当前 Termux:API 依赖；
- 同时保留 Termux 采集器为回退；
- 完成后按 §6 Phase 4 做 5 次重启与 24h 稳定性验收；
- 特权数据（全局 CPU/网络原始字节/冻结）继续留给 Shizuku/ADB 维护通道，不承诺常驻。

---

## 10. 与 DSH 的深度集成策略（补充）

**结论：要深度集成，但只集成在“控制/观测面”，不要做进程/运行依赖。**

DSH 是服务器的大脑/控制面（自然语言运维、诊断、server-ops 执行）；Bridge 是 Android 宿主感知面。正确关系是：

```text
Bridge APK ──HTTPS/token──> Server bridge_client ──> /api/sysinfo /api/ops
                                                        ▲
                                                        │ 只读/受控
                                                       DSH（经 server API / server-ops）
```

### 10.1 三层集成

| 层 | 做法 | 边界 |
|---|---|---|
| **数据面** | Bridge → server `bridge_client.py` → `/api/sysinfo`、Console；DSH 只读 server API | **DSH 不直接持有 Bridge token**，不直接连 Bridge |
| **控制面** | DSH 使用 `server-ops` Tier1/Tier2：查状态、健康、日志、备份、重启服务、nginx、备份 | Bridge 生命周期不能由 DSH 控制（proot 无 ADB，无法启动 Android App）；不要设计这种能力 |
| **策略面** | `/root/AGENTS.md` 规定：先 `server-ops status/health`，Tier2 需人工确认，Tier3 禁止；操作写 ops-audit | DSH 有审计、有确认；Bridge 不暴露 shell |

### 10.2 建议新增的集成动作

1. **`server-ops bridge status`**（只读）：
   - 显示 Bridge 来源（APK/回退 Termux）、版本、最后成功时间、缺失字段；
   - DSH 可直接用它判断“手机状态是否完整”。
2. **`/api/sysinfo` 增加 `bridge_source` / `bridge_age_s` / `bridge_version`**：
   - DSH 用自然语言问“手机现在状态”时，一次读 server API 即可回答；
   - Console 显示“数据来源：Bridge/回退”，避免假数据。
3. **DSH 技能/AGENTS 约定**：
   - `手机状态` → `server-ops status` + `curl /api/sysinfo`（只读）；
   - `手机为什么卡` → `/api/sysinfo` + `server-ops health` + 服务日志；
   - `重启某项` → `server-ops restart <svc> --confirm`，必须先说明并人工确认；
   - Bridge 缺失时提示用户检查 Bridge 自启，而不是尝试用 ADB 拉起。
4. **控制台展示**：Bridge 数据卡 + DSH/ops 审计卡并列；DSH 可以直接链接/引用。
5. **告警**（可选后续）：
   - Bridge 连续不可达 → Console 红色提示 + DSH 对话中解释；
   - 真正的推送告警仍属于外部服务（按用户要求暂不接）。

### 10.3 为什么不做“进程级深度集成”

- **DSH 是约 300–400MB 的 Node 进程**；Bridge 是 <30MB 的小 App。Bridge 不应依赖 DSH 启动/存活，否则 DSH 故障会拖垮遥测；
- **DSH 无法启动 Android App**（proot 无 ADB/Shizuku 自启），所谓“DSH 控制 Bridge 生命周期”在无 Root 下不可实现；
- **安全边界**：Bridge token/证书只在 server 内使用；DSH 作为公开入口（`/app-login`）不应持有宿主采集凭据；
- **故障隔离**：DSH 挂掉时，服务器、Bridge、Console 数据仍应正常；DSH 恢复后自动继续读数据。

### 10.4 推荐落地顺序

1. **Bridge MVP**（Phase 1）先把数据接进 server `/api/sysinfo`；
2. **C1**：`bridge_client.py` + `server-ops bridge status` 只读 + Console 数据来源；
3. **C2**：DSH 技能/AGENTS 文案与动作约束（不新增特权接口）；
4. **C3**：异常提示/告警规则（Console/DSH 对话层，不接外部推送）；
5. **不做**：把 DSH 嵌入 APK、让 Bridge 依赖 DSH、让 DSH 直接控制 Bridge、把 Bridge token 暴露给 DSH。

> 一句话：**“深度集成 DSH”= 深度接口与治理，不是深度进程耦合。** DSH 是运维入口和解释层；Bridge 是稳定感知层；server 是唯一数据聚合与安全边界。
