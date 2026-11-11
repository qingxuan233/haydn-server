---
id: GRD-001
title: 默认不 Root、不刷机、不解锁 Bootloader
type: guardrail
status: current
audience: human, agent
tags: root, bootloader, flash, default-route, authorization
depends: MTH-002, MTH-007
updated: 2026-11-11
agent_hint: 遇到 Root、解锁、刷机、改系统分区的请求先停下，要求风险评估结论与用户明确授权；未授权一律拒绝执行。
severity: blocker
scope: device
---

# GRD-001 · 默认不 Root、不刷机、不解锁 Bootloader

> 默认路线是 A（Termux + proot，无 Root）。B/C/D 路线仅在设备风险评估通过且用户明确授权后，才允许进入方案设计与评审——授权不等于可直接执行。

## 红线（MUST NOT）

1. **R1** 未取得「风险评估通过 + 用户明确授权」前，**MUST NOT** 执行解锁 Bootloader、刷机、刷入 Magisk/KernelSU/自定义内核、改写 boot/system/vendor 分区或关闭 AVB 验证。
2. **R2** **MUST NOT** 把 system/priv-app/Device Owner 当作提权捷径；不得安装系统应用、不得申请设备所有者、不得绕过 OEM 的禁用与权限限制。
3. **R3** **MUST NOT** 使用非官方解锁通道、付费解锁、漏洞利用或第三方工具绕过厂商解锁政策；不得在含个人数据的主力设备上尝试。
4. **R4** **MUST NOT** 在授权范围外"顺手"做高风险动作（同时升级固件、改分区、清数据等）；一次只做被批准的一件事。
5. **R5** **MUST NOT** 把 Root 当作所有问题的默认答案：容器、原生 Linux、系统级调优、特权遥测都需要各自验证，Root 不等于可用。

## 为什么（风险与案例）

- 解锁通常触发 userdata 擦除：照片、聊天、应用数据不可恢复；还会破坏验证链、影响 Play Integrity、银行类 App 与保修。
- 多个国行 OEM 的官方解锁通道已关闭，非官方路径的诈骗与变砖风险高，属于典型的"高成本低收益"路线（见 PIT-010）。
- 系统分区、内核与 OTA 的耦合度高：一次刷写失败可能进入不可在线修复的 bootloop，而恢复往往意味着清数据重建。
- 案例实证：[02 可行性分析](../docs/10-device/02-可行性分析.md)、[04 风险与回滚](../docs/10-device/04-风险与回滚.md)、[31 拍板与 Root 路线](../docs/10-device/31-拍板事项决策分析与Root升级路线.md)；案例最终以"锁定 + 无 Root + A+ 优化"稳定运行。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 默认走 A/A+：普通 App + Termux + proot + ADB 维护面，全链路不需要 Root。
- **MUST** 确需 B/C/D 时先完成 [MTH-002 评估](../methodology/01-assessment.md) 与门禁：数据备份、解锁可行性、救砖路径、时间成本、用户书面同意，并记录决策与回滚。
- **SHOULD** 把特权能力设计为可选项（capabilities/source/privileged 字段），主链路不依赖特权 provider。
- **MAY** 在专用研究机、完成备份与救援演练、且用户批准后，按 [MTH-003 路线图](../methodology/02-roadmap.md) 分阶段验证。

## 检查方式（Agent 可执行）

```bash
adb shell getprop ro.boot.verifiedbootstate
adb shell getprop ro.boot.flash.locked
adb shell getprop ro.debuggable
adb shell pm list packages | grep -E 'magisk|kernelsu|apatch'
```

- 人工核对：本次变更有无用户明确授权记录、风险评估链接、回滚路径；无授权记录即判红线违规。
- 人工核对：是否安装或计划安装 system/priv-app、Device Owner、特权 helper；有则默认拒绝，除非有独立评审。
- 人工核对：本次改动的脚本/命令是否含 fastboot flash/erase、解锁工具、非官方解锁服务调用。

## 关联

- 踩坑：[PIT-010 国行官方解锁关闭](../pitfalls/PIT-010-cn-oem-unlock-closed.md)、[PIT-006 Root 不等于容器可用](../pitfalls/PIT-006-no-user-ns-containers.md)
- 护栏：[GRD-004 变更前备份](GRD-004-backup-before-change.md)、[GRD-005 分级确认](GRD-005-tiered-ops-confirmation.md)、[GRD-012 Agent 行为](GRD-012-agent-operating-rules.md)
- 方法论：[MTH-002 评估与决策](../methodology/01-assessment.md)、[MTH-003 路线图](../methodology/02-roadmap.md)、[MTH-007 安全](../methodology/06-security.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)
