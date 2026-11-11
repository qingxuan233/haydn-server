---
id: PIT-005
title: 无 Root 读不到全局 proc 指标
type: pitfall
status: current
audience: human, agent
tags: procfs, telemetry, null-semantics, no-root, metrics
depends: MTH-005
updated: 2026-11-11
agent_hint: 指标读不到时输出 null + 能力声明，绝不填 0；面板要显示来源与新鲜度
severity: S3
domain: device
---

## 症状

- CPU 使用率、网络累计等全局指标长期缺失或恒定不变：`/proc/stat` 与 `/proc/net/dev` 读不到，或在 proot 内取到的值与真实负载无关。
- 普通 App / shell 采集器返回 0 或空字符串，面板把缺失画成“0% 使用/0 流量”，趋势图与告警因此失真。
- proot 内 `top`、`uptime` 显示的是假数据，用它们判断负载会得出错误结论。
- 同一套采集逻辑在有 Root/特权 provider 的设备上结果正常，换到无 Root 设备就“数据不完整”。

## 触发场景

- 在无 Root 设备上采集系统级指标，或把 Android 当普通 Linux 直接读 `/proc`；
- 远程终端/容器（proot）内使用 `top`/`uptime`/`vmstat` 类工具；
- 服务端把“字段缺失”当成 0 参与计算、绘图、告警；
- 升级/重启后权限变化，采集器未重新探测能力。

## 根因

- Android 对 `/proc` 的部分文件做了访问限制（App/shell 读不到全局统计），这是平台安全设计，不是权限配置错误。
- proot 是用户态 ptrace 重写路径，`/proc/stat` 等被替换成固定/近似值，容器内的“全局指标”本质上不可信。
- 无 Root 时没有特权读全局 counters 的通道；App 级 API（如网络累计）只能拿到自身或有限范围数据。
- 数据契约没定义“不可得”的表达方式，实现者用 0 兜底，掩盖了真实的信息缺口。

## 规避与修复

1. 统一 null 语义：不可得/无权限/厂商隐藏一律输出 `null`，禁止用 0 或空对象冒充；文档与 schema 同步定义。
2. 采集分层：先取 App 可访问字段（电池、内存、磁盘、屏幕、网络累计等），全局 CPU/网络原始字节明确标注为“不可得”。
3. 每个字段集带来源与新鲜度（`source` / `age` / `capabilities`）；缺失时由服务端决定回退或留空，不回退成伪造值。
4. UI 与告警只基于“可验证可得”的指标：服务健康、温度、内存、磁盘、重启计数；不要用不可得指标做核心告警阈值。
5. 确需精确全局值时，再引入特权 provider（Shizuku/root helper）并明确授权、白名单、审计；在此之前不要承诺。
6. 把能力探测纳入启动自检与换机验收：每次系统升级/换机后重新确认字段可得性。

## 验证

- 在无 Root 设备上请求状态：缺失字段明确为 `null`，响应中带能力声明与来源，不出现伪造 0。
- 面板对缺失字段显示“系统限制/不可得”，不画 0 值曲线；告警不因缺失字段误报。
- 有/无特权 provider 两种模式下，字段来源标注正确，切换不产生脏数据。
- 抽查可验证字段（电池、温度、内存等）与系统读数一致。

## 关联

- 方法论：[MTH-005 宿主遥测桥](../methodology/04-telemetry-bridge.md)（数据契约与 null 语义）
- 护栏：[GRD-013 不伪造验收](../guardrails/GRD-013-no-fake-acceptance.md)（缺数据不等于通过）
- 同类：[PIT-008 MIUI 权限重置](PIT-008-miui-permission-reset.md)、[PIT-006 容器内核能力缺失](PIT-006-no-user-ns-containers.md)

## 证据

- 案例实证：[02 可行性分析 §13.1](../docs/10-device/02-可行性分析.md)（实测 `/proc` 与 battery sysfs 权限限制、cgroup 形态）
- 案例实证：[当前状态 §7](../docs/00-overview/当前状态.md)（无 Root 硬边界与不可得字段清单）
- 案例实证：[28 全栈整体方案规范 §6.2/§7.2](../docs/00-overview/28-全栈整体方案规范.md)（null 语义、来源与新鲜度要求）
- 只读引用：[17 研究平台环境构建手册 §9](../docs/20-server/17-研究平台环境构建手册.md)（proot 假数据与监控限制）
