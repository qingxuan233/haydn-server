---
id: ADR-0002
title: 协议版本化与回归：AGENTS 语义化版本、变更必须回归、校验器中立
type: adr
status: accepted
audience: human, agent
tags: protocol-version, regression, validator-integrity, agent-sop
depends: ADR-0001, GRD-016
updated: 2026-11-13
agent_hint: 任何触及 AGENTS/提示词/模板/校验器的变更，先读本 ADR 与 GRD-016；按 MAJOR/MINOR/PATCH 判定版本，跑回归 AR-01..AR-10 与 preflight，不得为通过而改检查。
---

# ADR-0002 · 协议版本化与回归

## 状态

accepted（2026-11-13）。取代：无。本决策依赖 [ADR-0001](0001-adopt-agent-harness-v1-3.md) 的采纳范围。
修订：R1 2026-11-13 初版；建立协议语义化版本、强制回归与校验器中立三条规则。

## 背景

- `AGENTS.md` 是全仓唯一 Agent 协议（权威顺序仅低于用户指令）；协议、提示词、模板、校验器都是 Agent 的**一等公民制品**，其变更影响每个会话与每次交付。
- 现状风险：协议无版本行与语义，多会话/分支各自演化后无法判断"规则是否变了"；模板与校验器改动无回归，坏改动在下一个任务才暴露。
- 历史教训：Agent 最容易通过弱化检查"通过"验收（[GRD-013](../guardrails/GRD-013-no-fake-acceptance.md)）；参考规范中也有"改钩子路径使上游保护闸立即失效"的真实事故（本仓等价条款见 [MTH-014](../methodology/13-agent-sop.md) §12.1）。
- 触发：本仓库正批量改 AGENTS/模板/校验器（ADR-0001 落地），若无版本与回归，后续分支无法界定兼容性。

## 决策

1. **协议语义版本**（写入 AGENTS 头部"协议版本"行，遵循 MAJOR.MINOR.PATCH）：
   - `MAJOR`：红线变化或规则不兼容。所有分支/会话必须重读整改；**必须新建 ADR** 记录旧规则、新规则、理由、受影响文档/分支、迁移步骤。
   - `MINOR`：新增条款/新模板/新检查，向后兼容；分支应了解，任务卡记录适用版本。
   - `PATCH`：澄清措辞、修错字，不改变行为；无需行动。
2. **协议/提示词/模板变更必须走回归**：执行 Agent 回归集 AR-01..AR-10（定义见 MTH-014 §13）与 `preflight`，并在交付报告中附命令、退出码与关键输出；AR-04 要求"构造违规输入必须 exit 4"的反例自证。
3. **校验器中立**：不得修改 validate/lint/测试断言/CI 检查使其对自己的改动"变绿"；发现校验器 bug 的路径是"记录复现证据 → 报告 Lead → 批准后单独修校验器并补反例测试（AR-04）"，不是绕过。
4. **生成物不手改**：`agent-manifest.json` 与 `agent-manifest.d/` 只能由 `python -m toolkit.repurpose index` 重建；重建后 diff 由 Lead 评审。
5. **版本绑定**：分支/任务卡/需求基线卡记录其遵循的协议版本；跨版本合并前做一次 MAJOR/MINOR 差异核对。

## 备选方案对比

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| A 把 AGENTS 当非版本化自由文本 | 零维护，改了就生效 | 无法判断规则变化；分支/会话漂移；回归无从谈起 | 否决 |
| B 允许为了通过而改检查 | 短期最快 | 校验器公信力归零，所有历史与后续验收失效；与 GRD-013/016 直接冲突 | 否决 |
| C 只版本化、不做回归 | 有版本号 | 无证据证明行为未退化，版本号沦为装饰 | 否决 |
| D 语义化版本 + 强制回归 + 校验器中立（选定） | 变更级别可判定；回归可证；跨分支可迁移 | 一次性建设成本；每次变更多花检查时间 | 采纳 |

## 后果

### 正面

- 变更可判定：MAJOR/MINOR/PATCH 决定分支是否必须整改，降低"规则悄悄变了"的代价。
- 回归可证：AR-01..AR-10 + preflight 三态（0/3/4）让"协议没退化"成为可执行结论，而不是印象。
- 校验器可信：中立规则保证"全绿"仍然等于"符合规范"，历史证据链不被污染。
- 决策可追溯：MAJOR 必走 ADR，旧规则与新规则的边界可回查。

### 代价与风险

- 代价：每次协议/模板/校验器变更需附加回归证据与 preflight；CI 时间增加。
- 代价：校验器修复必须走独立任务与批准流程，短期效率下降（有意的摩擦）。
- 风险：回归集覆盖不足 → 用 AR-04 反例自证兜底，并由新增 PIT 触发回归扩展。
- 风险：维护者绕过回归 → [GRD-016](../guardrails/GRD-016-agent-protocol-regression.md) blocker + Lead 对 `git diff` 校验器/生成物的强制评审。
- 风险：版本号通胀（PATCH 当 MINOR）→ 版本行与 CHANGELOG 同条记录，季度抽查口径。

## 检查方式

```powershell
python -m toolkit.repurpose preflight          # 0=全绿 / 3=存在跳过 / 4=失败
python -m toolkit.repurpose validate --strict  # 协议章节/版本/哨兵/命名/ADR/PIT/backlog/归档
python scripts/dev/check-links.py --strict-anchors
python -m unittest discover -s toolkit/tests -t . -v
```

- 机检：协议 H2 关键字、协议版本行、末行哨兵、体积；ADR 状态/章节/索引；回归 AR-01..AR-10。
- 人工：`git diff` 涉及 `toolkit/repurpose/`、`toolkit/tests/`、`toolkit/schema/`、`scripts/dev/check-links.py`、`agent-manifest*` 时必须由 Lead 评审并核对"变更校验器的反例证据"。
- 报告：协议变更交付报告必须列出"协议版本增量、ADR 链接、回归/ preflight 结果、未弱化检查的说明"。

## 关联

- 决策：[ADR-0001](0001-adopt-agent-harness-v1-3.md)；索引 [adr/README.md](README.md)。
- 护栏：[GRD-016](../guardrails/GRD-016-agent-protocol-regression.md)、[GRD-013](../guardrails/GRD-013-no-fake-acceptance.md)、[GRD-012](../guardrails/GRD-012-agent-operating-rules.md)。
- 方法论：[MTH-014 §13 Agent 回归](../methodology/13-agent-sop.md)、[MTH-011](../methodology/10-document-lifecycle.md)、[MTH-013](../methodology/12-delivery-governance.md)。
- 协议：[AGENTS.md](../AGENTS.md) §5.4/§10；模板：[ADR](../toolkit/templates/adr.md)。
