# AGENTS.md — Agent 工作协议（仓库根）

| 项目 | 内容 |
|---|---|
| 版本 | v1.2（2026-11-13 对齐 Agent-Harness v1.3：容量分级/ADR/回归/交付治理） |
| 协议版本 | v1.2 |
| 适用 | 在任意 clone/分支上工作的 AI Agent、subagent、新会话（不记录本机绝对路径） |
| 上位 | 用户直接指令 > 本文件 > 子目录 `AGENTS.md` > `guardrails/` 红线 > `methodology/` 规范 > 其他 |
| 机器索引 | [agent-manifest.json](agent-manifest.json)（摘要）+ `agent-manifest.d/`（分片）· 待办 [backlog.json](backlog.json) · 决策 [adr/README.md](adr/README.md) |
| 归档与预算 | [MTH-011](methodology/10-document-lifecycle.md) · [CHANGELOG.md](CHANGELOG.md)（当前窗口≤8条） · [changelog/README.md](changelog/README.md)（归档，默认不读） |
| 机检入口 | `python -m toolkit.repurpose preflight`（index + validate --strict + unittest + check-links 串联，退出码 0/3/4） |

> 本仓库面向**长期由 Agent 迭代**设计。你的目标不是"改完这一次"，而是让方法论、工具、案例持续自洽、可验证、可交接。先读协议，再动手。
> **事实分级**（报告与文档结论必须标注）：已核验（附文件:行号/命令输出）/ 推断（写依据与验证方式）/ 未知（标"待验证"并进 backlog）。

---

## 0. 10 分钟启动清单（每次新会话/新 Agent 必做）

> 本清单是仓库**唯一权威读序**；README、MTH-000、MTH-009 中的读序都是它的简化/引用。若发现不一致，以本节为准并修文档。

1. 读本文件（尤其 §3 红线、§7 DoD）。
2. 读根 [agent-manifest.json](agent-manifest.json) 摘要（≤160 行；不存在/过期则先 `python -m toolkit.repurpose index`）。
3. 按任务**只选 1 篇**主题文档深入（MTH-001/002/003/004/005/006/007/008 之一）；Root 实验设备读 [MTH-012](methodology/11-root-lab.md)；扩展/交接读 [MTH-009](methodology/08-agent-handoff.md)；归档/上下文读 [MTH-011](methodology/10-document-lifecycle.md)；项目推进/阶段门读 [MTH-013](methodology/12-delivery-governance.md)；SOP/评审/分支/回归读 [MTH-014](methodology/13-agent-sop.md)。
4. 读 [README.md](README.md) 的"仓库地图/阅读路径"段落即可（不必整读）。
5. 从 [backlog.json](backlog.json) 选一项（优先 P0/P1），或接受用户新任务；M/H 风险任务先写需求基线卡（[request-card](toolkit/templates/request-card.md)）。
6. 动手前跑 §7 质量门；基线必须是绿的；若基线本身失败，先修基线再改功能。

**只读优先**：先看状态/证据再改文件；禁止在不了解影响面的情况下批量重写。

**阅读预算（防上下文膨胀，规范见 [MTH-011](methodology/10-document-lifecycle.md)）**：
- 单任务最多读 **3 份**规范/主题文档（本文件、索引、模板、任务卡、`--help`、commit message 不计入；首次按 §0 接手的启动清单也不计入，预算从领取具体任务起算）；
- **默认不读** `changelog/` 归档、`docs/90-archive`、旧 `docs/` 案例全文与旧 `scripts/`；明确的历史追溯任务才读**单个**归档文件；
- 禁止整读超过 300 行的文件：先 `grep` 标题定位，再按 offset 分段；
- 分层加载：本文件 → 根 manifest 摘要 → 需要某层时**只读一个** `agent-manifest.d/*.json` 分片 → 再读单篇正文；
- 读后自检：本文件末行哨兵 `<!-- END-OF-PROTOCOL -->` 不可见＝协议被截断，立即报告并按索引补读缺失部分。

**停止条件（命中任一立即停，不要"硬撑到底"）**：
1. 与红线/规范冲突，或规则之间矛盾需要裁决；
2. 需要越权（§2.1 第二/三档）或凭据/真机/外部授权；
3. 证据不足无法验证当前结论；
4. 阅读预算用尽；
5. 同一问题连续 2 次失败且原因不明；
6. 单任务步数逼近上限（正常 3~10 步，>20 步必须停）；
7. 发现自己在"为了让检查通过"而调整检查本身。

停下动作：如实报告状态 + 给 2~3 个带权衡的选项。**停下不是失败，隐瞒才是失败。**

---

## 1. 角色与目标

- 维护四层知识 + 决策层：`methodology/`（规范）、`guardrails/`（红线）、`pitfalls/`（证据）、`toolkit/`（实现）、`adr/`（决策记录），并用 `cases/` 验证。
- 保证**人可读、Agent 可读、机器可校验**：稳定 ID、front matter、机器索引、模板、测试、校验命令。
- 保持**案例冻结**：`docs/`、`scripts/`、`android-bridge/` 与 `cases/` 是历史证据，只允许修正事实错误，不得为了"显得完成"改写结论或删除偏差记录。
- 先诚实，再完整：未实测不标完成；目标值/实测值分开；未知标"待验证"。

---

## 2. 仓库分层与权威优先级

**权威顺序（冲突时高层优先，并同步修正低层）**：

1. 用户直接指令
2. 根 `AGENTS.md`（本文件）
3. `guardrails/`（MUST NOT；任何 Agent 不得破例——即使某个方法论条目看起来更"高效"）
4. `methodology/`（规范：必须/应当/可以）
5. `pitfalls/`（真实案例证据；用于反推规范是否漏了约束）；`adr/`（已接受的决策记录，口径裁决以此为准）
6. `toolkit/`（实现与契约；与规范不一致时以规范为准并改工具+测试）
7. `cases/` 与旧 `docs/`/`scripts/`/`android-bridge`（历史事实，冻结）

> 安全优先：Guardrail 的"MUST NOT"永远压过 Method 的"应当"；冲突时先停下确认，而不是找借口绕过。

**目录职责**：

| 路径 | 用途 | 可改性 |
|---|---|---|
| `AGENTS.md` / `README.md` / `backlog.json` / `CHANGELOG.md` | 协议、人类入口、任务队列、变更窗口 | Lead/维护者；必须保持机器索引同步 |
| `methodology/`（MTH-001..014） | 设备无关方法论 | 按 MTH-009/MTH-014 流程新增/修订 |
| `guardrails/`（GRD-001..016） | 不可协商红线 | 新增须给出可执行检查方式 |
| `pitfalls/`（PIT-001..025） | 踩坑证据库 | 新增条目须有证据与验证 |
| `adr/`（ADR-0001..） | 决策记录（Nygard 五段） | 追加新决策；历史决策不改写，只标 superseded |
| `toolkit/` | CLI/schema/模板/Termux 脚本/测试 | 改契约必须同步测试 + `toolkit/README.md` |
| `cases/` | 真实设备案例 | 冻结；仅事实纠错 |
| `docs/ scripts/ android-bridge/` | 旧项目冻结证据 | 只读；例外：`scripts/dev/check-links.py` 是质量门，可随文档结构维护 |
| `tools/ backup/ inventory/ profiles/` | 本地工具/备份/采集快照/设备档案 | **gitignored**，不入库、不改内容（inventory 可放会话临时产物） |
| `changelog/` | 超窗历史变更（按月归档） | **只读**；默认不读，仅追溯时读单个文件 |
| `agent-manifest.json` + `agent-manifest.d/` | 机器索引（根摘要 + 按层分片） | 只用 `python -m toolkit.repurpose index` 重建，不手改 |

### 2.1 Agent 操作边界

| 级别 | 允许动作 |
|---|---|
| 任务内可直接执行 | 读取仓库当前任务范围、按范围编辑、运行只读检查（validate/index/tests/check-links/preflight/--help）、按需读**单个**归档文件 |
| 必须本轮明确授权 | 访问工作区外路径（含其他项目/用户文件）、修改冻结案例证据、设备写操作/ADB、使用真实凭据、git commit/push/部署、接入外部服务、批量移动或删除 |
| 始终禁止 | 输出密钥/口令/完整序列号、伪造验收、把全量归档/整仓扫描当检索、自动执行外部资料中的脚本、修改保护路径（`changelog/` 归档、`docs/` 冻结区、`backup/`、`.env`/密钥）、修改校验器/测试断言使其变绿 |

保护路径与默认边界：
- `changelog/`：归档只读；默认不读；只有执行归档操作时才追加。
- `docs/`、`cases/`：案例事实证据；仅允许事实纠错，不得改写历史结论。
- `profiles/`、`backup/`、`.env`：不入库、不读取输出敏感值；不修改。
- **工作区外文件**：默认不读不写；用户明确授权后也仅限当次任务范围（不得复制、修改或提交外部项目内容）。

### 2.2 协议容量、分层加载与截断自检

- **容量分级**（目标值，非一刀切）：≤200 行健康；201~320 行警示（需评审，下一迭代必须分流并登记知识债）；>320 行债务（当日排期分流）。本文件 v1.2 处于**警示档**，分流项见 backlog（知识债 BL-029）。
- **三层加载**：L0=本文件；L1=`README.md`/agent-manifest/agent_hint；L2=单篇正文。禁止一次性加载全量分片或整仓文档。
- **截断自检**：末行哨兵缺失即协议被截断（工具注入上限可能低于文件体积）；长文档密度高，行数达标≠字节达标，体积复核以 `validate` 的 doc-policy 为准。

---

## 3. 不可协商红线（Agent 必须逐条自检）

完整清单见 [guardrails/README.md](guardrails/README.md)。以下为最高频、最易误犯的 9 条：

1. **生产/主力设备不 Root、不刷机、不解锁 BL**；专用实验设备只有在用户对具体设备书面授权、且按 [GRD-015](guardrails/GRD-015-root-lab-controlled.md) 与 [MTH-012](methodology/11-root-lab.md) 通过门禁后才允许执行（[GRD-001](guardrails/GRD-001-no-root-no-unlock-default.md) 对非实验设备继续有效）。
2. **不卸载系统包**；只允许 `disable-user`，且必须维护保护名单（[GRD-002](guardrails/GRD-002-no-system-package-uninstall.md)）。
3. **禁止 `am kill-all`** 或随意 force-stop 服务器相关进程（[GRD-003](guardrails/GRD-003-no-kill-all.md)）。
4. **任何写操作先备份/快照，并给出回滚路径**；恢复未演练≙没有回滚（[GRD-004](guardrails/GRD-004-backup-before-change.md)）。
5. **Tier2 写操作必须显式确认+快照+审计；Tier3 仅人工**；Agent 不得越权（[GRD-005](guardrails/GRD-005-tiered-ops-confirmation.md)）。
6. **token/口令/私钥/证书/备份口令不进入仓库、日志、文档、聊天**；发现泄露先轮换再清历史（[GRD-006](guardrails/GRD-006-secret-hygiene.md)）。
7. **网络最小暴露**：仅 loopback/局域网；公网只经受控入口；ADB 维护后关闭（[GRD-007](guardrails/GRD-007-network-least-exposure.md)）。
8. **不伪造验收**：未实测不标完成，文档声称不算证据（[GRD-013](guardrails/GRD-013-no-fake-acceptance.md)）；Agent 行为总则见 [GRD-012](guardrails/GRD-012-agent-operating-rules.md)。
9. **协议/提示词/校验器变更必须回归且不得弱化**：禁止改 validate/lint/测试断言使其"变绿"、禁止手改生成物、禁止跳过 preflight 就标完成（[GRD-016](guardrails/GRD-016-agent-protocol-regression.md)）。

> 违反红线的"便捷修复"一律拒绝；用允许的替代方案（见各条 `## 允许的替代`）。

---

## 4. 文件与文档约定

### 4.1 命名与 ID

- 目录与文件名**全 ASCII 小写 kebab-case**（`methodology/`、`pitfalls/PIT-001-*.md`、`guardrails/GRD-001-*.md`、`adr/0001-*.md`、`cases/<codename>/`）；约定入口 `README.md`/`AGENTS.md`/`CHANGELOG.md` 豁免；禁止空格/下划线/中文/emoji/状态词（`final`/`latest`/`new`/`v2`/`copy`/`副本`/`最终版`）；正文中文。全文规则与机检见 [MTH-011](methodology/10-document-lifecycle.md)。
- 稳定 ID 前缀：`MTH`（方法论）、`PIT`（踩坑）、`GRD`（护栏）、`ADR`（决策记录）、`REQ`（需求基线卡）、`TOOL`（工具）、`CASE`（案例）、`BL`（待办）、`ACP`（验收清单）、`RUN`（Runbook）、`TASK`（Agent 任务单）。**编号只增不复用**；新增前查 `agent-manifest.json` 或 `grep id:`；模板中的示例 ID 只是占位（模板文件不参与内容索引）。

### 4.2 front matter（新层 Markdown 必须）

**文件头部 front matter**（首行 `---`，到下一个 `---` 结束）为 **flat YAML**（禁止嵌套/多行块）。必需键：`id,title,type,status,audience,tags,updated,agent_hint`；`depends` 可选（逗号分隔）。示例与解析约束见 [MTH-009](methodology/08-agent-handoff.md)；**模板不写 TODO 占位**（未填写"待验证/待定"）。新增/修改后运行 `python -m toolkit.repurpose index` 重建索引。

### 4.3 链接与内容规范

- 只用**相对路径** Markdown 链接；新层**禁止 `#anchor`**、绝对路径、主机名、IP、端口、token、口令、序列号等敏感/环境相关值。
- 规范用语：**必须（MUST）** = 不可验收通过；**应当（SHOULD）** = 默认，偏离需记录理由；**可以（MAY）** = 可选。
- 引用案例事实必须给相对链接与"案例实证"标注；**历史证据豁免**：冻结/归档文档中的旧地址属历史事实，不得复制或当作当前配置。

### 4.4 决策记录与变更-文档联动

- **决策留痕**：架构选型、口径裁决、不可逆变更、被否决的重要备选 → `adr/NNNN-slug.md`（Nygard 五段：状态/背景/决策/后果；`superseded` 不删除并回链新 ADR）；够不上 ADR 的轻量决策进 `adr/README.md` 决策台账（D-NN 一行一条）。
- **联动矩阵摘要**（完整矩阵见 [MTH-011](methodology/10-document-lifecycle.md)）：改文档 → 更新索引与全仓引用；改命令/脚本契约 → `toolkit/README.md` + 测试 + schema；改 API/遥测/profile 字段 → 兼容矩阵 + CHANGELOG；新增 PIT → 评估能否机制化为检查；改 AGENTS/模板/提示词 → 协议版本 + 回归 + ADR（MAJOR 时）。
- **一次性产物**：调研/会话中间产物放 gitignored 的 `inventory/`（或临时目录），结论必须沉淀回正式层；正式文档不得引用一次性产物。

### 4.5 提示词、模板与生成物治理

- 提示词/AGENTS 规则/工具定义/模板都与代码同级：入库、可评审、**单一事实源**（不在多处抄写，抄写必漂移）、变更跑回归（MTH-014 §13）。
- 生成物（`agent-manifest.json`、`agent-manifest.d/`）禁止手改；`profiles/` 为运行期隐私数据，gitignored，只有脱敏 `cases/` 样例可入库。

---

## 5. 任务协议

### 5.1 单 Agent

1. 从 backlog 选任务（或用户指令），记录 `BL-ID`；M/H 风险任务先写需求基线卡（[request-card](toolkit/templates/request-card.md)）。
2. 只读核对现状、影响面、相关 MTH/PIT/GRD/ADR。
3. 更新 `backlog.json`：`status: in_progress`、`owner`、`updated`。
4. 按范围小步写文件（每步可回滚）；按 §4.4 联动矩阵同步下游文档/索引/测试。
5. 跑 §7 质量门 → 全绿；**对外可感知的事实/契约变化**在 [CHANGELOG.md](CHANGELOG.md) 当前窗口加一条（最新在上）；窗口将超 8 条时先归档最旧条目到 `changelog/YYYY-MM.md` 并更新 §4 索引（规则见 [MTH-011](methodology/10-document-lifecycle.md)）。
6. `backlog.json` 置 `done` 并写 `result`；报告列证据。

### 5.2 多 Agent（subagent/team）

- **写范围必须互斥**：按目录/文件前缀分配；跨范围改动由 Lead 统一集成。共享任务板写明 `write_scopes`；开工前 claim，完成即 complete。
- 同一文件同一时间只能一个 writer；冲突时**重读→在最新内容上重做→重试**，禁止用旧内容整体覆盖；成员 inactive 不代表完成，必须核对产出物与实跑证据。
- Lead 负责最终 `git diff` 审查、全量校验与提交；teammate 不 commit、不手改生成物。
- **入库才算交付态**：untracked 文件不在 `git diff` 中；提交前必须 `git add -A` 后检查 `git diff --cached` 与 `git status`。禁止把"工作区里文件存在"当成"已交付"。

### 5.3 证据、汇报与事实分级

- **五段报告**：结论一句话 / 证据清单（命令+退出码+关键输出+`路径:行号`）/ 事实分级（已核验/推断/未知）/ 未完成与风险 / 下一步建议。
- **禁止用语**：「应该/可能/大概/看起来/肯定可以/前文写过所以肯定对」不得作为结论收尾；需要表达不确定性时写成「推断，依据 X，验证方式 Y」。
- **失败如实上报**：报错就是报错，不得包装成部分成功；同一问题连续 2 次失败且原因不明必须停下并升级。

### 5.4 评审、测试、分支与协议版本

- **评审=独立复现证据**：从正确性、可验证性、规范一致性三视角查；评审者必须亲自跑关键命令或核对可复现证据，禁止弱化检查让 PR 通过。
- **测试策略**：单测（逻辑/边界，快而多）→ 集成（关键路径）→ 端到端/金标准（少而稳）；每个修复配一个"修复前会失败"的反例；fixture 用脱敏数据；不追求空洞覆盖率。
- **分支**：fork 前工作区干净、从最新主干分叉、分支名表达意图；合并前门禁与冲突处置见 [MTH-014](methodology/13-agent-sop.md) §11–§12；禁止用 `core.hooksPath` 等手法绕过钩子。
- **协议版本语义**：`MAJOR`=红线或规则不兼容（各分支必须重读整改，且必须走新 ADR）；`MINOR`=新增条款；`PATCH`=澄清。分支/任务卡记录其遵循的协议版本，跨版本合并前做一次差异核对。

---

## 6. 如何扩展（七类 SOP 速查）

| 想做的事 | 模板/入口 | 关键步骤 |
|---|---|---|
| 新增方法论（MTH） | [methodology-doc](toolkit/templates/methodology-doc.md) | 取新 MTH 号 → 写正文 → 交叉链接 → MTH-010 补术语 → index/validate |
| 新增踩坑（PIT） | [pitfall](toolkit/templates/pitfall.md) | 必含症状/根因/规避修复/验证/证据 → 关联 GRD/MTH → index |
| 新增护栏（GRD） | [guardrail](toolkit/templates/guardrail.md) | 必含红线/替代/检查方式 → 与 PIT 互链 → index |
| 新增决策（ADR） | [adr](toolkit/templates/adr.md) | 取下一个 ADR 号 → 五段 → `adr/README.md` 登记 → validate |
| 新增需求/交付卡 | [request-card](toolkit/templates/request-card.md) | 写目标/非目标/验收/风险 → 过 G0–G3 门（MTH-013） |
| 新增工具能力 | [toolkit/README.md](toolkit/README.md) | 先登记 `TOOL-<下一个号>` → 实现命令 + 测试 + README/schema |
| 新增设备案例 | [case-study](toolkit/templates/case-study.md) | 建 `cases/<codename>/{README.md,profile.json,oem-profile.md}` → `toolkit assess` 验证 → 登记 |

详细协议、变更传播与"改契约要同步什么"见 [MTH-009](methodology/08-agent-handoff.md) 与 [MTH-014](methodology/13-agent-sop.md)。

---

## 7. 验证与完成定义（DoD）

**每次变更最低门槛（全部必须绿）**：

```powershell
python -m toolkit.repurpose preflight          # index + validate --strict + unittest + check-links（退出码 0=全绿/3=有跳过/4=失败）
git add -A && git diff --cached --check        # 空白/冲突标记（须覆盖 untracked）
git status --short                             # 期望只有本次有意变更
```

**DoD 清单（逐项勾选）**：

- [ ] 改动落在授权范围内，未触碰冻结案例（除事实纠错）；未越界访问工作区外文件
- [ ] 新文档 front matter 合法、ID 唯一、无 TODO、无敏感值；命名与 ADR/协议机检通过
- [ ] 文档体积/条目在 [doc-policy](toolkit/schema/doc-policy.json) 上限内（CHANGELOG 窗口 ≤8 条）
- [ ] 所有新增/修改链接目标存在（`validate` + `check-links`）
- [ ] 工具改动有对应单元测试且全绿；`--help`/契约文档同步
- [ ] 协议/提示词/校验器变更已过 Agent 回归 AR-01..AR-10（[MTH-014](methodology/13-agent-sop.md) §13）且未弱化任何检查
- [ ] `agent-manifest.json` + `agent-manifest.d/` 已重建且与内容一致（`index` 无 warnings）
- [ ] 对外契约/事实变化已写入 CHANGELOG 当前窗口；超窗条目已归档且 §4 索引已更新
- [ ] `backlog.json` 状态和结果已更新
- [ ] 报告含验证证据、回滚方式与未完成项

---

## 8. 机器可读接口

| 文件/命令 | Schema | 说明 |
|---|---|---|
| `agent-manifest.json` | [agent-manifest.schema.json](toolkit/schema/agent-manifest.schema.json) | 内容索引**根摘要**（≤160 行）：entrypoints/reading_order/counts/shards/tools/invariants |
| `agent-manifest.d/*.json` | [manifest-shard.schema.json](toolkit/schema/manifest-shard.schema.json) | 按层分片（methodology/pitfalls/guardrails/case-studies）；Agent 按需只读一个 |
| `backlog.json` | [backlog.schema.json](toolkit/schema/backlog.schema.json) | 任务队列：必填 id/title/priority/area/status/acceptance/outputs/depends/notes/agent_hint；可选 requires/owner/updated/result/risk（`risk: L|M|H`）；in_progress/done 必须填 owner/updated/result |
| `adr/*.md` | 由 `validate` 机检 | 决策记录：文件名 `NNNN-slug.md`、status∈{proposed,accepted,superseded}、五段式 |
| `cases/*/profile.json` | [device-profile.schema.json](toolkit/schema/device-profile.schema.json) | 设备档案（脱敏） |
| `python -m toolkit.repurpose assess --profile <path> --json` | `repurpose.assessment.v1` | 路线/门禁/风险/下一步 |
| `python -m toolkit.repurpose plan --profile <path> --format json` | `repurpose.plan.v1` | P0–P6 阶段计划 |
| `python -m toolkit.repurpose validate --json` | `repurpose.validation.v1` | 内容/协议/命名/PIT/ADR/backlog/归档一致性 |
| `python -m toolkit.repurpose preflight --json` | `repurpose.preflight.v1` | 统一质量门：步骤状态与三态退出码 |

### 8.1 机器可读摘要

```yaml
source_of_truth:
  协议: AGENTS.md
  方法论文档地图: methodology/README.md
  待办队列: backlog.json
  决策记录: adr/README.md
  机器索引: agent-manifest.json
  当前变更: CHANGELOG.md
exit_codes: {0: VERIFIED_ALL, 3: SKIPPED, 4: FAILED}
forbidden:
  - 修改校验器/lint/测试断言使其变绿
  - 手改 agent-manifest.json 或 agent-manifest.d/
  - 未授权 Root/解锁/刷机/写设备
  - 秘密进入仓库/日志/文档/聊天
  - 未实测标完成、伪造验收
```

**未知/歧义处理**：先查 manifest 与相关 MTH/PIT/ADR；仍不确定时按 `guardrails/` 最保守方案执行，把假设写入报告与对应文档的"待验证"段，禁止擅自扩大范围。

---

## 9. 当前阶段与已知缺口（2026-11-14）

> 本节只写**结论与链接**（≤8 行），不复制数字；当前窗口变更见 [CHANGELOG.md](CHANGELOG.md)，历史变更见 [changelog/](changelog/README.md)（默认不读）。

- 方法论：MTH-001..014 初版完成（MTH-012 Root 轨、MTH-013 交付治理、MTH-014 Agent SOP 多为"已立规范、未全实测"）；工具链零依赖 CLI + fixture 单测，**尚未真机回归**。
- 交付治理与阶段门 G0–G7 已成文（[MTH-013](methodology/12-delivery-governance.md)），但**尚未在真实割接中演练**；首个真实 Go/No-Go 见 [backlog.json](backlog.json)。
- 案例是**部分验证**（24h soak、配对/轮换、mTLS、限流等未完成，详见 [cases/haydn-k40pro/README.md](cases/haydn-k40pro/README.md)）；不得表述为"全验收通过"。
- Root 轨：Ace Pro 已完成解锁/Root 与 3 轮救援演练（[CASE-003](cases/ace-pro-pgp110/README.md)），并部分落地 P1 管理面（Tailscale 登录/SSH、充电上限 80%、无用应用禁用、Quark 加密备份跑通一次；24h soak run #2 未满、tailnet 端到端与备份定时化未完成）；生产 haydn 保持无 Root。
- 本协议处于容量警示档（>200 行），分流为知识债（BL-029）；P0 仍是真机验证与基线绿化。

---

## 10. 本文件的维护

- 本协议是**活文件**：流程/契约变化时必须同步更新，并在 `CHANGELOG.md` 当前窗口记一条（超窗先归档，规则见 [MTH-011](methodology/10-document-lifecycle.md)）。
- **协议版本变更**：按 §5.4 语义化规则递增；MAJOR 变更必须走新 ADR（旧规则、新规则、受影响文档/分支、迁移步骤）；每次结构性变更后复核行数档位，>200 警示需评估分流，>320 必须当日分流。
- 结构性变更（新增顶层目录、改 ID 前缀、改权威顺序、改归档/读取规则）属于**破坏性变更**：必须同时更新 README、manifest schema、模板与校验器，并给出迁移说明。
- 任何 Agent 不得通过删除本文件或降低红线来"通过验收"。

<!-- END-OF-PROTOCOL -->
