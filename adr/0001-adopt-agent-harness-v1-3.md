---
id: ADR-0001
title: 定向采纳 Agent-Harness v1.3 增量机制
type: adr
status: accepted
audience: human, agent
tags: agent-harness, adoption, governance, tooling
updated: 2026-11-13
agent_hint: 引入任何"参考规范里的新机制"前先核对本 ADR 的采纳/裁剪/不采纳清单；本 ADR 不自动追随外部规范更新，边界变化须新建 ADR 取代。
---

# ADR-0001 · 定向采纳 Agent-Harness v1.3 增量机制

## 状态

accepted（2026-11-13）。取代：无。后续协议版本与回归规则见 [ADR-0002](0002-protocol-versioning-and-regression.md)。
修订：R1 2026-11-13 初版；采纳 Agent-Harness v1.3 的增量机制，按仓库形态裁剪，不做全量移植。

## 背景

- 本仓库是**设备改造方法论型**仓库（规范/证据/工具为主，非构建型产品），当前协议 v1.2、方法论 MTH-001..014、护栏 GRD-001..016、踩坑 PIT-001..025、工具为本地零第三方依赖 Python 包。
- 既有缺口：没有决策记录层（重大裁剪与口径裁决无留痕）、协议无版本语义（多会话/分支各自演化）、提示词与模板变更无回归、机器校验未覆盖协议/命名/PIT/ADR/backlog。
- 参考材料：本地冻结参考副本（gitignored，不作为正式层）暴露的四类失效模式——上下文错乱、幻觉、过度自信、知识流失。
- 约束：冻结区 `docs/`/`scripts/`/`cases/` 只允许事实纠错；仓库规模不支撑完整阶段门/SBOM/多项目流程；所有新规则必须能由现有工具机检。

## 决策

**定向采纳（方案 C）**：只引入能补缺口、且可被本仓工具链机检或模板化的机制，其余裁剪或不采纳；参考副本不进入正式层、不自动跟随更新。

### 采纳清单（参考条款 → 落点 → 机检）

| 参考机制 | 本仓落点 | 机检方式 |
|---|---|---|
| §1.2 AGENTS 容量分级/必备章节/协议版本行 | `AGENTS.md` v1.2 | PROTOCOL_SECTION/VERSION/PROTOCOL_SIZE |
| §1.2 末尾截断哨兵 | `AGENTS.md` 末行哨兵 | PROTOCOL_SENTINEL |
| §1.3 文档命名规范 | MTH-011 命名规范节 | DOC_NAMING |
| §2.5 决策记录 ADR | `adr/` 层 + ADR-0001/0002 + 模板 | ADR_FILENAME/ID/STATUS/SECTION/INDEX |
| §2.6 变更-文档联动矩阵 | AGENTS §4.4 摘要 + MTH-011 完整矩阵 | 人工核对 + 索引检查 |
| §4.6 长文档截断/检测 | AGENTS §2.2 截断自检 + MTH-011 | 人工核对（doc-policy 体积） |
| §4.7 提示词/工具定义治理 | MTH-014 §12 + [GRD-016](../guardrails/GRD-016-agent-protocol-regression.md) | 回归 AR-01..AR-10 |
| §4.8 Agent 评估与回归 | MTH-014 §13 定义 AR-01..AR-10 | `toolkit/tests` + AR-04 反例自证 |
| §6.4 七条停止条件 | AGENTS §0 + MTH-014 | 人工核对 |
| §7 踩坑触发/升级/退役制度 | `pitfalls/README.md` §3.1–§3.3 + pitfall 模板 | PIT_ID_GAP/SECTION/COUNT |
| §9.4 知识债与度量 | MTH-011 知识债节 + backlog | BACKLOG_SEMANTIC |
| §9.5 工具化校验 | validate 扩展 + `preflight` 三态 + CI | PREFLIGHT / AGENT_REGRESSION |
| 03 全册交付治理 | MTH-013 + acceptance/runbook/request-card 模板 | 人工核对 + 反例自证 |

### 裁剪或不采纳（含理由）

| 条款 | 处理 | 理由 |
|---|---|---|
| Diátaxis 四象限全量分类 | 不落为强制分类，只借"一个文档一个问题"与按任务取文档 | 增层会引入分类维护成本，收益低于现状 |
| 日期任务区 `YYYY-MM-DD/` | 改为 gitignored 的本地会话产物区 | 不入库、不污染索引 |
| 分支模型（主干保护/短生命周期） | 不强制，只写规则与合并前门禁说明 | 单人仓库无远程保护；写死模型会空转 |
| 阶段门 G0–G7、SBOM/provenance、CODEOWNERS | 不完整落地，仅 MTH-013 引用原则 | 规模不匹配；保留升级空间 |
| 参考规范副本入库 | 不采纳 | 本地参考区为 gitignored 副本，正式层不复制外部规范全文 |

## 备选方案对比

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| A 保持不动 | 零迁移成本、无新维护面 | 决策/版本/回归缺口持续；Agent 行为无机制约束，靠自觉 | 否决 |
| B 全量移植 | 覆盖最全，与参考规范一致 | 大量条款与仓库形态不匹配（构建型代码/组织流程）；AGENTS 与冻结区冲突；维护成本高 | 否决 |
| C 定向采纳（选定） | 只补缺口，全部可机检/可模板化；与现有四层结构兼容 | 新增 `adr/` 层与模板（新增 2、更新 4）、校验器增量工作；需一次性迁移与同步 | 采纳 |

## 后果

### 正面

- 决策可追溯：裁剪边界、备选否决、协议升级都有 ADR 或台账留痕。
- 协议/提示词/模板变更可回归：AR-01..AR-10 + preflight 让"改规则"像"改代码"一样有检查。
- 规则机制化：命名/ADR/PIT/backlog/协议检查进入 validate，减少"口号条款"。
- 跨分支/跨会话可迁移：协议版本行 + 哨兵 + 语义化版本能判断规则是否变化。

### 代价与风险

- 代价：新增 `adr/` 层、ADR/request-card 模板与校验器扩展；AGENTS、MTH、README 需同步更新；学习成本上升。
- 代价：validate/tests/CI 增加运行时间；新增检查需维护测试与反例。
- 风险：新类型/新 ID 与既有 schema 不兼容 → 由兼容降级与测试覆盖兜底；失败即回退本次扩展。
- 风险：ADR 退化为形式文档 → 只在有后果的决策写；索引与机检强制登记，季度复核。
- 风险：参考规范持续演进造成漂移 → 副本冻结在 gitignored 参考区；本 ADR 记录边界，不自动追随。

## 迁移步骤与验证方式

1. 新增 `adr/` 层、ADR-0001/0002 与 ADR/request-card 模板。
2. MTH-011/MTH-013/MTH-014 补机制条款，模板逐条重建。
3. validate/preflight/doc-policy/测试扩展，AGENTS 升 v1.2 + 版本行 + 哨兵，由 Lead 集成验证。
4. 验证：`python -m toolkit.repurpose preflight` 退出码 0（全绿）或 3（明示跳过项）；`validate --strict` 无 error/warning；AR-01..AR-10 回归覆盖（MTH-014 §13）。
5. 回滚：若机制落地失败，本 ADR 标 superseded 并新建 ADR 记录撤回范围；文件停用走同一流程，不静默回退、不删除历史。

## 关联

- 决策：本 ADR；[ADR-0002 协议版本化与回归](0002-protocol-versioning-and-regression.md)；决策台账见 [adr/README.md](README.md)。
- 护栏：[GRD-016 协议/提示词变更回归](../guardrails/GRD-016-agent-protocol-regression.md)、[GRD-013 不伪造验收](../guardrails/GRD-013-no-fake-acceptance.md)。
- 方法论：[MTH-011](../methodology/10-document-lifecycle.md)、[MTH-013](../methodology/12-delivery-governance.md)、[MTH-014](../methodology/13-agent-sop.md)、[MTH-009](../methodology/08-agent-handoff.md)。
- 模板：[ADR](../toolkit/templates/adr.md)、[需求卡](../toolkit/templates/request-card.md)；协议：[AGENTS.md](../AGENTS.md)。
