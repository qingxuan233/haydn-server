---
id: MTH-000
title: 方法论门户：定位、路径与文档地图
type: index
status: current
audience: human, agent
tags: methodology, portal, index, navigation
depends: ""
updated: 2026-11-11
agent_hint: 先读本页确认定位与阅读路径；Agent 的完整启动顺序以根 AGENTS.md 为准，本页不是工作协议。
---

# MTH-000 · 方法论门户

> **一句话**：把一台闲置 Android 手机改造成**低功耗、可远程维护、可观测的家用 Linux 服务器**的**设备无关方法论**。
> 本页是 `methodology/` 的索引与导航；**仓库人类入口是 [根 README](../README.md)**，**Agent 工作协议是 [AGENTS.md](../AGENTS.md)**，机器索引是 [agent-manifest.json](../agent-manifest.json)。
> 默认边界：**不 Root、不刷机、不解锁 Bootloader、不接未授权外部服务**；所有变更必须**可回退、有证据**。

---

## 1. 定位：是什么 / 不是什么

| 是 | 不是 |
|---|---|
| 一套设备无关的改造方法论：评估 → 决策 → 服务器栈 → 遥测桥 → 控制面 → 验收 | 某个机型的刷机教程 |
| 可直接运行的工具链：探测、能力矩阵、路线评估、阶段计划、索引/校验 | 一键"全自动改造"脚本 |
| 可长期由 Agent 维护的知识库：方法论 + 踩坑库 + 红线 + 模板 + 机器索引 | 通用 Linux 服务器教程（默认场景是 Android 宿主 + 无 Root） |
| 有真实端到端案例（haydn K40 Pro）作为证据与回归样例 | 对任何机型都保证可行的承诺 |

**适用对象**：想用旧手机做自托管服务器的人；需要把改造流程交接给 Agent 的维护者；需要换机迁移/多设备扩展的人。
**不适用对象**：需要系统级特权/容器编排的生产业务；需要刷机/解锁教程的人；需要"一次点完"的人；要求 SLA/合规审计的服务。

---

## 2. 两条阅读路径

### 2.1 人类（约 30 分钟）

1. [根 README](../README.md)（仓库定位与 30 秒路线判断）→ 本页
2. [MTH-001 边界与原则](00-foundations.md)（适用前提、三轨架构、十条原则、DoD）
3. [MTH-002 评估与可行性决策](01-assessment.md)（路线表、门禁、assess 输出）
4. [MTH-003 通用路线图](02-roadmap.md)（P0–P6、交付物、回滚）
5. 按需：[MTH-004 服务器栈](03-server-stack.md) / [MTH-005 遥测桥](04-telemetry-bridge.md) / [MTH-006 控制面](05-control-plane.md) / [MTH-007 安全](06-security.md) / [MTH-008 验收](07-validation.md)
6. 动手前必读：[guardrails/README.md](../guardrails/README.md)；排障先查 [pitfalls/README.md](../pitfalls/README.md)

### 2.2 Agent（分层最小，权威读序见 [AGENTS.md §0](../AGENTS.md)）

1. [AGENTS.md](../AGENTS.md)：工作协议、红线、DoD、任务协议。
2. [agent-manifest.json](../agent-manifest.json)：根摘要（≤160 行）；需要某层时只读一个 `agent-manifest.d/` 分片。
3. 按任务**只选 1 篇**主题 MTH（评估/路线图/服务器/桥/控制面/安全/验收之一）；扩展/交接读 [MTH-009](08-agent-handoff.md)，归档/上下文预算读 [MTH-011](10-document-lifecycle.md)。
4. [README](../README.md) 只读"仓库地图/阅读路径"段；[backlog.json](../backlog.json) 领取任务。
5. 动手前按 AGENTS §0 跑基线校验；只读优先、小步变更、证据不伪造。

> **最小判断路径**：只想回答"这台手机能不能做服务器" → [MTH-002](01-assessment.md) §4 决策表 + [MTH-003](02-roadmap.md) §1 阶段总览，5 分钟足够。

---

## 3. 三轨一句话

| 轨道 | 一句话 | 详细 |
|---|---|---|
| **Track A** 服务器栈 | Android 用户态里跑 Termux + proot Linux，用 supervisord 管服务，负责聚合/备份/审计 | [MTH-004](03-server-stack.md) |
| **Track B** 宿主遥测桥 | 伴生只读 App，把 App 可访问的宿主状态经本机 HTTPS 提供给服务器 | [MTH-005](04-telemetry-bridge.md) |
| **Track C** 集成与控制面 | 服务器读取/合并状态，提供只读查询与受控运维（Tier1/2） | [MTH-006](05-control-plane.md) |

**故障隔离**：任一轨故障不得阻断其余两轨；桥不可用时服务器回退并标注来源；控制面不得持有桥凭据（见 [MTH-001](00-foundations.md) §3）。

---

## 4. 文档地图（MTH-000 ~ MTH-011）

| ID | 文档 | 解决什么问题 | 主要读者 |
|---|---|---|---|
| **MTH-000** | 本页（门户） | 定位、阅读路径、文档地图、贡献方式 | 人 + Agent |
| MTH-001 | [边界与原则](00-foundations.md) | 适用/不适用、前提、三轨、十条原则、非目标、DoD | 人 + Agent |
| MTH-002 | [评估与可行性决策](01-assessment.md) | device-profile schema、四步 SOP、A/A+/B/C/D 决策、门禁 G-A/G-B0 等、assess 输出 | Agent 为主 |
| MTH-003 | [通用路线图 P0–P6](02-roadmap.md) | 阶段目标/交付/门禁/估时/回滚、状态机、变更管理 | 人 + Agent |
| MTH-004 | [服务器栈（Track A）](03-server-stack.md) | 为什么 proot、启动链、服务分层、网络、备份、日志、预算、安装与排障 | 人 + Agent |
| MTH-005 | [宿主遥测桥（Track B）](04-telemetry-bridge.md) | 何时需要桥、FGS/loopback、数据契约、null 语义、降级 | Agent 为主 |
| MTH-006 | [AI 控制面（Track C）](05-control-plane.md) | Tier1/2/3、自愈、审计、蓝绿升级、边界 | 人 + Agent |
| MTH-007 | [安全与密钥生命周期](06-security.md) | 威胁模型、凭据管理、暴露面、轮换、泄露处理 | 人 + Agent |
| MTH-008 | [验收与稳定性](07-validation.md) | 5 重启、24h soak、故障注入、恢复演练、证据格式 | Agent 为主 |
| MTH-009 | [Agent 交接与扩展协议](08-agent-handoff.md) | 目录/ID/任务/扩展/变更传播/DoD（Agent 必读） | Agent |
| MTH-010 | [术语表](09-glossary.md) | 统一术语口径（proot/FGS/AVB/FBE/soak/Tier 等） | 人 + Agent |
| MTH-011 | [文档生命周期、归档与上下文预算](10-document-lifecycle.md) | 记录边界、CHANGELOG 归档、阅读预算、分层加载与停止条件 | 人 + Agent |

**配套层入口**

| 层 | 入口 | 用途 |
|---|---|---|
| 工具 | [toolkit/README.md](../toolkit/README.md) | CLI、schema、模板、Termux 脚本与测试 |
| 踩坑 | [pitfalls/README.md](../pitfalls/README.md) | 真实案例证据与通用风险 |
| 护栏 | [guardrails/README.md](../guardrails/README.md) | 不可协商红线与检查方式 |
| 案例 | [cases/haydn-k40pro/README.md](../cases/haydn-k40pro/README.md) | 实证案例（部分验收）与回归样例 |
| 冻结证据 | [docs/README.md](../docs/README.md) | 改造过程的原始文档/脚本（历史事实） |

---

## 5. 当前成熟度

> 只给结论与链接，不维护数字快照：文档范围见 §4；工具测试/限制见 [toolkit/README.md](../toolkit/README.md) 与 [CHANGELOG.md](../CHANGELOG.md) 当前窗口；案例成熟度见 [cases/README.md](../cases/README.md)；未完成/优先级见 [backlog.json](../backlog.json)。

| 层 | 结论 |
|---|---|
| methodology | v2 初版可用（MTH-000..011；随实践修订，变更进 CHANGELOG 窗口/归档） |
| cases | 实证案例 1 个，**部分验收**（未完成项以案例内记录为准，不得表述为全通过） |
| toolkit | alpha：fixture 单测可跑、**尚未真机回归**；限制与测试数见 toolkit/README |
| pitfalls / guardrails | 初版条目，均含证据/检查方式；新增/变更进 CHANGELOG |

---

## 6. 如何贡献（人或 Agent）

1. **先读协议**：[AGENTS.md](../AGENTS.md) → [MTH-009](08-agent-handoff.md) → 本页 → 目标文档。
2. **领取任务**：从 [backlog.json](../backlog.json) 选一项（优先 P0/P1），记录 BL-ID；没有对应项先补任务。
3. **新建/修改文档**：
   - 新方法论用 [toolkit/templates/methodology-doc.md](../toolkit/templates/methodology-doc.md)；
   - ID 用未用号（查 [agent-manifest.json](../agent-manifest.json) 或 `id:`），**编号只增不复用**；
   - 文件名全 ASCII；正文中文；**文件头部 front matter**（首行 `---` 到下一个 `---`）为**flat YAML**（禁嵌套/多行块）；必需键 `id,title,type,status,audience,tags,updated,agent_hint`，`depends` 可选（逗号串）。
4. **内容要求**：结论先行、决策表、可执行命令、检查清单、验收标准、失败处理；未知写"待设备验证/默认假设"；**禁止**留空占位符、绝对路径、主机名/IP/端口/凭据。
5. **链接规则**：只用**相对路径** Markdown 链接；方法论层**禁止 `#anchor`**；引用案例必须给相对链接并标"案例实证"。
6. **交叉链接**：新的 MTH/PIT/GRD/TOOL 必须互链相关条目，并更新 [MTH-010 术语表](09-glossary.md)（如引入新术语）。
7. **校验**（全部通过才算完成）：`python -m toolkit.repurpose validate --strict`、`python -m toolkit.repurpose index`、`python -m unittest discover -s toolkit/tests -t . -v`、`python scripts/dev/check-links.py --strict-anchors`。
8. **记录**：对外契约/事实变化写变更记录与 ADR；案例层（`cases/`、`docs/`、`scripts/`、`android-bridge/`）**冻结**，只允许事实纠错。

**新增 MTH 的最小交叉更新**：本页文档地图 → [MTH-010](09-glossary.md)（新术语）→ 相关 MTH/PIT/GRD 互链 → `toolkit index` 重建索引。

---

## 7. 快速开始（仓库根目录）

```powershell
python -m toolkit.repurpose --help

# 设备评估（无真机可用 fixture 走通流程）
python -m toolkit.repurpose detect --out profiles/<codename>.json
python -m toolkit.repurpose probe --base profiles/<codename>.json --out profiles/<codename>.capabilities.json
python -m toolkit.repurpose assess --profile profiles/<codename>.json --json
python -m toolkit.repurpose plan --profile profiles/<codename>.json --route auto --format md

# 内容索引与校验
python -m toolkit.repurpose index
python -m toolkit.repurpose validate --strict
python scripts/dev/check-links.py --strict-anchors
```

> `profiles/` 是运行期隐私数据（已 gitignore）；只有脱敏后的案例档案可以入库。基线必须全绿；基线失败先修基线，不要绕开校验。

---

## 8. 维护规则摘要（必须）

1. **单一事实源**：同一个事实只在一处维护（状态类→案例状态源；方法论→`methodology/`）；其他文档只引用不复制。
2. **案例冻结**：`docs/`、`scripts/`、`android-bridge/`、`cases/` 是历史证据；只允许事实纠错，不改写历史结论。
3. **ID 稳定**：MTH/PIT/GRD/TOOL/CASE/BL 前缀；编号只增不复用；删除只标记弃用。
4. **front matter 必填**：缺键/嵌套 YAML/重复 ID 一律不合格。
5. **链接约束**：相对路径、无 anchor、无绝对路径、无敏感值。
6. **过期处理**：文档 `updated` 超期或与实现不一致时，先标记 `status` 并安排复核；不允许"悄悄漂移"。
7. **破坏性变更**（目录结构、ID 前缀、权威顺序、对外契约）必须走 ADR + 迁移说明 + 同步索引/模板/校验器。
8. **诚实优先**：未实测不标完成；目标值/实测值分列；失败与偏差保留在案例与踩坑库。

---

## 9. 术语与变更

- 术语统一口径见 [MTH-010 术语表](09-glossary.md)；不确定时查表，不在正文自造定义。
- 本页 `updated` 变化代表导航/成熟度/贡献规则被复核；结构性变化另记变更记录。
- 文档抱怨/纠错入口：优先在 [backlog.json](../backlog.json) 建项，或按 [MTH-009](08-agent-handoff.md) 的扩展协议提变更。
