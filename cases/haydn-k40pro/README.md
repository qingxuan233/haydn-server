---
id: CASE-001
title: haydn K40 Pro 实证案例：无 Root 手机改造为家用 Linux 服务器
type: case-study
status: current
audience: human, agent
tags: case, haydn, redmi-k40-pro, hyperos, android14, termux, proot, bridge-apk, no-root
depends: MTH-001, MTH-002, MTH-003, MTH-004, MTH-005, MTH-006, MTH-007, MTH-008, PIT-008, PIT-015, PIT-017, PIT-019, GRD-006
updated: 2026-11-11
agent_hint: 已冻结案例，仅修事实错误；复用前先读“关键事实”“方法论验证（未验证清单）”和“已知偏差与教训”
---

# CASE-001 · haydn K40 Pro：无 Root 手机改造为家用 Linux 服务器

> **案例状态：已冻结（2026-11-11）。** 仅允许修正事实错误（数字、链接、错别字、脱敏遗漏）；不得改写结论、删除偏差记录或追加"后来已修复"式美化。新进展写进方法论/踩坑/护栏层并在此加"后续见"链接。
> 一句话：在**不解锁 Bootloader、不 Root** 的国行 Redmi K40 Pro 上，用 Termux + proot 搭起可远程维护的家用 Linux 服务器，用自建 Bridge APK 补齐宿主状态，用 DSH 做只读控制面。
> 机器可读档案：[profile.json](profile.json) · OEM 人工步骤：[oem-profile.md](oem-profile.md) · 层索引：[CASE-000](../README.md)

---

## 1. 案例概览

| 项 | 内容 |
|---|---|
| 设备 | Redmi K40 Pro（型号 `M2012K11C`，代号 `haydn`，SoC Snapdragon 888 / SM8350，8GB / 256GB，国行） |
| 系统 | Android 14（SDK 34）/ HyperOS 1.0（OS1.0，MIUI 内部版本 V816）；构建类型 `user` / `release-keys` |
| 改造前状态 | Bootloader 锁定、AVB green、dm-verity enforcing、**无 Root**、零售机（未做任何破坏性操作） |
| 目标 | 低功耗、可远程维护的家用 Linux 服务器 + Android 宿主状态桥 + AI 控制面；不承诺系统级特权能力 |
| 最终路线 | **A（Termux + proot，无 Root）**；B（解锁 + Root + chroot）因国行官方解锁入口关闭而取消；C（自定义内核/原生移植）未实施、不推荐 |
| 落地结果 | 服务器栈 12/12 supervisord 服务 RUNNING、自启链实测、Bridge release 运行中、Console/DSH 可用；**24h soak 未完成** |
| 案例价值 | 方法论的首个端到端验证样本：验证了"锁定机优先无 Root 路线""能力边界必须显式声明""控制面不持桥凭据"等结论；也暴露了凭据卫生、伪 pin、权限重置等偏差，已沉淀为 PIT/GRD |

本案例的路线起点不是"想做什么"，而是"这台机器不允许做什么"：AVB 完整 + 官方解锁关闭，决定了任何需要解锁/刷内核的方案都不成立；内核缺 `USER_NS`/`PID_NS`，决定了容器与"真 Linux"不成立。**先证明不能做什么，再决定能做什么**——这是本案例对方法论最大的贡献。

---

## 2. 关键事实表

| 项目 | 值 | 证据 |
|---|---|---|
| 设备身份 | 厂商 Xiaomi / 品牌 Redmi；市场名 Redmi K40 Pro；型号 `M2012K11C`；代号 `haydn` | [01 设备档案](../../docs/10-device/01-设备档案.md) |
| SoC / ABI | Qualcomm Snapdragon 888（SM8350 / 平台 `lahaina`）；`arm64-v8a`；8 核（1 + 3 + 4 三簇） | [01 设备档案](../../docs/10-device/01-设备档案.md) |
| 系统 | Android 14（SDK 34）；HyperOS 1.0；固件 `V816.0.15.0.UKKCNXM`；编译 `UKQ1.231207.002`；安全补丁 2025-03-01；`user` / `release-keys` | [01 设备档案](../../docs/10-device/01-设备档案.md) |
| 内核 | `Linux 5.4.274-qgki-gcc3ec22f5061`（GKI 1.x 代）；`CONFIG_USER_NS` / `CONFIG_PID_NS` 未启用；cgroup 混合（v2 无委派）；`unshare` 失败 | [01 §3.1](../../docs/10-device/01-设备档案.md) · [02 §13](../../docs/10-device/02-可行性分析.md) |
| 内存 / 存储 | 标称 8GB（MemTotal ≈7.13 GiB）；标称 256GB（`/data` ≈225 GiB、f2fs）；A/B 双分区 + 动态 `super` 分区；无 MicroSD 槽 | [01 §5](../../docs/10-device/01-设备档案.md) |
| 启动链 | `ro.boot.flash.locked=1`、`verifiedbootstate=green`、`vbmeta.device_state=locked`、`veritymode=enforcing`、SELinux Enforcing | [01 §3](../../docs/10-device/01-设备档案.md) |
| Root | **完全无 Root**：无 `su`/`magisk`；ADB 身份仅 `uid=2000(shell)` | [01 §3](../../docs/10-device/01-设备档案.md) |
| 加密 / 锁屏 | FBE；研究机保持**无锁屏凭据**，否则 `BOOT_COMPLETED` 在解锁前不下发，开机自启失效 | [06 §3.4](../../docs/20-server/06-A+优化方案.md) · [08 事故复盘](../../docs/20-server/08-事故复盘与重置重建报告.md) |
| 服务器形态 | Termux + proot Ubuntu 24.04（aarch64，faked root）；supervisord **12/12** 服务 RUNNING；Termux:Boot 自启 | [当前状态 §2](../../docs/00-overview/当前状态.md) |
| Bridge 形态 | `com.qingxuan.bridge` **release**（`debuggable=false`，约 25KB）；`specialUse` FGS；仅环回 HTTPS + Bearer token + 服务器证书 pin；Phase 2 字段已接入 | [33 实施记录](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) · [android-bridge/README](../../android-bridge/README.md) |
| 控制面 | DSH 只读 Server API + `server-ops`；Tier1 只读 / Tier2 `--confirm` + 快照 + 审计 / Tier3 人工；**不持有 Bridge token** | [当前状态 §3](../../docs/00-overview/当前状态.md) · [server AGENTS](../../scripts/server/AGENTS.md) |
| 构建环境 | JDK 17/21 + 仓库内 Android SDK；**无 Gradle**；`build.ps1` 手工构建（aapt2 + javac + d8 + zipalign + apksigner）；路径必须 ASCII | [当前状态 §6](../../docs/00-overview/当前状态.md) |
| 长期插电风险 | 电池长期满电 + 高温；充电上限 sysfs 对 shell 不可读，只能先用系统"充电保护"，需 Root 后验证 | [01 §7](../../docs/10-device/01-设备档案.md) · [04 R-04](../../docs/10-device/04-风险与回滚.md) |

> 精确字段与来源见 [profile.json](profile.json)；本表只列"换机时必须重新确认"的字段。

**设备与能力基线（2026-11-11 核对）**

```text
profile.json：cases/haydn-k40pro/profile.json（repurpose.device-profile.v1，脱敏；source.mode=documented）
关键门禁：G-A=pass（aarch64 可跑 proot）、G-B0=fail（锁定 + 国行解锁关闭）、G-B1=fail（无 Root）、
          G-B2=fail（user_ns/pid_ns/cgroup 委派缺失）、G-C=fail、G-D=fail（无原生移植）
assess 结论：route=A，confidence=0.73（documented 档案的启发式置信度，不是成功概率）
```

---

## 3. 落地时间线

| 日期 | 阶段 | 事实 | 证据 |
|---|---|---|---|
| 2026-11-10 上午 | T0 基线 | 首次建档：ADB 直连全量采集设备/能力；标称 8GB/256GB、无 Root、BL 锁定 | [01](../../docs/10-device/01-设备档案.md) |
| 2026-11-10 | 决策门禁 | 可行性论证；**Gate B0 失败**（国行官方解锁入口已关闭）→ B 路线（解锁 + Root + chroot）取消，转 A+ 无 Root 深度优化 | [02 §13](../../docs/10-device/02-可行性分析.md) · [06 §1](../../docs/20-server/06-A+优化方案.md) · [04 R-16](../../docs/10-device/04-风险与回滚.md) |
| 2026-11-10 | 服务器栈落地 | Termux + proot Ubuntu 稳定运行（当时 9 个 supervisord 服务）；A+ 优化（8 项系统设置、debloat、ADB 资源让渡）；随后自托管 DSH | [06 A+](../../docs/20-server/06-A+优化方案.md) · [07 DSH](../../docs/30-dsh/07-DSH与Linux优化.md) |
| 2026-11-10 | 事故与重建 | bootloop 事故（误停用系统必需包）→ 恢复出厂 → 从备份重建服务器；固化自启链与"无锁屏凭据 + wake-lock/白名单 + 看门狗"策略 | [08 事故复盘](../../docs/20-server/08-事故复盘与重置重建报告.md) · [04 R-19](../../docs/10-device/04-风险与回滚.md) |
| 2026-11-10 | 规范化 | 形成 Bridge 架构调研、全栈方案规范、项目评审、新会话接手指南、D1–D10 决策、多厂商 OEM 适配矩阵 | [27](../../docs/50-bridge/27-Android-Bridge-APK架构调研.md) · [28](../../docs/00-overview/28-全栈整体方案规范.md) · [29](../../docs/00-overview/29-项目文档评审报告.md) · [30](../../docs/00-overview/30-新会话接手指南.md) · [31](../../docs/10-device/31-拍板事项决策分析与Root升级路线.md) · [32](../../docs/10-device/32-多厂商Android适配与迁移指南.md) |
| 2026-11-11 凌晨 | Bridge Phase 0/1 | 用户批准 D1–D10；SDK/JDK 构建链、Bridge MVP（BootReceiver + specialUse FGS + loopback HTTPS + token/pin）、服务器集成、5/5 debug 重启 | [33](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |
| 2026-11-11 | Console 改版 | Console 从单页改为"总览 + 详情双视图"（服务/检查/审计/账号/备份/入口/运维） | [34](../../docs/40-console/34-Console总览详情改版.md) |
| 2026-11-11 | Bridge 加固 | release 升级（`debuggable=false`，同签名原地升级 token 保留）；Phase 2 字段（display/usage/network/uptime）接入 API/UI；1/1 release 重启；**24h soak 未完成** | [33 §8](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |
| 2026-11-11 | 仓库重构 | 仓库改名 `haydn-server`（aapt2 无法处理中文路径）→ `docs` 按主题分组、`scripts` 按运行侧分组、`build.ps1` 去掉 ASCII junction；状态集中到单页、变更集中在 CHANGELOG | [CHANGELOG](../../CHANGELOG.md) · [33 §9](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |
| 2026-11-11 | 方法论化 | 建立 `methodology/`（规范）、`pitfalls/`（证据）、`guardrails/`（红线）、`toolkit/`（实现）分层；旧目录冻结为案例证据，本案例登记为首例 | 本页 · [CASE-000](../README.md) |

> 上表只写"发生了什么"；当前运行状态一律以 [当前状态](../../docs/00-overview/当前状态.md) 为准，历史数字标注快照。

---

## 4. 三轨实现

### 4.1 Track A · 服务器栈（已落地并在线）

| 项 | 实现 | 证据 |
|---|---|---|
| 运行时 | Termux + proot Ubuntu 24.04（aarch64）；`proot` 是用户态 chroot/bind/binfmt，非真 root | [02 §4](../../docs/10-device/02-可行性分析.md) |
| 服务管理 | supervisord；12 个服务：api / fileui / frpc / gitea / nginx / runner / sshd / syncthing / webdav / dsh / dsh-login / dsh-guard | [当前状态 §2](../../docs/00-overview/当前状态.md) |
| 自启链 | Termux:Boot → `00-server.sh` → `ubuntu.sh` → `server-up` + `server-watch`；重启实测（ADB 32s / Console 45s / 完整服务 + DSH 111s） | [当前状态 §2](../../docs/00-overview/当前状态.md) · [17 重建手册](../../docs/20-server/17-研究平台环境构建手册.md) |
| 对外入口 | 局域网 Web/SSH；公网仅经**现有受控入口**（frp），不新增监听面；Bridge 永不公网监听 | [当前状态 §2](../../docs/00-overview/当前状态.md) · [31 D7](../../docs/10-device/31-拍板事项决策分析与Root升级路线.md) |
| 备份 | `server-backup` + `server-backup-sessions` 每日、加密、`server-restore --verify` 可校验 | [当前状态 §2](../../docs/00-overview/当前状态.md) |
| 审计 | `ops-audit.jsonl`、`console-actions.jsonl`；写操作先快照 | [server AGENTS](../../scripts/server/AGENTS.md) |
| 运维分层 | Tier1 只读；Tier2 受控写（`--confirm` + 快照 + 审计）；Tier3 仅人工 SSH | [22 Tier2](../../docs/30-dsh/22-DSH-Tier2受控写落地.md) · [server AGENTS](../../scripts/server/AGENTS.md) |
| 能力边界 | 无 Root：全局 `/proc/stat`、`/proc/net/dev`、`dumpsys` / `settings` / 冻结 / 停用不可得；proot 内 `top`/`uptime` 是假数据 | [当前状态 §7](../../docs/00-overview/当前状态.md) · [02 §4](../../docs/10-device/02-可行性分析.md) |

### 4.2 Track B · Android Bridge APK（release 运行中）

| 项 | 实现 | 证据 |
|---|---|---|
| 形态 | 普通 App（非 system/priv-app），包名 `com.qingxuan.bridge`，release 签名，`debuggable=false`、`allowBackup=false` | [android-bridge/README](../../android-bridge/README.md) |
| 自启/常驻 | `BootReceiver`（BOOT_COMPLETED / MY_PACKAGE_REPLACED / 厂商 QUICKBOOT）+ `specialUse` 前台服务；`START_STICKY` | [33 §3](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |
| 接口 | 仅本机环回 HTTPS、只允许 GET；`/v1/health`、`/v1/version`、`/v1/status`；Bearer token + 服务器证书 pin | [28 §6.1](../../docs/00-overview/28-全栈整体方案规范.md) |
| 采集字段 | MVP：battery / wifi / build / memory / disk / thermal / packages；Phase 2：display / usage / network 累计 / uptime（可空） | [33 §8.2](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |
| 验收 | 5/5 debug 重启 + 1/1 release 重启；无 token 访问 status 返回 401；非环回不可达；Bridge 停止后服务器回退 Termux 采集 | [33 §5/§8](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |
| 未落地 | mTLS / 配对码 / token exchange / 证书轮换 / Keystore 硬件 key / 限流 / `onTaskRemoved` 兜底 | [28 §8.3](../../docs/00-overview/28-全栈整体方案规范.md) · 本页 §6 |

### 4.3 Track C · 集成层（Console / API / DSH）

| 项 | 实现 | 证据 |
|---|---|---|
| 桥客户端 | `bridge_client.py`：环回 HTTPS + 证书 pin + token + 超时/缓存/熔断 | [33 §4.2](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |
| 数据合并 | `/api/sysinfo` 合并 bridge 字段并标 `bridge_source` / `bridge_available` / `bridge_age_s` / `bridge_version` 等；缺失字段 `null`，不伪造 0 | [28 §6.2](../../docs/00-overview/28-全栈整体方案规范.md) |
| 只读健康入口 | `server-ops bridge status`（来源/版本/新鲜度/缺失字段） | [server AGENTS](../../scripts/server/AGENTS.md) |
| Console | 总览 + `?view=details` 详情双视图；显示数据来源；Bridge 故障时标注回退 `termux` | [34](../../docs/40-console/34-Console总览详情改版.md) · [26](../../docs/40-console/26-Console手机状态补全.md) |
| DSH | 只读 Server API + `server-ops`；**不持 Bridge token、不直连 Bridge、不试图启停 Android App**；故障不影响采集 | [当前状态 §3](../../docs/00-overview/当前状态.md) · [server AGENTS](../../scripts/server/AGENTS.md) |

---

## 5. 证据地图

| 主题 | 权威证据 | 关键事实 |
|---|---|---|
| 设备基线（硬件/系统/属性/电池/热区） | [01 设备档案](../../docs/10-device/01-设备档案.md) | T0 快照；启动链/内核能力实测 |
| 路线可行性与内核能力 | [02 可行性分析](../../docs/10-device/02-可行性分析.md) | A/B/C/D 路线论证；容器否决；systemd 不保证 |
| 拍板决策与 Root 未来路线 | [31 拍板事项](../../docs/10-device/31-拍板事项决策分析与Root升级路线.md) | D1–D10；双模架构预留 |
| OEM 适配矩阵 | [32 多厂商适配](../../docs/10-device/32-多厂商Android适配与迁移指南.md) | 标准基线 + 厂商私有步骤 |
| 全栈规范（契约/安全/验收） | [28 全栈整体方案规范](../../docs/00-overview/28-全栈整体方案规范.md) | 三轨边界、数据契约、门禁 |
| 服务器从零重建 | [17 研究平台环境构建手册](../../docs/20-server/17-研究平台环境构建手册.md) | 换机/重置 runbook |
| A+ 无 Root 优化 | [06 A+ 优化方案](../../docs/20-server/06-A+优化方案.md) | 设置/debloat/备份/回滚；FBE 自启限制 |
| 风险登记与回滚 | [04 风险与回滚](../../docs/10-device/04-风险与回滚.md) | R-01…R-20；电池/变砖/事故 |
| 事故复盘 | [08 事故复盘与重置重建](../../docs/20-server/08-事故复盘与重置重建报告.md) | bootloop 根因、恢复流程、锁屏凭据结论 |
| Bridge 架构调研 | [27 Bridge 架构调研](../../docs/50-bridge/27-Android-Bridge-APK架构调研.md) | 选型依据、Android 14/15 证据 |
| Bridge 实施与加固 | [33 Bridge MVP 实施记录](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) · [android-bridge/README](../../android-bridge/README.md) | Release/Phase 2/构建路径 |
| DSH 控制面 | [20 方案](../../docs/30-dsh/20-DSH控制平面方案.md) · [21 落地](../../docs/30-dsh/21-DSH控制平面落地手册.md) · [22 Tier2](../../docs/30-dsh/22-DSH-Tier2受控写落地.md) · [23 蓝绿](../../docs/30-dsh/23-DSH蓝绿升级演练.md) · [24 sessions](../../docs/30-dsh/24-DSH-sessions持久化补全.md) | 控制面边界与受控写 |
| Console | [34 总览详情](../../docs/40-console/34-Console总览详情改版.md) · [26 手机状态](../../docs/40-console/26-Console手机状态补全.md) | 双视图、状态字段 |
| 当前事实 | [当前状态](../../docs/00-overview/当前状态.md) | 唯一权威状态源 |
| 变更历史 | [CHANGELOG](../../CHANGELOG.md) | 逐版本记录 |
| 机器可读档案 | [profile.json](profile.json) | 本案例字段与证据映射 |

---

## 6. 方法论验证

> 阅读方式：**已验证** = 本案例有实测/一手证据支撑；**部分验证** = 主链路通过，但验收项未完成；**未验证** = 明确没做或硬约束不可做。禁止把"未验证"写成"已完成"。

### 6.0 验收结果（区分实测/未实测）

| 验收项 | 结果 | 证据 |
|---|---|---|
| 5 次重启自启 | **通过**：5/5 debug + 1/1 release（每次重启后 Bridge FGS、健康检查、API 来源、服务器 12/12） | [33 §5/§8](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |
| 24h soak | **未实测**（未执行；仅有约 6h21m 连续运行记录） | [33 §8.4](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |
| 故障注入 | **部分手工、未系统化**（杀进程/回退有验证；断网、401、超时、Server/DSH 重启矩阵未做） | [33 §5.3](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) · 本页 §6.1 |
| 恢复演练 | **未实测**（备份/verify 机制有，完整恢复与旧 APK 回滚演练未做） | [PIT-017](../../pitfalls/PIT-017-snapshot-without-rollback.md) |

| MTH | 被验证的结论 | 本案例结果 | 状态 |
|---|---|---|---|
| [MTH-001 基础模型](../../methodology/00-foundations.md) | 设备能力分层；锁定/无 Root 决定能力上限；能力边界必须显式声明 | 命名空间/cgroup/充电节点/`/proc` 限制均有实测；未知字段一律 null | 已验证 |
| [MTH-002 评估](../../methodology/01-assessment.md) | 锁定 + 无 Root + OEM 解锁关闭 → A 路线；容器需 `USER_NS`/`PID_NS` → 阻断；Gate B0 失败即退出 B | 用户确认国行无解锁入口；容器实测否决；最终走 A | 已验证 |
| [MTH-003 路线图](../../methodology/02-roadmap.md) | Phase 0→4 门禁推进；B/C 路线有明确退出条件 | Phase 0/1 过门禁；B 取消、C 未实施；Phase 2 部分；Phase 4 待办 | 部分验证 |
| [MTH-004 服务器栈](../../methodology/03-server-stack.md) | Termux + proot + supervisord 可服务化；不依赖 systemd；备份/审计/分级运维 | 12/12 服务、重启实测、每日备份、Tier1/2 审计落地 | 已验证（systemd 未尝试，按命名空间/cgroup 证据排除） |
| [MTH-005 遥测桥](../../methodology/04-telemetry-bridge.md) | BootReceiver + `specialUse` FGS + 环回 HTTPS + token + pin；null/来源/capabilities 语义 | 5/5 + 1/1 重启、401、非环回不可达、回退 termux 全部验证 | 部分验证（mTLS/配对/限流/Keystore/onTaskRemoved 未落地） |
| [MTH-006 控制面](../../methodology/05-control-plane.md) | Tier1/2/3 分级；DSH 不持凭据、不控制 Bridge；故障隔离 | `server-ops` + 审计 + `dsh-guard` + AGENTS 约束落地；DSH 仅只读 | 已验证（Tier3 未触发演练） |
| [MTH-007 安全](../../methodology/06-security.md) | 环回/最小暴露/token/pin/秘密卫生 | 401 与非环回隔离通过；但"pin 非双向认证"、明文凭据历史欠账 | 部分验证（mTLS/轮换未落地，见 §7） |
| [MTH-008 验收](../../methodology/07-validation.md) | 5 次重启 + 24h soak + 故障注入 + 恢复演练四件套 | 重启矩阵通过；soak/故障注入/恢复演练未做 | 部分验证 |
| [MTH-009 交接](../../methodology/08-agent-handoff.md) | 状态单页、CHANGELOG、AGENTS、机器索引与冻结边界 | 28/29/30 成文；状态集中；本案例 + profile + OEM profile 登记 | 部分验证（manifest/工具链在本轮建立中） |
| [MTH-000 索引](../../methodology/README.md) | 四层 + 案例的分层与阅读路径 | 本案例按分层组织，通用步骤不复制进案例 | 已验证 |

### 6.1 本案例**未验证**清单（诚实清单，换机时必须重跑）

1. **24h soak 未完成**：长稳可用率、内存/CPU 占用、无崩溃循环均未验证；现有结论只到"5/5 + 1/1 重启 + 曾连续约 6h21m 无重启"。
2. **mTLS / 配对码 / token exchange / 证书轮换 / Keystore 硬件 key 未落地**：安全结论仅到"token + 自签证书 pin"。
3. **限流与请求审计加严未落地**：规范写的是目标，实现未验收。
4. **故障注入未系统化演练**：Bridge 被杀/断网/401/超时、Server 重启、DSH 重启、APK 升级失败等故障矩阵只有部分手工验证。
5. **备份恢复与回滚演练未完成**：`server-restore --verify` 有机制，但完整恢复演练、旧 APK 回滚演练待补。
6. **OEM profile 矩阵未实测**：只有 MIUI/HyperOS 的人工白名单路径经过 5 次重启验证，其他厂商未验证。
7. **容器 / 原生 Linux / 特权指标在当前设备不可验证**：不是遗漏，是内核与解锁策略的硬约束（见 [02 §13](../../docs/10-device/02-可行性分析.md)）。
8. **长期插电的电池老化与热节流曲线未观测**：需要 2–4 周长跑数据；目前只有单点温度读数。

---

## 7. 已知偏差与教训

> 这一节是案例的"负资产清单"，后续 Agent 必须读：它比成功列表更能防止重复踩坑。

| # | 偏差 / 教训 | 影响 | 关联 | 当前状态 |
|---|---|---|---|---|
| 1 | **明文凭据曾进入脚本/会话/备份**（凭据文件、SSH 私钥曾贴入会话、源码硬编码旧入口地址） | 一旦泄露必须轮换；文档已去敏但源码值仍在 | [PIT-015](../../pitfalls/PIT-015-plaintext-credentials.md) · [GRD-006](../../guardrails/GRD-006-secret-hygiene.md) | 文档去敏完成；**轮换与外置配置待办** |
| 2 | **桥 "pin" 是 CA 信任，不是双向认证**：TLS 证书/私钥构建时自签并静态打包，服务器 pin 只是"信任这张证书"；真实认证仍是 Bearer token | 同机恶意 App 读到 token 即可伪造状态；没有 mTLS/配对 | [PIT-019](../../pitfalls/PIT-019-fake-pinning-bridge.md) | Phase 2 待办 |
| 3 | **MIUI/HyperOS 重启重置权限**：通知权限被重置为 ignore（FGS 仍工作）、使用情况访问回到默认（`usage` 字段为空） | 通知不可见、前台应用字段缺失，需人工再授权 | [PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md) | 已知限制，未实现自动恢复 |
| 4 | **规范-实现不一致**：规范要求限流、Keystore/EncryptedSharedPreferences、`onTaskRemoved` 兜底，MVP 实际为文件 token + `START_STICKY` | 读者会把"规范要求"误读为"已实现"；安全/可靠性结论偏乐观 | [MTH-005](../../methodology/04-telemetry-bridge.md) · [MTH-007](../../methodology/06-security.md) | 案例已标"未落地"；Phase 2 待办 |
| 5 | **备份有、恢复演练不足**："恢复未演练 ≙ 没有回滚"；旧 APK 回滚演练同样待补 | 真故障时恢复时间不可预期 | [PIT-017](../../pitfalls/PIT-017-snapshot-without-rollback.md) | 待办 |
| 6 | **公网入口/地址硬编码在源码**：历史脚本与页面源码写死旧入口地址（文档已去敏） | 暴露面不透明、轮换困难 | [GRD-006](../../guardrails/GRD-006-secret-hygiene.md) · [GRD-007](../../guardrails/GRD-007-network-least-exposure.md) | 外置配置 + 轮换待办 |
| 7 | **状态数字多口径**：服务数 9→10→11→12、自启耗时 31/43s 与 32/45/111s 曾并存 | 引用易错、文档互相矛盾 | [当前状态 §11](../../docs/00-overview/当前状态.md) · [CHANGELOG](../../CHANGELOG.md) | 已集中到状态单页；历史值标快照 |
| 8 | **把目标值写成完成度**：Phase 2/4 门禁、soak 等目标值曾与已实现项混写 | 读者误判完成度，后续验收失去基线 | [MTH-008](../../methodology/07-validation.md) · [GRD-013](../../guardrails/GRD-013-no-fake-acceptance.md) | 案例已分离"目标/实测/未验证" |
| 9 | **验收窗口未完成**：24h soak 未做即长期按"运行中"表述 | 可用率 ≥99%、内存/CPU 占用等稳定性结论缺证据 | [MTH-008](../../methodology/07-validation.md) · [GRD-013](../../guardrails/GRD-013-no-fake-acceptance.md) | 待办（Phase 4 门禁） |

**从 9 条偏差提炼的 4 条教训**：

1. **文档必须三分**：目标值 / 实测值 / 未验证，混写一次就会误导下一轮 Agent。
2. **安全加固写进规范 ≠ 已实现**：凡是"必须"项，没有验收证据就只能标"未落地"。
3. **凭据与入口必须外置并轮换**：不要把 token/证书/入口地址写进脚本、会话或文档。
4. **案例冻结 + 偏差进 PIT**：只改案例不改证据库，下一次换机仍会踩同一个坑。

---

## 8. 复用指南（换机时）

### 8.1 保留（设备无关，直接复用）

- **三轨架构与边界**：Server 唯一聚合/存储/展示、Bridge 只做宿主采集、DSH 只读控制面、故障隔离与回退。
- **Bridge 核心设计**：包名 `com.qingxuan.bridge`；BootReceiver + `specialUse` FGS；环回 HTTPS + GET-only + token（后续升 mTLS）；null 语义与 capabilities。
- **服务器栈**：Termux + proot + supervisord（不用 systemd）；启动链 + 看门狗；`server-ops` Tier1/2/3；每日加密备份 + 审计。
- **数据契约**：`bridge_source` / 新鲜度 / 字段来源标记 / 缺失即 null / 不可得字段由 capabilities 解释。
- **验收框架**：5 次重启 + 24h soak + 故障注入 + 恢复演练；未过项必须显式记录。

### 8.2 必须重做 / 重探测（换机时）

| 项 | 为什么 | 怎么做 |
|---|---|---|
| OEM profile | 自启动/省电/后台/安装弹窗各厂商不同，无标准 API | 按 [oem-profile.md](oem-profile.md) 的模板结构逐项填写；以 5 次重启为准 |
| `profile.json` 全部字段 | 硬件/启动链/内核能力是设备事实 | 用 `toolkit probe`/`detect` 重新探测，`source.mode` 改为 `adb`/`fixture`，更新 `unknowns` |
| 内核能力评估 | `USER_NS`/`PID_NS`/cgroup/overlay 决定容器与原生 Linux 是否可能 | `toolkit assess` 复评；不要沿用"本机不可用"的结论 |
| 设备专属脚本 | MIUI 安装弹窗、debloat/保护名单只对当前设备成立 | 只作案例证据，不迁移为通用脚本；换机按标准 ADB 基线重写 |
| 构建环境 | JDK/SDK 位置与路径 ASCII 要求 | 重新探测 JDK/SDK；仓库路径保持 ASCII；跑一次构建验收 |
| 凭据与入口 | 换设备必须重新生成 token/证书/密钥，公网入口外置后轮换 | 新配对流程；不要把旧凭据/入口复制到新文档 |
| 存储与分区策略 | A/B、动态分区、无 SD 卡影响刷机/扩容/备份 | 写进新案例关键事实与 profile |
| 若新机可解锁/Root | 结论不能沿用"无 Root" | 按 [MTH-002](../../methodology/01-assessment.md) 重评路线；容器仍需实测命名空间 |

### 8.3 换机步骤（本案例视角，与 MTH 对齐）

1. 读 [MTH-002 评估](../../methodology/01-assessment.md) 与本案例 §2 → 用 `toolkit` 探测新机，填新 `profile.json`；
2. 用 `toolkit assess` 得到路线/门禁/风险，先拒绝"做不了"的路线（锁定/OEM 策略/内核缺项）；
3. 按 [OEM profile 模板](oem-profile.md) 完成标准 Android 基线 + 厂商人工白名单，跑 5 次重启；
4. 按 [MTH-004 服务器栈](../../methodology/03-server-stack.md) 与 [17 重建手册](../../docs/20-server/17-研究平台环境构建手册.md) 重建/迁移服务器，接备份与审计；
5. 按 [MTH-005 遥测桥](../../methodology/04-telemetry-bridge.md) 构建/安装 Bridge，验证自启、401、回退；
6. 按 [MTH-008 验收](../../methodology/07-validation.md) 跑完整验收；未过项写进新案例"未验证清单"，不得美化。

---

## 9. 案例冻结声明

- 本案例自 **2026-11-11** 起冻结，作为 haydn K40 Pro 改造过程的原始证据；对应旧目录（[docs/README.md](../../docs/README.md)、[scripts/README.md](../../scripts/README.md)、[android-bridge/README.md](../../android-bridge/README.md)）同为冻结证据。
- **允许**：修正事实错误（设备字段、数字、链接、错别字、脱敏遗漏）、补充证据链接。
- **禁止**：改写结论、删除偏差/未验证项、把后来新增的实现倒灌回案例历史、用"已完成"表述覆盖"部分完成"。
- 脱敏：本案例不记录设备序列号、网络地址、凭据等敏感值；[profile.json](profile.json) 中 `identity.serial=null`、`serial_redacted=true`，需要真实值请在本地 `inventory/`（gitignored）查看，勿写入仓库。
- 新进展的落点：规范修订 → [methodology/README.md](../../methodology/README.md)；新踩坑 → [pitfalls/README.md](../../pitfalls/README.md)；新红线 → [guardrails/README.md](../../guardrails/README.md)；工具/校验 → [toolkit/README.md](../../toolkit/README.md)。
- 任何事实修正须同步 [profile.json](profile.json) 与 [oem-profile.md](oem-profile.md)，并在提交说明中写明"案例事实纠错"。

---

## 10. 关联入口

| 层 | 入口 |
|---|---|
| 案例层 | [CASE-000 索引](../README.md) · [profile.json](profile.json) · [oem-profile.md](oem-profile.md) |
| 方法论 | [methodology/README.md](../../methodology/README.md) · [MTH-002 评估](../../methodology/01-assessment.md) · [MTH-004 服务器栈](../../methodology/03-server-stack.md) · [MTH-005 遥测桥](../../methodology/04-telemetry-bridge.md) · [MTH-008 验收](../../methodology/07-validation.md) |
| 踩坑库 | [pitfalls/README.md](../../pitfalls/README.md) · [PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md) · [PIT-015](../../pitfalls/PIT-015-plaintext-credentials.md) · [PIT-017](../../pitfalls/PIT-017-snapshot-without-rollback.md) · [PIT-019](../../pitfalls/PIT-019-fake-pinning-bridge.md) |
| 护栏 | [guardrails/README.md](../../guardrails/README.md) · [GRD-006 秘密卫生](../../guardrails/GRD-006-secret-hygiene.md) |
| 工具链 | [toolkit/README.md](../../toolkit/README.md) |
| 旧项目证据 | [docs 索引](../../docs/README.md) · [scripts 索引](../../scripts/README.md) · [android-bridge](../../android-bridge/README.md) |
| 协议与状态 | [AGENTS.md](../../AGENTS.md) · [当前状态](../../docs/00-overview/当前状态.md) · [CHANGELOG](../../CHANGELOG.md) |
