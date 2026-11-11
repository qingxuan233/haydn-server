# 安卓手机改造通用方法论（Android Phone Repurpose Methodology）

> **把一台闲置 Android 手机改造成低功耗、可远程维护、可观测的家用 Linux 服务器**的一套可迁移方法论、工具链与安全护栏。
>
> 本仓库由 `haydn-server` 实战项目升级而来（2026-11-11）。Redmi K40 Pro 的完整落地过程保留为**实证案例（部分验收，24h soak 等未完成）**：[cases/haydn-k40pro/README.md](cases/haydn-k40pro/README.md)；旧文档/脚本/APK 源码作为**冻结证据**保留在 [docs/](docs/README.md)、[scripts/](scripts/README.md)、[android-bridge/](android-bridge/README.md)。仓库名沿用历史名称，不影响新的通用定位。

---

## 1. 这是什么 / 不是什么

| 是 | 不是 |
|---|---|
| 一套设备无关的改造方法论：评估 → 决策 → 服务器栈 → 遥测桥 → 控制面 → 验收 | 某个机型的刷机教程 |
| 可直接运行的工具链：设备探测、能力矩阵、路线评估、阶段计划、索引/校验 | 一键"全自动改造"脚本（改造必须分阶段、可回退、有人工门禁） |
| 可被后续 Agent 长期维护的知识库：踩坑库 + 红线护栏 + 机器可读索引 + 待办队列 | 通用 Linux 服务器教程（默认场景是 Android 宿主 + 无 Root） |
| 一个真实的端到端案例（haydn K40 Pro）作为证据与回归样例 | 对任何机型都保证可行的承诺 |

**默认边界**：不 Root、不刷机、不解锁 BL；不承诺 Android 系统级特权数据；不接未授权的外部服务；所有变更必须可回退。

---

## 2. 30 秒路线判断

| 设备/需求条件 | 推荐路线 | 要点 |
|---|---|---|
| Bootloader 锁定 / 无法解锁 / 需要保 Play Integrity / 不愿清数据 | **A（Termux + proot，无 Root）** | 默认路线；零解锁风险，当天可用 |
| 同上，但想压低温度/功耗、提高稳定性 | **A+（A 的优化档）** | 系统设置 + 包治理 + 看门狗；仍无 Root |
| BL 可解锁、接受清数据/失保/Play Integrity 风险、需要 chroot/特权 | **B（解锁 + Root + chroot）** | 必须先过 G-B0 解锁门；能力上限更高 |
| 需要内核级能力且有社区移植/自编译条件 | **C（自定义内核/ROM）** | 高风险，非默认 |
| 该机型存在可用的原生 Linux 移植（postmarketOS 等） | **D（原生 Linux）** | 先验证社区支持与硬件可用性 |

> 判定必须基于**探测数据**而非感觉。先跑 [MTH-002 评估与可行性决策](methodology/01-assessment.md)，再用 `toolkit assess` 得到结构化结论与门禁。

---

## 3. 仓库地图（四层 + 一案例）

```text
AGENTS.md                     Agent 工作协议（新会话/新 Agent 从这里开始）
agent-manifest.json           机器可读索引根摘要（≤160 行，由 toolkit index 生成）
agent-manifest.d/             按层分片（methodology/pitfalls/guardrails/case-studies，按需只读一个）
backlog.json                  结构化待办（Agent 领取任务用）
README.md                     本文件：人类入口
methodology/                  规范层：可迁移的方法论正文（MTH-001..011）
pitfalls/                     证据层：踩过的坑（PIT-001..020），每条含根因/规避/验证/证据
guardrails/                   约束层：红线与注意事项（GRD-001..014），每条含检查方式
toolkit/                      工具层：零依赖 Python CLI + schema + 模板 + Termux 脚本 + 测试
cases/                        案例层：真实设备落地记录（haydn K40 Pro）
docs/ scripts/ android-bridge/  旧项目冻结证据（案例原始文档、脚本、Bridge 源码）
CHANGELOG.md                  当前变更窗口（≤8 条，含 2026-11-11 改造摘要）
changelog/                    历史变更归档（按月，默认不读；规则见 MTH-011）
```

**权威优先级**：用户指令 > [AGENTS.md](AGENTS.md) > `guardrails/` 红线 > `methodology/` 规范 > `pitfalls/` 案例证据 > `toolkit/` 实现细节 > `cases/` 与旧目录历史事实。冲突时以更高层为准（红线永远压过"应当"），但必须修正低层并记录。

---

## 4. 阅读路径

### 人类（约 30 分钟）
1. 本文 → [MTH-001 边界与原则](methodology/00-foundations.md)
2. [MTH-002 评估与决策](methodology/01-assessment.md) → [MTH-003 路线图](methodology/02-roadmap.md)
3. 按兴趣选读：[MTH-004 服务器栈](methodology/03-server-stack.md)、[MTH-005 遥测桥](methodology/04-telemetry-bridge.md)、[MTH-006 控制面](methodology/05-control-plane.md)
4. 动手前必读：[MTH-007 安全](methodology/06-security.md)、[guardrails/README](guardrails/README.md)

### Agent / 新会话（10 分钟）
1. [AGENTS.md](AGENTS.md)（工作协议、红线、DoD）
2. [agent-manifest.json](agent-manifest.json)（根摘要与阅读顺序；**不要**一次加载全部分片）
3. [MTH-009 Agent 交接与扩展协议](methodology/08-agent-handoff.md) → [MTH-011 文档生命周期与上下文预算](methodology/10-document-lifecycle.md)
4. [backlog.json](backlog.json) 领取任务；变更前跑 `python -m toolkit.repurpose validate --strict`

**上下文预算（防膨胀，详见 [MTH-011](methodology/10-document-lifecycle.md)）**：
- 单任务最多读 **3 份**规范/主题文档（索引/模板/任务卡/`--help` 不计）；
- **默认不读** `changelog/` 归档、`docs/90-archive`、旧 `docs/` 案例全文与旧 `scripts/`；追溯时才读**单个**归档文件；
- 禁止整读 >300 行的文件；先读索引/标题，按需 `grep` + 分段；
- 分层加载：根 manifest → 需要某层时只读 `agent-manifest.d/<layer>.json` 一个分片 → 再读单篇主题。

---

## 5. 快速开始

```powershell
# 在仓库根目录执行（需要 Python 3.10+；ADB 相关子命令需要本机安装 platform-tools）
python -m toolkit.repurpose --help

# 设备探测：有真机时只读采集（默认脱敏，不写序列号）
python -m toolkit.repurpose detect --out profiles/<codename>.json
python -m toolkit.repurpose probe --base profiles/<codename>.json --out profiles/<codename>.capabilities.json

# 无真机时：用 fixture 离线跑通完整链路
python -m toolkit.repurpose detect --adb-fixture toolkit/tests/fixtures/adb-haydn.json --out profiles/demo.json
python -m toolkit.repurpose probe --base profiles/demo.json --adb-fixture toolkit/tests/fixtures/adb-haydn.json --out profiles/demo-probed.json

# 路线评估与阶段计划（离线，不依赖设备）
python -m toolkit.repurpose assess --profile profiles/<codename>.json --json
python -m toolkit.repurpose plan --profile profiles/<codename>.json --route auto --format md

# 内容索引与一致性校验
python -m toolkit.repurpose index
python -m toolkit.repurpose validate --strict

# 单元测试（fixture 模式，不需要真机）
python -m unittest discover -s toolkit/tests -t . -v

# 文档链接检查（已覆盖新方法论层）
python scripts/dev/check-links.py --strict-anchors
```

> ⚠️ 运行期设备档案默认放在 `profiles/`（已 gitignore，含序列号等隐私）；仅脱敏后的 `cases/` 样例可入库。

---

## 6. 方法论文档（MTH）

| ID | 文档 | 解决什么问题 |
|---|---|---|
| MTH-001 | [边界与原则](methodology/00-foundations.md) | 适用/不适用、三轨架构、设计原则、DoD |
| MTH-002 | [评估与可行性决策](methodology/01-assessment.md) | 探测字段、A/A+/B/C/D 决策树、门禁、assess 输出 |
| MTH-003 | [通用路线图](methodology/02-roadmap.md) | P0–P6 阶段、交付物、门禁、回滚 |
| MTH-004 | [服务器栈](methodology/03-server-stack.md) | Termux+proot 启动链、服务集、网络、备份 |
| MTH-005 | [宿主遥测桥](methodology/04-telemetry-bridge.md) | 何时需要桥、FGS/loopback/数据契约/安全 |
| MTH-006 | [AI 控制面](methodology/05-control-plane.md) | Tier1/2/3、自愈、审计、蓝绿、边界 |
| MTH-007 | [安全与密钥生命周期](methodology/06-security.md) | 威胁模型、秘密管理、轮换、暴露面 |
| MTH-008 | [验收与稳定性](methodology/07-validation.md) | 5 重启、24h soak、故障注入、恢复演练 |
| MTH-009 | [Agent 交接与扩展协议](methodology/08-agent-handoff.md) | 目录/协议/任务/扩展/DoD（Agent 必读） |
| MTH-010 | [术语表](methodology/09-glossary.md) | proot/FGS/AVB/FBE/soak/Tier 等统一口径 |
| MTH-011 | [文档生命周期、归档与上下文预算](methodology/10-document-lifecycle.md) | 记录边界、CHANGELOG 归档、阅读预算、分层加载 |

---

## 7. 踩坑库与护栏（先读这里再动手）

- **踩坑库** [pitfalls/README.md](pitfalls/README.md)：20 条真实踩坑 + 通用风险，按 S1–S4 分级；每条都给出症状、根因、修复步骤、验证方法与证据链接。
  高频必读：[S1 系统包卸载 bootloop](pitfalls/PIT-002-system-package-uninstall-bootloop.md)、[无 USER_NS 容器不可用](pitfalls/PIT-006-no-user-ns-containers.md)、[明文凭据入库](pitfalls/PIT-015-plaintext-credentials.md)、[伪证书 pin](pitfalls/PIT-019-fake-pinning-bridge.md)、[快照无回滚](pitfalls/PIT-017-snapshot-without-rollback.md)。
- **护栏层** [guardrails/README.md](guardrails/README.md)：14 条不可协商红线与检查方式；Agent 每次变更前逐条对照。
  高频必读：[不 Root/不解锁默认](guardrails/GRD-001-no-root-no-unlock-default.md)、[不卸载系统包](guardrails/GRD-002-no-system-package-uninstall.md)、[变更前备份](guardrails/GRD-004-backup-before-change.md)、[密钥卫生](guardrails/GRD-006-secret-hygiene.md)、[Agent 行为红线](guardrails/GRD-012-agent-operating-rules.md)。

---

## 8. 工具链（TOOL）

| ID | 能力 | 命令 |
|---|---|---|
| TOOL-001 | 设备身份探测（脱敏） | `python -m toolkit.repurpose detect` |
| TOOL-002 | 能力矩阵探测（NS/cgroup/分区/FBE/权限） | `python -m toolkit.repurpose probe` |
| TOOL-003 | 路线评估与门禁判定 | `python -m toolkit.repurpose assess` |
| TOOL-004 | 阶段计划生成 | `python -m toolkit.repurpose plan` |
| TOOL-005 | 新设备档案脚手架 | `python -m toolkit.repurpose new-profile` |
| TOOL-006 | Agent 清单生成 | `python -m toolkit.repurpose index` |
| TOOL-007 | 内容一致性校验 | `python -m toolkit.repurpose validate` |
| TOOL-008 | 服务器只读健康检查 | [toolkit/termux/healthcheck.sh](toolkit/termux/healthcheck.sh) |
| TOOL-009 | 24h soak 观测记录 | [toolkit/termux/soak.sh](toolkit/termux/soak.sh) |
| TOOL-010 | Termux:Boot 自启引导（幂等/dry-run） | [toolkit/termux/boot-starter.sh](toolkit/termux/boot-starter.sh) |

> **工具登记表以 [toolkit/README.md](toolkit/README.md) 为准**（含 CLI 契约、退出码、schema、扩展 SOP）；上表是给人类的总览。新增工具必须先在该登记表分配 `TOOL-<下一个号>` 再实现。

详见 [toolkit/README.md](toolkit/README.md)：CLI 契约、JSON schema、模板、扩展方式与测试。

---

## 9. 实证案例：Redmi K40 Pro（部分验收）

[cases/haydn-k40pro/README.md](cases/haydn-k40pro/README.md) 记录了完整落地：无 Root、Termux + proot Ubuntu、supervisord 12 服务、Android Bridge APK（release）、Console/DSH 控制面、每日加密备份；也诚实记录了**未完成项与偏差**（24h soak、mTLS/配对/限流、曾出现的明文凭据与"伪 pin"等）。

用途：
- **验证方法论**：哪些 MTH 结论被实测支持，哪些仍是待验证假设；
- **回归样例**：`cases/haydn-k40pro/profile.json` 可直接跑 `toolkit assess` / `plan`；
- **反面教材**：偏差项已沉淀为 PIT/GRD，避免换机重蹈覆辙。

> 案例目录冻结（frozen evidence）：只允许修正事实错误，不允许为了"看起来更好"改写历史结论。

---

## 10. 当前状态与成熟度

> 本节只写摘要（≤8 行）；详细状态见 [methodology/README.md 成熟度](methodology/README.md) 与 [CHANGELOG.md](CHANGELOG.md) 当前窗口（≤8 条），历史见 [changelog/](changelog/README.md)（默认不读）。

- 方法论：MTH-000..011 初版完成；工具链：零依赖 CLI + fixture 单测，**尚未真机回归**；案例：部分验收（24h soak 等未完成，不得表述为全验收）。
- 已知缺口与下一步见 [backlog.json](backlog.json)；模板、schema、校验与归档规则分别见 [toolkit/README.md](toolkit/README.md) 与 [MTH-011](methodology/10-document-lifecycle.md)。

---

## 11. 如何扩展（人或 Agent）

统一流程：**读 AGENTS.md → 领取 backlog 任务 → 按模板新建内容 → 跑校验 → 更新索引/变更记录 → 完成定义（DoD）**。

- 新增一篇方法论：使用 [toolkit/templates/methodology-doc.md](toolkit/templates/methodology-doc.md)，ID 取 MTH 未用号；
- 新增一条踩坑：使用 [toolkit/templates/pitfall.md](toolkit/templates/pitfall.md)，必须含证据与验证；
- 新增一条护栏：使用 [toolkit/templates/guardrail.md](toolkit/templates/guardrail.md)，必须含可执行检查方式；
- 新增工具能力：实现命令 + 单元测试 + 更新 `toolkit/README.md` 与 schema；
- 新增设备案例：复制 [toolkit/templates/case-study.md](toolkit/templates/case-study.md) 并填 `profile.json`。

索引不会手工维护：`python -m toolkit.repurpose index` 从各文档 front matter 重建根 [agent-manifest.json](agent-manifest.json) 摘要与 [agent-manifest.d/](agent-manifest.d/) 分片；`validate --strict` 校验 ID 唯一、front matter、断链、文档体积与 CHANGELOG 窗口上限。**同样的变更**若改变对外事实/契约，还要在当前 [CHANGELOG.md](CHANGELOG.md) 窗口加一条；与相邻 `changelog/` 归档规则见 [MTH-011](methodology/10-document-lifecycle.md)。

---

## 12. 历史、安全与许可

- **历史**：本仓库前身 `haydn-server`（2026-11-10 ~ 2026-11-11），原始 README 已归档于 [docs/90-archive/README-2026-11-10.md](docs/90-archive/README-2026-11-10.md)；变更历史见 [CHANGELOG.md](CHANGELOG.md)（当前窗口）与 [changelog/](changelog/README.md)（按月归档，默认不读）；案例状态以 [docs/00-overview/当前状态.md](docs/00-overview/当前状态.md) 为准（仅描述 haydn 案例，不描述方法论层）。
- **归档**：`CHANGELOG.md` 当前窗口 ≤8 条；超窗条目按月移入 `changelog/YYYY-MM.md`（只读、默认不读）；记录边界与操作步骤见 [MTH-011](methodology/10-document-lifecycle.md) 与 [changelog/README.md](changelog/README.md)。
- **安全**：任何 token/密码/证书私钥/备份口令都不进入仓库、日志、文档、聊天；发现泄露先轮换再清理历史（[GRD-006](guardrails/GRD-006-secret-hygiene.md)）。
- **许可**：个人自用与研究项目；第三方项目仅按许可证参考/使用，GPL 只读参考不复制（[GRD-010](guardrails/GRD-010-license-compliance.md)）。

> 本仓库默认不提供任何"一键 Root/刷机/破解"内容；所有高风险路径都必须先过评估门禁并取得设备所有者明确授权。
