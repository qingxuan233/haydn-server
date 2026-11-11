---
id: GRD-004
title: 变更前必须备份、快照并准备回滚
type: guardrail
status: current
audience: human, agent
tags: backup, snapshot, rollback, restore-drill, tier2
depends: MTH-004, MTH-008
updated: 2026-11-11
agent_hint: 开始任何 Tier2 写、升级、迁移或恢复前，先要求"备份+快照+回滚路径+恢复校验"四项证据，缺一项即停止。
severity: blocker
scope: server
---

# GRD-004 · 变更前必须备份、快照并准备回滚

> 判断标准不是"有没有备份"，而是"这个备份最近是否被成功恢复验证过"。没有演练过的回滚等于没有回滚。

## 红线（MUST NOT）

1. **R1** **MUST NOT** 在未完成「新备份 + 配置快照 + 书面回滚路径 + 可恢复性校验」四项前，执行 Tier2 写操作、升级、迁移或恢复。
2. **R2** **MUST NOT** 把未经校验的备份当作回滚依据；加密包必须验证可解密、可解包、关键文件存在（至少一次 tar/清单/校验和检查）。
3. **R3** **MUST NOT** 在新备份未被验证前删除或覆盖旧备份/旧快照；保留至少一份可回退的上一状态。
4. **R4** **MUST NOT** 声称"已备份/可回滚"却给不出具体产物：备份 ID、时间、位置、校验结果、快照路径、回滚步骤。
5. **R5** **MUST NOT** 在恢复/回滚后跳过验收；回滚本身也是变更，必须重跑验收并记录结果。
6. **R6** **MUST NOT** 在 soak/观察窗口内执行与观测目标无关的变更；如需变更，先结束或重置观测窗口并记录原因。

## 为什么（风险与案例）

- 案例事故中设备进入 bootloop 后只能清数据，服务器数据全靠既有备份与离线物料重建；若备份不可恢复，损失将从"停机"升级为"数据丢失"。
- 常见失败模式是"有快照但不会恢复"：快照缺少依赖、备份口令丢失、恢复步骤未演练，事故时才暴露（见 PIT-017）。
- 配置类变更（服务配置、代理、限流、升级）经常因语法或权限错误导致入口不可用；快照 + 单步回滚是最低成本的止损方式（见 PIT-014）。
- 案例实证：[08 事故复盘与重建](../docs/20-server/08-事故复盘与重置重建报告.md)、[17 研究平台构建手册](../docs/20-server/17-研究平台环境构建手册.md)、[28 全栈规范 §10.4–10.5](../docs/00-overview/28-全栈整体方案规范.md)。

## 允许的替代（MUST/SHOULD/MAY）

- **MUST** 变更前生成新备份并校验（如 `server-ops backup-verify` 一类的只读校验）；记录备份 ID/时间/结果。
- **MUST** Tier2 写操作依赖受控 CLI 自动生成配置快照；同时手写回滚步骤（命令级，可被他人照做）并给出预计影响。
- **SHOULD** 按周期做恢复演练：解密、解包、在临时目录校验关键文件与服务可启动，记录 RTO/RPO 观察值。
- **SHOULD** 至少保留设备本地 + 一台可信主机上的加密副本；副本本身遵守 [GRD-006](GRD-006-secret-hygiene.md)。
- **MAY** 对不可逆操作增加"双人确认/延迟执行"；恢复只走 CLI 并带确认参数，不做网页一键恢复。

## 检查方式（Agent 可执行）

```bash
server-ops status
server-ops backup-verify
server-ops audit 20
```

- 人工核对四项证据：备份 ID 与校验结果、配置快照路径、回滚命令、恢复演练记录（日期 + 结果 + 执行人）。
- 产物核对：`tar -tzf <备份文件> | head` 能列出关键配置/数据文件；加密备份需要解密成功后才算通过。
- 快照核对：快照目录中存在变更前的配置文件；与正在运行的版本对比差异可解释。
- 时间顺序核对：备份/快照时间必须早于变更时间；变更后的审计条目应引用对应快照。
- 回滚演练核对：最近一次演练是否覆盖"恢复服务并验证健康"，而不是只看文件是否存在。

## 关联

- 踩坑：[PIT-017 快照无回滚](../pitfalls/PIT-017-snapshot-without-rollback.md)、[PIT-014 配置重载锁死](../pitfalls/PIT-014-config-reload-lockout.md)
- 护栏：[GRD-005 分级确认](GRD-005-tiered-ops-confirmation.md)、[GRD-006 密钥卫生](GRD-006-secret-hygiene.md)、[GRD-012 Agent 行为](GRD-012-agent-operating-rules.md)
- 方法论：[MTH-004 服务器栈](../methodology/03-server-stack.md)、[MTH-008 验收与稳定性](../methodology/07-validation.md)
- 案例：[haydn K40 Pro 案例](../cases/haydn-k40pro/README.md)
