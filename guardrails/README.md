---
id: GRD-000
title: 护栏索引与使用规范
type: guardrail
status: current
audience: human, agent
tags: guardrails, index, checklist, governance
depends: MTH-001, MTH-007
updated: 2026-11-14
agent_hint: 每次变更前后按本索引逐条自检；命中 blocker 红线立即停止，改用「允许的替代」或走授权评审，不得以效率为由破例。
severity: warning
scope: repo
---

# GRD-000 · 护栏索引与使用规范

> 本层是**不可协商**的约束，编号 GRD-001..016。每篇结构固定：红线（MUST NOT）→ 为什么 → 允许的替代 → 检查方式 → 关联。
> 权威顺序见 [AGENTS.md](../AGENTS.md)；任何 Agent 不得自行降低红线，规则冲突时以用户直接指令为最高并记录例外。

## 1. 用途

- 把真实案例中的事故（系统包误删 bootloop、服务全灭、密钥泄露等）反推成**执行前自检**的规则，而不是事后解释。
- 给人类维护者与后续 Agent 一份共同的"不做清单"，降低高风险操作的默认概率。
- 让红线可判定：每条都有可执行检查（命令或人工核对清单），可与 [MTH-008 验收](../methodology/07-validation.md) 联动。
- 不阻碍合理实验：需要非常规操作时，走「允许的替代」或按 [GRD-001](GRD-001-no-root-no-unlock-default.md)/[GRD-012](GRD-012-agent-operating-rules.md) 完成评审、授权与记录。

## 2. 严重度与适用范围

| severity | 含义 | 默认处置 |
|---|---|---|
| blocker | 违反即不得开始、合并或发布 | 立即停止；整改并补齐证据后才可继续 |
| warning | 可延后，但交付前必须清零或记录已批准的例外 | 记入 backlog 或例外清单，由维护者批准 |

scope 取值：device（宿主/设备操作）、server（服务器栈与控制面）、agent（Agent 行为）、repo（仓库、文档与供应链）。本索引文件不是一条红线，其 severity/scope 仅表示覆盖全仓。

## 3. Agent 使用方式（变更前后检查清单）

1. 变更前：读相关 GRD 与对应 PIT；只读核对现状（状态、健康、差异、审计），确认写范围与冻结区。
2. 逐条自检：命中 blocker 红线 → 停止，改用「允许的替代」；确需例外时按 GRD-012 申请人工授权并留记录。
3. 变更中：写操作走 GRD-005 分级流程；没有备份/快照/回滚路径不开始（GRD-004）。
4. 变更后：运行验证命令并保存证据（GRD-013）；失败立即回滚并如实报告（GRD-012）。
5. 提交前：跑 `python -m toolkit.repurpose validate --strict` 与 `python scripts/dev/check-links.py --strict-anchors`；确认未触碰冻结案例。
6. 协议/提示词/模板/校验器变更：加跑 `python -m toolkit.repurpose preflight` 与 Agent 回归 AR-01..AR-10（[GRD-016](GRD-016-agent-protocol-regression.md)）；不得为通过而修改检查。

## 4. 索引
| ID | 标题 | severity | scope | 一句话 | 文档 |
|---|---|---|---|---|---|
| GRD-001 | 默认不 Root、不刷机、不解锁 Bootloader | blocker | device | 高风险路线必须先过评估与用户明确授权 | [GRD-001](GRD-001-no-root-no-unlock-default.md) |
| GRD-002 | 禁止卸载系统包，只允许受控禁用 | blocker | device | 误删系统必需包会导致不可在线修复的 bootloop | [GRD-002](GRD-002-no-system-package-uninstall.md) |
| GRD-003 | 禁止 kill-all 与误杀服务器进程 | blocker | device | 一键清理会杀掉服务器栈并中断远程维护 | [GRD-003](GRD-003-no-kill-all.md) |
| GRD-004 | 变更前必须备份、快照并准备回滚 | blocker | server | 未验证可恢复的备份不算备份 | [GRD-004](GRD-004-backup-before-change.md) |
| GRD-005 | Tier1/Tier2/Tier3 分级确认 | blocker | server | 写操作必须确认、快照、审计；Tier3 只人工 | [GRD-005](GRD-005-tiered-ops-confirmation.md) |
| GRD-006 | 密钥与凭据卫生 | blocker | repo | 任何真实秘密不得进入仓库、日志、聊天或公网页面 | [GRD-006](GRD-006-secret-hygiene.md) |
| GRD-007 | 网络最小暴露 | blocker | server | 默认只监听回环/局域网，公网只经受控入口 | [GRD-007](GRD-007-network-least-exposure.md) |
| GRD-008 | 供电与热安全 | blocker | device | 7×24 插电必须管理温度、电池与单点故障 | [GRD-008](GRD-008-power-thermal-safety.md) |
| GRD-009 | 外部服务须用户明确同意 | warning | server | 监控/异地备份/MFA/VPN 等未获同意不接入 | [GRD-009](GRD-009-external-services-consent.md) |
| GRD-010 | 开源许可合规 | warning | repo | GPL 只参考不复制，引入第三方保留版权/NOTICE | [GRD-010](GRD-010-license-compliance.md) |
| GRD-011 | 隐私数据采集与脱敏 | blocker | repo | 序列号/SSID/账号/位置等采集物必须隔离或脱敏 | [GRD-011](GRD-011-privacy-inventory.md) |
| GRD-012 | Agent 行为红线 | blocker | agent | 先只读核对、不越权、不伪造验收、变更走 DoD | [GRD-012](GRD-012-agent-operating-rules.md) |
| GRD-013 | 不伪造验收 | blocker | agent | 未实测不得标完成，目标值/实测值分开并有证据链 | [GRD-013](GRD-013-no-fake-acceptance.md) |
| GRD-014 | 固件冻结与受控升级 | blocker | device | 禁止自动 OTA，升级前后都要评估与重跑验收 | [GRD-014](GRD-014-firmware-freeze-ota.md) |
| GRD-015 | Root 实验设备的受控操作边界 | blocker | device | 仅授权专用实验设备；官方解锁/救援就绪/不降级/不关 AVB/最小 su | [GRD-015](GRD-015-root-lab-controlled.md) |
| GRD-016 | 协议/提示词变更须回归且不得弱化校验 | blocker | agent | 协议、提示词、模板、校验器变更必须跑 preflight+回归，禁止为变绿改检查 | [GRD-016](GRD-016-agent-protocol-regression.md) |
> **例外关系**：GRD-015 是 GRD-001 的受控例外实施细则，不是普遍放宽；非实验设备仍按 GRD-001 默认拒绝。两者冲突时以更严格者为准。
## 5. 格式规范

- front matter 是**文件头部**（首行 `---` 到下一个 `---`；末尾不要求 `---`）；必填 `id,title,type,status,audience,tags,updated,agent_hint`，**GRD 额外必需** `severity,scope`（缺失/非法会被 `validate --strict` 判失败），`depends` 用逗号串；禁止嵌套结构。
- 正文固定五节：红线、为什么、允许的替代、检查方式、关联；红线用编号列表，允许的替代区分 MUST/SHOULD/MAY。
- 只用相对路径链接，禁止 `#anchor`；不写绝对路径、IP、端口、凭据与个人信息；不写占位待办。
- 文件名 `GRD-NNN-<kebab-topic>.md`，全 ASCII；ID 只增不复用；索引/README 用 `GRD-000`。
- 每条红线都必须能被检查：命令可复现，或给出可逐项勾选的人工核对清单。

## 6. 如何新增一条护栏

1. 先确认现有 GRD/PIT 未覆盖；来源必须是真实事故、可复现风险或明确的通用风险（后者需标注）。
2. 取新编号（查 [agent-manifest.json](../agent-manifest.json) 或 `grep 'id:'`），按 [模板](../toolkit/templates/guardrail.md) 起草；工具未就绪时按本文件 §5。
3. 必写内容：红线、风险与案例证据（相对链接）、允许的替代、可执行检查、与 PIT/MTH 的双向链接。
4. 跑 `validate --strict` 与 `check-links --strict-anchors`；索引由 `toolkit index` 生成，不手改 manifest。
5. 对外契约或红线变化记入 [CHANGELOG](../CHANGELOG.md)，并在报告中说明理由与回滚方式。

## 7. 与踩坑、方法论、案例的关系

- PIT 记录"发生了什么"，GRD 把根因固化为"以后禁止什么"，MTH 给出"应该怎么做"。
- 案例 [haydn K40 Pro](../cases/haydn-k40pro/README.md) 是证据来源；引用需标注"案例实证"，通用结论必须能在新设备复现。
- 新增 PIT 若暴露未覆盖的红线，应同步补一条 GRD；GRD 若无 PIT 支撑，必须注明"通用风险"。

## 8. 关联入口

- 踩坑库：[../pitfalls/README.md](../pitfalls/README.md)
- 方法论：[../methodology/README.md](../methodology/README.md)、[MTH-001 边界与原则](../methodology/00-foundations.md)、[MTH-007 安全](../methodology/06-security.md)
- 工具链：[../toolkit/README.md](../toolkit/README.md)、[工具模板](../toolkit/templates/guardrail.md)
- 案例：[../cases/haydn-k40pro/README.md](../cases/haydn-k40pro/README.md)
