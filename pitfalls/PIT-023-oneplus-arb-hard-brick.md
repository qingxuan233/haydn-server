---
id: PIT-023
title: 硬件级防回滚（ARB/e-fuse）触发后降级即硬砖，EDL 也救不回
type: pitfall
status: current
audience: human, agent
tags: arb, anti-rollback, e-fuse, coloros, oneplus, hard-brick, edl, downgrade
updated: 2026-11-14
agent_hint: 解锁/root 设备一律冻结固件；任何降级、刷旧第三方 ROM、刷旧全量包的念头先停：先查 ARB 与版本后缀。
severity: S1
domain: boot
oem: oneplus
---

# PIT-023 · 硬件级防回滚（ARB/e-fuse）触发后降级即硬砖，EDL 也救不回

> 证据等级：**公开报道 + 社区/厂商公告；本项目未实测**。适用于一加/OPPO ColorOS 与后续可能的 OxygenOS/其他 OEM。

## 1. 症状

```text
- 已升级到某批 ColorOS 16.0.3.500/.501/.503 构建后，尝试降级/刷旧第三方 ROM：
  设备直接无法启动（硬砖）；
- 传统 EDL/9008、第三方救砖工具也无效，因为电子熔丝已烧断、软件无法重置；
- 只能更换主板/整机。
影响范围：设备永久不可恢复 + 全部数据/服务损失。
```

**触发场景**：设备/ROM — 已报道一加 13/13T（16.0.3.501）、一加 15（16.0.3.503）、一加 Ace 5/Ace 5 Pro（16.0.3.500），Find X8、一加 11/12 有后续风险，Ace Pro 是否/何时引入**待验证**；触发动作 — 安装含 ARB 的构建后刷入更旧官方固件/旧第三方 ROM/旧全量包；频率 — 触发后降级必现硬砖。

## 3. 根因

- 一加在部分 ColorOS 16 构建中引入硬件级 Anti-Rollback（ARB）：安装时烧断主板 e-fuse，把 CPU/XBL 安全版本计数器升级；该状态不可软件回退。
- ARB 属于 Verified Boot/安全启动体系的一部分，用于禁止降级到更旧、更不安全的固件；与软件层"禁止降级"不同，物理熔丝一旦烧断无法重置。
- 一旦 ARB 生效，旧镜像/旧 ROM 会在启动验证处失败并可能直接硬砖；EDL/9008 依赖的 loader/授权也被"熔断"策略限制，无法修复硬件计数器。

## 4. 规避与修复

```text
规避（事前）：
1) 解锁/Root 前冻结固件（关闭自动更新），记录 build 后缀与安全补丁；
2) 把 .500/.501/.503 等已知 ARB 批次列入禁止清单；收到 OTA 先查是否命中；
3) 只在"解锁 → Root → 验收"窗口内保持同一构建；不降级、不刷旧第三方 ROM；
4) 救援包只准备"同版本或更新"的官方全量包；旧包可能触发 ARB。
修复（事后）：
- 若已硬砖：只能走官方售后/换主板；不要反复尝试旧包/EDL（可能扩大损失）；
- 若尚未熔断但误装了新构建：保持该构建，不降级；重新评估解锁与 Root 方案。
```

## 5. 验证

```bash
# 只读核对版本与安全状态（禁止用于降级前"试试看"）
adb shell getprop ro.build.fingerprint
adb shell getprop ro.build.version.security_patch
adb shell getprop ro.boot.verifiedbootstate
adb shell getprop ro.boot.flash.locked
```

人工核对：版本号后缀是否命中 ARB 批次；厂商公告/社区熔断报告；OFP/全量包版本与设备当前版本的新旧关系（**旧包禁止**）。

## 6. 关联

- 护栏：[GRD-014 固件冻结](../guardrails/GRD-014-firmware-freeze-ota.md) · [GRD-015](../guardrails/GRD-015-root-lab-controlled.md)；方法论：[MTH-012 §7/§8](../methodology/11-root-lab.md)；案例：[一加 Ace Pro 预研](../cases/ace-pro-pgp110/README.md)；同类：[PIT-017 只有快照没有回滚](PIT-017-snapshot-without-rollback.md)

## 7. 证据

- Android Authority 2026-01-19 报道（ARB 机型与版本；外部资料未入库）：13/13T/15/Ace 5 系列；EDL 失效。
- 安兔兔 2026-01-20 报道（e-fuse/计数器/救砖失效；外部资料未入库）：中文细节；官方降级包撤回。
- 社区 OTA/熔断分析（公开仓库文章；外部资料未入库）：9008 免授权被熔断的机制分析；未实测。
