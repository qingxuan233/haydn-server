---
id: GRD-012
title: Agent 行为红线
type: guardrail
status: current
audience: human, agent
tags: agent, protocol, scope, honesty, rollback, dod
depends: MTH-009
updated: 2026-11-11
agent_hint: 动手前只读核对现状与写范围；不越权、不伪造、不改案例证据；高风险操作与契约变更必须人工批准，失败立即回滚并报告。
severity: blocker
scope: agent
---

# GRD-012 · Agent 行为红线

> 后续 Agent 会继承这套知识库。你的每一步都在定义"以后 Agent 可以怎么做"，因此行为红线比一次任务结果更重要。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 在未完成只读核对（状态、健康、git 差异、清单、相关 MTH/PIT/GRD）前动手修改；不得凭印象或旧记忆操作。
2. **R2** **MUST NOT** 超出授权写范围，或为"顺手美化"改动冻结证据（旧 docs/scripts/Bridge 源码与 cases）；跨范围改动交回 Lead 集成。
3. **R3** **MUST NOT** 伪造验收或证据：不得编造命令输出、回填时间戳、篡改日志、把"文档已写"当作"功能已验证"。
4. **R4** **MUST NOT** 自主执行高风险操作：解锁、Root、刷机、Tier3 恢复、升级、删数据、外部服务接入、凭据轮换、破坏性契约变更、改动案例证据；这些必须人工批准并记录。
5. **R5** **MUST NOT** 修改护栏、测试、校验器或阈值来"通过验收"；也不得跳过 validate/index/unittest/check-links。
6. **R6** **MUST NOT** 失败后隐瞒或继续堆叠改动；必须先回滚到已知良好状态，如实报告失败命令与影响。
7. **R7** **MUST NOT** 自行扩大权限、替用户拍板或删除"不完美但真实"的偏差记录；不确定时按最保守方案执行并写清假设。

## 为什么（风险与案例）

- 项目已多次证明"自动化便利"会放大破坏面：kill-all 一次误杀整栈、系统包一次误删导致 bootloop；Agent 的"快速修复"必须受协议约束（见 [AGENTS.md](../AGENTS.md) §3/§5/§7）。
- 没有回滚验证的变更会把故障变成事故；没有证据的"完成"会污染知识库，让后续 Agent 基于假前提行动（见 PIT-017、PIT-020）。
- 案例与旧目录是历史证据，改动它们等于篡改证据链；新层文档的价值恰恰来自诚实的偏差记录。
- 案例实证：[30 新会话接手指南](../docs/00-overview/30-新会话接手指南.md) §6/§7/§9、[29 文档评审报告](../docs/00-overview/29-项目文档评审报告.md) 维护规则。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 先只读核对并列出影响面；写范围与其他人不一致时先协调，禁止盲写共享文件。
- **MUST** 高风险/跨契约操作先提交方案（影响、回滚、验证、风险），获人工批准后执行，并在审计或变更记录留痕。
- **MUST** 变更后跑 DoD 最低门槛（validate/index/unittest/check-links/diff 检查），失败即修或回滚，不接受"带病完成"。
- **SHOULD** 小步提交、每次只解决一件事；提交由 Lead 审核，subagent 不自行 commit。
- **SHOULD** 报告固定包含：改了什么、为什么、验证命令与结果、风险/回滚、未完成项与假设。
- **MAY** 提出改进建议或新增 PIT/GRD，但必须按新增流程评审后落地。

## 检查方式（Agent 可执行）

```bash
git status --short --untracked-files=all
git diff --stat
git diff --check
python -m toolkit.repurpose validate --strict
python scripts/dev/check-links.py --strict-anchors
```

- 范围核对：`git status`/`git diff` 的文件清单必须全部落在授权写范围；出现冻结目录改动即停止并上报。
- 证据核对：报告中的每条"已完成/已验证"是否对应真实命令、输出、时间与记录；无法复现的结论撤回。
- 审计核对：执行过的高风险操作是否有批准记录与 ops 审计条目；Tier2 是否有快照。
- 状态核对：失败或回滚后工作区是否干净、服务是否恢复；是否留下未说明的临时文件或半成品。
- 协议核对：是否跳过 DoD 校验、是否改动校验器/阈值；出现即判违规。

## 关联

- 踩坑：[PIT-017 快照无回滚](../pitfalls/PIT-017-snapshot-without-rollback.md)、[PIT-020 看门狗自愈级联](../pitfalls/PIT-020-watchdog-selfheal-cascade.md)、[PIT-014 配置重载锁死](../pitfalls/PIT-014-config-reload-lockout.md)
- 护栏：[GRD-001 默认不 Root](GRD-001-no-root-no-unlock-default.md)、[GRD-004 变更前备份](GRD-004-backup-before-change.md)、[GRD-005 分级确认](GRD-005-tiered-ops-confirmation.md)、[GRD-013 不伪造验收](GRD-013-no-fake-acceptance.md)
- 方法论：[MTH-009 Agent 交接与扩展协议](../methodology/08-agent-handoff.md)、[MTH-008 验收](../methodology/07-validation.md)
- 协议：[AGENTS.md](../AGENTS.md)、[backlog.json](../backlog.json)
