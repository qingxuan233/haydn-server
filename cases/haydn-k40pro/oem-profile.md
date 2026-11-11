---
id: CASE-002
title: 小米 / HyperOS OEM 适配 profile（以 haydn K40 Pro 为实例）
type: oem-profile
status: current
audience: human, agent
tags: oem-profile, xiaomi, redmi, hyperos, miui, autostart, battery-optimization, fbe, firmware-freeze
depends: CASE-001, MTH-004, MTH-005, PIT-008, GRD-002
updated: 2026-11-11
agent_hint: 换小米/HyperOS 设备时逐项照做并以 5 次重启验收；其他 OEM 按 §2 模板结构另填，不要照抄小米设置名
---

# CASE-002 · 小米 / HyperOS OEM 适配 profile

> 定位：本文件是 [CASE-001](README.md) 的 OEM 侧补充，说明**标准 Android 之外**必须由人工完成的设置、重启后会被重置的项、以及踩过的系统级坑。
> 用途：换机/重装/系统更新后照单核对；也是 [MTH-004 服务器栈](../../methodology/03-server-stack.md) 与 [MTH-005 遥测桥](../../methodology/04-telemetry-bridge.md) 在小米 ROM 上的实例化。
> 铁律：**OEM 私有设置没有标准 API**，不承诺全自动；脚本只能辅助，验收以真机重启为准；不得把厂商设置写进核心代码/数据契约。

---

## 1. 适用范围与前置

| 项 | 说明 |
|---|---|
| 适用 | 小米 / Redmi，HyperOS / MIUI，Android 13+，**无 Root** 的改造机（本实例：Android 14 / HyperOS 1.0 / 国行 / 代号 `haydn`） |
| 前置 | 标准 Android 基线已完成（见 §2.2）；Bridge 已安装、Termux + Termux:Boot 已就绪 |
| 不适用 | 有 Root 设备（可改用 Magisk 自启/特权 provider，见 [MTH-002](../../methodology/01-assessment.md)）；非小米机型（按 §2 模板另填 profile） |
| 证据等级 | 本机**实测**（5/5 debug + 1/1 release 重启、权限重置实测）；其他 OEM 为**社区/文档证据**或待验证 |
| 证据来源 | [CASE-001](README.md)、[32 多厂商适配](../../docs/10-device/32-多厂商Android适配与迁移指南.md)、[33 Bridge 实施记录](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)、[06 A+ 优化](../../docs/20-server/06-A+优化方案.md)、[08 事故复盘](../../docs/20-server/08-事故复盘与重置重建报告.md) |

---

## 2. 通用 OEM profile 模板结构（本案例是其小米实例）

> 新增其他厂商时，复制下面的结构，只换 §2.1/§2.3/§2.4 的内容；§2.2 是所有 OEM 共用的标准基线，不要改。
> 本结构与 [toolkit OEM 模板](../../toolkit/templates/oem-profile.md) 的六节骨架对应：模板「基本信息/安装差异/自启动与保活/已知重置行为/验收步骤/关联」分别实例化为本文 §1、§3 #6、§3 #1/#2/#3/#7、§3.0、§2.8、§6；本文额外保留"通用模板结构"与"其他 OEM 复用"两节，便于换机时直接改写。

### 2.1 元信息

| 字段 | 填写要求 |
|---|---|
| `oem` / `rom` | 厂商 + ROM 名称/版本（如 Xiaomi + HyperOS 1.0） |
| `android` / `sdk` / `device` | 版本与代号；与 `cases/<codename>/profile.json` 一致 |
| `updated` / `evidence` | 核对日期；每项设置的证据链接或"待验证" |
| `scope` | 本 profile 覆盖的功能：自启、保活、通知、权限、安装、系统包、固件策略 |

### 2.2 标准 Android 基线（所有 OEM 必做，非厂商私有）

| 基线项 | 做法 | 作用 |
|---|---|---|
| 安装 | 标准 `adb install -r`（侧载） | 不依赖应用商店 |
| 通知/定位权限 | `pm grant` 通知、定位（WiFi 需要） | FGS 通知与 WiFi 字段 |
| 后台白名单 | `cmd appops set <pkg> RUN_ANY_IN_BACKGROUND allow` + `dumpsys deviceidle whitelist +<pkg>` | 降低被 Doze 杀的概率 |
| 电池优化豁免 | 系统"电池优化"中对 App/Termux 设为不优化 | 保活基础 |
| 使用情况访问（可选） | Usage Access 授权（`GET_USAGE_STATS`） | Phase 2 usage 字段 |
| 验收 | 5 次重启 + 24h soak（[MTH-008](../../methodology/07-validation.md)） | 唯一可信的"自启成立"证据 |

> 实测提醒（小米）：**仅做 appops/deviceidle 不足**，必须叠加 §3 的厂商自启动 UI 白名单，才达到 5/5 重启。

### 2.3 OEM 私有项清单（表模板）

每项固定四问：**设置路径 → 影响 → 验证方法 → 失效风险**。本案例的小米实例见 §3；不要只写"打开自启动"，要写清菜单层级与验证命令。

### 2.4 安装 / 升级特殊行为

- 安装弹窗、安装器审查、静默安装限制、ADB 安装被拦截的 UI 流程；
- 升级后是否保留 App 权限、token、自启动白名单；
- 失败时的回退方式（旧 APK / 重装）。

### 2.5 重启后会被重置的项

- 通知权限、Usage Access、后台 appops、自启动白名单是否被 ROM 重置；
- 每条给"实测结果 + 再授权方式 + 对主链路的影响"；
- 影响主链路的必须做启动自愈/人工提示，不能默认"用户会记得"。

### 2.6 FBE / 锁屏凭据权衡

- 有锁屏凭据时 FBE 在解锁前不完成解密 → `BOOT_COMPLETED` 延迟 → 开机自启失效；
- 研究机可保持"无锁屏凭据"换取无人值守，但这是**安全降级**，必须由用户知情接受；
- 若必须设锁屏：接受"重启后人工解锁一次"，或未来用 Root 方案替代（见 [MTH-002](../../methodology/01-assessment.md)）。

### 2.7 系统包保护与固件策略

- **禁止卸载系统包**（只允许可逆 `disable-user` + 保护名单）；误删可能导致 bootloop/RescueParty（[GRD-002](../../guardrails/GRD-002-no-system-package-uninstall.md)）；
- 是否冻结固件（关闭自动更新）：换取接口/权限稳定，代价是安全补丁滞后；升级前必须备份与核对。

### 2.8 验收记录

- 5 次重启矩阵（每次记录：Bridge FGS、HTTP 健康检查、服务器服务数、数据来源）；
- 24h soak 结果（未完成就写"未完成"，不得写"稳定"）；
- 系统更新后回归一次（权限/白名单/内核接口是否变化）。

### 2.9 未验证与遗留

- 未实测的项、厂商版本差异、依赖用户操作而无法自动化的项；
- 与 [pitfalls/README.md](../../pitfalls/README.md) 的对应条目。

---

## 3. 小米 / HyperOS 实例

> 设置菜单名会随 HyperOS/MIUI 版本变化；找不到时按"同义路径"搜索（自启动/后台/省电/权限）。下表是本案例实测过的版本。

| # | 项 | 设置路径 / 命令 | 影响 | 验证方法 | 失效风险 |
|---|---|---|---|---|---|
| 1 | 自启动管理允许 | 设置 → 应用 → 自启动管理 → 将 Bridge（`com.qingxuan.bridge`）与 Termux/Termux:Boot 设为允许 | 决定 `BOOT_COMPLETED` 后 App 能否被拉起；**不批准则 FGS/服务器不自启** | 5 次重启后查 Bridge 前台服务、`/v1/health`、`server-ops bridge status`；Termux 侧查 12/12 服务 | 系统更新/清理后白名单可能被重置；**仅 appops/deviceidle 不足以替代 UI 白名单**（已实测） |
| 2 | 省电策略"无限制" | 设置 → 电池 → 应用智能省电 → 找到 Bridge/Termux → 无限制（关闭"智能省电"） | 降低后台被杀概率；决定长稳 | 重启后观察 FGS 是否存活；长跑看进程重启次数 | OEM 可能改回"智能省电"；省电模式/低电量模式会覆盖该设置 |
| 3 | 允许后台弹出 / 锁定后台 | 设置 → 应用 → 权限管理 → 后台弹出界面（允许）；最近任务中锁定 Bridge/Termux | 影响从后台启动 Activity/FGS 的拦截 | 重启 + 从最近任务划掉后再看服务是否恢复 | 版本差异大；部分版本无此开关；锁定后台会被清理工具解除 |
| 4 | 通知权限（重启重置） | 设置 → 通知管理 → 允许通知；`pm grant ... POST_NOTIFICATIONS` | FGS 仍在运行，但通知不可见时用户无法从通知栏确认存活 | 重启后查看通知栏与"正在运行的服务"；`dumpsys` 检查 FGS 状态 | **实测重启后被重置为 ignore**（FGS 仍工作）→ 需要人工再开；用 Console/看门狗兜底提示（[PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md)） |
| 5 | 使用情况访问（重启重置） | 设置 → 应用 → 使用情况访问 → 允许 Bridge；或 `cmd appops set <pkg> GET_USAGE_STATS allow` | 决定 Phase 2 `usage`（前台应用）字段是否有值 | 重启后查 `/api/sysinfo` 的 `usage`/`usage_available` 与 Bridge `/v1/status` | **实测重启后回到 default**，字段为空；需人工/ADB 再授权；属可选字段，不阻塞主链路（[PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md)） |
| 6 | 安装器 UI 自动化 | 走 `adb install` 被 MIUI 安装确认拦截时，用 [miui-adb-install.ps1](../../scripts/adb/miui-adb-install.ps1) 自动点按"继续安装" | 决定换机/升级能否脚本化安装 | 安装后 `pm list packages` 命中、`/v1/health` 可用 | 弹窗文案/Activity 名随版本变化，脚本会失效；**不得**把自动点按当唯一安装路径，保留人工兜底 |
| 7 | QUICKBOOT 厂商广播 | Bridge `BootReceiver` 同时监听 `QUICKBOOT_POWERON`（含 `com.htc.intent.action.QUICKBOOT_POWERON`） | 覆盖部分 ROM 的"快速开机"路径，提高自启成功率 | 重启后看 Bridge 启动日志与 `/v1/health` | 厂商广播非标准；不同 ROM 可能不发；不能作为唯一自启依据，必须保留 `BOOT_COMPLETED` |
| 8 | FBE / 锁屏凭据权衡 | 研究机保持**无锁屏凭据**（无 PIN/图案/密码）；若要设锁屏，接受重启后人工解锁一次 | 无锁屏：FBE 开机即解密，`BOOT_COMPLETED` 正常下发 → 无人值守自启；设锁屏：自启延迟/失效 | 设锁屏后重启，观察 Termux:Boot/服务是否自启；再解锁一次看是否恢复 | 安全降级（设备丢失无锁）必须用户知情；部分 ROM 行为差异；这是运维策略不是可脚本化项 |
| 9 | 禁止卸载系统包 | 系统包只做 `pm disable-user`（可逆）+ 保护名单；**禁止** `pm uninstall` 系统包 | 误删系统必需包会导致 system_server 崩溃/bootloop/RescueParty | 变更后必须重启验证；`pm list packages -d` 核对禁用清单；出现异常按 [08 事故复盘](../../docs/20-server/08-事故复盘与重置重建报告.md) 恢复 | **已发生一次 bootloop 事故**（误停用 ext.services）；恢复靠清数据+备份重建，代价极高（[GRD-002](../../guardrails/GRD-002-no-system-package-uninstall.md)） |
| 10 | 固件冻结 | 关闭自动更新并保持当前固件（`ota_disable_automatic_update` 类设置）；升级前先备份/核对接口 | 避免 OTA 改变 sysfs/属性/权限接口与自启策略 | `settings get` 核对开关；升级后按 §2.8 回归一次 | 失去安全补丁；系统可能强制更新；长期冻结需评估漏洞风险，属用户决策 |

### 3.0 已知重置行为（实测）

| 项 | 重启后行为 | 证据 |
|---|---|---|
| `POST_NOTIFICATIONS` | **重置为 ignore**；FGS 仍运行，仅通知不可见，需人工再开 | [33 §8.3](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) · [PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md) |
| `GET_USAGE_STATS` | **回到 default**；`usage` 字段为空，需人工/ADB 再授权 | [33 §8.3](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) · [PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md) |
| 自启动白名单 | **保持**（release 原地升级/重启后仍生效） | [33 §4.1/§8.3](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) |

### 3.1 本案例实测结论（写入证据）

- **自启动 UI 白名单是硬门槛**：打开后 5/5 debug 重启 + 1/1 release 重启通过；仅 appops/deviceidle 时会失败（[33 §4.1](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)）。
- **权限会被重置**：通知权限重启后 ignore（FGS 仍工作）；使用情况访问重启后回默认（`usage` 空）。这两项已在 [PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md) 沉淀为通用坑。
- **FBE 与锁屏凭据**：保持无锁屏凭据时开机自启实测通过；设锁屏则 `BOOT_COMPLETED` 延迟（[06 §3.4](../../docs/20-server/06-A+优化方案.md) · [08](../../docs/20-server/08-事故复盘与重置重建报告.md)）。
- **系统包卸载是红线**：历史 bootloop 事故根因是误停用系统必需包；此后系统包只 disable 且有保护名单（[04 R-17/R-19](../../docs/10-device/04-风险与回滚.md)）。
- **24h soak 未完成**：以上结论只代表重启矩阵，不代表长期稳定；换机验收必须重跑（[MTH-008](../../methodology/07-validation.md)）。

---

## 4. 其他 OEM 复用要点（保持设备无关）

| OEM / ROM | 私有项重点 | 与小米的关键差异 |
|---|---|---|
| AOSP / Pixel / Nothing / Sony / Motorola | 标准 `BOOT_COMPLETED` + FGS；电池优化设为不优化即可 | 一般无厂商自启动开关；最接近标准 |
| Samsung One UI | 电池 → 后台使用限制 → "从不休眠的应用"；Device care 勿优化 | 名称不同；Knox 影响 Root 方案 |
| OnePlus / OPPO / realme（ColorOS/OxygenOS） | 电池 → 应用电池管理 → 允许后台活动；自启动/关联启动放行 | 后台策略更强，需逐 App 放行 |
| vivo / iQOO（OriginOS） | 自启动管理放行；关闭后台耗电保护 | 部分型号限制更多 |
| Huawei / Honor（EMUI/MagicOS） | 应用启动管理 → 手动管理（允许自启动/关联启动/后台活动）；电池不优化 | Root 通常受限，先确认解锁 |
| 其他通用 Android | 电池优化不限制 + `deviceidle whitelist` + 允许自启 | 以实测为准 |

换机填 profile 时只改 §2.1/§2.3/§2.4 与 §2.6/§2.7；§2.2 标准基线保持通用；**不得把小米菜单名/脚本复制成"通用路径"**。

---

## 5. 维护规则与冻结

1. 本文件是 **CASE-001 的附属证据**，随案例冻结（2026-11-11）：只修事实错误（设置错、链接失效、脱敏），不改写"已实测"结论。
2. 新增/修订 OEM 项必须给证据（版本、日期、验证命令/日志），未验证的写"待验证"。
3. 通用 OEM 方法论写入 [MTH-004](../../methodology/03-server-stack.md)/[MTH-005](../../methodology/04-telemetry-bridge.md)；新踩坑写入 [pitfalls/README.md](../../pitfalls/README.md)；红线写入 [guardrails/README.md](../../guardrails/README.md)。
4. 不得写 token/口令/私钥/序列号/IP/主机名/端口；不得给"卸载系统包/解锁/刷机"建议（见 [GRD-002](../../guardrails/GRD-002-no-system-package-uninstall.md)）。
5. 修改后跑 `python -m toolkit.repurpose validate --strict` 与 `python scripts/dev/check-links.py --strict-anchors`。

---

## 6. 关联

| 入口 | 说明 |
|---|---|
| [CASE-001 案例正文](README.md) | 案例总览、三轨实现、方法论验证 |
| [profile.json](profile.json) | 机器可读设备档案（本 profile 对应设备） |
| [CASE-000 索引](../README.md) | 案例层约定与登记流程 |
| [MTH-004 服务器栈](../../methodology/03-server-stack.md) · [MTH-005 遥测桥](../../methodology/04-telemetry-bridge.md) · [MTH-008 验收](../../methodology/07-validation.md) | 通用方法论 |
| [32 多厂商适配](../../docs/10-device/32-多厂商Android适配与迁移指南.md) | OEM 矩阵与换机清单 |
| [33 Bridge 实施记录](../../docs/50-bridge/33-Android-Bridge-MVP实施记录.md) | 自启/权限实测证据 |
| [06 A+ 优化](../../docs/20-server/06-A+优化方案.md) · [08 事故复盘](../../docs/20-server/08-事故复盘与重置重建报告.md) | FBE/锁屏、debloat 事故 |
| [PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md) · [GRD-002](../../guardrails/GRD-002-no-system-package-uninstall.md) | 权限重置踩坑、系统包红线 |
