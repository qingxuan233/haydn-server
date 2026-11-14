---
id: ADR-0003
title: AGENTS 容量分流：细节下沉 MTH，本文件保留红线、边界与索引
type: adr
status: accepted
audience: human, agent
tags: protocol-capacity, single-source-of-truth, agents-md, adr
depends: ADR-0002, MTH-011, MTH-014, MTH-015
updated: 2026-11-14
agent_hint: 修改 AGENTS 前先确认细节是否已由 MTH-011/MTH-014/MTH-015/MTH-009 承载；AGENTS 只保留红线、操作边界、索引与摘要，协议版本随结构性分流递增。
---

# ADR-0003 · AGENTS 容量分流

## 状态

accepted（2026-11-14）。取代：无。关联 [ADR-0002](0002-protocol-versioning-and-regression.md)、[ADR-0004](0004-mth-011-split.md)、[MTH-011](../methodology/10-document-lifecycle.md)、[MTH-014](../methodology/13-agent-sop.md)、[MTH-015](../methodology/15-archive-and-context-budget.md)。

## 背景

- AGENTS.md 曾达 291 行，处于 [AGENTS §2.2](../AGENTS.md) 的**警示档**（201~320 行），并被登记为知识债 BL-029；单会话注入成本高，且与 MTH-009/MTH-011/MTH-014 存在成段重复，容易漂移。
- 重复内容集中在：启动读序的预算/停止条件（[MTH-015](../methodology/15-archive-and-context-budget.md) §4、MTH-014 §10）、文件与文档约定（MTH-009 §2/§4、MTH-011 §2.3/§2.5）、任务协议（MTH-014 §3/§8/§9/§11/§12）、扩展 SOP（MTH-009 §7）。
- 约束：不得删减红线与操作边界，不得改变权威顺序，不得为压缩而弱化任何校验或改写冻结案例。

## 决策

1. **单一事实源**：AGENTS 只保留不可协商条款（权威顺序、§2.1 操作边界、§3 红线、§7 DoD）、机器接口表与**指向 MTH 的摘要**；完整流程/命名/联动/汇报/分支规则以 MTH-009/MTH-011/MTH-014/MTH-015 为唯一正文。
2. **等义迁移**：每条被压缩的规则必须在对应 MTH 已有等价条款（本轮仅去重与加指针，不新增或放宽规则）；无法一一对应时不压缩。
3. **段落结构保持**：保留 §0 读序权威、§3 红线 9 条、§7 DoD、§8 机器接口表与 §9 状态段；删除重复的 §8.1 YAML 摘要，改为指向 agent-manifest 的 `entrypoints`/`exit_codes`。
4. **版本与回归**：属协议 MINOR（结构性分流、规则等价），协议版本 v1.2 → v1.3；按 ADR-0002 跑 AR-01..AR-10 与 `preflight`，不得弱化检查。
5. **容量门**：分流后目标 ≤200 行（健康档）；后续新增规则优先写入对应 MTH，AGENTS 只加指针，避免再次膨胀。

## 后果

- 正面：AGENTS 回到健康档（197 行），单次注入成本下降；重复条款收敛到 MTH，减少漂移；分支通过协议版本行识别结构性变化。
- 负面/风险：读者若只读 AGENTS 会缺少流程细节，需按指针跳转；若 MTH 条款缺失，压缩即造成规则丢失——本轮已逐条核对并保持等义。
- 迁移：旧分支若仍按 v1.2 引用 AGENTS §4/§5 细节，合并前按 v1.3 差异核对，改读 MTH-009/MTH-011/MTH-014/MTH-015；无需改红线或工具契约。
- 回滚：恢复 AGENTS 至 v1.2 版本内容并同步协议版本；不影响工具与校验器。
