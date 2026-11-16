---
id: ADR-0009
title: 实验设备固件与内核冻结：不刷内核、不升级固件（KernelSU 保持上游最新）
type: adr
status: accepted
audience: human, agent
tags: firmware, kernel, kernelsu, ota, freeze, single-slot, arb, adr
depends: ADR-0002, GRD-014, PIT-023, MTH-012
updated: 2026-11-16
agent_hint: 实验设备 PGP110 固件/内核冻结：KernelSU 已 v3.3.1（上游最新，无需动作）；Android 内核 5.10.236 属 OEM 固件，单独"更新内核"= 刷新固件 boot 镜像；因单槽（B 槽 liblp 元数据已被覆盖、数据区 99.3% 被 A 覆盖）+ ARB 硬砖风险 + 冻结决定，明确**不刷**。需要重新评估时先读本文"复审触发点"。
---

# ADR-0009 · 实验设备固件与内核冻结（不刷内核）

## 状态

`accepted`（2026-11-16，用户选择"不刷内核"）。取代：无。修订：R1 2026-11-16 初版（用户否决刷固件/第三方内核后定稿）。

## 背景

**已核验事实**（2026-11-16，设备侧只读）：

- Android 内核：`5.10.236-android12-9-o-g55571f3ffcfa #1 SMP PREEMPT Sat Feb 28 09:56:13 UTC 2026`；`ro.build.version.release=15`、安全补丁 `2026-07-01`、fingerprint `OnePlus/PGP110/OP5551L1:15/AP3A.240617.008/S.24910f0-1b2e9-1b2e8:user/release-keys`。
- KernelSU：`su -v` = `3.3.1:KernelSU`；GitHub `tiann/KernelSU` 最新 release = **v3.3.1**（2026-10-12 发布）→ **已是上游最新，无升级动作可言**。
- 分区姿态：当前活动槽 `_a`；B 槽 data 区已被 A extents 覆盖 99.3%，且 `fastbootd` 逻辑分区写会覆盖 metadata slot 1（见 [CASE-003 §6.7](../cases/ace-pro-pgp110/execution-log.md)）。
- 系统更新已按用户决定关闭（自动下载=关闭、夜间自动更新=关闭、`com.oplus.ota` disable-user），见同文 §6.8。

**关键约束**：Android 内核随 OEM 固件发布，**没有独立的内核升级通道**。所谓"更新内核到最新"在本机只有两条路径：刷入更新官方固件的 `boot`/整包（OTA 级写操作），或刷开发者自编译/第三方内核（需匹配 KMI 5.10 并自行承担 bootloop）。

## 决策

**接受"固件与内核冻结"**：保持 ColorOS 15.0.0.1901(CN01C20P01)、内核 5.10.236、安全补丁 2026-07-01、KernelSU v3.3.1；**不刷入任何更新固件或第三方内核**。用户 2026-11-16 明确选择"不刷内核"。

## 后果

**正向**：不触发 [PIT-023](../pitfalls/PIT-023-oneplus-arb-hard-brick.md) 的 ARB 回滚硬砖路径；不触碰单槽约束下的非激活槽元数据；无需重新完成"解锁→Root→5/5 重启→救援演练"全链；已验证的 chroot/supervisord/DSH 自启链保持稳定。

**负向（必须如实记录）**：

- 上游安全补丁停在 2026-07-01；内核层漏洞无法通过常规更新修复。补偿手段限于：仅 loopback/局域网暴露（[GRD-007](../guardrails/GRD-007-network-least-exposure.md)）、公网只经控制台网关、无系统包卸载、ADB 维护后关闭。
- 若某天必须获得新内核特性或修补，只能整机固件升级 → 需重走 GRD-014 全流程（备份→官方 OFP→维护窗口→重 Root→全量验收），且需处理单槽/ARB 风险。

## 备选方案（已评估、未采用）

| 方案 | 未采用原因 |
|---|---|
| 刷入最新官方固件（含新内核） | 与用户"冻结固件、关闭更新"决定冲突；单槽姿态下重启切槽有失败风险；需维护窗口与重新授权 |
| 刷第三方/自编译内核 | 需匹配 KMI 5.10 并自行解决 bootloop；可能破坏现有 KernelSU 补丁 boot 与模块自启链；收益（"内核版本更新"）不抵风险 |
| 只升级 KernelSU | 无动作：已是 v3.3.1（上游最新） |

## 复审触发点

出现以下任一条时重新评审本文（而不是直接执行）：

1. 官方发布针对 KMI 5.10 且与当前固件兼容的**安全**更新（非大版本），且 ARB index 未递增；
2. 用户明确给出维护窗口并重新书面授权刷机；
3. 出现必须依赖新内核能力才能闭环的故障；
4. KernelSU 发布需要配套新内核的重大安全修复（届时评估"仅更新 KSU 补丁 boot"的可行性，仍属刷 boot 级写操作，需授权）。
