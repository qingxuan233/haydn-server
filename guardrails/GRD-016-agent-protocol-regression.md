---
id: GRD-016
title: 协议与提示词变更必须回归，不得弱化校验
type: guardrail
status: current
audience: human, agent
tags: protocol, regression, validator-integrity, preflight, launch-blocker
depends: GRD-012, GRD-013
updated: 2026-11-13
agent_hint: 改 AGENTS/提示词/模板/校验器前先读本条；发现校验器误报先记录证据并报告 Lead，禁止改检查让自己变绿；完成协议变更必跑 preflight 与回归 AR-01..AR-10。
severity: blocker
scope: agent
---

# GRD-016 · 协议与提示词变更必须回归，不得弱化校验

> 协议/提示词/模板/校验器是 Agent 的一等公民制品：改它们就是改"所有后续任务的行为"。本条的检查对象是**变更方式**，不是具体规则内容。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 修改 `validate`/lint/测试断言/CI 检查的判据、阈值或白名单，使自己的改动"变绿"；包括删除或注释测试、放宽 schema、加豁免、跳过 strict 模式。
2. **R2** **MUST NOT** 手改 `agent-manifest.json` 或 `agent-manifest.d/`；生成物只能由 `python -m toolkit.repurpose index` 重建，禁止把"工作区文件看起来对"当交付。
3. **R3** **MUST NOT** 跳过 `preflight` 或 Agent 回归集（AR-01..AR-10）就宣称协议/提示词/模板/校验器变更完成；未跑检查只能标"待验证"。
4. **R4** **MUST** 协议语义变更同步 `AGENTS.md` 协议版本（MAJOR/MINOR/PATCH）并留 ADR 指针；新规则尽量机制化，能写成检查的不写成口号。
5. **R5** **MUST NOT** 以"旧文档/旧案例就是这么写的"为由复制绕过现行检查；复制前先读当前协议版本与相关 GRD/PIT。

## 为什么（风险与案例）

- 影响面：`AGENTS.md` 是所有会话的唯一协议入口，校验器是所有交付的验收判据；弱化一次，后续每个任务的"全绿"都不再可信。
- 真实代价：校验器被削弱后，假验收无法被自动发现，历史证据链失效，下一个 Agent 将在错误基线上继续（[GRD-013](GRD-013-no-fake-acceptance.md)；[PIT-017](../pitfalls/PIT-017-snapshot-without-rollback.md) 假安全、[PIT-019](../pitfalls/PIT-019-fake-pinning-bridge.md) 伪加固的同类思路：**没有会失败的检查，承诺就是空的**）。
- 参考规范实证：改钩子路径使上游保护闸立即失效，任何提交可直入主干（见 [MTH-014](../methodology/13-agent-sop.md) §11）；本仓等价条款见 [AGENTS.md](../AGENTS.md) §10"不得通过降低红线来通过验收"。协议变更不回归的后果不是"慢一点"，而是**规则漂移**：不同会话按不同版本的协议工作，质量门口径分裂。

## 允许的替代

| 禁止动作 | 允许替代 |
|---|---|
| 发现校验器误报/漏检 | 记录复现证据（命令＋输入＋期望 vs 实际）→ 报告 Lead → 批准后**单独任务**修校验器，并补 AR-04 反例测试 |
| 新内容被现有检查判失败 | 修内容使其符合现行规范；若判定规范过时，先写 ADR 改规范与校验器，再改内容 |
| 本地调试需临时绕过 | 仅限非 strict 本地调试，不得 commit；记录绕过原因与恢复 strict 的命令，不得剪除检查 |
| 生成物不一致 | 跑 `python -m toolkit.repurpose index` 重建，diff 由 Lead 评审；不手改 |

## 检查方式

```powershell
python -m toolkit.repurpose preflight             # 0=全绿 / 3=有跳过 / 4=失败
python -m toolkit.repurpose validate --strict
python scripts/dev/check-links.py --strict-anchors
python -m unittest discover -s toolkit/tests -t . -v
git diff --stat -- toolkit/repurpose toolkit/tests toolkit/schema scripts/dev/check-links.py agent-manifest.json
```

- 机检：preflight 三态；AR-01..AR-10（定义见 [MTH-014 §13](../methodology/13-agent-sop.md)）；协议章节/版本/哨兵/体积。
- 评审：`git diff` 涉及校验器、测试断言、schema、生成物时必须由 Lead 复核，并核对"变更前后检查行为差异"与反例证据；报告是否列出协议版本增量、ADR 指针、回归/preflight 结果与"未弱化任何检查"的说明。

## 关联

- 决策：[ADR-0002 协议版本化与回归](../adr/0002-protocol-versioning-and-regression.md)、[ADR-0001 定向采纳](../adr/0001-adopt-agent-harness-v1-3.md)。
- 方法论：[MTH-014 Agent SOP §12/§13](../methodology/13-agent-sop.md)、[MTH-011](../methodology/10-document-lifecycle.md)、[MTH-013](../methodology/12-delivery-governance.md)。
- 护栏：[GRD-012 Agent 行为](GRD-012-agent-operating-rules.md)、[GRD-013 不伪造验收](GRD-013-no-fake-acceptance.md)。
- 踩坑思路：[PIT-017](../pitfalls/PIT-017-snapshot-without-rollback.md)、[PIT-019](../pitfalls/PIT-019-fake-pinning-bridge.md)；协议：[AGENTS.md](../AGENTS.md) §7/§10。
