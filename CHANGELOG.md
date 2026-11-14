# 变更记录（CHANGELOG）

> 本文件是**当前迭代对外可感知变更摘要**，不是工作日志。当前窗口最多 **8 条**；更早条目按月归档到 `changelog/YYYY-MM.md`（**归档默认不读**，只在追溯时读单个文件）。
> 记录边界见 [MTH-011](methodology/10-document-lifecycle.md)，归档窗口与上下文预算规则见 [MTH-015](methodology/15-archive-and-context-budget.md)；归档索引见 §4。

| 项目 | 内容 |
|---|---|
| 文档 ID | HB-CHANGELOG-001 |
| 版本 | v2.0（2026-11-11 归档规范化） |
| 状态 | 现行 |
| 关联 | [MTH-011](methodology/10-document-lifecycle.md) · [MTH-015](methodology/15-archive-and-context-budget.md) · [changelog/README.md](changelog/README.md) · [当前状态](docs/00-overview/当前状态.md) · [README](README.md) · [AGENTS](AGENTS.md) |

## 1. 记录边界

| 内容 | 唯一位置 |
|---|---|
| 当前方法/规范/边界 | `methodology/`（MTH-001..018） |
| 红线与必须检查项 | `guardrails/`（GRD-001..016） |
| 踩坑证据与修复 | `pitfalls/`（PIT-001..025） |
| 当前任务/未完成/需要授权 | [backlog.json](backlog.json) |
| 对外可感知变更摘要 | 本文件（当前窗口 ≤8 条） |
| 历史变更 | `changelog/YYYY-MM.md`（归档，默认不读） |
| 原始过程/逐条命令输出 | git commit（本仓库无 PR/远程时由 commit message 承载） |
| 设备案例事实 | [cases/](cases/README.md) 与旧 `docs/`（冻结证据） |
| 机器索引 | `agent-manifest.json` 摘要 + `agent-manifest.d/` 分片 |

## 2. 硬上限

1. **每条最多一行**（三要素：变更 / 验证 / 未完成；无未完成可省略），禁止原始日志、测试计数明细、临时账号与清理记录。
2. **当前窗口最多 8 条**；新增第 9 条时，立即把最旧条目移入对应 `changelog/YYYY-MM.md`，不等月末。
3. 归档文件**只读不改**、按时间倒序追加；同一能力的后续修补并入原条目，不重复开条。
4. 归档索引在 §4 维护；`CHANGELOG.md` 体积与条数由 `toolkit validate` 机检（见 [doc-policy](toolkit/schema/doc-policy.json)）。

## 3. 当前变更（最新在上，最多 8 条）

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-11-14 | v1.65 | **机检补齐（BL-015 + updated 新鲜度）**：`validate` 新增 TOOL 登记表一致性（`toolkit/README` §3.1 ↔ `cli.build_parser()` 子命令 ↔ 根 manifest `tools`/`commands`；`TOOL_REGISTRY`/`TOOL_COMMAND`/`TOOL_MANIFEST`，strict 下 error）与 front matter `updated` 新鲜度（git `%cs` 比对最近提交日；`DOC_UPDATED_STALE` advisory，只覆盖 methodology/pitfalls/guardrails，无 `.git`/未跟踪/浅克隆/git 不可用时静默跳过）；新增 9 项单测（一致/漏登记/多登记/断号/manifest 漂移/缺 README 跳过/新鲜/滞后/未跟踪），并把 14 篇活跃层文档 `updated` 同步为 2026-11-14；同步 [toolkit/README](toolkit/README.md)、[tests/README](toolkit/tests/README.md)、[MTH-011](methodology/10-document-lifecycle.md) §2.3、[MTH-015](methodology/15-archive-and-context-budget.md) §5、`backlog-archive` BL-015 result；v1.57 归档至 `changelog/2026-11.md`（窗口 8 条）；验证：preflight 全绿（validate --strict 0/0/0、全部单测、check-links、index 一致）；未完成：无。 |
| 2026-11-14 | v1.64 | **manifest 分片自动拆分（BL-017）**：`index` 单层 >40 条时按层内既有顺序每 40 条一片，拆为 `<layer>-p01.json`…（≤40 条仍用 `<layer>.json`，非末片满片、末片 1..40 条），根 `shards` 改为 `{count, parts[]}`；`validate` 新增 `SHARD_SPLIT`/`SHARD_NAMING` 校验片数、命名、非末片满片与各片合计；新增 40 不拆/41 拆、拆分完整性、单文件↔多片切换清理测试（297 项）；同步 [toolkit/README](toolkit/README.md)、[根 schema](toolkit/schema/agent-manifest.schema.json)、[分片 schema](toolkit/schema/manifest-shard.schema.json)、[MTH-015](methodology/15-archive-and-context-budget.md)；验证：preflight 全绿（validate 0/0/0、297 单测、check-links、index 一致）；未完成：无。 |
| 2026-11-14 | v1.63 | **附录编号归位（误用编号回收）**：`cases/ace-pro-pgp110/p1-config.md` 与 `cases/haydn-k40pro/reuse-guide.md` 改为普通附录（`APP-001`/`APP-002`，文件位置与内容不变），不再占用 CASE 编号、不进入案例登记表，当前最大案例编号回到 CASE-004、005/006 可复用；新增 `APP` 前缀并记入 [AGENTS](AGENTS.md) §4.1 与 [MTH-009](methodology/08-agent-handoff.md) §4.2（协议 v1.3→v1.4，MINOR），同步两篇案例 README 指针、[cases/README](cases/README.md)、[backlog](backlog.json) BL-036 记录与 manifest；验证：validate --strict 0 error/0 warning/0 advisory、preflight 全绿；v1.55 归档至 `changelog/2026-11.md`（窗口 8 条）；未完成：无。 |
| 2026-11-14 | v1.62 | **余量预警清零（BL-036）**：10 篇距上限 <15 行的文档全部处理到余量 ≥16 行——PIT-022/023/024/025 合并触发场景与关联/证据列表（69/70/73/74 行）、[GRD-015](guardrails/GRD-015-root-lab-controlled.md) 合并关联引用（74）、[adr/README](adr/README.md) 新增与维护流程改指 MTH-011 §2.4/§2.5 与 MTH-014 §7（74）、[toolkit/README](toolkit/README.md) 测试覆盖清单下沉 [toolkit/tests/README.md](toolkit/tests/README.md)（413）、[runbook 模板](toolkit/templates/runbook.md) 关联段合并（113）；用户授权下对冻结案例仅做结构下沉与指针：CASE-003 §6.3→[附录 APP-001](cases/ace-pro-pgp110/p1-config.md)（210）、CASE-001 §8→[附录 APP-002](cases/haydn-k40pro/reuse-guide.md)（240），事实/结论/未完成项未改写并在两篇 README 记录授权；验证：validate --strict 0 error/0 warning/0 advisory、preflight 全绿；BL-036 done、BL-026 归档；v1.54 归档至 `changelog/2026-11.md`（窗口 8 条）；未完成：无。 |
| 2026-11-14 | v1.61 | **MTH-009/MTH-002 拆分与容量余量预警（BL-035 / ADR-0006、ADR-0007）**：`methodology/08-agent-handoff.md` 284→约 200 行（七类扩展 SOP/变更传播/CLI 契约迁入 [MTH-017](methodology/17-expansion-and-cli-contract.md)），`methodology/01-assessment.md` 277→约 180 行（命令顺序/OEM 清单/产出物/失败处理/示例迁入 [MTH-018](methodology/18-assessment-execution.md)）；不删规则、两篇互链不抄写，交接协议与评估口径仍归原篇；[doc-policy](toolkit/schema/doc-policy.json) 新增「余量 <15 行」预警（`DOC_LINES_MARGIN`，advisory 级，不使 `validate --strict`/preflight 失败）；同步 AGENTS/README/methodology/README/MTH-000/001/003/004/005/006/007/009/010/013/015 与 [toolkit/README](toolkit/README.md)，新增 ADR-0006/0007 并登记台账；backlog BL-035 done、BL-025 移入 [backlog-archive.json](backlog-archive.json)、BL-036 登记 10 篇余量预警处置；v1.53 归档至 `changelog/2026-11.md`（窗口 8 条）；验证：preflight 全绿（validate --strict 0 error/0 warning、单测、check-links、index 一致）；未完成：历史 ADR 与已归档条目中指向旧节的引用不改写。 |
| 2026-11-14 | v1.60 | **MTH-013 拆分（BL-034 / ADR-0005）**：`methodology/12-delivery-governance.md` 290→187 行，拆出 [MTH-016 发布就绪、兼容与数据治理](methodology/16-release-compatibility-data.md)（150 行）承接原 §7–§10（部署/观测/runbook/Go-No-Go、兼容矩阵与弃用、数据地图与六问、依赖许可/SBOM/制品来源）；G0–G7 门禁仍归 MTH-013，MTH-016 只给 G5/G6 检查项；不删规则、两篇互链不抄写；同步 AGENTS/README/methodology/README/MTH-008/009/010/011/014/015 与 backlog pending 引用；新增 [ADR-0005](adr/0005-mth-013-split.md) 并登记台账；backlog BL-034 done、BL-024 移入 [backlog-archive.json](backlog-archive.json)；v1.52 归档至 `changelog/2026-11.md`（窗口 8 条）；验证：preflight 全绿；未完成：历史 ADR 与已归档条目中指向旧节的引用不改写。 |
| 2026-11-14 | v1.59 | **MTH-011 拆分（BL-033 / ADR-0004）**：`methodology/10-document-lifecycle.md` 299→158 行，拆出 [MTH-015 归档、上下文预算与机器校验](methodology/15-archive-and-context-budget.md)（190 行）承接 CHANGELOG 窗口/归档、状态段上限、阅读预算与分层加载、截断检测、机检上限；MTH-011 保留归属/记录边界/命名/ADR/联动矩阵；不删规则、两篇互链不抄写；同步 AGENTS/README/methodology/README/MTH-009（08）/MTH-013（12）/MTH-014（13）/pitfalls/toolkit/README/doc-policy 描述/changelog 索引与 [adr 台账](adr/README.md)（ADR-0004）；backlog BL-033 done、BL-023 移入 [backlog-archive.json](backlog-archive.json)（active done ≤5）；v1.51 归档至 `changelog/2026-11.md`（窗口 8 条）；验证：preflight 全绿（validate --strict 0/0、单测、check-links、index 一致）；未完成：历史 ADR-0001/0002 中指向旧篇的引用不改写（ADR 不改写历史，文件仍存在）。 |
| 2026-11-14 | v1.58 | **AGENTS 容量分流至健康档（BL-029 / ADR-0003）**：AGENTS.md 291→197 行（validate `protocol_tier=healthy`）——§0 阅读预算/停止条件、§4 文档约定、§5 任务协议、§6 扩展 SOP 去重并改为指向 MTH-009/011/014 的摘要，删除重复的 §8.1 YAML（改指 agent-manifest 的 `entrypoints`/`exit_codes`）；协议版本 v1.2→v1.3（MINOR，ADR-0003），未删红线、未改权威顺序、未弱化校验；backlog.json 上限 640→600 行（超限先压缩/归档，与 done ≤5 窗口共同机检）；同步 README 协议版本、MTH-011 §2.2 归属表；验证：preflight 全绿（validate --strict 0/0、292 单测、check-links、index 一致）。 |

## 4. 归档索引

| 月份 | 条目 | 文件 |
|---|---|---|
| 2026-11 | 58 条（v1.0–v1.57） | [changelog/2026-11.md](changelog/2026-11.md) |
