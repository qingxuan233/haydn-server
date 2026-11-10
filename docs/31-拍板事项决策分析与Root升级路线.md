# 31 · 拍板事项决策分析与 Root 升级路线

> 用途：给用户拍板前的一页式决策参考；不替代 [docs/28 全栈规范](28-全栈整体方案规范.md)。
> 目标：解释每个开放项的好处/代价/限制，并说明“将来换有 Root 手机”时哪些能优化、现在需要预留什么。
> 所有推荐都是**默认建议**，最终由用户决定。

> **决策状态（2026-11-11）：用户已批准 D1–D10 按推荐执行，进入 Phase 0/1。**

---

## 1. 拍板事项总览

| ID | 事项 | 选项 | 推荐 |
|---|---|---|---|
| D1 | Bridge MVP 是否含 UsageStats/NetworkStats | 含 / 不含 | **不含，Phase 2** |
| D2 | 传输安全 | TLS+token+pin / 直接 mTLS | **TLS+token+pin；mTLS Phase 2** |
| D3 | 是否安装 Android SDK/Gradle | 允许 / 不允许 | **允许（一次性构建环境）** |
| D4 | Bridge 包名 | `com.qingxuan.bridge` / `io.qingxuan.bridge` | **`com.qingxuan.bridge`（厂商无关）** |
| D5 | 是否现在接 Shizuku 特权 | 现在 / 延后 | **延后；Root 手机后做** |
| D6 | DSH 集成深度 | 最小 AGENTS / 正式技能 | **先最小；Bridge 稳定后再技能** |
| D7 | 公网入口 | 保留 frp / 仅局域网 | **保留现有 frp，不新增端口** |
| D8 | OEM 自启/省电白名单 | 标准核心+OEM profile / 尝试厂商自动化 | **标准核心+OEM profile，5 次重启验证** |
| D9 | Bridge APK 资产 | 仅 checksum / 纳入备份 | **仅版本+checksum** |
| D10 | 数据频率 | 10s / 更实时 | **10s，可配置** |

---

## 2. 逐项分析

### D1 · MVP 是否包含 UsageStats / NetworkStats

**选项 A：不含（推荐）**
- 优点：MVP 更快、权限更少、无隐私敏感数据、厂商差异少、稳定；
- 缺点：Console 暂时看不到前台应用、应用使用时长、网络用量；状态不“全”；
- 限制：`UsageStatsManager` 需 `PACKAGE_USAGE_STATS`，用户还要在 Settings 里授权；`NetworkStatsManager` 同样受使用情况访问权限约束；OEM 行为差异大；
- Root 影响：将来 Root 后可直接用 `dumpsys`/root shell 读取，**现在不做不会造成返工**。

**选项 B：MVP 就做**
- 优点：Console 字段更完整，更接近“全部状态”；
- 缺点：权限弹窗/授权流程、测试矩阵变大、隐私暴露、可能遇到 MIUI 限制；首版进度变慢；
- 推荐：不做。Phase 2 通过 feature flag 增加，默认关闭，用户显式授权后开启。

### D2 · mTLS 是否进 v1.0

**选项 A：TLS + token + 证书 pin（推荐 MVP）**
- 优点：实现简单、配对流程短、可快速验证；loopback + TLS + token + pin 已能防同机普通 App 伪造/窃听；
- 缺点：token 若被读取可伪造请求；服务端需保管 token；轮换需维护窗口；
- 限制：Android Keystore/EncryptedSharedPreferences 保护 token；`debuggable=false`；token 不进日志/DSH；
- Root 影响：Root 后攻击面更大，mTLS 更有价值；但可 Phase 2 升级，不影响 MVP。

**选项 B：v1.0 直接 mTLS**
- 优点：双向身份，服务端不需要 bearer token；更强；
- 缺点：证书生成/导入 Android Keystore、配对/轮换/故障恢复复杂；开发+调试时间增加；证书失效会直接断链；
- 推荐：v1.0 不做，Phase 2 将 server 设计为**可选要求客户端证书**；先 token+pin，后 mTLS。

### D3 · 是否安装 Android SDK/Gradle

**选项 A：允许安装（推荐）**
- 优点：可本地出 APK、可重复构建、可签名；JDK 17/21 已就绪；
- 缺点：下载/磁盘约数 GB；需处理 SDK license/checksum；Gradle 依赖网络；
- 限制：只装 cmdline-tools + platform 34/35 + build-tools 即可，不必装完整 Android Studio；
- 替代：换一台有 SDK 的 PC/云端构建（仍是一次性，不改变运行时）。

**选项 B：不安装**
- 结果：无法进行 Phase 0/1，Bridge 计划停摆；只能继续 Termux:API 人工方案。

### D4 · Bridge 包名

**选项 A：`com.qingxuan.bridge`（推荐）**
- 优点：厂商无关、项目语义清晰、唯一；不占用 Shizuku/Termux 保留包名；不占用 Shizuku/Termux 保留包名；侧载无域名要求；
- 缺点：一旦安装/签名后基本不可改（改包名=新应用，token/权限需迁移）；名字较长；
- 限制：不能使用 `moe.shizuku.privileged.api`、`com.termux*` 或冒充官方；release 签名一旦确定需长期保管。

**选项 B：`io.qingxuan.bridge`**
- 优点：域名风格、简短；
- 缺点：与现有 `com` 风格不一致，个人项目无域名强绑定；
- 推荐：A。

### D5 · 现在是否接 Shizuku 特权

**选项 A：延后（推荐）**
- 优点：不引入额外维护；Bridge MVP 不依赖 Shizuku；无“每次开机 ADB 重启 Shizuku”的运维负担；
- 缺点：全局 CPU/网络原始字节、dumpsys/settings/appops/冻结等仍不可得；
- 限制：非 Root 的 Shizuku 每次开机需 ADB 手动重启；不能作为常驻自启依赖；
- Root 影响：将来 Root 手机的 **Sui（Magisk 模块）** 可让 Shizuku API 自启；或改 root helper，不必现在接。

**选项 B：现在接**
- 优点：可提前验证特权 API；
- 缺点：需要 ADB/Shizuku 维护、Bridge 增加失败分支；首版复杂度提升；
- 推荐：不进 MVP；Phase 3 作为可选 provider。

### D6 · DSH 集成深度

**选项 A：最小 AGENTS + shell 命令（推荐）**
- 优点：零新增接口；DSH 读 server API/`server-ops`；风险低；马上可用；
- 缺点：自然语言引导较弱，agent 可能不知道查哪个命令；
- 限制：DSH 不持 Bridge token；不能启动 Bridge；Tier2 必须确认。

**选项 B：正式 DSH 技能/插件**
- 优点：标准化“手机状态/为什么卡/重启服务”流程，减少误操作；
- 缺点：依赖 DSH 技能格式/版本；增加代码与维护；可能重复 server-ops；
- 推荐：Bridge 稳定后再做；先更新 `/root/AGENTS.md` + `server-ops bridge status`。

### D7 · 公网入口

**选项 A：保留现有 frp，不新增端口（推荐）**
- 优点：继续远程 DSH/Console；用户体验不变；已有 Basic Auth/限流；
- 缺点：依赖外部 frp 中继；公网攻击面；需要持续安全维护；
- 限制：Bridge **永不**公网监听；DSH 不持 Bridge token；frp 仅暴露 nginx 8080/8443；限流 429 已启用。

**选项 B：仅局域网**
- 优点：攻击面最小；无外部依赖；
- 缺点：离开家无法远程；不符合你当前远程使用需求。

**选项 C：Tailscale/WireGuard**
- 优点：加密私网、比公网端口安全；
- 缺点：外部依赖/额外配置；目前未接。

**推荐**：D7 A 保持现状；后续需要更强安全时可切 C，但不在本轮实施。

### D8 · OEM 自启/省电白名单（厂商无关）

**选项 A（推荐）：标准 Android 核心 + OEM profile**
- 标准核心：`BOOT_COMPLETED` + `specialUse` FGS + 电池优化豁免 + `deviceidle whitelist` + `appops RUN_ANY_IN_BACKGROUND`；
- OEM profile：MIUI/HyperOS、Samsung、ColorOS、OriginOS、EMUI/MagicOS 等各自“自启动/电池/后台”人工设置；
- 优点：换机只换 profile，不改核心；可靠可控；5 次重启验证；
- 缺点：首次需要人工点几项；
- 限制：厂商私有设置无标准 API，不能承诺全自动。

**选项 B：尝试厂商自动化**
- 风险：私有设置/版本差异；可能误改；不可持续；不作为验收依据。

**推荐**：A。具体 OEM 矩阵见 [docs/32 多厂商适配指南](32-多厂商Android适配与迁移指南.md)。

### D9 · Bridge APK 资产

**选项 A：仅版本+checksum（推荐）**
- 优点：备份轻；避免 APK 进入加密备份；便于审计/回滚记录；
- 缺点：恢复时需重新拿 APK；
- 限制：APK 本身可公开/侧载，不属机密；签名 key 单独保管。

**选项 B：纳入每日备份**
- 优点：恢复方便；
- 缺点：变更大；必要性低。

### D10 · 数据频率

**选项 A：10s 轮询（推荐）**
- 优点：开销低、简单、和现有 Termux 采集一致；
- 缺点：延迟 10s；
- 限制：可配置 5–30s；不使用 WebSocket（减少复杂度和常驻连接）。

### D11 · Termux:API 过渡保留
- 推荐：Bridge 稳定 24h 前保留；稳定后可停止在采集器里调用 battery/wifi，Termux:API 仍可用于其它研究命令。
- 限制：重启后仍需手动打开一次，不能作为验收依赖。

---

## 3. Root 手机后期路线

> 当前手机 BL 锁定、无 Root（官方解锁关闭）；本节是**未来换 Root 手机**的设计，不是对当前机器的承诺。

### 3.1 换 Root 手机的选购/准入清单

> **不按品牌选机**：按能否解锁、Root 方案/社区、内核能力、可恢复性选；OEM 只影响解锁政策，不影响 Bridge 核心。详见 [docs/32 §5](32-多厂商Android适配与迁移指南.md#5-root-选机矩阵厂商无关的准入标准)。


| 项 | 要求 |
|---|---|
| BL 解锁 | 官方/社区可解锁；解锁会清数据，需先接受 |
| Root 方案 | Magisk / KernelSU / APatch 至少一种成熟；有活跃社区 |
| 内核 | 能确认 `/proc`/cgroup/zram 等配置；是否支持容器需实测（**Root 不等于 USER_NS/PID_NS 可用**） |
| Android | 14+；A/B 分区/OTA 恢复能力 |
| 硬件 | ≥8GB RAM、≥256GB、散热可、USB/OTG |
| 安全 | Root 后 Play Integrity/银行 App 可能失效；需接受 |
| 恢复 | 有 fastboot/recovery/救砖路径；能接受 bootloop 风险 |

### 3.2 Root 能带来的优化（按优先级）

| 优先级 | 优化项 | 当前（无 Root） | Root 后 | 价值/风险 |
|---|---|---|---|---|
| P1 | **精确 CPU/逐核频率** | `/proc/stat` 禁读 | root shell 读 `/proc/stat`、cpufreq | 高价值/低风险（只读） |
| P1 | **网络原始字节/连接** | `/proc/net/dev` 禁读 | root 读 net/dev、iptables/conntrack | 高价值/低风险（只读） |
| P1 | **特权遥测** | battery/WiFi 部分 | dumpsys battery/wifi/power、settings、appops | 高/中 |
| P2 | **自启/常驻** | BootReceiver+FGS+OEM 自启/省电白名单 | Magisk `post-fs-data`/`service.d`；Sui/Shizuku 自启；可选 priv-app | 高/中 |
| P2 | **系统级 debloat/freeze** | `pm disable-user` 受限、suspend | systemless 模块/冻结、appops、settings | 高/中（勿删 boot 必需包） |
| P2 | **CPU/热/功耗** | 无 | governor、thermal profile、cgroup、taskset、isolcpus | 中/高 |
| P3 | **内存/zram/IO** | 无 | zram 大小/算法、swappiness、I/O scheduler、drop caches | 中/中 |
| P3 | **ADB/Shizuku 自启** | 每次开机 ADB | root 启动 adbd/Shizuku/Sui | 高便利/高安全风险 |
| P3 | **Bridge 系统化** | 普通 App | Magisk 模块/priv-app（需 allowlist/权限） | 高复杂度/高权限 |
| P4 | **服务器 chroot/systemd** | proot（假 root） | chroot/systemd 可试，但需实测 | 中/高 |
| P4 | **容器 Docker/LXC** | 内核无 USER_NS/PID_NS | **仅 Custom Kernel 可能**；Root 单独不够 | 不确定/高 |
| P4 | **公网/VPN** | frp | iptables/WireGuard/Tailscale | 中/中 |

### 3.3 Root 不能解决的问题

- 当前 haydn **无官方解锁**，不能靠 Root 改造本机；
- **原生 Linux（postmarketOS 等）仍无移植**；Root 不等于可刷主线 Linux；
- **容器**仍取决于内核配置；Root 不能热改运行内核的 CONFIG_USER_NS/PID_NS，需要自定义内核/ROM，风险高；
- Root 会破坏 Play Integrity/银行/部分 App；OTA 需手动维护；
- 系统级操作仍可能 bootloop；必须先备份/可恢复；
- 厂商 Android 的私有策略（MIUI/HyperOS）仍可能存在，Root 只是拿到更高权限，不等于无 bug。

### 3.4 现在就要预留的“双模架构”

**原则：当前 Bridge 不依赖 Root；未来 Root 作为可选 Provider。**

1. **数据 Schema 加字段**（现在就加，可空）：
   - `capabilities: ["battery","wifi","usage","cpu_global","network_raw","privileged"]`
   - `source`: `android` / `shizuku` / `root`
   - `privileged`: bool
2. **Bridge 拆成两层**：
   - `BridgeCore`（普通 App 权限：电池/WiFi/Build/内存/磁盘/热区）；
   - `PrivilegedProvider`（未来可选：Sui/Shizuku binder 或 root helper；**不把 su 调用写进 Bridge 主进程**）。
3. **Root Helper 设计**（未来）：
   - 独立 app/service 或 Magisk 模块；
   - 只接受本机 loopback + 独立 token/mTLS；
   - **命令白名单**（读 `/proc/stat`、读 net/dev、dumpsys battery/wifi、冻结指定包、appops 指定项），**禁止通用 shell**；
   - 每次特权操作审计；高风险操作人工确认。
4. **Server-ops 分层**：
   - Tier1 只读；Tier2 普通写；未来 **Tier2R（root 特权）**：确认+快照+审计+白名单；
   - **DSH 公共入口永不直接执行 root 操作**；Tier3 仍只人工 SSH。
5. **API 兼容**：
   - `/v1/status` 版本不变，新增字段可忽略；server 按 capability 降级；
   - `bridge_client` 根据 capability 显示“无 Root/带 Root”。

### 3.5 Root 迁移阶段（未来手机）

| 阶段 | 内容 |
|---|---|
| R0 | 选机/解锁/备份/救援演练；确认能否 root、内核能力、社区支持 |
| R1 | Magisk/KernelSU + Sui/Shizuku；root helper 最小只读 provider |
| R2 | Bridge 接特权 provider（先只读 CPU/网络/电池/无线；不做控制） |
| R3 | 自启/持久化：Magisk service.d、Sui 自启；可选 priv-app（谨慎） |
| R4 | 系统级优化：debloat/freeze、thermal/CPU、内存/IO（每步回滚） |
| R5 | 服务器 chroot/systemd/容器评估（仅在内核/社区验证后；否则继续 proot） |
| R6 | 安全/验收：24h soak、故障注入、备份/回滚、权限审计 |

### 3.6 Root 安全护栏（未来必须）

- Root helper **不得**暴露通用 `su -c`、任意 URL、任意文件读写；
- Root token/证书与 Bridge token **分离**；DSH 不持有；
- 公网 DSH 禁止 root 操作；只在本地 SSH/Console 管理 token + 确认；
- 白名单包/白名单命令；dry-run + 快照 + 审计；
- 系统包不卸载；只用 systemless freeze/disable；保留救援；
- Root/解 BL 后先评估 Play Integrity/银行/OTA 影响。

---

## 4. 推荐组合（供拍板）

| 事项 | 推荐 |
|---|---|
| D1 MVP 范围 | 不含 Usage/Network；Phase 2 feature flag |
| D2 安全 | TLS+token+pin；Phase 2 可选 mTLS |
| D3 SDK/Gradle | 允许安装（cmdline-tools + platform 34/35） |
| D4 包名 | `com.qingxuan.bridge` |
| D5 Shizuku | 不进 MVP；Root 手机后由 Sui/root helper 替代 |
| D6 DSH | 先 AGENTS + server-ops；稳定后再技能 |
| D7 公网 | 保留现有 frp，不新增端口 |
| D8 OEM 白名单 | 标准核心+OEM profile，5 次重启验收 |
| D9 APK 资产 | 版本+checksum |
| D10 频率 | 10s 可配置 |

---

## 5. 结论

- **当前无 Root 手机**：按 docs/28 的 Bridge MVP（D1–D10 默认）推进，不引入 Root/Shizuku 依赖；
- **未来 Root 手机**：当前设计已预留 `capabilities/source/privileged` 与 Provider 边界；Root 主要提升**特权遥测、自启/持久化、系统级优化**；
- **不要现在为 Root 重写架构**：Bridge 主进程保持无特权，Root Helper 作为未来可选模块；
- **不要试图用 Root 解决本机**：当前 BL 锁定、无官方解锁，按 docs/16 不尝试非官方 Root。
