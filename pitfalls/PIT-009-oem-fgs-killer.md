---
id: PIT-009
title: OEM 后台清理杀死 FGS
type: pitfall
status: current
audience: human, agent
tags: oem, fgs, autostart, battery-optimization, miui, oneui, coloros
depends: MTH-005
updated: 2026-11-11
agent_hint: 跨 OEM 只保证标准基线 + 人工 profile；appops/deviceidle 单独不足以保活 FGS
severity: S2
domain: bridge
oem: xiaomi, samsung, oppo, vivo, huawei
---

## 症状

- 重启后遥测桥的前台服务没有启动，或启动几分钟后被清理；开机广播被拦截，App 不出现。
- 只做 appops 与 deviceidle 白名单时仍失效；在厂商“自启动管理/电池无限制/允许后台活动”里人工放行后才稳定。
- 不同品牌设置路径与名称不同，无法用同一套脚本覆盖；换机后旧配置直接失效。
- 服务端只看到 `bridge_available=false` 或数据过期，却不知道是 OEM 清理还是 App 崩溃。

## 触发场景

- MIUI/HyperOS、Samsung One UI、ColorOS/OxygenOS、OriginOS、EMUI/MagicOS 等厂商 ROM；
- 开启省电/深度睡眠、长期未打开 App、安装后首次重启；
- 只按 AOSP 文档配置就宣称“已保活”，未做 OEM 白名单；
- 换机/迁移时沿用上一台设备的 profile 脚本。

## 根因

- 厂商在 AOSP 之上增加了自启动管理与后台清理策略，`BOOT_COMPLETED` 与前台服务都受其管控；这些是私有设置，没有公开 API。
- `appops`/`deviceidle` 属标准层，厂商可以忽略或覆盖；“电池优化白名单”不等于“允许自启动”。
- 保活是“标准机制 + OEM 人工配置”的组合，任何单点手段都不充分；换 OEM 必须重新验证。
- 缺少“服务端可见的失联信号”时，问题只能靠用户发现。

## 规避与修复

1. 标准基线（必要不充分）：电池优化不限制 + `deviceidle` 白名单 + `appops RUN_ANY_IN_BACKGROUND allow`，在换机/重启后重放。
2. OEM profile：自启动管理放行、电池策略“无限制”、允许后台弹出/锁定后台（按品牌路径），必须人工一次并录入 profile 文档。
3. 验收：每种 OEM 至少 5 次重启 + 24h soak，记录服务进程存活与健康检查结果，不以一次成功为准。
4. 兜底：前台服务返回粘性 + Alarm/Job 调度 + 用户打开 App 时自愈；不要指望服务端/控制面去拉起 Android App。
5. 监控：服务端暴露 `available/age/last_seen` 并在控制台显示，失联可见并提示“检查手机端自启/权限”，让问题可观测。
6. 文档化：OEM 差异只进 profile，不进核心逻辑；禁止把某个品牌专用脚本当成通用方案。

## 验证

- 5 次重启后服务进程存活、健康检查通过、数据来源正确。
- 24h soak 期间无中断；人为杀进程后能按兜底机制恢复（在允许范围内）。
- 换 OEM 时按矩阵重跑“标准基线 + 人工白名单 + 5 次重启”，并更新 profile。
- 控制台能明确显示失联与“需人工检查”的提示，而不是仅显示空白。

## 关联

- 方法论：[MTH-005 宿主遥测桥](../methodology/04-telemetry-bridge.md)（FGS/自启与降级）
- 护栏：[GRD-012 Agent 行为规则](../guardrails/GRD-012-agent-operating-rules.md)（不越权代操作 Android）
- 同类：[PIT-008 MIUI 权限重置](PIT-008-miui-permission-reset.md)、[PIT-012 厂商安装器交互](PIT-012-oem-installer-ui-automation.md)

## 证据

- 案例实证：[32 多厂商 Android 适配与迁移指南 §3/§4](../docs/10-device/32-多厂商Android适配与迁移指南.md)（OEM 保活矩阵与统一 ADB 基线）
- 案例实证：[33 Bridge MVP 实施记录 §4.1](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)（仅 appops/deviceidle 不足、人工自启动放行后 5/5 通过）
- 案例实证：[28 全栈整体方案规范 §9.4](../docs/00-overview/28-全栈整体方案规范.md)（标准核心 + OEM profile 的分层要求）
- 案例实证：[当前状态 §7](../docs/00-overview/当前状态.md)（OEM 自启动需人工一次、已知限制）
