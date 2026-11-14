---
id: ADR-0007
title: 行数余量预警采用 advisory 级，不改变 validate --strict 与 preflight 的失败语义
type: adr
status: accepted
audience: human, agent
tags: documentation, capacity, doc-policy, validate, preflight, advisory, adr
depends: ADR-0002, ADR-0006, MTH-015, MTH-017
updated: 2026-11-14
agent_hint: 改 doc-policy 数值或 validate 严重级别前读本文；余量预警是 advisory，不阻断质量门。
---

# ADR-0007 · 行数余量预警的级别与失败语义

## 状态

accepted（2026-11-14）。关联 [ADR-0002](0002-protocol-versioning-and-regression.md)、[ADR-0006](0006-mth-009-mth-002-split.md)、[MTH-015](../methodology/15-archive-and-context-budget.md)、[MTH-017](../methodology/17-expansion-and-cli-contract.md)。

## 背景

- 现有容量规则只有"超过上限即失败"（`DOC_LINES`）与协议档位（AGENTS 200/320 的 `protocol_tier`，仅作指标）。多篇文档在触限前才被发现（MTH-009 余 16、MTH-002 余 23、MTH-013 余 10），拆分往往与功能变更混在同一批，风险高。
- 需求：在"距上限不足 15 行"时由 `validate` 提前报出，但不让 `preflight` 变红；同时不得弱化任何既有检查。
- 约束：`validate --strict` 的既有语义是"任何 error 或 warning 均失败"；如果把预警做成 warning，会让全仓立刻红，或被迫临时改文档凑数。

## 决策

1. **新增严重级别 `advisory`**：只打印、计入 `advisory_count`，**不参与** `failed` 判定（`failed = 有 error，或 strict 且有 warning`）；`preflight` 退出码不受影响。
2. **阈值放在 doc-policy**：新增 `line_limit_margin.warning_within`（当前 15），由 `validate_doc_policy` 读取；不新增第二份数字来源。
3. **触发条件**：文件行数 `≤ 上限` 且 `上限 - 行数 < warning_within` 时报 `DOC_LINES_MARGIN`；超过上限仍走既有 `DOC_LINES`（error/warning 依 strict），语义不变。
4. **配套契约**：`repurpose.validation.v1` 增加 `advisory_count`；人类摘要增加"预警：N（不阻断）"；`preflight` 步骤摘要增加 `advisories=N`；`toolkit/README` 与 MTH-015 §5 同步说明。
5. **处置要求**：预警出现时必须在 backlog 登记拆篇/精简计划；本轮不阻断，但不得在同一文档继续新增内容使其触限。连续两轮未处理，由维护者按超限处理。
6. **不弱化检查**：`DOC_LINES`、`DOC_NAMING`、`PROTOCOL_*`、backlog/归档等既有 error/warning 的级别与判定逻辑一律不改；新增测试覆盖"advisory 不使 strict 失败"与"余量恢复后预警消失"。

## 后果

- 正面：触限前获得可见提示；质量门保持全绿；无需为通过校验而临时删规则。
- 负面/风险：`advisory` 可能被忽略；由 backlog 登记要求与"连续两轮"规则兜底。报告消费方若只读 `error_count`/`warning_count`，仍能看到 `advisory_count`。
- 迁移：无需迁移；旧报告缺 `advisory_count` 时按 0 处理。
- 回滚：删除 doc-policy 的 `line_limit_margin` 段即可停用预警（代码在阈值 ≤0 时不报），不影响其他检查。

## 备选方案

| 方案 | 利 | 弊 | 结论 |
|---|---|---|---|
| A. 新级别 advisory，不阻断 | 提前预警且不红 | 多一个级别概念 | 采纳 |
| B. 用 warning（strict 失败） | 无新概念 | 全仓立即红，逼出凑数修改 | 否决 |
| C. 只写进 `checked` 指标 | 零风险 | 不进入摘要，容易被忽略 | 否决 |
| D. 放宽上限 | 零改动 | 掩盖膨胀 | 否决 |
