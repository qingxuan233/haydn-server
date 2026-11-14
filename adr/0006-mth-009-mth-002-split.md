---
id: ADR-0006
title: MTH-009/MTH-002 拆分：交接与评估口径留原篇，扩展契约与执行清单各自成篇
type: adr
status: accepted
audience: human, agent
tags: documentation, capacity, single-source-of-truth, mth-002, mth-009, mth-017, mth-018, adr
depends: ADR-0002, ADR-0004, ADR-0005, MTH-009, MTH-002
updated: 2026-11-14
agent_hint: 改交接协议/评估决策读 MTH-009/MTH-002；改扩展 SOP/变更传播/CLI 契约读 MTH-017；改评估执行/OEM/失败处理读 MTH-018。
---

# ADR-0006 · MTH-009 与 MTH-002 拆分

## 状态

accepted（2026-11-14）。取代：无。关联 [ADR-0002](0002-protocol-versioning-and-regression.md)、[ADR-0004](0004-mth-011-split.md)、[ADR-0005](0005-mth-013-split.md)、[MTH-009](../methodology/08-agent-handoff.md)、[MTH-002](../methodology/01-assessment.md)、[MTH-017](../methodology/17-expansion-and-cli-contract.md)、[MTH-018](../methodology/18-assessment-execution.md)。

## 背景

- `methodology/08-agent-handoff.md`（MTH-009）达 284/300 行、余 16 行；`methodology/01-assessment.md`（MTH-002）达 277/300 行、余 23 行，均已进入"再补一条规则即触限"的状态。
- 两篇正文都混装了**低频口径**与**高频执行细则**：MTH-009 前半是交接协议（分层/读序/ID/生命周期/DoD），后半是七类扩展 SOP、变更传播与 CLI 契约；MTH-002 前半是评估流程/决策表/门禁/输出契约，后半是命令顺序、OEM 清单、产出物、失败处理与示例。
- 约束：拆分不得删规则、不得复制抄写；全仓引用、索引、manifest、ADR 台账与 backlog 必须同步；不得弱化任何既有检查。

## 决策

1. **MTH-009 拆分边界**：[MTH-009](../methodology/08-agent-handoff.md) 保留分层/权威、目录职责、启动读序、front matter/ID、任务生命周期与 DoD 摘要、禁止事项、backlog 指针、10 分钟清单与维护；新增 [MTH-017](../methodology/17-expansion-and-cli-contract.md)《扩展 SOP、变更传播与工具契约》，承接原 §7–§9（七类扩展 SOP、变更传播矩阵、统一 CLI 契约）。
2. **MTH-002 拆分边界**：[MTH-002](../methodology/01-assessment.md) 保留输入/输出、device-profile schema、评估流程、路线决策表、门禁规则与 `assess` 输出契约；新增 [MTH-018](../methodology/18-assessment-execution.md)《评估执行、OEM 清单与失败处理》，承接原 §7–§12（计划与命令、OEM 现场清单、产出物、失败处理、脱敏示例、相关入口）。
3. **单一事实源**：被移出的正文只保留在新篇；原篇只留一段"见 MTH-017/MTH-018"的定位与链接，不复制细则。路线判定口径仍唯一定义在 MTH-002，扩展/契约规则仍以 MTH-017 为准。
4. **编号与引用**：MTH-009 自身 §10–§13 前移重编号为 §7–§10（§1–§6 不变）；MTH-002 原 §7–§12 移除后以 §7 定位段收尾（§1–§6 不变）。全仓引用按新篇更新：AGENTS、README、methodology/README、MTH-000/001/003/004/005/006/007/009/010/013/015、toolkit/README；历史 ADR 与已归档 CHANGELOG 不改写（文件仍存在）。
5. **版本与回归**：属方法论文档结构性分流，红线、权威顺序与门禁不变；按 ADR-0002 跑 `preflight`（index + validate --strict + unittest + check-links），不修改任何检查器与测试断言。

## 后果

- 正面：两篇回到健康档（MTH-009 约 200 行、MTH-002 约 180 行；MTH-017/MTH-018 约 110–120 行）；交接高频路径更短，扩展与执行细则可独立演进。
- 负面/风险：扩展与评估执行规则各多一层跳转；边界漂移会重新重复，由各篇"权威边界"段与 `preflight` 兜底。
- 迁移：旧引用 `MTH-009 §7–§9` → MTH-017 §1–§3；`MTH-009 §10–§13` → §7–§10；`MTH-002 §7–§12` → MTH-018 §1–§6；`MTH-002 §5.3.1`、`§4` 等编号不变。
- 回滚：将 MTH-017 合回 MTH-009、MTH-018 合回 MTH-002 并恢复原编号；不影响工具与校验器。

## 备选方案

| 方案 | 利 | 弊 | 结论 |
|---|---|---|---|
| A. 两篇各拆出一篇（MTH-017/MTH-018） | 职责单一、四篇均留余量 | 多两层跳转 | 采纳 |
| B. 压缩原文到 ≤260 行 | 不增文件 | 必然删规则或丢证据 | 否决 |
| C. 放宽 doc-policy 单文件上限 | 零改动 | 掩盖膨胀，违背容量治理 | 否决 |
