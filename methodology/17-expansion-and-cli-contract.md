---
id: MTH-017
title: 扩展 SOP、变更传播与工具契约
type: methodology
status: current
audience: human, agent
tags: expansion, change-propagation, cli-contract, tool, adr, request, methodology
depends: MTH-009, MTH-011, MTH-013, MTH-016
updated: 2026-11-14
agent_hint: 新增 MTH/PIT/GRD/案例/ADR/需求卡、改契约或改工具 CLI 前读本文；交接与任务生命周期读 MTH-009，文档归属与命名读 MTH-011。
---

# MTH-017 · 扩展 SOP、变更传播与工具契约

> **一句话**：新层文档怎么取号、怎么写、怎么登记，改契约时哪些地方必须同步，以及统一 CLI 的输入/输出/退出码——这三类"可复制执行的扩展规则"集中在本篇，避免散落在交接协议里。
> **权威边界**：交接协议、front matter/ID 规则、任务生命周期与 DoD 在 [MTH-009](08-agent-handoff.md)；文档归属、命名与联动矩阵在 [MTH-011](10-document-lifecycle.md)；数值上限唯一来源是 [doc-policy](../toolkit/schema/doc-policy.json)（规则见 [MTH-015](15-archive-and-context-budget.md) §5）；交付治理与需求基线在 [MTH-013](12-delivery-governance.md)、发布/兼容/数据在 [MTH-016](16-release-compatibility-data.md)。本文只保留扩展 SOP、变更传播与 CLI 契约。

## 1. 扩展 SOP（七类）

> 所有新层文件写完后都必须：跑索引 + 校验 + 链接检查；必要时更新索引 README 与交叉链接。模板在 [toolkit/templates/](../toolkit/templates/)；SOP 细节（评审/证据/回归）见 [MTH-014](13-agent-sop.md)。

### 1.1 新增方法论篇（MTH）

1. 取号：查 [methodology/README.md](README.md) 与 manifest，取未使用 MTH 号（只增不复用）。
2. 文件：`methodology/<编号>-<ascii-slug>.md`；front matter `type: methodology`，`depends` 写真实依赖。
3. 正文必备：定位/适用边界 → 决策表或流程图 → 命令与清单 → 验收标准 → 失败处理/fallback → 证据与案例链接 → 与其他篇交叉链接。
4. 索引与验收：`index` 后确认 README 索引与 manifest 均列出；`validate --strict` + `check-links --strict-anchors` 全绿；ID 唯一、无未完成标记/无敏感值、链接目标存在、与至少 2 篇既有文档互链、`updated` 为当天。

### 1.2 新增踩坑（PIT）

1. 取号：`PIT-<下一个号>`；文件 `pitfalls/PIT-<编号>-<ascii-slug>.md`；一条一个问题。
2. front matter：`type: pitfall`；`depends` 指向相关 MTH/GRD。
3. 正文必备：症状 → 触发场景 → 根因 → 规避与修复 → 验证方式 → 关联（MTH/GRD）→ 证据（旧 docs/案例相对链接；无实测则标"通用风险"）。
4. 索引与验收：更新 [pitfalls/README.md](../pitfalls/README.md) + `index` + `validate --strict`；规避方式可执行、证据链接可打开、severity 分级明确、不得编造案例。

### 1.3 新增护栏（GRD）

1. 取号：`GRD-<下一个号>`；文件 `guardrails/GRD-<编号>-<ascii-slug>.md`；front matter `type: guardrail`。
2. 正文必备：红线（一句可判定）→ 为什么（动机/事故证据）→ 允许的替代方案 → 检查方式（可执行命令/人工核对）→ 关联。
3. 索引与验收：更新 [guardrails/README.md](../guardrails/README.md) + `index` + `validate --strict`；红线可判定且不重复、必须有检查方式、必须与至少一条 PIT 或案例互链；与已有红线冲突时先澄清。

### 1.4 新增工具子命令（TOOL）

1. 取号：`TOOL-<下一个号>`；先在 [toolkit/README.md](../toolkit/README.md) 的「工具登记表（TOOL-001..010）」登记（新增工具第一步），再实现。
2. 实现：`toolkit/repurpose/` 新增子命令；零第三方依赖、不联网；人类摘要 + `--json`；参数有默认值与校验；契约见 §3。
3. 测试：`toolkit/tests/` 增加夹具驱动单测（无真机可跑）→ `python -m unittest discover -s toolkit/tests -t . -v` 全绿。
4. 索引与验收：`index` 重建 manifest；更新 `toolkit/README.md`（用法/参数/输出/退出码/示例）；schema 放 `toolkit/schema/`；`--help` 可运行、测试全绿、schema 与实际输出一致、不引入未记录依赖、不改变既有子命令语义（破坏性变更需版本化+迁移说明）。

### 1.5 新增案例（CASE）

1. 取号：`CASE-<下一个号>`；目录 `cases/<codename>/`（小写 ASCII）。
2. 文件：`README.md`（总述/门禁证据/局限）、`profile.json`（脱敏设备档案，按 schema）、`oem-profile.md`（该 OEM 自启/省电/权限步骤）；front matter `case-study`/`oem-profile`。
3. 脱敏：序列号、IP、账号、token、口令、个人信息一律不入库；profile 的 `source` 标注 documented 或 measured。
4. 索引与验收：更新 [cases/README.md](../cases/README.md) + `index` + `validate --strict`；`assess` 对 profile 输出稳定；案例关联至少 1 条 PIT 或 MTH、证据可追溯、未实测部分标"待设备验证"、示例值不得写成实测。

### 1.6 新增决策记录（ADR）

1. 取号：`ADR-<下一个四位号>`；文件 `adr/<NNNN>-<ascii-slug>.md`；序号从 `0001` 起连续，只增不复用。
2. 正文：Nygard 五段——`状态 / 背景 / 决策 / 后果`（重大决策加「备选方案正反对比」）；front matter `type: adr`、`status ∈ proposed/accepted/superseded`；被取代不删除旧文件并写 `superseded_by` 回链。
3. 触发：架构/方案选型、口径裁决、不可逆变更、被否决的重要备选、Stop/Pivot、协议 MAJOR 变更、破坏性契约变更（规则见 [MTH-011](10-document-lifecycle.md) §2.4）。
4. 索引与验收：在 [adr/README.md](../adr/README.md) 索引登记（无孤儿 ADR）；轻量决策进台账（D-NN 一行一条）；`validate` ADR 检查（文件名/ID/status/五段/索引）全绿；模板 [toolkit/templates/adr.md](../toolkit/templates/adr.md)。

### 1.7 新增需求卡/交付卡（REQUEST）

1. 取号：`REQ-<下一个号>`（可选 ID；需求卡是交付物，不进入内容索引）；模板 [request-card](../toolkit/templates/request-card.md)。
2. 必填：ID/状态/DRI/验收人/目标版本、背景与问题、目标、非目标、场景、验收条件（含失败/空数据/权限不足/错误恢复）、依赖与约束、风险与备选、影响面。
3. 流程：M/H 任务先过 G0/G1/G2（[MTH-013](12-delivery-governance.md) §5），验收条件批准后为基线，变更走变更单；发布/割接卡与 Go/No-Go 见 [MTH-016](16-release-compatibility-data.md) §2。
4. 验收：需求卡与 [acceptance 模板](../toolkit/templates/acceptance.md) 的判据一致；完成态以用户/验收人实际走通为准，Agent 自测不替代用户验收。

## 2. 变更传播

| 改了什么 | 必须同步 |
|---|---|
| front matter 字段/ID 规则 | 校验器 + 模板 + MTH-009 + AGENTS.md + 新层文档抽查 |
| ID 前缀/新增顶层目录 | README + manifest schema + 模板 + 校验器 + 迁移说明（破坏性变更） |
| JSON schema / 字段语义 | 生成器 + 消费者（工具/API/UI）+ 测试 + 模板 + 案例 + [MTH-009](08-agent-handoff.md) |
| 工具 CLI（参数/输出/退出码） | toolkit README + schema + 测试 + 模板/脚本调用方 + 本文 §3 |
| 安全控制（认证/pin/凭据位置） | MTH-007 + 实现 + 测试 + 部署说明 + 验收清单 |
| 验收门禁/口径 | MTH-008 + 采集工具 + 报告模板 + 案例记录 |
| 对外事实/状态 | `CHANGELOG.md` + 权威状态文件 + 相关索引 |

**破坏性变更**（新增顶层目录、改 ID 前缀、改权威顺序、改 schema 主版本）：用户/Lead 批准 → 更新 README/manifest schema/模板/校验器 → 给迁移说明 → 全量校验。任何 Agent 不得通过删除协议、降低红线、跳过校验来"通过验收"。

## 3. 工具 CLI 契约

统一入口 `python -m toolkit.repurpose <subcommand>`（零第三方依赖、不联网）。

| 子命令 | 用途 | 关键输入 | 输出 | 退出码 |
|---|---|---|---|---|
| `detect` | 识别连接设备/环境 | 传输层（可注入） | 摘要；`--json` 结构化 | 0/2/3 |
| `probe` | 只读采集设备字段 | 设备 + 权限 | 字段 JSON / 摘要 | 0/2/3 |
| `assess` | 路线/门禁/风险/下一步 | profile 或 probe 输出 | `repurpose.assessment.v1` | 0/2/3/4 |
| `plan` | P0–P6 阶段计划 | profile/评估 | `repurpose.plan.v1`（`--format json`） | 0/2/3/4 |
| `new-profile` | 生成脱敏设备 profile | 交互/参数 | profile 文件 + 校验 | 0/2/3/4 |
| `index` | 重建机器索引（根摘要 + 分片） | 仓库内容 | `agent-manifest.json` + `agent-manifest.d/*.json` | 0/2/3/4 |
| `validate` | 校验 front matter/ID/断链/体积/命名/协议/PIT/ADR/backlog/CHANGELOG 归档 | `--strict`、`--json` | 摘要 + 错误定位 | 0/2/3/4 |
| `preflight` | 统一质量门：`index` → `validate --strict` → `unittest discover` → `check-links --strict-anchors` | `--root`、`--skip-tests`、`--skip-links`、`--no-index`、`--json` | 步骤表；`--json` 输出 `repurpose.preflight.v1` | 0/3/4 |

**统一约定**：退出码固定（0 成功 / 2 用法错 / 3 前置不满足 / 4 校验失败），CI 只按退出码判定；默认人类摘要，`--json`/`--format json` 输出稳定 schema；错误信息不含凭据/绝对路径/设备序列号；确定性（除时间戳/环境探测外不随机）；只写自己的产物（`index` 只写 manifest，`new-profile` 只写目标 profile）；设备能力必须支持注入 fixture 以在无真机环境测试。新增子命令见 §1.4，破坏性变更需版本化+迁移说明。

**validate 已实现（契约与状态见 [toolkit/README.md](../toolkit/README.md)）**：`validate` 新增协议（`PROTOCOL_*`）、命名（`DOC_NAMING`）、PIT（`PIT_*`）、ADR（`ADR_*`）、backlog（`BACKLOG_*`）、CHANGELOG 归档（`CHANGELOG_ARCHIVE`）与 Agent 回归（`AGENT_REGRESSION`）检查（语义见 [MTH-015](15-archive-and-context-budget.md) §5.3）；`preflight` 退出码 **0=全绿 / 3=有 SKIPPED / 4=任一步 FAILED**，三态语义见 [MTH-014](13-agent-sop.md) §7。若工具尚未包含某检查，如实标注"未机检"，不得写已通过。

## 4. 与其他文档的关系

| 文档 | 职责 | 与本文关系 |
|---|---|---|
| [MTH-009](08-agent-handoff.md) | 交接协议、分层/权威、front matter/ID、任务生命周期、DoD 摘要 | 本文是其扩展执行细则；ID/front matter 规则仍以它为准 |
| [MTH-011](10-document-lifecycle.md) | 文档归属、命名、ADR 触发、联动矩阵 | 新增文档的"放哪里、叫什么"以它为准 |
| [MTH-014](13-agent-sop.md) | Agent SOP、评审、汇报、回归 | 执行细节以它为准，本文不重复 |
| [MTH-015](15-archive-and-context-budget.md) | 数值上限、归档与阅读预算 | 本文不写数字上限，统一读 doc-policy |
| [MTH-013](12-delivery-governance.md) / [MTH-016](16-release-compatibility-data.md) | 交付门 G0–G7 / 发布兼容与数据 | 需求卡流程与发布检查项以它们为准 |
| [toolkit/README.md](../toolkit/README.md) | CLI 契约现状与质量门 | 本文 §3 是规范摘要，实现状态以它为准 |
