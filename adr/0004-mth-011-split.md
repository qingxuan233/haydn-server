---
id: ADR-0004
title: MTH-011 拆分：生命周期归 MTH-011，归档/预算/机检归 MTH-015
type: adr
status: accepted
audience: human, agent
tags: documentation, capacity, single-source-of-truth, mth-011, mth-015, adr
depends: ADR-0002, ADR-0003, MTH-011
updated: 2026-11-14
agent_hint: 改归档/状态段/阅读预算/机检上限读 MTH-015；改归属/命名/索引/ADR/联动读 MTH-011；两篇不得互相抄写。
---

# ADR-0004 · MTH-011 拆分

## 状态

accepted（2026-11-14）。取代：无。关联 [ADR-0002](0002-protocol-versioning-and-regression.md)、[ADR-0003](0003-agents-capacity-split.md)、[MTH-011](../methodology/10-document-lifecycle.md)、[MTH-015](../methodology/15-archive-and-context-budget.md)。

## 背景

- `methodology/10-document-lifecycle.md` 达 299/300 行，逼近 [doc-policy](../toolkit/schema/doc-policy.json) 的 methodology 单文件硬上限；继续修订已无余量。
- 原文混装两类职责：**文档归属/命名/索引/ADR/联动**（长期稳定）与 **CHANGELOG 窗口/状态段/阅读预算/机器校验**（随工具与上下文策略演进）。两类变化的触发频率与读者不同，混在一篇导致相互挤占。
- 约束：拆分不得删规则、不得复制抄写；引用、索引、manifest 与 backlog 必须同步；不得弱化任何既有检查。

## 决策

1. **拆分边界**：[MTH-011](../methodology/10-document-lifecycle.md) 保留《文档生命周期、归属、命名与变更联动》（索引四表、记录边界、命名、ADR、联动矩阵、一次性产物、知识债）；新增 [MTH-015](../methodology/15-archive-and-context-budget.md)《归档、上下文预算与机器校验》（CHANGELOG 窗口与归档、状态段上限、阅读预算与分层加载、截断检测、机检上限与失败处理、维护操作）。
2. **单一事实源**：每条规则只在一篇正文出现，另一篇只写定位与链接；原"单篇超限先拆篇（取新 ID，走 MTH-009）"规则保留在 MTH-015 §5.4。
3. **引用同步**：AGENTS、README、methodology/README、MTH-008/009/012/013/014、guardrails、pitfalls、toolkit（README/validate 提示/doc-policy 描述）、CHANGELOG 头部、changelog/README 与 adr 台账同步改指正确篇；历史 ADR-0001/0002 不改写，新 ADR 回链。
4. **ID 与依赖**：MTH-015 取未占用号（编号只增不复用）；两篇 front matter `depends` 互相声明，避免单向依赖。
5. **版本与回归**：属方法论文档结构性分流，红线、权威顺序与校验强度不变；按 ADR-0002 跑 `preflight`（index + validate --strict + unittest + check-links），检查器与测试断言不做任何放宽。

## 后果

- 正面：两篇均回到健康档（MTH-011 158 行、MTH-015 190 行）；职责单一，归档/预算策略演进不再挤占归属/命名篇。
- 负面/风险：读者多一层跳转；两篇边界若漂移会重新重复——由 MTH-011 §4.1 自检清单与 `preflight` 兜底。
- 迁移：旧引用中的 `MTH-011 §3`／`§5`／`§6` 分别改读 MTH-015 §2／§4／§5；`MTH-011 §2.x`（命名/ADR/联动）保持原篇。
- 回滚：将两篇合回 `10-document-lifecycle.md` 并撤销引用替换；不影响工具与校验器。

## 备选方案

| 方案 | 利 | 弊 | 结论 |
|---|---|---|---|
| A. 拆为 MTH-011 + MTH-015 | 职责单一、两篇均留余量 | 多一层跳转 | 采纳 |
| B. 压缩原文到 ≤200 行 | 不增文件 | 必然删规则或丢证据，违反"不删规则" | 否决 |
| C. 只放宽 doc-policy 上限 | 零改动 | 掩盖膨胀，违背容量治理目标 | 否决 |
