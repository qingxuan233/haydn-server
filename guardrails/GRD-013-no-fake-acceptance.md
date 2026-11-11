---
id: GRD-013
title: 不伪造验收
type: guardrail
status: current
audience: human, agent
tags: acceptance, evidence, target-vs-measured, soak, honesty
depends: MTH-008
updated: 2026-11-11
agent_hint: 任何"完成/通过"结论必须有当场实测的命令、输出、时间与环境；目标值写目标，实测值写实测，未知只能标待验证。
severity: blocker
scope: agent
---

# GRD-013 · 不伪造验收

> "看起来已经完成"不是验收结论。验收的定义是：在声明的时间与环境里，有人能复现出同样结果。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 在未实际运行验证的情况下，把功能、阶段或任务标记为完成/通过；文档、脚本、配置"写好了"不算验收。
2. **R2** **MUST NOT** 混淆目标值与实测值：目标/预期必须单独标注，实测必须带采样时间、环境、样本量与命令。
3. **R3** **MUST NOT** 用截图、摘要或精选日志替代完整证据链；证据至少包含命令、原始输出、时间、执行者/环境、结论。
4. **R4** **MUST NOT** 用单次重启、单次请求或短时观察代表稳定性；必须按该阶段定义的门禁样本（多次重启、24h soak、故障注入、恢复演练）执行。
5. **R5** **MUST NOT** 在环境/权限/设备与目标不一致时宣称通过；差异必须记录，缺失项只能标记"待验证"或"部分通过"。
6. **R6** **MUST NOT** 隐藏失败、偏差与回归；部分通过必须列出剩余缺口，失败必须附原因与回滚结果。
7. **R7** **MUST NOT** 事后补写或修改历史证据以匹配结论；追加新证据可以，改写旧输出不行。

## 为什么（风险与案例）

- 案例中 24h soak 与部分门禁仍未完成，正确做法是保持"待验证/部分完成"，而不是用"连续运行几小时"代替（见 [README](../README.md) §10、[30 接手指南](../docs/00-overview/30-新会话接手指南.md) §7）。
- 自动自愈会掩盖故障：看门狗不断重启服务可能让"可用率"看起来正常，却没有真实的稳定性证据（见 PIT-020、PIT-017）。
- 验收结论会流入索引、报告与后续决策；一个假"通过"会污染整条证据链，让下一个 Agent 在错误基线上继续。
- 案例实证：[28 全栈规范 §11.6 验收清单](../docs/00-overview/28-全栈整体方案规范.md)、[33 Bridge MVP 实施记录](../docs/50-bridge/33-Android-Bridge-MVP实施记录.md)、[08 事故复盘](../docs/20-server/08-事故复盘与重置重建报告.md)。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 用证据链记录：命令 → 原始输出（可裁剪但要保留关键行）→ 时间（含时区）→ 环境/版本 → 结论；存入案例或采集快照。
- **MUST** 用"目标 vs 实测"表：目标值、实测值、样本量/时长、是否达标、证据位置；未测项写"待验证"。
- **MUST** 按 MTH-008 的门禁执行：重启矩阵、24h soak、故障注入、恢复演练；任一未执行则整体保持"未完成"。
- **SHOULD** 在报告里区分"案例实证""通用风险""待验证假设"；通用结论要在新设备上复现后才升级为已验证。
- **MAY** 使用 toolkit 的 soak/验收脚本生成结构化记录；脚本输出本身仍是证据，需附带运行时间与环境。
- **MAY** 分阶段接受"部分完成"，但必须同步 backlog 状态与剩余项，不得对外宣称全部完成。

## 检查方式（Agent 可执行）

```bash
python -m toolkit.repurpose validate --strict
python scripts/dev/check-links.py --strict-anchors
git log --oneline -5
```

- 人工核对：验收记录是否同时包含目标、实测、命令、时间、环境、结论六要素；缺项即判不合格。
- 证据核对：抽查一条"通过"结论，按记录中的命令重新执行；结果不一致则原结论失效。
- 抽样核对：稳定性结论是否有足够的样本与时长；单次结果不得支撑"稳定"。
- 状态核对：案例/阶段状态表与证据是否一致；存在未完成门禁却标"全部完成"即违规。
- 偏差核对：报告是否列出失败、剩余缺口与回滚结果；只写成功即视为隐瞒。

## 关联

- 踩坑：[PIT-017 快照无回滚](../pitfalls/PIT-017-snapshot-without-rollback.md)、[PIT-020 看门狗自愈级联](../pitfalls/PIT-020-watchdog-selfheal-cascade.md)、[PIT-005 无 Root 指标失真](../pitfalls/PIT-005-no-root-proc-metrics.md)
- 护栏：[GRD-004 变更前备份](GRD-004-backup-before-change.md)、[GRD-012 Agent 行为](GRD-012-agent-operating-rules.md)
- 方法论：[MTH-008 验收与稳定性](../methodology/07-validation.md)、[MTH-002 评估与决策](../methodology/01-assessment.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)
