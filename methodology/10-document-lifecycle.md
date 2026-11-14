---
id: MTH-011
title: 文档生命周期、归属、命名与变更联动
type: methodology
status: current
audience: human, agent
tags: documentation, naming, adr, index, linkage, manifest, agent, knowledge-debt
depends: MTH-009, MTH-001, MTH-015, MTH-017
updated: 2026-11-14
agent_hint: 新增/移动文档、判断事实归属、命名、写 ADR 或同步变更时读本文；归档窗口、阅读预算与机器校验读 MTH-015；归档默认不读。
---

# MTH-011 · 文档生命周期、归属、命名与变更联动

> **一句话**：仓库长期由 Agent 迭代，文档必须**有归属、有索引、有决策、有联动**——同一事实只写一处，新增/移动必须登记索引并全仓替换引用，改动必须同步它声明的下游。
> **权威边界**：读序权威在 [AGENTS.md](../AGENTS.md) §0；操作/红线权威在 AGENTS §2.1/§3；本文规定**写入边界、命名、索引、ADR 与变更联动**；CHANGELOG 归档窗口、阅读预算、分层加载与机检见 [MTH-015](15-archive-and-context-budget.md)；数值上限唯一来源是 [toolkit/schema/doc-policy.json](../toolkit/schema/doc-policy.json)。

## 1. 适用场景与目标

- 本层回答四个问题：**这条事实写在哪（归属）、文件叫什么（命名）、为什么要这样定（ADR）、改动要同步什么（联动）**。窗口/状态段/预算/机检规则见 [MTH-015](15-archive-and-context-budget.md)。
- **目标**：① 单一归属（每类事实一处维护，其余只链接）；② 索引完备（文档不进索引＝不存在）；③ 变更可追溯（决策有 ADR/台账，契约变更同步下游）。
- **丢失症状**（命中任一即按 §2 核对归属与联动）：同一结论多篇且已不一致；新建/移动文档未登记索引；决策只停留在口头或聊天；改完契约未同步 schema/测试/README。

## 2. 索引四表、命名、决策与联动

### 2.1 索引四表责任（参考 01 §2.3）

| 表 | 位置 | 内容 | 维护责任 | 更新时机 |
|---|---|---|---|---|
| ① 按任务取文档 | [methodology/README.md](README.md) §4 | 「我要做 X → 先读 A 再读 B」 | 维护者；文档作者提供入口 | 新增/移动文档、任务类型变化 |
| ② 文档地图 | 同上 §4 | 每篇：ID、规模、解决什么、主要读者 | 维护者；作者登记 | 新增/移动/改变读者定位 |
| ③ 单一事实源 | 同上 §4 | 每类事实只认哪篇（协议/方法/证据/索引/队列） | 维护者 | 新增事实类型或归属变化 |
| ④ 维护规则 | 本页 §4 + [AGENTS.md](../AGENTS.md) §10 | 谁维护、何时更新、更新后跑什么校验 | Lead/维护者 | 结构性/契约变更 |

- **执法** ⛔：新建文档必须登记索引，迁移必须改引用并全仓搜索旧路径；**未入索引的文档等于丢失**（ERP-R VER-006 教训）。能用脚本查的（manifest/validate/check-links）必须脚本化；不能的写进 DoD 自检。
- **自动兜底**：`agent-manifest.json` + 分片由 `python -m toolkit.repurpose index` 生成，`validate` 校验其与内容一致；不为未登记文档建手工索引。

### 2.2 记录边界（单一归属）

| 事实类型 | 唯一归属 | 其他位置只允许 |
|---|---|---|
| 当前规范/方法/边界 | `methodology/`（MTH） | 链接 + 一句话定位 |
| 红线与不可协商约束 | `guardrails/`（GRD） | 链接；不得改写成"应当" |
| 踩坑证据/根因/修复 | `pitfalls/`（PIT） | 链接；不得只抄结论 |
| 决策与口径裁决 | `adr/`（ADR）；轻量决策进 [adr/README.md](../adr/README.md) 台账 | 链接；不得只写"团队决定了" |
| 对外可感知变更摘要（当前） | [CHANGELOG.md](../CHANGELOG.md) 窗口（≤8 条，规则见 [MTH-015](15-archive-and-context-budget.md) §2） | 引用版本号/条目标题 |
| 当前任务/未完成/需授权 | [backlog.json](../backlog.json)（仅 pending/in_progress 与最近 ≤5 条 done；更早进 `backlog-archive.json`；文件 ≤600 行，超限先压缩/归档再新增） | 链接 BL-ID |
| 设备与案例事实 | `cases/` + 旧 `docs/`（冻结） | 链接并标"案例实证/历史快照" |
| 一次性过程产物 | gitignored `inventory/`（见 §2.6） | 正式文档**不得引用** |
| 机器索引 | `agent-manifest.json` 根摘要 + `agent-manifest.d/` 分片（生成物） | 只引用，不手改 |

- **必须**：新增事实先判归属再落笔；同一事实只写一处、其余改链接；发现重复以唯一归属收敛；冻结区只允许事实纠错。
- **禁止**：把 A 正文复制到 B、在状态段复述 CHANGELOG 细节、把归档摘要搬回方法论；`blocked` 必须写具体阻塞条件，不得只写"待定"。

### 2.3 命名规范（机器可检）

- **文件名**：全 ASCII、小写 **kebab-case**（`^[a-z0-9]+(?:-[a-z0-9]+)*\.md$`）；禁止空格/下划线/中文/emoji/混合大小写。
- **约定入口豁免**：`README.md`、`AGENTS.md`、`CHANGELOG.md`、`LICENSE` 以及已被外部工具/脚本引用的固定入口保留原名。
- **目录前缀**：methodology=`<两位>-slug`；pitfalls=`PIT-<3位>-slug`；guardrails=`GRD-<3位>-slug`；adr=`<4位>-slug`；cases 用 ascii 子目录；templates 用 ascii slug。
- **禁状态词**：`final`、`latest`、`new`、`v2`、`copy`、`副本`、`最终版`；版本用 Git 历史、front matter `status` 或 ADR/CHANGELOG 表达，被取代的稳定文档保留 ID 并标 `superseded`，不另造 `-v2` 文件。
- **日期快照**：仅时点快照/调研/审计用 `YYYY-MM-DD-<topic>.md`；长期有效的规范/指南/模板**不带日期**。
- **`updated` 语义**：front matter `updated` 表示**内容**最后一次实质修订日期，不是排版/重排日期；改了正文、规则或链接目标就应当同步为提交当日。`validate` 以 git 提交日期为参照机检"内容改了但日期没改"（`DOC_UPDATED_STALE`，advisory，不阻断门禁）；判定口径、适用边界（只覆盖 methodology/pitfalls/guardrails）与误报边界见 [MTH-015](15-archive-and-context-budget.md) §5.3。
- **一个文件一个主题**：禁止 `notes.md`/`misc.md`/`document.md`/`temp.md` 等无区分力名称；目录表达类别，文件名表达主题，禁止重复编码（如 `docs/agent/agent-guide.md`）。
- **重命名纪律** ⛔：文件名是仓库接口——原子化同步全部 Markdown 引用、索引、README、脚本/配置路径，搜索旧文件名；`check-links --strict-anchors` 全绿前不算完成；被外部引用/多仓引用的文件先登记影响与过渡期。
- **机检**：`validate` 的 `DOC_NAMING` 检查（规则见 [MTH-015](15-archive-and-context-budget.md) §5）；人工核对仅作兜底。

### 2.4 决策记录（ADR）

- **触发**：架构/方案选型、口径裁决、不可逆变更、被否决的重要备选、Stop/Pivot、协议 MAJOR 变更、破坏性契约变更。
- **格式**：`adr/NNNN-slug.md`（四位序号，`0001` 起连续）；默认 Nygard 五段：`状态 / 背景 / 决策 / 后果`（重大决策加「备选方案正反对比」）；front matter 含 `id: ADR-NNNN`、`type: adr`、`status`、`updated`，被取代时可写 `superseded_by`。
- **status 枚举**：`proposed / accepted / superseded`；**被取代不删除**，新 ADR 回链旧 ADR；状态表内追加修订行（R1、R2…含日期与一句话内容），勘误不抹历史。
- **轻量决策台账**：够不上 ADR 的一行一条记入 [adr/README.md](../adr/README.md)（D-01、D-02…），条数增长后再升级为 ADR；新 ADR 必须在索引登记（无孤儿 ADR）。
- **禁止**：口头决策不留痕、删除旧 ADR、用 ADR 替代需求卡（需求基线与交付流程见 [MTH-013](12-delivery-governance.md)）。

### 2.5 变更-文档联动矩阵（改了什么，就同步它声明的下游）

| 变更类型 | 必须联动 | 机检/证据 |
|---|---|---|
| 新增/移动/归档文档 | 索引四表（§2.1）+ 全仓旧路径替换 + 交叉链接 | `check-links`、`validate`、`index` |
| 改命令/脚本契约（参数/输出/退出码） | [toolkit/README.md](../toolkit/README.md) + schema + 测试 + 调用方脚本 | 单测 + `--help` |
| 改 API/遥测字段（改名/删除/语义） | 兼容矩阵 + 消费者（控制面/仪表盘/审计）+ CHANGELOG + 兼容/弃用流程（[MTH-016](16-release-compatibility-data.md) §3） | 契约测试 + 兼容证据 |
| 改 profile schema | [device-profile.schema.json](../toolkit/schema/device-profile.schema.json) + assess/plan + 案例 profile + 模板 | schema 校验 + 案例回归 |
| 新增 PIT 条目 | 索引登记 + 评估能否机制化为检查（lint/validate/测试） | `validate` PIT 检查 |
| 改 AGENTS/规范正文 | 协议版本（MAJOR/MINOR/PATCH）+ 回归（AR-01..10）+ CHANGELOG + ADR（MAJOR 时） | `preflight` 回归 |
| 改模板 | 模板示例 ID 不占号 + 使用方文档同步 + 模板一致性测试 | 一致性测试（`BL-009`） |
| 改 backlog 状态/结构 | schema + `owner/updated/result` + 归档窗口（[AGENTS.md](../AGENTS.md) §8） | `validate` backlog 检查 |
| 改红线/目录结构/ID 前缀/权威顺序 | 破坏性变更流程：ADR + 迁移说明 + README/manifest/模板/校验器同步 | 全量质量门 |

- **判定**：联动失败即视为本单元未完成；同步不了的，在汇报中列为未完成项并进 backlog（[MTH-014](13-agent-sop.md) §9）。
- **未实测声明**：矩阵中遥测字段契约、profile schema 兼容回归与模板一致性测试**尚未形成自动化证据**（待落地，对齐 [MTH-013](12-delivery-governance.md) §8）。

### 2.6 一次性产物与会话任务区

- **位置**：本仓库以 gitignored 的 `inventory/`（或临时目录）承载调研、审计、会话中间产物；不得在正式层新建 `YYYY-MM-DD/` 目录。
- **定位声明**：任务区产物是**时点快照**，权威顺序最低；**结论必须沉淀回 `methodology/`/`adr/`/`pitfalls/`/`cases/` 正式层才算存在**。
- **保留期**：默认保留建议 ≤30 天后清理/归档；正式文档**不得引用**任务区产物（引用即断链或误导）。
- **纪律**：入任务区前先判断是"证据/结论"还是"过程"；过程不必入库，结论不得只留在任务区。

### 2.7 知识债与度量

- **登记**：知识债像技术债一样三档进 [backlog.json](../backlog.json)，给时限与 Owner：
  - **P0**：影响正确性（口径漂移、索引缺失、未入索引文档、失效红线引用）——当轮修；
  - **P1**：影响效率（文档过时/重复、模板漂移、示例失效）——两周内；
  - **P2**：锦上添花（措辞、排版、可读性）——按容量安排。
- **实证缺口设时限**：知识体系声称"已验证"但缺实证的条目（如真机/soak/割接类）必须挂时限与验证计划，否则知识库空转（[MTH-008](07-validation.md) §7 目标值纪律）。
- **度量（建议每周期体检，选 5 项）**：索引覆盖率（正式文档入链率）、PIT 机制化率（有自动兜底的条目占比）、文档平均行数与超长篇数、会话任务区滞留量、机检通过率（`preflight`/`validate` 全绿轮次）。
- **禁止**：用"暂无时间"无限期挂账；用度量数字美化报告（数字须可复现，见 [MTH-010](09-glossary.md)）。

## 3. 维护与反例

### 3.1 操作清单

| 场景 | 步骤 |
|---|---|
| 新增/修订/移动文档 | ①按 [MTH-009](08-agent-handoff.md) 取 ID/用模板 → ②判归属与命名（§2.3）→ ③登记索引四表 → ④改引用后全仓搜旧路径 → ⑤跑质量门 |
| 做出关键决策 | ①判是否够 ADR（§2.4）→ ②写 `adr/NNNN-slug.md` 或台账 → ③登记 adr 索引 → ④联动矩阵（§2.5） |
| 结题/收尾 | ①会话产物结论回写正式层（§2.6）→ ②未完成项进 backlog/知识债（§2.7）→ ③清理任务区 |
| 记录变更/更新状态/重建索引/清理归档 | 见 [MTH-015](15-archive-and-context-budget.md) §6（窗口、状态段与索引操作） |

### 3.2 反例

| 反例 | 为什么错 | 正确做法 |
|---|---|---|
| 同一结论多处重复展开（文档无限追加） | 规范漂移，无法判断权威 | 单一归属 + 链接，其他位置只留定位 |
| `final-v2.md` / 中文文件名 / 带日期规范名 | 搜索与跨平台失效、状态词无从判断新旧 | kebab-case + 稳定 ID/status |
| 无 ADR 的"我们决定过了" | 后来者无法追为什么，反复争论或误删约束 | ADR 或决策台账留痕 |
| 移动/重命名后不搜旧路径 | 断链与旧副本并存，读者读到过期内容 | 原子化替换全部引用并跑 `check-links` |
| 正式文档引用 `inventory/` 一次性产物 | 产物清理后断链；权威顺序错位 | 结论回写正式层，过程不引用 |

> 归档窗口、状态段与阅读预算的反例见 [MTH-015](15-archive-and-context-budget.md) §6。

## 4. 与其他文档的关系

| 文档 | 职责 | 与本文关系 |
|---|---|---|
| [AGENTS.md](../AGENTS.md) §0/§2/§4/§9 | 权威读序、操作边界、命名/ADR/联动摘要、当前状态 | 读序与边界冲突以它为准；§9 受 MTH-015 §3 约束；归档只读边界在 §2.1 |
| [MTH-015](15-archive-and-context-budget.md) | CHANGELOG 窗口/归档、状态段上限、阅读预算、分层加载、机器校验 | 本文的"容量与读取"配套篇；两篇不重复抄写 |
| [README.md](../README.md) | 人类入口与状态/成熟度表 | 状态表受 MTH-015 §3 约束 |
| [CHANGELOG.md](../CHANGELOG.md) + [changelog/README.md](../changelog/README.md) | 当前窗口与归档索引 | 归档规则见 MTH-015 §2 |
| [backlog.json](../backlog.json) | 当前任务/未完成/需授权 | 状态详情不写进入口；知识债登记见 §2.7 |
| [adr/README.md](../adr/README.md) | 决策索引与轻量台账 | 格式与纪律见 §2.4 |
| [toolkit/README.md](../toolkit/README.md) | CLI 契约与质量门 | MTH-015 §5 命令语义以它为准 |
| [toolkit/schema/doc-policy.json](../toolkit/schema/doc-policy.json) | 数值上限唯一来源 | 本文只写语义，不抄数字 |
| [MTH-009](08-agent-handoff.md) | 交接、ID/front matter、任务生命周期、DoD | 新增文档取 ID 与交接走它 |
| [MTH-017](17-expansion-and-cli-contract.md) | 扩展 SOP、变更传播、CLI 契约 | 新增文档与 caps 变更走它 |
| [MTH-014](13-agent-sop.md) | Agent SOP/评审/汇报/回归 | 执行细节以它为准，本文不重复 |
| [MTH-013](12-delivery-governance.md) | 交付治理/阶段门/用户验收 | 交付流程产生的决策/证据按本文归档 |
| [MTH-016](16-release-compatibility-data.md) | 发布就绪/兼容弃用/数据隐私/依赖许可 | 交付流程产生的决策/证据按本文归档 |
| [MTH-003](02-roadmap.md)、[MTH-010](09-glossary.md) | 阶段口径与术语 | 状态摘要引用不复制；术语冲突以 MTH-010 为准 |

**权威顺序**（冲突时高层优先并修正低层）：用户指令 > AGENTS.md > `guardrails/` > `methodology/`（本文）> `pitfalls/` > `toolkit/` > `cases/` 与旧证据。本文**只管归属、索引、命名、ADR 与变更联动**，不改变读序（读序权威在 AGENTS §0），也不重新定义红线。

### 4.1 自检清单（交付前逐项勾选）

- [ ] 每条事实写了唯一归属，其他位置是链接而非复制；未新增第二事实源
- [ ] 新文件命名合规并已登记索引四表；移动/重命名已全仓替换旧路径
- [ ] 关键决策有 ADR 或台账；无"口头决定"
- [ ] 联动矩阵（§2.5）四类下游已同步：索引/契约/schema/测试/CHANGELOG
- [ ] 会话任务区结论已回写正式层，正式文档未引用一次性产物
- [ ] 容量与读取项（窗口 ≤8、状态段 ≤8、预算 ≤3、分片不手改）按 [MTH-015](15-archive-and-context-budget.md) §6 勾选
- [ ] `preflight`/`validate --strict` 全绿（含 doc-policy 上限、命名、协议、ADR/backlog/归档一致性）
