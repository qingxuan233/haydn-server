---
id: CASE-000
title: 案例层索引：设备实证案例的目录约定与登记流程
type: index
status: current
audience: human, agent
tags: cases, index, evidence, device-profile, onboarding
depends: MTH-000, MTH-002
updated: 2026-11-14
agent_hint: 新增设备案例先读本页：复制模板 → 填 profile → 标注证据 → toolkit assess/validate → 登记清单
---

# CASE-000 · 案例层索引

> `cases/` 是四层知识体系（`methodology/` 规范、`guardrails/` 红线、`pitfalls/` 证据、`toolkit/` 实现）之外的**实证层**。
> 每个真实改造过的设备一个目录，记录"这台机器上方法论被验证到什么程度、哪里不成立、为什么"。案例是证据，不是教程；通用步骤写在 [methodology/README.md](../methodology/README.md)，不要复制到案例里。
> 首例：[haydn K40 Pro 案例](haydn-k40pro/README.md)（CASE-001，已冻结）。**预研/实验案例**（未购入或仅部分实测）允许以 `status: draft` 入档，但必须显著标注实测程度，不得当作完整验收证据（如 [一加 Ace Pro 实验轨](ace-pro-pgp110/README.md)）。

---

## 1. 用途与定位

| 用途 | 说明 |
|---|---|
| 端到端验证 | 记录一套设备从评估、决策、落地到验收的完整事实，证明方法论在真实硬件上可执行 |
| 反例来源 | 偏差、事故、未验证项沉淀为 [pitfalls/README.md](../pitfalls/README.md) 条目，反推规范漏洞 |
| 换机基线 | 新设备案例与首例对比，快速判断"哪些通用、哪些要重做" |
| 机器可读 | `profile.json` 让 [toolkit/README.md](../toolkit/README.md) 可对案例做评估/校验，而不靠读长文 |
| 冻结证据 | 案例一旦验收即冻结，保留历史事实；新结论写进方法论层，不回头改写案例结论 |

**案例不做什么**：

- 不写"通用步骤/最佳实践"（属于 methodology）；
- 不写"红线/禁止项"（属于 guardrails）；
- 不写"工具用法"（属于 toolkit）；
- 不复制旧 `docs/`、`scripts/`、`android-bridge/` 的内容，只给相对链接与事实摘要。

## 2. 与其他层的关系

| 层 | 目录 | 与案例的关系 |
|---|---|---|
| 规范 | [methodology/README.md](../methodology/README.md) | 案例逐条验证 MTH 结论；验证不了的在案例中明确标"未验证" |
| 踩坑 | [pitfalls/README.md](../pitfalls/README.md) | 案例里的偏差/事故必须提炼成 PIT 条目（带证据链接），不能只留在案例 |
| 护栏 | [guardrails/README.md](../guardrails/README.md) | 案例中的事故用于校验 GRD 红线是否足够；红线被执行/被违反都要记录 |
| 工具 | [toolkit/README.md](../toolkit/README.md) | `assess` 消费案例 `profile.json`；`validate` 校验 front matter/ID/断链与 JSON 可解析；工具结论与案例事实不符时，以案例事实为准并修订工具 |
| 旧项目证据 | [docs/README.md](../docs/README.md) / [scripts/README.md](../scripts/README.md) / [android-bridge/README.md](../android-bridge/README.md) | 该案例的原始证据（设备档案、实施记录、脚本/APK 源码），冻结只读 |

反馈闭环：**案例事实 → PIT（证据）→ MTH 修订（规范）→ GRD 补充（红线）→ toolkit 校验（实现）→ 下一个案例复验**。

## 3. 目录约定

```text
cases/
├── README.md                      # 本文件（CASE-000，索引与登记流程）
└── <codename>/                    # 设备代号，ASCII（如 haydn-k40pro）
    ├── README.md                  # CASE-00N，type: case-study（案例正文）
    ├── profile.json               # repurpose.device-profile.v1（机器可读档案）
    ├── oem-profile.md             # CASE-00N，type: oem-profile（OEM 人工适配清单）
    └── <appendix>.md              # APP-00N，type: case-study（正文下沉的结构性附录，不占 CASE 编号）
```

| 文件 | 必填 | 作用 | 约束 |
|---|---|---|---|
| `README.md` | 是 | 案例概览、关键事实、时间线、三轨实现、证据地图、方法论验证、偏差教训、复用指南 | 冻结后仅修事实错误 |
| `profile.json` | 是 | 设备能力的结构化档案；被 `assess` 消费、被 `validate` 做 JSON 可解析检查 | 符合 [device-profile.schema.json](../toolkit/schema/device-profile.schema.json)；数值不可确认用 `null`；不得含敏感值 |
| `oem-profile.md` | 建议 | 该厂商/ROM 的自启动、省电、安装、FBE、系统包保护等人工步骤 | 只写 OEM 私有项；标准 Android 基线不重复 |

命名与脱敏：

- 目录名**全 ASCII**、小写、可用 `-`（不要用中文/空格/大写）；一个设备/代号一个目录。
- 正文中文；`README.md`/`oem-profile.md`/结构性附录（`<appendix>.md`）顶部必须是 flat YAML front matter（首行与末行均为 `---`），附录 ID 只增不复用。
- 不得出现序列号、账号、token、口令、私钥、IP、主机名、端口或绝对路径（如 `D:\...`）；引用旧文档给仓库相对路径链接即可。

### 3.1 profile.json 填写规则

1. **`source.mode` 必须诚实**：`documented`（只从既有文档整理，未经工具重新探测）、`adb` / `fixture`（探测工具产出）、`manual`（人工补填）；`documented` 时 `source.commands` 为空数组，并在 `notes` 写明"未经工具重新探测"。
2. **`evidence_refs` 给证据链**：数组元素是仓库相对路径（如 `docs/10-device/01-设备档案.md`），不写外部 URL、不写绝对路径；具体字段的对应关系写在案例正文"关键事实"表里，机器档案只保留证据清单。
3. **不可确认就留空**：数值无法确认写 `null`，无法确认的字段路径登记到 `unknowns[]`，不得猜测或凑整。
4. **风险与边界写进 `warnings[]`**：锁定/OEM 策略、内核能力缺失、未完成验收、快照时效等，必须显式写出。
5. **字段名以 schema 为准**：不要自行改名/加私有字段；工具与案例不一致时先改工具并回归测试（顶层键顺序与 [toolkit/schema/device-profile.schema.json](../toolkit/schema/device-profile.schema.json) 一致）。

## 4. 如何新增一个设备案例

> 目标：20–60 分钟产出一个"可被工具校验、可被下一个 Agent 复用"的案例骨架；事实密度比篇幅重要。

1. **复制模板**：以 [toolkit/templates/case-study.md](../toolkit/templates/case-study.md) 为正文骨架，建立 `cases/<codename>/README.md`；`oem-profile.md` 按 [首例的模板结构](haydn-k40pro/oem-profile.md) 填写；`profile.json` 可用 `python -m toolkit.repurpose new-profile` 生成骨架（参数见 [toolkit/README.md](../toolkit/README.md)）。
2. **填 profile**：按第 3.1 节逐组填 `identity`、`boot`、`root`、`kernel`、`hardware`、`storage`、`crypto`、`features`、`constraints`；先跑只读探测（`toolkit probe`/`detect`），把 `source.mode` 从 `documented`/`manual` 升级为 `adb` 或 `fixture`（探测产出）。
3. **标注证据**：关键事实（启动链、Root、内核命名空间/cgroup、存储、权限重置、验收数字）逐条给证据链接或"待验证"标记；引用旧项目证据用 `../../docs/...`，引用方法论用 `../../methodology/...`。
4. **运行校验**：`python -m toolkit.repurpose assess --profile cases/<codename>/profile.json --json` 评估路线/门禁/风险，`python -m toolkit.repurpose validate --strict` 校验 front matter/ID/断链；两者结果写进案例的"方法论验证"小节（包括与预期不一致的项）。
5. **登记**：在 §5 案例清单表加一行；同步 `agent-manifest.json`（`python -m toolkit.repurpose index`）；若验证出方法论偏差，开对应 PIT；若属新红线，开 GRD。

案例完成后的**冻结规则**：只允许修事实错误（数字、链接、错别字、脱敏遗漏），不得改写结论、删除偏差记录、追加"后来已修复"式美化；新进展写进方法论/踩坑/护栏层并在本案例对应条目加一处"后续见"链接。

## 5. 案例清单

| 案例 ID | 目录 | 设备 | 系统 | 关键约束 | 路线 | 验证状态 | 入口 |
|---|---|---|---|---|---|---|---|
| CASE-001 | `cases/haydn-k40pro/` | Redmi K40 Pro（`M2012K11C` / `haydn` / SM8350 / 8GB / 256GB） | Android 14 / HyperOS 1.0（国行） | BL 锁定、AVB green、无 Root、内核缺 USER_NS/PID_NS | A（Termux + proot，无 Root） | Phase 0/1 完成，Phase 2 部分完成；24h soak 未完成 | [案例正文](haydn-k40pro/README.md) · [profile](haydn-k40pro/profile.json) · [复用指南附录](haydn-k40pro/reuse-guide.md) |
| CASE-002 | `cases/haydn-k40pro/` | 同上（OEM 侧清单） | 小米 / HyperOS | OEM 私有设置无标准 API；本机实测 5/5 debug + 1/1 release 重启与权限重置 | A | 小米实例已实测；其他 OEM 未验证 | [OEM profile](haydn-k40pro/oem-profile.md) |
| CASE-003 | `cases/ace-pro-pgp110/` | OnePlus Ace Pro（`PGP110` / `ovaltine` / SM8475 / 16GB / 256GB） | ColorOS 12.1→15（Android 12→15） | 已购机；2026-11-13 完成官方解锁 + KernelSU LKM Root + 3/3 救援演练；P1 管理面部分落地（Tailscale/SSH、充电上限 80%、无用应用禁用、Quark 加密备份跑通（自动化脚本二次执行））；24h soak run #2/chroot 基准/割接未完成 | 目标 B（Root + chroot，受控实验） | **draft/实验轨（部分实测，未全验收）**；按 [MTH-012](../methodology/11-root-lab.md) 门禁推进 | [实验轨正文](ace-pro-pgp110/README.md) · [profile](ace-pro-pgp110/profile.json) · [P1 配置附录](ace-pro-pgp110/p1-config.md) |
| CASE-004 | `cases/ace-pro-pgp110/` | 同上（OEM 侧清单） | 一加 / ColorOS | 深度测试、ARB、Root 后指纹/完整性部分待实测 | B | **draft/实验轨（OEM 侧部分待实测）** | [OEM profile](ace-pro-pgp110/oem-profile.md) |

> 清单按案例 ID 递增；一个案例一行，状态写"已完成/部分/未验证"的事实，不写目标值。

## 6. 维护规则

1. 新增/修改后跑：`python -m toolkit.repurpose validate --strict`、`python -m toolkit.repurpose index`、`python scripts/dev/check-links.py --strict-anchors`（全绿才提交）。
2. 案例正文必须给"方法论验证"表：明确哪些 MTH 结论**被验证**、哪些**未验证/不成立**；未验证项不得写成已完成。
3. 案例中发现的偏差，必须同时开 PIT 并在案例里给链接；不允许只删现象不改证据。
4. `profile.json` 任何字段变更都要保留证据链接，并在案例正文"关键事实"表同步；数值口径变化必须标注日期/快照。
5. 案例正文只给相对链接，**禁止 `#anchor`**；引用旧文档用 `../../docs/...`，引用工具用 `../../toolkit/...`。
6. 本索引（CASE-000）随案例增删同步更新；ID 只增不复用。
