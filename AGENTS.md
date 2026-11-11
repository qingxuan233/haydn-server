# AGENTS.md — Agent 工作协议（仓库根）

| 项目 | 内容 |
|---|---|
| 版本 | v1.0（2026-11-11，方法论化改造同期建立） |
| 适用 | 在 `D:\CODE\haydn-server` 及任意 clone/分支上工作的 AI Agent、subagent、新会话 |
| 上位 | 用户直接指令 > 本文件 > 子目录 `AGENTS.md` > `guardrails/` 红线 > `methodology/` 规范 > 其他 |
| 机器索引 | [agent-manifest.json](agent-manifest.json) · 待办 [backlog.json](backlog.json) |

> 本仓库面向**长期由 Agent 迭代**设计。你的目标不是"改完这一次"，而是让方法论、工具、案例持续自洽、可验证、可交接。先读协议，再动手。

---

## 0. 10 分钟启动清单（每次新会话/新 Agent 必做）

> 本清单是仓库**唯一权威读序**；README、MTH-000、MTH-009 中的读序都是它的简化/引用。若发现不一致，以本节为准并修文档。

1. 读本文件（尤其 §3 红线、§7 DoD）。
2. 读 [README.md](README.md) 了解仓库定位与阅读路径。
3. 读 [agent-manifest.json](agent-manifest.json)（不存在或过期则先运行 `python -m toolkit.repurpose index`）。
4. 读 [methodology/08-agent-handoff.md](methodology/08-agent-handoff.md)（扩展协议细则）。
5. 读 [methodology/README.md](methodology/README.md) 与 [MTH-001](methodology/00-foundations.md)、[MTH-002](methodology/01-assessment.md)、[MTH-003](methodology/02-roadmap.md)。
6. 从 [backlog.json](backlog.json) 选一项（优先 P0/P1），或接受用户新任务。
7. 动手前跑：
   ```powershell
   python -m toolkit.repurpose validate --strict
   python scripts/dev/check-links.py --strict-anchors
   python -m unittest discover -s toolkit/tests -t . -v
   ```
   基线必须是绿的；若基线本身失败，先修基线再改功能。

**只读优先**：先看状态/证据再改文件；禁止在不了解影响面的情况下批量重写。

---

## 1. 角色与目标

- 维护四层知识：`methodology/`（规范）、`guardrails/`（红线）、`pitfalls/`（证据）、`toolkit/`（实现），并用 `cases/` 验证。
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
5. `pitfalls/`（真实案例证据；用于反推规范是否漏了约束）
6. `toolkit/`（实现与契约；与规范不一致时以规范为准并改工具+测试）
7. `cases/` 与旧 `docs/`/`scripts/`/`android-bridge`（历史事实，冻结）

> 安全优先：Guardrail 的"MUST NOT"永远压过 Method 的"应当"；冲突时先停下确认，而不是找借口绕过。

**四层 + 一案例**目录：

| 目录/文件 | 用途 | 谁可以改 |
|---|---|---|
| `AGENTS.md` / `README.md` / `backlog.json` | 协议、人类入口、任务队列 | Lead/维护者；需保持机器索引同步 |
| `methodology/MTH-*.md` | 设备无关方法论 | 按 MTH-009 流程新增/修订 |
| `pitfalls/PIT-*.md` | 踩坑证据库 | 新增条目须有证据与验证 |
| `guardrails/GRD-*.md` | 不可协商红线 | 新增须给出可执行检查方式 |
| `toolkit/` | CLI/schema/模板/Termux 脚本/测试 | 改契约必须同步测试+文档 |
| `cases/haydn-k40pro/` | 已验证案例（含 profile） | 冻结；仅事实纠错 |
| `docs/ scripts/ android-bridge/` | 旧项目冻结证据 | 只读；唯一例外：`scripts/dev/check-links.py` 是仓库质量门，允许随文档结构维护（改动需同 commit 记录） |
| `tools/ backup/ inventory/` | 本地工具/加密备份/采集快照 | **gitignored**，不入库、不改内容 |
| `scripts/server/AGENTS.md` | 旧案例的服务器操作策略（会被工具自动加载） | 冻结；与根协议冲突时以根协议为准 |
| `profiles/` | 运行期设备档案（含隐私） | **gitignored**，不入库 |
| `agent-manifest.json` | 机器索引（生成物） | 用 `toolkit index` 重建，不手改 |

---

## 3. 不可协商红线（Agent 必须逐条自检）

完整清单见 [guardrails/README.md](guardrails/README.md)。以下为最高频、最易误犯的 8 条：

1. **不 Root、不刷机、不解锁 BL**，除非用户对具体设备明确授权且评估门禁通过（[GRD-001](guardrails/GRD-001-no-root-no-unlock-default.md)）。
2. **不卸载系统包**；只允许 `disable-user`，且必须维护保护名单（[GRD-002](guardrails/GRD-002-no-system-package-uninstall.md)）。
3. **禁止 `am kill-all`** 或随意 force-stop 服务器相关进程（[GRD-003](guardrails/GRD-003-no-kill-all.md)）。
4. **任何写操作先备份/快照，并给出回滚路径**；恢复未演练≙没有回滚（[GRD-004](guardrails/GRD-004-backup-before-change.md)）。
5. **Tier2 写操作必须显式确认+快照+审计；Tier3 仅人工**；Agent 不得越权（[GRD-005](guardrails/GRD-005-tiered-ops-confirmation.md)）。
6. **token/口令/私钥/证书/备份口令不进入仓库、日志、文档、聊天**；发现泄露先轮换再清历史（[GRD-006](guardrails/GRD-006-secret-hygiene.md)）。
7. **网络最小暴露**：仅 loopback/局域网；公网只经受控入口；ADB 维护后关闭（[GRD-007](guardrails/GRD-007-network-least-exposure.md)）。
8. **不伪造验收**：未实测不标完成，文档声称不算证据（[GRD-013](guardrails/GRD-013-no-fake-acceptance.md)）；Agent 行为总则见 [GRD-012](guardrails/GRD-012-agent-operating-rules.md)。

> 违反红线的"便捷修复"一律拒绝；用允许的替代方案（见各条 `## 允许的替代`）。

---

## 4. 文件与文档约定

### 4.1 命名与 ID

- 新层目录与文件名**全 ASCII**（`methodology/`, `pitfalls/PIT-001-*.md`, `guardrails/GRD-001-*.md`, `cases/<codename>/`）；正文中文。
- 稳定 ID 前缀：`MTH`（方法论）、`PIT`（踩坑）、`GRD`（护栏）、`TOOL`（工具）、`CASE`（案例）、`BL`（待办）、`ACP`（验收清单）、`RUN`（Runbook）、`TASK`（Agent 任务单）。**编号只增不复用**；新增前查 `agent-manifest.json` 或 `grep id:`；模板中的示例 ID 只是占位，复制时必须改成当前未占用的编号（模板文件不参与内容索引）。
- 一个文件一个主 ID；索引/README 用 `*-000`；`toolkit/templates/*` 例外（模板示例号不占用正式编号）。

### 4.2 front matter（新层 Markdown 必须）

**文件头部 front matter**（首行 `---`，到下一个 `---` 结束；只出现在文件开头，文件末尾不要求 `---`）为 **flat YAML**（禁止嵌套/多行块）：

```yaml
---
id: MTH-002
title: 评估与可行性决策
type: methodology
status: current
audience: human, agent
tags: assessment, feasibility, decision
depends: MTH-001
updated: 2026-11-11
agent_hint: 新设备接入第一步；先 probe 再 assess
---
```

必需键：`id,title,type,status,audience,tags,updated,agent_hint`；`depends` 可选（逗号分隔 ID）。列表一律逗号分隔。新增/修改后必须运行 `python -m toolkit.repurpose index` 重建索引。

### 4.3 链接与内容规范

- 只用**相对路径** Markdown 链接；**新层链接禁止 `#anchor`**（跨平台稳定性）。
- 禁止绝对路径（如 `C:\...`）、主机名、IP、端口、token、口令、序列号等敏感/环境相关值。
- 引用案例事实必须给相对链接与"案例实证"标注；通用结论必须可被新设备验证。
- 规范用语：**必须（MUST）** = 不可验收通过；**应当（SHOULD）** = 默认，偏离需记录理由；**可以（MAY）** = 可选。
- 历史/案例文档保留原编号与历史结论，不迁移、不改写；通用层新文档使用 ASCII 文件名。

### 4.4 工具与产物

- `toolkit/repurpose/` 为零第三方依赖 Python 包；新增/修改能力必须补单元测试与 `toolkit/README.md`。
- `agent-manifest.json` 是生成物：不要手改；提交前运行 `python -m toolkit.repurpose index`。
- `profiles/` 为运行期隐私数据，gitignored；只有脱敏 `cases/` 样例可入库。

---

## 5. 任务协议

### 5.1 单 Agent

1. 从 backlog 选任务（或用户指令），记录 `BL-ID`。
2. 只读核对现状、影响面、相关 MTH/PIT/GRD。
3. 更新 `backlog.json`：`status: in_progress`、`owner`、`updated`。
4. 按范围写文件（尽量小步、可回滚）。
5. 跑校验（§7）→ 全绿。
6. 更新索引、必要文档交叉链接、`CHANGELOG.md`（如果改变了对外事实/契约）。
7. `backlog.json` 置 `done` 并写 `result`；在最终报告里列证据。

### 5.2 多 Agent（subagent/team）

- **写范围必须互斥**：按目录/文件前缀分配；跨范围改动由 Lead 统一集成。
- 共享任务板上写明 `write_scopes`；开工前 claim，完成即 complete。
- 同一文件同一时间只能一个 writer；发现他人改动（FS_STALE_VERSION）先重读再 rebase，禁止盲写。
- Lead 负责最终 `git diff` 审查、全量校验与提交；teammate 不 commit。
- **入库才算交付态**：未提交的新文件（untracked）不在 `git diff` 里，DoD 检查会漏掉；提交前必须 `git add -A` 后检查 `git diff --cached` 与 `git status` 干净。禁止把"工作区里文件存在"当成"已交付"。

### 5.3 证据与报告

- 完成报告必须含：改了什么、为什么、验证命令与结果、风险/回滚、未完成项。
- 失败要如实报告（含命令输出摘要），不要用"应该可以"替代。

---

## 6. 如何扩展（五类 SOP 速查）

| 想做的事 | 模板 | 关键步骤 |
|---|---|---|
| 新增方法论（MTH） | [toolkit/templates/methodology-doc.md](toolkit/templates/methodology-doc.md) | 取新 MTH 号 → 写正文 → 交叉链接 → MTH-010 补术语 → index/validate |
| 新增踩坑（PIT） | [toolkit/templates/pitfall.md](toolkit/templates/pitfall.md) | 必含 症状/根因/规避修复/验证/证据 → 关联 GRD/MTH → index |
| 新增护栏（GRD） | [toolkit/templates/guardrail.md](toolkit/templates/guardrail.md) | 必含 红线/替代/检查方式 → 与 PIT 互链 → index |
| 新增工具能力 | [toolkit/README.md](toolkit/README.md) | 实现命令+测试+README/schema 同步 → 全量测试 |
| 新增设备案例 | [toolkit/templates/case-study.md](toolkit/templates/case-study.md) | 建 `cases/<codename>/{README.md,profile.json,oem-profile.md}` → `toolkit assess` 验证 → 登记 |

详细协议、变更传播与"改契约要同步什么"见 [MTH-009](methodology/08-agent-handoff.md)。**模板不写 TODO 占位**；宁可标注"待验证"也不要留空。

---

## 7. 验证与完成定义（DoD）

**每次变更最低门槛（全部必须绿）**：

```powershell
python -m toolkit.repurpose validate --strict     # front matter/ID/断链
python -m toolkit.repurpose index                  # 重建 agent-manifest.json，确认无 warnings
python -m unittest discover -s toolkit/tests -t . -v   # 工具单元测试
python scripts/dev/check-links.py --strict-anchors     # 全仓相对链接（含新层）
git add -A && git diff --cached --check               # 空白/冲突标记（须覆盖 untracked）
git status --short                                   # 期望只有本次有意变更
```

**DoD 清单（逐项勾选）**：

- [ ] 改动落在授权范围内，未触碰冻结案例（除事实纠错）
- [ ] 新文档 front matter 合法、ID 唯一、无 TODO、无敏感值
- [ ] 所有新增/修改链接目标存在（`validate` + `check-links`）
- [ ] 工具改动有对应单元测试且全绿；`--help`/契约文档同步
- [ ] `agent-manifest.json` 已重建且与内容一致
- [ ] 对外契约/事实变化已写入 `CHANGELOG.md`；相关 MTH/PIT/GRD 交叉链接已更新
- [ ] `backlog.json` 状态和结果已更新
- [ ] 报告含验证证据、回滚方式与未完成项

---

## 8. 机器可读接口

| 文件/命令 | Schema | 说明 |
|---|---|---|
| `agent-manifest.json` | [toolkit/schema/agent-manifest.schema.json](toolkit/schema/agent-manifest.schema.json) | 内容索引、阅读顺序、工具清单、约束摘要 |
| `backlog.json` | 见本文件 §8 末 | `schema/items[]` 必填：id,title,priority,area,status,acceptance,outputs,depends,notes,agent_hint；可选：owner,updated,result,requires（in_progress/done 时应填） |
| `cases/*/profile.json` | [toolkit/schema/device-profile.schema.json](toolkit/schema/device-profile.schema.json) | 设备档案（脱敏） |
| `python -m toolkit.repurpose assess --profile <path> --json` | `repurpose.assessment.v1` | 路线/门禁/风险/下一步 |
| `python -m toolkit.repurpose plan --profile <path> --format json` | `repurpose.plan.v1` | P0–P6 阶段计划 |

**backlog.json 最小结构**：

```json
{
  "schema": "repurpose.backlog.v1",
  "updated": "2026-11-11",
  "items": [
    {
      "id": "BL-001",
      "title": "…",
      "priority": "P1",
      "area": "toolkit",
      "status": "pending",
      "acceptance": "可验证的完成条件",
      "outputs": ["相对路径"],
      "depends": [],
      "notes": "",
      "agent_hint": "第一步做什么",
      "requires": "真机 + 用户授权（可选；无则写空串）",
      "owner": "",
      "updated": "",
      "result": ""
    }
  ]
}
```

> `requires` 用于标注"需要真机/授权/外部服务"等前置；`owner/updated/result` 在 `status` 变为 `in_progress`/`done` 时填写。`validate` 目前只保证 JSON 可解析；backlog 的语义一致性由维护者/Agent 自检（机器强校验见 backlog BL-015）。

**未知/歧义处理**：先查 manifest 与相关 MTH/PIT；仍不确定时，按 `guardrails/` 最保守方案执行，并把假设写入报告与对应文档的"assumptions/待验证"段，禁止擅自扩大范围。

---

## 9. 当前阶段与已知缺口（2026-11-11）

- 方法论 v2.0 初版：MTH-000..010（11 个文件）、PIT-000..020（21 个文件）、GRD-000..014（15 个文件）、TOOL-001..010（7 个 CLI 子命令 + 3 个 Termux 脚本；PowerShell 包装器不单独编号；manifest 的物理工具条目为 5 个）已完成初稿。工具登记表以 [toolkit/README.md](toolkit/README.md) 为准。
- `toolkit` 为 alpha：**140 项 fixture 单元测试通过，尚未真机回归**；`detect/probe` 的字段解析以实测为准，可能需随设备差异调整。
- 案例是**部分验证**：服务器/桥/Console/备份已落地，但 24h soak、配对/token 轮换、mTLS、限流、OEM profile 矩阵、外部监控均未完成；不得把案例说成"全验收通过"。
- 待办见 [backlog.json](backlog.json)；优先级 P0 是一切真机验证与基线绿化。

---

## 10. 本文件的维护

- 本协议是**活文件**：流程/契约变化时必须同步更新，并在 `CHANGELOG.md` 记一条。
- 结构性变更（新增顶层目录、改 ID 前缀、改权威顺序）属于**破坏性变更**：必须同时更新 README、manifest schema、模板与校验器，并给出迁移说明。
- 任何 Agent 不得通过删除本文件或降低红线来"通过验收"。
