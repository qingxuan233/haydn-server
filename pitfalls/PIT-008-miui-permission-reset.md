---
id: PIT-008
title: MIUI 重启重置通知/用量权限
type: pitfall
status: current
audience: human, agent
tags: permission-reset, notifications, usage-stats, fgs, miui
depends: MTH-005
updated: 2026-11-11
agent_hint: 重启后通知不可见/usage 字段为空是预期重置，按能力降级展示并给人工恢复步骤
severity: S3
domain: bridge
oem: xiaomi
---

## 症状

- 重启或 APK 原地升级后，遥测桥的前台服务仍在运行、健康检查正常，但前台通知不可见；`usage_foreground` 为空，控制台相关卡片缺失。
- 重新授权后字段恢复，下一次重启又回到默认；形成“重启→字段消失→手动修→再消失”的循环。
- 若巡检把“可选字段缺失”判为服务故障，会产生误报与无意义的重启。
- 通知权限状态为 ignore，但 FGS 不受影响，容易被误以为“权限没问题”。

## 触发场景

- HyperOS/MIUI 设备重启、APK `install -r` 升级、厂商安全中心策略更新；
- 用户/ADB 授权“使用情况访问”后没有持久化方案；
- 验收脚本只看单个可选字段是否非空，未区分“权限重置”与“服务故障”。

## 根因

- 厂商安全中心在重启/更新时重置 appops 与特殊访问权限；`GET_USAGE_STATS` 属于特殊访问（AppOps），`POST_NOTIFICATIONS` 属运行时权限但被厂商策略改写。
- FGS 的存活与通知的可见性是解耦的：通知被重置为 ignore 时 FGS 仍在跑，只是用户看不到。
- 数据契约未把“可选字段/权限状态”建模为可空能力，导致实现层用“非空”当健康判据。

## 规避与修复

1. 把权限重置当作**预期行为**：每次重启/升级后的验收矩阵都检查这两项，并记录状态。
2. 数据契约层：usage/notification 字段允许为空/不可得，响应中带 capability 标记；UI 显示“权限被系统重置，需重新授权”。
3. 能脚本化的部分自恢复（通知权限、usage 的 appops 授权等）；不能自动的给出明确的人工操作步骤（系统设置路径），不要让 Agent 猜。
4. 健康检查只看 FGS 进程与主健康端点，不把可选字段缺失判为故障；主链路只依赖基础字段。
5. 在 OEM profile 记录重置行为、恢复步骤与验收结果；换机时作为必查项。
6. 降低依赖：可选字段只作为增强，缺字段时 Console 标注来源与能力，不影响服务与告警。

## 验证

- 连续 3 次重启：每次记录通知状态与 usage 字段；确认与预期一致（重置或保持）。
- 重新授权后 usage 恢复非空；FGS 全程存活、健康检查 200。
- Console 在字段缺失时显示“权限/能力缺失”提示而不是报错；告警无误报。
- 巡检/恢复脚本重复执行幂等，不产生权限副作用。

## 关联

- 方法论：[MTH-005 宿主遥测桥](../methodology/04-telemetry-bridge.md)（可选字段与 null/能力语义）
- 护栏：[GRD-013 不伪造验收](../guardrails/GRD-013-no-fake-acceptance.md)（缺字段不等于通过）
- 同类：[PIT-009 OEM 清理 FGS](PIT-009-oem-fgs-killer.md)、[PIT-005 无 Root 指标缺失](PIT-005-no-root-proc-metrics.md)

## 证据

- 案例实证：[33 Bridge MVP 实施记录 §8.3](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)（release 安装/重启后权限重置实测）
- 案例实证：[03 操作手册 §2.3](../docs/20-server/03-操作手册.md)（重启后需重放的权限项与处理）
- 案例实证：[32 多厂商适配 §3](../docs/10-device/32-多厂商Android适配与迁移指南.md)（当前设备权限状态与换机复核提示）
- 案例实证：[当前状态 §5/§7](../docs/00-overview/当前状态.md)（Bridge 权限重置与已知限制）
