---
id: CASE-004
title: 一加 / ColorOS OEM 适配 profile（Ace Pro PGP110 预研）
type: oem-profile
status: draft
audience: human, agent
tags: oem-profile, oneplus, coloros, deep-test, autostart, battery, fbe, ota, arb, root-regression
depends: CASE-003, MTH-012, MTH-004, MTH-009, PIT-022, PIT-023, PIT-025, GRD-002, GRD-014, GRD-015
updated: 2026-11-11
agent_hint: 本文件是**公开资料预研**，单项证据等级标为"待实测/社区/官方"；收货后逐项实测再改写结论，不得把社区说法当本机实测。
---

# CASE-004 · 一加 / ColorOS OEM 适配 profile（Ace Pro PGP110 预研）

> 定位：[CASE-003 预研案例](README.md) 的 OEM 侧清单；说明标准 Android 之外、ColorOS/一加需要人工完成或特别注意的项。
> 铁律：**OEM 私有设置没有标准 API**，不承诺全自动；脚本只能辅助；验收以真机重启/实测为准；不得把厂商设置写进核心代码/数据契约。
> 证据等级：本页除标注"官方"外，均为公开资料/社区经验，**未在本机实测**。

---

## 1. 适用范围与前置

| 项 | 内容 |
|---|---|
| 适用 | 一加 Ace Pro（PGP110 / ovaltine），ColorOS 12.1–15，Android 12–15，**专用实验机 + 已授权 Root 轨** |
| 前置 | G-L0..G-L6 通过（[MTH-012 §3](../../methodology/11-root-lab.md)）；固件冻结；救援包就绪；实验机无个人数据 |
| 不适用 | 生产机 haydn（小米/HyperOS）、含个人账号/支付数据的设备、未授权设备、ColorOS 16+ 且 ARB 状态不明 |
| 证据等级 | 官方参数/公告（高）；社区资料（中，未实测）；本机实测（**暂无**） |

---

## 2. 标准 Android 基线（所有 OEM 必做）

| 基线项 | 做法 | 作用 |
|---|---|---|
| 安装 | 标准 `adb install -r`；ColorOS 安装器可能弹确认（见 §3 #4） | 不依赖应用商店 |
| 通知/定位权限 | `pm grant` 通知；按需定位（WiFi 相关） | 前台服务通知/网络字段 |
| 后台白名单 | `cmd appops set <pkg> RUN_ANY_IN_BACKGROUND allow` + `dumpsys deviceidle whitelist +<pkg>` | 降低 Doze 杀进程概率 |
| 电池优化豁免 | 系统"电池优化"设为不优化 | 保活基础 |
| 使用情况访问（可选） | Usage Access（`GET_USAGE_STATS`） | 前台应用字段 |
| 验收 | 5 次重启 + 24h soak（[MTH-008](../../methodology/07-validation.md)） | 唯一可信的"自启成立"证据 |

> 注意：Android 标准基线只保证"系统层不主动杀"，**不保证 ColorOS 厂商层策略**；厂商项必须按 §3 单独处理。

---

## 3. 一加 / ColorOS 私有项与 Root 轨注意项

| # | 项 | 路径 / 命令 | 影响 | 验证方法 | 失效风险 / 证据 |
|---|---|---|---|---|---|
| 1 | 官方解锁入口/深度测试 | 开发者选项 OEM 解锁；一加社区深度测试 APP（新机型）；`fastboot flashing unlock` | 决定 G-L4 能否开始 | 只读核对版本/入口；不点解锁 | 政策随 ColorOS 版本变化；Ace Pro 是否需深度测试**待实测**（[PIT-022](../../pitfalls/PIT-022-oem-unlock-quota.md)） |
| 2 | 自动更新关闭 | 设置 → 关于本机 → 系统更新；关闭自动下载/夜间安装；记录版本 | 防止 OTA 改变解锁/ARB 前提 | `settings get`/系统界面核对；确认无待装更新 | 系统可能强制/弹窗；`.500/.501/.503` 禁止清单（[PIT-023](../../pitfalls/PIT-023-oneplus-arb-hard-brick.md)） |
| 3 | 自启动/后台/省电 | 设置 → 电池/应用 → 自启动管理、后台运行、省电策略（ColorOS 菜单名随版本变化） | 决定重启后服务是否被拉起/被杀 | 5 次重启后查 chroot 服务/端口/健康检查 | 厂商策略可能重置/清理；**待实测** |
| 4 | 安装器拦截 | 走 `adb install` 被"安全检查/继续安装"弹窗拦截时，人工点按或改用系统允许路径 | 决定升级/换机能否脚本化安装 | `pm list packages` 命中、服务健康 | 弹窗文案/Activity 随版本变化；不得把 UI 自动化当唯一安装路径（[PIT-012](../../pitfalls/PIT-012-oem-installer-ui-automation.md)） |
| 5 | 通知权限重置 | `pm grant`/设置 → 通知管理；重启后核对 | 前台服务通知不可见时难确认存活 | 重启后查通知栏/FGS 状态 | 是否重置**待实测**；用看门狗/控制台兜底（参考 [PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md)） |
| 6 | 使用情况访问 | 设置 → 使用情况访问；`cmd appops set GET_USAGE_STATS allow` | 决定前台应用字段 | 重启后查 API 字段 | 是否重置**待实测**；可选字段不阻塞主链路 |
| 7 | FBE / 锁屏凭据 | 实验机保持无锁屏凭据或接受重启后人工解锁 | 有锁屏时 FBE 解锁前 `BOOT_COMPLETED` 延迟→自启失效 | 设锁屏后重启观察服务/自启；再解锁一次 | 安全降级需用户知情；**待实测** |
| 8 | 系统包保护 | 只允许 `pm disable-user` + 保护名单；**禁止** `pm uninstall` 系统包 | 误删导致 bootloop/RescueParty | 变更后重启验证；`pm list packages -d` 核对 | 红线 [GRD-002](../../guardrails/GRD-002-no-system-package-uninstall.md)；不因 Root 放宽 |
| 9 | Root 后指纹/支付/完整性 | 不开启隐藏类模块或按官方/社区兼容方案处理；实验机不登支付账号 | ColorOS 上隐藏类模块可致指纹异常；解锁后完整性/DRM 可能降级 | 指纹录入/支付 App/Play Integrity 只读检测 | 社区证据，**待实测**（[PIT-025](../../pitfalls/PIT-025-root-module-regression.md)） |
| 10 | OTA 与 Root 共存 | OTA 前恢复原厂 boot；KernelSU LKM 可装非活动槽；升级后重跑验收 | OTA 错配→bootloop/Root 失效 | 升级后 5 重启 + Root 状态 + 服务健康 | 见 [MTH-012 §7](../../methodology/11-root-lab.md)；**待实测** |
| 11 | 救援/EDL | 优先 `fastboot flash boot` 原厂镜像；官方全量包；9008 仅最后手段 | 决定硬砖可恢复性 | 3 轮恢复演练 | EDL 工具/loader 来源风险；ARB 熔断后可能失效（[PIT-024](../../pitfalls/PIT-024-flash-tool-supply-chain.md)） |
| 12 | 充电/温控 | 7×24 插电时关注电池温度/健康；充电上限节点若可写需先验证 | 长期插电电池膨胀/热降频 | `dumpsys battery`/sysfs 观测；24h soak | 不关闭温控；按 [GRD-008](../../guardrails/GRD-008-power-thermal-safety.md) |

---

## 4. 已知/待验证的重置行为

| 项 | 预期行为 | 证据 |
|---|---|---|
| 通知权限 | 可能重启后重置或保持（**待实测**） | 参考小米案例 [PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md) 的通用机制，不套用结论 |
| 使用情况访问 | 可能回默认（**待实测**） | 同上 |
| 自启动/后台白名单 | ColorOS 可能清理/重置（**待实测**） | 需 5 次重启矩阵验证 |
| Root 状态 | LKM 模式下 Root 在重启后仍可用；OTA 后可能失效（**待实测**） | KernelSU 官方文档（高） |
| ARB 状态 | 触发后不可逆（**待实测本机是否触发**） | [PIT-023](../../pitfalls/PIT-023-oneplus-arb-hard-brick.md) |

---

## 5. 收货与 Root 后验收步骤

1. 只读采集：`adb shell getprop` 身份/启动/内核字段装入 profile（`source.mode=adb`），不升级、不解锁。
2. 核对 ColorOS 版本、build 后缀、安全补丁；确认不在 ARB 禁止清单。
3. 确认无待装系统更新；关闭自动更新并记录。
4. 救援包：原厂 boot/init_boot、全量包、哈希清单、两条数据线、第二台电脑（G-L1）。
5. 官方通道解锁（G-L4）；解锁后先正常开机 1 次，不装 Root。
6. Root：KernelSU LKM 为首选（G-L5）；零模块 24h；su 最小授权；记录 Root 状态（G-L6）。
7. 自启/保活实测：5 次重启矩阵（服务、端口、健康检查、Root 存活性）。
8. 24h soak + 温度/电池/资源观测；异常即回滚。
9. 救援演练 3 轮（制造可恢复故障→恢复→复验）。
10. 系统更新（若将来必须）→ 恢复原厂镜像→升级→重 Root→重跑 5 重启/soak/演练。

---

## 6. 关联

| 入口 | 说明 |
|---|---|
| [CASE-003 预研案例](README.md) | 决策、证据摘要、阶段计划、风险登记 |
| [profile.json](profile.json) | 机器可读档案（documented） |
| [MTH-012](../../methodology/11-root-lab.md) · [MTH-004](../../methodology/03-server-stack.md) · [MTH-008](../../methodology/07-validation.md) | Root 轨/服务器栈/验收 |
| [GRD-002](../../guardrails/GRD-002-no-system-package-uninstall.md) · [GRD-008](../../guardrails/GRD-008-power-thermal-safety.md) · [GRD-014](../../guardrails/GRD-014-firmware-freeze-ota.md) · [GRD-015](../../guardrails/GRD-015-root-lab-controlled.md) | 红线 |
| [PIT-008](../../pitfalls/PIT-008-miui-permission-reset.md) · [PIT-012](../../pitfalls/PIT-012-oem-installer-ui-automation.md) · [PIT-022](../../pitfalls/PIT-022-oem-unlock-quota.md) · [PIT-023](../../pitfalls/PIT-023-oneplus-arb-hard-brick.md) · [PIT-024](../../pitfalls/PIT-024-flash-tool-supply-chain.md) · [PIT-025](../../pitfalls/PIT-025-root-module-regression.md) | 风险证据 |
| [haydn K40 Pro OEM profile](../haydn-k40pro/oem-profile.md) | 小米实例（换机对比，不照抄设置名） |
