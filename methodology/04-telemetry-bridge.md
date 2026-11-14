---
id: MTH-005
title: 宿主遥测桥（Track B）
type: methodology
status: current
audience: human, agent
tags: telemetry, bridge, android, fgs, data-contract, no-root
depends: MTH-001, MTH-004
updated: 2026-11-11
agent_hint: 先判定是否真的需要桥，再按数据契约与安全最低要求实现；无实测证据不得标验收通过；Android 14/15 FGS 规则以本文件约束表为准
---

# MTH-005 · 宿主遥测桥（Track B）

> **一句话**：当"宿主状态只有 App 能稳定拿到、且宿主 App 必须自动启动"时，才自建一个**普通无 Root 伴生 App**（BootReceiver + specialUse 前台服务 + 仅 loopback 的 HTTPS 只读接口），把状态交给服务器聚合；否则优先用服务器侧采集。
>
> 设备无关：本文不绑定厂商、机型、包名与端口；具体值由部署配置提供。**端口、IP、凭据、绝对路径不得写入仓库与文档。**

## 0. 前置与边界

- 适用对象：Android 宿主（普通 App 权限，无 Root、未解锁 BL、未装 priv-app）。
- 上位规范：[MTH-001 基础与边界](00-foundations.md)、[MTH-004 服务器栈](03-server-stack.md)；安全细节以 [MTH-007 安全与密钥生命周期](06-security.md)为准。
- **不承诺**任何系统级特权能力（全局 CPU、原始网络字节、`dumpsys`/`settings`、冻结/停用）；这些只能由 Shizuku/ADB/Root 维护通道提供，且**不是**运行时依赖。
- 桥不是运行时必需组件：桥缺失时服务器必须降级并明确标注来源，不得伪造数据。

## 1. 何时需要桥（决策表）

先问三个问题：

1. 需要的数据是否**只有 Android App 权限**能拿到（电池、WiFi、屏幕、前台应用、`TrafficStats` 累计等）？
2. 是否要求**无人值守自启/常驻**（重启后无需人工打开 App）？
3. 服务器侧（Termux/proot）是否已经能稳定采集同等数据？

| 方案 | 许可 | 自启/常驻 | 数据能力 | 代价/问题 | 结论 |
|---|---|---|---|---|---|
| **自建伴生桥 App**（本文件） | 自研 | ✅ BOOT_COMPLETED + FGS | App 可访问的宿主状态 | 需要构建/签名/维护；受 OEM 清理 | **需要宿主状态 + 无人值守时首选** |
| 服务器侧采集（Termux 脚本 + proot `/proc`） | 自研 | ✅ 随服务器启动链 | 服务/磁盘/内存/负载等 | 拿不到 App 专属宿主状态 | **默认起点**；不足时再上桥 |
| Termux:API | GPLv3 | ❌ 接收器不导出，后台拉不起 | 部分设备 API | 每次重启需人工/ADB 打开 | 仅作过渡/参考，不作长期依赖 |
| Shizuku（无 Root） | Apache-2.0/MIT | ❌ 非 Root 每次开机需 ADB 重启 | 特权字段 | 不能自启 | 可选维护通道，不做运行时依赖 |
| 现成开源 App（Home Assistant/WallPanel/LocalSend 等） | 多为 Apache/BSD | ✅ 部分可 | 侧重各自场景 | 耦合重、鉴权弱、集成差 | 只借鉴生命周期/本地 HTTPS 模式，不直接套用 |
| Root/priv-app/Device Owner | —— | ✅ 真系统级 | 全部 | 需解锁/重置/保修与安全代价 | **默认不做**，除非用户对具体设备明确授权 |

**判定**：只有"问题 1 是、问题 2 是、服务器侧确实拿不到"三条同时成立，才立项建桥；否则先写清"服务器侧缺口清单"，用最小采集补齐。

## 2. Android 14/15 前台服务约束（必须满足）

| # | 约束（事实） | 必须做的事 | 验收检查 |
|---|---|---|---|
| C1 | Android 14（targetSdk 34+）起，`startForeground()` 必须声明 `foregroundServiceType` 并持有对应 `FOREGROUND_SERVICE_*` 权限，否则抛异常 | manifest 声明 `foregroundServiceType="specialUse"` + `FOREGROUND_SERVICE_SPECIAL_USE`；`startForeground` 传 `FOREGROUND_SERVICE_TYPE_SPECIAL_USE` | 低版本/高版本设备各启动一次，`dumpsys activity services` 见 `isForeground=true` |
| C2 | `specialUse` 类型必须在 service 内声明子类型说明 `<property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE">` | 填写可解释的用途字符串（宿主机遥测，不含厂商/机型） | manifest 静态检查；安装后系统任务管理器可见该服务 |
| C3 | Android 15 起，**不得**从 BOOT_COMPLETED 启动 `dataSync` 类型 FGS；`dataSync` 还有累计时长限制 | **禁止用 dataSync 做常驻桥**；常驻只用 `specialUse`（或确有伴生硬件时用 `connectedDevice`） | 重启后服务仍在；`onStartCommand` 未被系统超时中断 |
| C4 | BOOT_COMPLETED / MY_PACKAGE_REPLACED 属后台启动 FGS 的**豁免**场景 | BootReceiver 只监听系统 protected broadcast；`onReceive` 内 `startForegroundService` | 5 次重启见 [MTH-008](07-validation.md) |
| C5 | Android 13+ 通知需 `POST_NOTIFICATIONS` 运行时权限；被 OEM 重置为 ignore 时 FGS 仍运行但通知不可见 | 首次启动请求通知权限；通知渠道用低优先级、常驻；App 内/服务器侧自检"通知是否可见" | 重启后系统任务管理器仍能看见 FGS（通知横幅可缺失，属预期） |
| C6 | 后台存活还受 Doze/省电策略影响 | 申请电池优化白名单；OEM 自启/省电白名单按 profile 执行，核心代码不含厂商逻辑 | 5 次重启 + 24h soak；OEM profile 见 [MTH-002](01-assessment.md) |
| C7 | 从后台/任务移除后进程可能被回收 | `START_STICKY`；`onTaskRemoved` 用 JobScheduler/AlarmManager 有界兜底（不做无界自拉） | 手动移除任务后服务可恢复；不得形成拉起循环 |
| C8 | Activity 直接自启在新系统不稳定 | 开机路径**只走 FGS**，不要用 Activity 拉起 | 重启日志中无 UI 依赖 |

**禁止**：`exported=true` 的 FGS；把桥做成 `system/priv-app`；依赖 `SYSTEM_ALERT_WINDOW` 等敏感豁免；用轮询 Activity 保活。

## 3. 组件架构与请求契约

```text
Android 宿主（普通 App）
  BootReceiver ──BOOT_COMPLETED / MY_PACKAGE_REPLACED / QUICKBOOT──> BridgeService (specialUse FGS)
      │  startForegroundService(无需 UI)
      ▼
  BridgeService ──启动/守护──> LoopbackHttpsServer（仅 loopback，GET-only）
      │                          ├─ /v1/health   无 token
      │                          ├─ /v1/version  版本/schema
      │                          └─ /v1/status   Bearer token
      ▼
  Collectors（battery/wifi/memory/disk/thermal/packages/display/usage/network/device/uptime）
      ▲
服务器（同一设备上的 Linux 容器用户态）
  bridge_client ──HTTPS + 证书固定 + token + 超时 + 缓存/熔断──> 聚合 API（含来源/新鲜度字段）
```

| 组件 | 职责 | 不得做 |
|---|---|---|
| BootReceiver | 仅接收系统广播并拉起 FGS | 不做业务逻辑、不启 Activity |
| BridgeService | 前台通知、`START_STICKY`、启动/停止 HTTPS 服务 | 不做特权操作、不绑定非 loopback |
| LoopbackHttpsServer | TLS、路由、鉴权、只读 GET、超时/关闭连接 | 无 shell/exec/任意 URL/写设置端点；无 CORS |
| Collectors | 逐个字段采集并归一为 null 语义 | 不伪造字段、不阻塞主链路（单字段失败不影响整体） |
| 配对/TokenStore | 首次本地生成随机 token、持久化到 App 私有目录 | 不把 token 写日志/通知/外部存储 |
| 服务器客户端 | 读 token/证书、校验 pin、超时、缓存、失败回退 | 不把凭据暴露给控制面 Agent |

**请求契约（v1）**：

- 仅 `GET`；其他方法返回 `405`；未知路径 `404`；未带/错 token 访问 `/v1/status` 返回 `401`。
- 响应 `Content-Type: application/json; charset=utf-8`；`Cache-Control: no-store`；`Connection: close`。
- 错误体统一 `{ok:false,error:"..."}`；**不得**回显 token、路径、栈信息。
- 单请求处理超时（秒级），并发有上限；响应体有上限（建议 ≤16KB）；限流（建议 ≤10 req/s，超限 429）。

## 4. 数据契约（bridge.status.v1）

### 4.1 信封字段

| 字段 | 类型 | 必须 | 说明 |
|---|---|---|---|
| `schema` | string | ✅ | 固定 `bridge.status.v1`；**语义变更必须升版本** |
| `ts` | string | ✅ | 采集时刻，UTC ISO8601，以 `Z` 结尾；同一快照单一时钟源 |
| `version` | string | ✅ | App 版本（与 `/v1/version` 一致） |
| `source` | string | ✅ | 固定 `android`，表示数据来自宿主桥 |
| `uptime_s` | int | ✅ | 进程/开机时长（声明口径） |
| `capabilities` | string[] | ✅ | 本 App 声明"当前构建能提供"的字段集 |
| `device/battery/wifi/memory/disk/thermal/packages/display/usage/network/cpu` | object | ✅ | 以对象存在，内部字段可全为 null |

### 4.2 null 语义（最关键）

- **null = 不可得**（无权限/无该硬件/OEM 隐藏/API 不支持/暂时读取失败），**禁止用 0、空串、`false` 冒充未知**。
- `capabilities` 与 null 的关系：**未声明** = 该构建不提供该字段（消费者不得期待）；**声明了但 null** = 本应可得、本次暂时不可得，UI 应显示"暂不可用"而非"0"。
- 时间类字段（`ts`）缺失即视为无效快照，不得用本地时间替换。
- 枚举字段（`battery.status` 等）取值固定集合；无法映射时输出 null，不输出厂商私有字符串。

### 4.3 新鲜度与来源标记

- 桥只负责"采集时快照"；**新鲜度由拉取方计算**：`age = now - last_seen`（用同源时钟；跨设备时钟偏差需容忍）。
- **默认假设（待设备验证）**：`age ≤ 30s` 视为新鲜；`30s < age ≤ 120s` 标 stale 并保留旧值；`age > 120s` 视为不可用并回退。
- 聚合层必须返回：`source`（`bridge`/`termux`/`none`）、`age_s`、`last_seen`、`version`、`error`、`capabilities`；Console/控制面只能按这些字段解释，不得自行猜测。
- 回退顺序：桥 → 服务器侧采集（标注 `termux`）→ 无数据（标注 `none`）；任何一级回退都要记录且可追溯。

### 4.4 字段清单（可得性以运行时 capabilities 为准）

| 对象 | 字段 | 单位/枚举 | 备注 |
|---|---|---|---|
| device | manufacturer/brand/model/android/sdk/build | —— | 不含序列号/账号等个人标识 |
| battery | level/status/plugged/health/temp_c/voltage_mv/current_ma | %/枚举/°C/mV/mA | current 可为近似或 null |
| wifi | ssid/bssid/ip/rssi/link_mbps/freq_mhz | ——/dBm/Mbps/MHz | `ssid` 受系统限制，**必须归一为 null**，不得输出 `<unknown ssid>` 原文 |
| memory | total_mb/available_mb/low_memory/swap_* | MB/bool | swap 常不可得 → null |
| disk | total_gb/free_gb/used_pct | GB/% | 用应用可见分区，说明口径 |
| thermal | battery_c/max_c/cpu_c/status | °C/枚举 | `cpu_c` 默认 null（无 Root 不可得） |
| packages | count | 个 | 只给数量，不给包名清单（减少隐私面） |
| display | interactive/locked/refresh_hz/brightness | bool/Hz/0-255 | 亮度只读尽力 |
| usage | foreground/available | 包名/bool | 需 Usage Access；重启后可能失效 |
| network | rx_bytes/tx_bytes/since_boot | bytes/bool | `TrafficStats` 累计，必须标注 `since_boot=true` |
| cpu | approx_pct | % | 普通 App 不可保证 → 默认 null |

## 5. 安全最低要求（细节见 MTH-007）

| 控制项 | 必须实现 | 反例（禁止） | 验证方式 |
|---|---|---|---|
| 监听面 | 仅 `loopback`；不监听非回环地址/全部网卡 | 绑局域网/公网；ADB 端口转发到外部 | 局域网另一设备访问必失败；只读端口清单 |
| TLS | TLS 1.2+，服务端持有效密钥 | 明文 HTTP、关闭校验 | 客户端无 CA/pin 时连接失败 |
| 认证 | `Authorization: Bearer <token>`；常量时间比较 | 无 token、明文口令、query 传 token | 无/错 token 均 401 |
| 配对 | 首次 token 经"维护通道一次性下发"或本地配对码；不依赖 run-as | 公开渠道回传 token；token 写日志 | 新装设备可在维护窗口内完成配对并留记录 |
| 证书固定 | 先完成 X.509 校验（信任锚=固定证书），再比对证书 SHA-256 指纹；不匹配**硬失败** | `verify=False`；只比较前缀/长度；失败后降级不校验 | pin 错误时客户端拒绝；见 [PIT-019](../pitfalls/PIT-019-fake-pinning-bridge.md) |
| 密钥存储 | 优先 Android Keystore/硬件支持；token 存 App 私有目录 | token/私钥进仓库、外部存储、日志 | 静态检查 + 备份/日志抽查 |
| 限流/上限 | 请求速率、并发、请求行/头/体大小上限 | 无限制、可被同机 App 打满 | 压测记录（可本地注入） |
| 发布态 | `debuggable=false`、`allowBackup=false`、release 签名、组件最小导出 | debug 包上生产、导出 Service/Receiver、备份含凭据 | `aapt2 dump`/安装后静态核对 |
| 端点面 | 只读 GET 白名单；无 shell/exec/设置写入 | 提供"执行命令/改设置"接口 | 路由枚举 + 代码审计 |
| 日志 | 不打印 token/证书私钥/请求头 | 调试日志含凭据 | 日志抽查与 secret scan |

## 6. 无 Root 可得/不可得矩阵

| 数据 | 无 Root 可得性 | 实现/说明 | 不可得时的处理 |
|---|---|---|---|
| 电池电量/状态/健康/温度/电压/电流 | ✅ 可得 | 系统 sticky 广播 + 电池属性 | 单字段 null + capabilities |
| WiFi IP/BSSID/RSSI/link/频率 | ✅ 大体可得 | 标准 WiFi API | SSID 归一 null |
| 内存总量/可用/低内存 | ✅ 可得 | ActivityManager.MemoryInfo | swap 字段 null |
| 磁盘总量/可用 | ✅ 可得 | 应用可见分区统计 | 注明口径 |
| 电池温度/热状态 | ✅ 大体可得 | 电池温度 + 系统热状态 | `cpu_c` 恒 null |
| 应用包数 | ✅ 可得（侧载可接受） | PackageManager 计数 | 只给数量 |
| 屏幕交互/锁屏/刷新率/亮度 | ✅ 大体可得 | PowerManager/Keyguard/Display/Settings | 亮度 null |
| 前台应用 | ⚠️ 需 Usage Access | UsageStatsManager | 授权缺失 → null + `available=false` |
| 网络累计字节 | ⚠️ 用 TrafficStats 替代 | 只能拿累计值，标注 `since_boot` | 不可用 → null |
| 全局 CPU 精确占用 | ❌ 不可得 | 普通 App 无 `/proc/stat` | `approx_pct=null`；见 [PIT-005](../pitfalls/PIT-005-no-root-proc-metrics.md) |
| 原始网络字节（`/proc/net/dev`） | ❌ 不可得 | 只能近似/累计 | 不提供；不得伪造 |
| `dumpsys`/`settings`/`appops`/冻结/停用 | ❌ 不可得 | 特权面 | 只留维护通道，不进运行时 |
| 电池 sysfs 底层参数 | ❌ 多数不可读 | 厂商限制 | 见 [PIT-011](../pitfalls/PIT-011-battery-sysfs-unreadable.md) |

**降级策略**：不可得字段一律 null；用 `capabilities` 声明可得边界；UI/控制面解释"为什么没有"；可选 Shizuku（不自启）与 ADB 维护期补数据，均可缺失。

## 7. 交付阶段与门禁

| 阶段 | 产出 | 门禁 |
|---|---|---|
| 设计 | 数据字段清单、威胁模型、pin/token 方案、失败矩阵 | 无未解释字段；安全项全部映射到控制 |
| MVP | BootReceiver + specialUse FGS + loopback HTTPS + health/version/status + 核心字段 | 安装可启动；5/5 重启；无 token 401；局域网不可达 |
| 加固 | 配对/token 轮换、证书 pin 强化、Keystore、限流/上限、release 签名、组件最小导出、usage/network 字段 | 安全清单全过；pin 反例测试通过；升级不丢 token |
| 验收 | 24h soak、故障注入、升级/回滚 | 见 [MTH-008](07-validation.md)；无实测证据不得标完成 |

## 8. 验收清单（可直接照做）

```bash
# 1) 存活（无 token）
curl --fail --cacert "$BRIDGE_CA" "$BRIDGE_URL/v1/health"
# 2) 版本
curl --fail --cacert "$BRIDGE_CA" "$BRIDGE_URL/v1/version"
# 3) 状态（凭据由部署配置注入，禁止写入文档/日志）
curl --fail --cacert "$BRIDGE_CA" -H "Authorization: Bearer $BRIDGE_TOKEN" "$BRIDGE_URL/v1/status"
# 4) 认证反例：不带 token 必须 401
# 5) 暴露面反例：从另一台设备访问该 loopback 地址必须失败
```

- [ ] `/v1/health` 200；`/v1/version` 的 schema 与 status 一致。
- [ ] 不带/错 token → 401；错误方法 → 405；未知路径 → 404；错误体不泄露内部信息。
- [ ] 非 loopback 不可达；无其他监听端口。
- [ ] 5 次重启后 FGS 存活、数据合流且 `source=bridge`（SOP 见 MTH-008）。
- [ ] 停用桥后聚合层回退并标注 `termux`；恢复后回到 `bridge`。
- [ ] 桥端与服务器端 token/cert 轮换流程演练通过（维护窗口）。
- [ ] 24h soak 达标；无崩溃循环、无假数据。

## 9. 常见失败与 fallback

| 现象 | 常见原因 | 排查顺序 | fallback |
|---|---|---|---|
| 重启后 `/v1/health` 不通 | 被 OEM 清理/自启被拦；FGS 类型错误；通知权限缺失 | 1) 系统任务管理器看服务；2) 服务启动日志；3) OEM 自启/省电白名单 | 服务器回退 `termux` 并提示人工检查；不得用 ADB 代拉 |
| `/v1/status` 401 | token 不匹配（重装/换机/轮换未同步） | 1) 是否重装过 App；2) token 时间戳/配对记录；3) 维护窗口重新配对 | 保留旧快照并标 stale；`source=termux` |
| TLS/证书校验失败 | 证书与当前 APK 不匹配；pin 未随证书更新 | 1) 比对客户端信任锚；2) 证书指纹记录；3) 是否重建过 APK | 硬失败 → 回退 `termux`；不得跳过校验 |
| 通知不可见 | OEM 重置 `POST_NOTIFICATIONS` | 1) 通知渠道状态；2) FGS 是否仍 running | 记录为已知限制；服务照常运行，不改架构 |
| `usage` 字段为空 | Usage Access 被重置 | 1) 权限状态；2) 是否重启后失效 | 字段 null + UI 解释；不阻塞主链路 |
| 端口被占用/服务起不来 | 上次进程未退出；其他组件占用 | 1) 进程/监听检查；2) 服务生命周期日志 | 服务重启；持续失败则回退 `termux` |
| 升级/重装后丢 token | 全新安装未走配对；签名不一致 | 1) 安装参数；2) 签名一致性 | 维护期重新配对；旧 APK 回滚 |

## 10. 案例实证与证据

- [docs/27 Android Bridge 架构调研](../docs/50-bridge/27-Android-Bridge-APK架构调研.md)：开源方案对比、Android 14/15 依据、无 Root 能力边界（**历史调研，结论仍有效**）。
- [docs/33 Bridge MVP 实施记录](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)：5/5 重启、release 加固、Phase 2 字段、已知限制（**历史记录**，状态以案例当前状态为准）。
- [android-bridge/README.md](../android-bridge/README.md)：构建/安装/授权/回滚的现行操作说明。
- [haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)：本方法论的实证案例；设备相关的 OEM 步骤只放在案例层。
- 踩坑闭环：[PIT-008 MIUI/HyperOS 权限重置](../pitfalls/PIT-008-miui-permission-reset.md)、[PIT-009 OEM 清理 FGS](../pitfalls/PIT-009-oem-fgs-killer.md)、[PIT-019 伪证书 pin](../pitfalls/PIT-019-fake-pinning-bridge.md)、[PIT-005 无 Root 指标](../pitfalls/PIT-005-no-root-proc-metrics.md)。
- 护栏：[guardrails 索引](../guardrails/README.md)、[GRD-007 网络最小暴露](../guardrails/GRD-007-network-least-exposure.md)。
- 工具：[toolkit 索引](../toolkit/README.md)、[健康检查脚本](../toolkit/termux/healthcheck.sh)。
- 后续路线：[MTH-002 评估与可行性](01-assessment.md)、[MTH-006 控制面](05-control-plane.md)、[MTH-007 安全](06-security.md)、[MTH-008 验收](07-validation.md)、[术语表](09-glossary.md)。

> 契约变更（端点、字段语义、schema 版本）必须同步：服务器客户端 + 聚合 API + 控制面解释 + 验收用例 + 案例记录 + [CHANGELOG](../CHANGELOG.md)。传播规则见 [MTH-017](17-expansion-and-cli-contract.md) §2。
