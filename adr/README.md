---
id: ADR-000
title: 决策记录索引（ADR Index）
type: index
status: current
audience: human, agent
tags: adr, index, decisions
depends: MTH-011, MTH-015
updated: 2026-11-14
agent_hint: 涉及架构选型、口径裁决、不可逆变更或协议 MAJOR 变更时先查本索引；够不上 ADR 的轻量决策记入 §5 台账（D-NN），不要为小事造 ADR。
---

# ADR-000 · 决策记录索引

> 本层记录**有后果的决策**及理由：回答"当时为什么这么选、否决了什么"。格式参考 Nygard 五段式，重大决策加"备选方案对比"。相关：[MTH-011 文档生命周期](../methodology/10-document-lifecycle.md)、[MTH-015 归档与上下文预算](../methodology/15-archive-and-context-budget.md)、[MTH-014 Agent SOP](../methodology/13-agent-sop.md)、[MTH-009 交接](../methodology/08-agent-handoff.md)。

## 1. 用途

- 让"为什么"与"是什么"一起入库：后来者无需重推论证，只读结论与备选；决策可追溯、可被推翻——推翻旧决策必须新建 ADR，旧 ADR 标 superseded。
- 机器可检索：文件名 `NNNN-slug.md`、flat front matter、状态枚举、索引链接均由 `validate --strict` 机检（见 §6）。

## 2. 何时写 ADR

| 触发 | 例子 |
|---|---|
| 架构/目录/分层选型 | 新增 `adr/` 层；工具维持零第三方依赖 |
| 不可逆或高代价变更 | 协议 MAJOR 变更；改权威顺序；改 ID 前缀 |
| 口径裁决 | 两份文档矛盾时确定唯一事实源 |
| 重要备选被否决 | 全量移植 vs 定向采纳的取舍 |
| 对外契约变化 | 命令退出码、字段语义变化 |

够不上任一条的（如局部命名、模板微调）→ 记 §5 决策台账（D-NN 一行一条），不写 ADR。机制条款由 MTH 承载，ADR 只记"这次为什么这么定"。

## 3. 状态枚举

| 状态 | 含义 | 处理规则 |
|---|---|---|
| proposed | 已提出、未裁决 | 不得据此改实现；相关文档标注"待定" |
| accepted | 已接受、生效 | 后续行为以此为准；变更须新建 ADR 取代 |
| superseded | 被新 ADR 取代 | **不删除、不改写历史结论**：front matter 加 `superseded_by: ADR-NNNN`，正文首段保留原决策并指向新 ADR |

> 状态只能前进：proposed → accepted → superseded。勘误与补充走"修订行"（R1、R2…含日期与一句话），不抹历史。

## 4. 索引

| ID | 决策 | 状态 | 更新 | 文档 |
|---|---|---|---|---|
| ADR-0001 | 定向采纳 Agent-Harness v1.3 增量机制（采纳/裁剪/不采纳清单） | accepted | 2026-11-13 | [ADR-0001](0001-adopt-agent-harness-v1-3.md) |
| ADR-0002 | AGENTS 协议语义化版本 + 协议/提示词变更必须回归、校验器中立 | accepted | 2026-11-13 | [ADR-0002](0002-protocol-versioning-and-regression.md) |
| ADR-0003 | AGENTS 容量分流：细节下沉 MTH，保留红线/边界/索引（协议 v1.3，197 行） | accepted | 2026-11-14 | [ADR-0003](0003-agents-capacity-split.md) |
| ADR-0004 | MTH-011 拆分：生命周期归 MTH-011，归档/预算/机检归 MTH-015 | accepted | 2026-11-14 | [ADR-0004](0004-mth-011-split.md) |
| ADR-0005 | MTH-013 拆分：治理流程留 MTH-013，发布/兼容/数据/许可归 MTH-016 | accepted | 2026-11-14 | [ADR-0005](0005-mth-013-split.md) |
| ADR-0006 | MTH-009/MTH-002 拆分：扩展契约归 MTH-017，评估执行归 MTH-018 | accepted | 2026-11-14 | [ADR-0006](0006-mth-009-mth-002-split.md) |
| ADR-0007 | 行数余量预警采用 advisory 级，不改变 strict/preflight 失败语义 | accepted | 2026-11-14 | [ADR-0007](0007-line-margin-advisory.md) |
| ADR-0008 | 公网入口采用大陆节点 IP + 非标端口（放弃域名 443、境外节点、CF Tunnel、Tailscale Funnel） | accepted | 2026-11-14 | [ADR-0008](0008-public-entry-after-icp-sni-block.md) |

新增 ADR 必须同步本表；索引与文件双向无遗漏（validate 的 ADR_INDEX 检查）。

## 5. 轻量决策台账（D-NN）

| 编号 | 日期 | 决策 | 理由/证据 |
|---|---|---|---|
| D-01 | 2026-11-13 | ADR 层放仓库根 `adr/`，不放冻结的 `docs/` | 冻结区只读；新层需可机检、可索引 |
| D-02 | 2026-11-13 | `adr/README.md` 用 `type: index`，ADR 正文用 `type: adr` | 索引不是决策记录；机检按文件名/ID 区分 |

台账只增行、不改旧行；某条升格为 ADR 时在行末标注"升级为 ADR-NNNN"。

## 6. 新增与维护（见 MTH-011 §2.4）
触发条件、`NNNN-kebab-slug.md` 命名、五段格式、`status` 枚举、"被取代不删除 + 回链"、轻量台账与禁止项**只维护在** [MTH-011 §2.4](../methodology/10-document-lifecycle.md)，索引/指针/协议版本联动按 [§2.5](../methodology/10-document-lifecycle.md) 与 [MTH-014 §7](../methodology/13-agent-sop.md) 执行；本页不重复，避免两处漂移。

## 7. 与其他层的关系

- **methodology/**：规范正文（"应当怎么做"）；ADR 记录"这次为什么选这个方案"，被采纳的机制最终固化为 MTH 条款。
- **guardrails/**：不可协商红线；红线永远压过 ADR，冲突时以 GRD 为准并报告 Lead 裁决。
- **pitfalls/**：证据层；ADR 后果/风险段的证据应回链 PIT，不得只用推测；机检/模板/索引由 toolkit 实现，不手写生成物。
