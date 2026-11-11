---
id: GRD-005
title: Tier1/Tier2/Tier3 分级确认
type: guardrail
status: current
audience: human, agent
tags: tier, confirmation, audit, snapshot, control-plane, privilege
depends: MTH-006, MTH-007
updated: 2026-11-11
agent_hint: 任何写操作先判定 Tier；Tier2 必须走受控 CLI 的 --confirm+快照+审计+人工同意；Tier3 禁止 Agent/网页执行，只接受人工 SSH 双重确认。
severity: blocker
scope: server
---

# GRD-005 · Tier1/Tier2/Tier3 分级确认

> 控制面的"大脑"可以有，但"手"必须收在白名单工具层里。分级不是为了流程好看，而是为了让每次变更都有确认、快照与审计。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 在受控 ops CLI 之外执行服务器写操作（直接 shell 删除、重启、恢复、改配置），包括通过网页控制台或聊天指令绕过。
2. **R2** **MUST NOT** 执行 Tier2 写操作时缺少任一项：显式确认参数、变更前配置快照、审计记录、人工同意。
3. **R3** **MUST NOT** 向 DSH/网页/Agent 开放 Tier3 能力（恢复备份、升级、删除数据、重建环境）；Tier3 只允许人工 SSH + 双重确认 + 已验证备份。
4. **R4** **MUST NOT** 扩大 ops 白名单（服务、命令、参数、目标路径）而不更新文档与审计；禁止通配符参数与任意命令透传。
5. **R5** **MUST NOT** 让 DSH 持有 Bridge token、直连遥测桥、启动 Android App 或跨层执行设备特权操作。
6. **R6** **MUST NOT** 用"临时方便"直接改运行态配置绕过快照；所有变更必须能被审计追溯到人/时间/命令/目标。

## 为什么（风险与案例）

- DSH 公网入口被打穿约等于拿到服务器 shell：能读备份密钥、改配置、删数据；"大脑"越权是最高频的控制面风险（见 PIT-019 的暴露与信任面）。
- 无确认的配置重载可能把 SSH/入口配置改坏并锁死自己，案例中确有"改完即失联"的风险模式（见 PIT-014）。
- 分级 + 快照 + 审计让错误可逆、责任可查；案例 Tier2 演练已验证"缺少 --confirm 被拒绝、非法服务被拒绝、快照与审计可查"。
- 案例实证：[22 Tier2 受控写](../docs/30-dsh/22-DSH-Tier2受控写落地.md)、[20 控制面方案](../docs/30-dsh/20-DSH控制平面方案.md)、[21 落地手册](../docs/30-dsh/21-DSH控制平面落地手册.md)、[AGENTS 协议](../scripts/server/AGENTS.md)。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** Tier1 只读命令免确认；任何状态不确定时先用 Tier1 诊断，不写。
- **MUST** Tier2 走受控 CLI：显式确认参数 + 自动配置快照 + 审计条目 + 人工同意记录；限定服务/目标白名单。
- **MUST** Tier3 由人工在 SSH 中执行，变更前按 [GRD-004](GRD-004-backup-before-change.md) 完成备份与恢复校验，执行中双人确认。
- **SHOULD** DSH/Agent 仅做 Tier1 与"申请 Tier2"，由人类确认后触发；DSH 的系统提示与技能文案同步该边界。
- **MAY** 引入审批 UI、MFA 或 IP 允许列表来强化确认链；接入前必须取得用户同意（[GRD-009](GRD-009-external-services-consent.md)）。

## 检查方式（Agent 可执行）

```bash
server-ops status
server-ops audit 20
server-ops help
supervisorctl status
```

- 演练核对（只读观察即可）：在测试实例/演练窗口分别执行"缺确认参数"和"非法服务名"的调用，确认两者都被拒绝且不产生副作用。
- 审计核对：每条 Tier2 记录应包含时间、调用者、命令、目标、结果、快照路径；缺快照路径即判违规。
- 白名单核对：受控 CLI 帮助与配置中只允许枚举命令/服务；出现通配参数、任意 shell、任意路径透传即违规。
- 边界核对：DSH/网页可调用的命令集合中不含 Tier3 动作；DSH 配置中无私钥/遥测 token。
- 回滚核对：Tier2 失败时能从快照恢复并重跑验收；恢复动作本身必须走 Tier3 流程。

## 关联

- 踩坑：[PIT-014 配置重载锁死](../pitfalls/PIT-014-config-reload-lockout.md)、[PIT-017 快照无回滚](../pitfalls/PIT-017-snapshot-without-rollback.md)、[PIT-019 伪证书 pin](../pitfalls/PIT-019-fake-pinning-bridge.md)
- 护栏：[GRD-003 禁止 kill-all](GRD-003-no-kill-all.md)、[GRD-004 变更前备份](GRD-004-backup-before-change.md)、[GRD-006 密钥卫生](GRD-006-secret-hygiene.md)、[GRD-012 Agent 行为](GRD-012-agent-operating-rules.md)
- 方法论：[MTH-006 控制面](../methodology/05-control-plane.md)、[MTH-007 安全](../methodology/06-security.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)
