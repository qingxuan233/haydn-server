---
id: TOOL-000
title: 通用改造工具链 toolkit（CLI / schema / 模板 / Termux 脚本 / 测试）
type: index
status: current
audience: human, agent
tags: toolkit, cli, schema, templates, termux, index, validate, offline-fixture
depends: MTH-000, MTH-002
updated: 2026-11-11
agent_hint: 改工具前先读本页契约与 [AGENTS](../AGENTS.md) §7；任何子命令/字段/schema 变更必须同步 tests + schema + 本 README，并重跑 validate/index/unitest
---

# TOOL-000 · 通用改造工具链 toolkit

> **定位**：把"安卓手机改造成家用 Linux 服务器"的方法论落成**可复用的零第三方依赖工具**：
> 只读探测 → 离线评估 → 阶段计划 → 模板/schema → Termux 运维脚本 → 机器索引与内容校验。
> **不写设备、不刷机、不持凭据**；无真机时用 `--adb-fixture` 离线跑通，测试不依赖网络/设备。
>
> 上位协议：[AGENTS.md](../AGENTS.md)（仓库根）> [methodology/README.md](../methodology/README.md)（MTH）
> > [guardrails/README.md](../guardrails/README.md)（GRD）> 本文（工具契约）。
> 方法论评估 SOP 见 [MTH-002](../methodology/01-assessment.md)；扩展/交接协议见
> [MTH-009](../methodology/08-agent-handoff.md)。

## 1. 快速开始（所有命令在仓库根执行）

```powershell
# 1) 查看全部子命令与退出码
python -m toolkit.repurpose --help

# 2) 无真机：用离线 fixture 走完整链路
python -m toolkit.repurpose detect --adb-fixture toolkit/tests/fixtures/adb-haydn.json --out profiles/demo.json
python -m toolkit.repurpose probe --base profiles/demo.json --adb-fixture toolkit/tests/fixtures/adb-haydn.json --out profiles/demo-probed.json
python -m toolkit.repurpose assess --profile profiles/demo-probed.json --json
python -m toolkit.repurpose plan --profile profiles/demo-probed.json --format md

# 3) 有真机（只读）：默认脱敏，不把序列号写入产物
python -m toolkit.repurpose detect --serial <device-serial> --out profiles/<codename>.json
python -m toolkit.repurpose probe --base profiles/<codename>.json --out profiles/<codename>-probed.json

# 4) 内容层维护
python -m toolkit.repurpose index              # 重建仓库根 agent-manifest.json
python -m toolkit.repurpose validate --strict  # front matter/ID/断链/JSON/manifest
python -m unittest discover -s toolkit/tests -t . -v

# 5) Windows 包装（等价命令）
powershell -NoProfile -ExecutionPolicy Bypass -File toolkit\repurpose.ps1 --help
```

离线样例 profile：[profile-haydn-locked.json](tests/fixtures/profile-haydn-locked.json)
（`documented` 来源、已脱敏）。运行产物应写入 gitignored 的 `profiles/`，不要入库。

## 2. 目录结构

```text
toolkit/
├── README.md              # 本文件（TOOL-000，工具契约）
├── repurpose.ps1          # PowerShell 包装：python -m toolkit.repurpose
├── repurpose/             # Python 包（零第三方依赖，py3.10+）
│   ├── __main__.py        # python -m 入口
│   ├── cli.py             # argparse 子命令 + 退出码
│   ├── adb.py             # AdbTransport / FixtureTransport（可注入）
│   ├── detect.py          # 只读采集 device-profile 骨架
│   ├── probe.py           # 补 capabilities/verdicts
│   ├── assess.py          # 离线路线评估 A/B/C/D + 门禁
│   ├── plan.py            # P0–P6 阶段计划（json/md）
│   ├── profile.py         # profile 结构校验 + new-profile 生成
│   ├── frontmatter.py     # flat YAML front matter 解析（容 BOM/CRLF）
│   ├── indexgen.py        # 生成 agent-manifest.json
│   ├── validate.py        # 内容层校验（退出码 4）
│   ├── util.py            # JSON I/O/时间/错误类型/路径工具
│   └── __init__.py
├── templates/             # 模板（front matter 示例合法；占位符只在代码块）
├── schema/                # 3 个自描述 JSON Schema
├── termux/                # Termux 侧脚本（只读/安全可中断）
└── tests/                 # unittest + fixtures（离线、无真机）
```

## 3. CLI 契约

全局参数：`--verbose`（把过程信息写到 stderr）。所有输出默认不打印序列号/token/IP 等敏感值。
`python -m toolkit.repurpose <子命令> --help` 可查看每个参数的完整说明。

| 子命令 | 关键参数 | 默认输出 | 说明 |
|---|---|---|---|
| `detect` | `--serial`、`--out`、`--include-serial`、`--adb-fixture` | 打印 profile JSON | 只读采集 `repurpose.device-profile.v1` 骨架；默认脱敏；ADB 不可用/无设备 → exit 3；fixture 可离线 |
| `probe` | `--base`（可选）、`--out`、`--adb-fixture`、`--json` | 人类摘要；`--json` 打印完整 JSON | 在 profile 上补 12 项 `capabilities` 与 `verdicts`；无设备但有 `--base` 时进入离线模式 |
| `assess` | `--profile`（必填）、`--json` | 人类摘要 | 输出 `repurpose.assessment.v1`：route/route_label/confidence/gates/blocked/alternatives/risks/next_steps/assumptions/unknowns |
| `plan` | `--profile`（必填）、`--route auto\|A\|B\|C\|D`、`--format json\|md` | markdown | 输出 P0–P6 阶段：id/title/objective/actions/deliverables/gate/exit_criteria/rollback；A 与 B 动作不同；auto 用 assess 结论 |
| `new-profile` | `--codename`（必填）、`--out` | 打印 profile JSON | 从模板生成可编辑骨架（含 unknowns 提示），后续人工补证 |
| `index` | `--root`、`--out`、`--json` | 人类摘要 | 扫描 methodology/pitfalls/guardrails/cases 的 front matter，生成 `<root>/agent-manifest.json`；目录缺失跳过不失败 |
| `validate` | `--root`、`--strict`、`--json` | 人类摘要 | 检查必需 front matter 键、ID 唯一、相对链接存在（不检查 anchor）、JSON 可解析、manifest 过期/计数 |

**退出码**（与 `--help` epilog 一致）：

| 码 | 含义 | 触发场景 |
|---|---|---|
| 0 | 成功 | 命令完成且无失败 |
| 2 | 用法/输入错误 | argparse 参数错误、profile 结构不合法、`--route` 非法 |
| 3 | 前置条件不满足 | 无 adb、无在线设备、fixture 文件不存在/格式错误、probe 无 base 且无设备 |
| 4 | 校验失败 | `validate` 发现 error；`--strict` 下 warning 也算失败 |
| 130 | 被中断 | Ctrl-C（脚本类：termux 脚本明确可中断；Python 命令不写设备） |

`index` 是唯一会写仓库根文件的子命令（生成物 `agent-manifest.json`）；其余探测命令只读设备。
在无权限写根目录的环境可用 `index --out <path>` 重定向（CI 中用于对比）。

## 3.1 工具登记表（TOOL-001..010，新增工具先在这里登记）

| ID | 能力 | 入口 | 设备/环境 |
|---|---|---|---|
| TOOL-001 | 设备身份探测（默认脱敏） | `python -m toolkit.repurpose detect` | 真机或 `--adb-fixture` |
| TOOL-002 | 能力矩阵探测（NS/cgroup/分区/FBE/权限） | `python -m toolkit.repurpose probe` | 真机或 `--adb-fixture` |
| TOOL-003 | 路线评估与门禁判定 | `python -m toolkit.repurpose assess` | 离线（消费 profile） |
| TOOL-004 | P0–P6 阶段计划 | `python -m toolkit.repurpose plan` | 离线 |
| TOOL-005 | 新设备档案脚手架 | `python -m toolkit.repurpose new-profile` | 离线 |
| TOOL-006 | Agent 清单生成（agent-manifest.json） | `python -m toolkit.repurpose index` | 离线（仓库内） |
| TOOL-007 | 内容一致性校验（front matter/ID/断链/JSON） | `python -m toolkit.repurpose validate` | 离线（仓库内） |
| TOOL-008 | 服务器只读健康检查 | [termux/healthcheck.sh](termux/healthcheck.sh) | proot 服务器内 |
| TOOL-009 | 24h soak 观测记录（可中断） | [termux/soak.sh](termux/soak.sh) | proot 服务器内 |
| TOOL-010 | Termux:Boot 自启引导（幂等/dry-run） | [termux/boot-starter.sh](termux/boot-starter.sh) | Termux 内 |

> 规则：①新增能力**先登记** `TOOL-<下一个号>` 再实现；ID 只增不复用。②`agent-manifest.json` 的 `tools` 是**物理入口视图**（当前 5 个：CLI/包装器/3 个 Termux 脚本），不替代本登记表。③`toolkit/templates/*` 中的 `TOOL-*`/示例 ID 只是排版示例，不占正式编号。④改契约必须同步实现 + tests + 本表 + schema + README，并重跑 §10 质量门。

---

## 4. device-profile 字段表（`repurpose.device-profile.v1`）

完整 schema：[device-profile.schema.json](schema/device-profile.schema.json)；模板：
[device-profile.json](templates/device-profile.json)。**未知字段必须为 `null` 并列入 `unknowns`，不得臆测**。
`detect` 输出全部顶层键；`probe` 额外追加 `capabilities`/`verdicts`/`probe`。

| 顶层键 | 关键字段 | 用途 |
|---|---|---|
| `schema` / `generated_at` | 固定 schema 字符串 / UTC ISO 时间 | 版本与可追溯性 |
| `source` | `mode`（`adb`/`fixture`/`documented`/`manual`）、`commands[]`、`notes` | 证据来源（不含敏感值） |
| `identity` | `codename`、`model`、`market_name`、`manufacturer`、`brand`、`product`、`fingerprint`、`android_version`、`sdk`、`build_id`、`build_type`、`security_patch`、`serial`（默认 null）、`serial_redacted` | 设备/系统身份；序列号不落库 |
| `boot` | `bootloader_unlocked`、`verified_boot_state`、`vbmeta_device_state`、`dm_verity_mode`、`selinux`、`slot_suffix`、`partition_style`、`has_init_boot`、`oem_unlock_policy`（open/available/closed/unknown）、`oem_unlock_evidence` | G-B0 解锁前置与刷机风险 |
| `root` | `state`（none/magisk/kernelsu/apatch/unknown）、`su_available`、`root_manager_packages[]`、`adb_uid`、`ro_secure`、`ro_debuggable` | G-B1 Root 可用性 |
| `kernel` | `release`、`version_string`、`arch`、`gki_generation`、`config_source`、`config_readable` | 架构/ptrace/内核世代判断 |
| `hardware` | `soc{manufacturer,platform,model,marketing_name}`、`cpu{cores,abi[],governors[],clusters[]}`、`memory{total_kb,available_kb,swap_total_kb}`、`display{width_px,height_px,density_dpi,refresh_hz}`、`battery{...charge_control_nodes[]}`、`thermal{zone_count,status,max_temp_c}` | 资源预算、温度/电池、限充节点 |
| `storage` | `data_total_kb`、`data_used_kb`、`data_available_kb`、`data_filesystem`、`external_sdcard`、`external_expandable`、`zram`、`zram_total_kb` | 容量规划/扩展性 |
| `crypto` | `userdata_encrypted`、`encryption_type`（FBE/FDE/none/unknown）、`keystore`、`play_integrity_required`、`play_integrity_level` | 加密/完整性约束；`play_integrity_required=true` 时 assess 提示 Root 风险 |
| `features` | `user_ns`、`pid_ns`、`mount_ns`、`net_ns`、`uts_ns`、`ipc_ns`、`cgroup_v1`、`cgroup_v2`、`cgroup_v2_delegation`、`overlay_fs`、`binfmt_misc`、`seccomp_filter`、`kallsyms`、`modules`、`ptrace_allowed`、`native_linux_port`、`custom_kernel`、`termux_available`、`shizuku_available`、`boot_completed_receiver`（均 `bool\|null`） | 能力原始事实（容器/systemd/proot/D/C 路线的判据） |
| `constraints` | `external_storage`、`oem_autostart`、`background_execution`、`battery_long_term_plugged`、`root_required_capabilities[]`、`notes[]` | 环境限制与替代方案 |
| `unknowns[]` | 字段路径字符串 | 未证实项清单 |
| `evidence_refs[]` | 只读命令或仓库相对路径 | 证据引用（禁止 IP/端口/token/序列号） |
| `warnings[]` | 采集异常/权限不足说明 | 不静默失败 |
| `capabilities`（probe） | 12 项，每项 `{status: pass\|fail\|unknown, evidence}` | 能力结论 |
| `verdicts`（probe） | `summary{pass,fail,unknown}`、`route_hint`、`items` | 快速消费 |
| `probe`（probe） | `probed_at`、`mode`（adb/fixture/offline/none）、`commands[]` | 探测元数据 |

probe 的 12 项能力（顺序固定）：`proot`、`containers`、`systemd`、`native_linux`、`precise_cpu`、
`raw_network_bytes`、`battery_sysfs`、`charge_limit_shell`、`dumpsys`、`appops`、`usage_stats`、
`boot_autostart`。每项必须带 `evidence`；无证据时为 `unknown`，不得填 `pass`。

### 4.1 front matter 契约（新层 Markdown）

解析器：[frontmatter.py](repurpose/frontmatter.py)；schema：[frontmatter.schema.json](schema/frontmatter.schema.json)。
必需键：`id,title,type,status,audience,tags,updated,agent_hint`（详见 [AGENTS.md](../AGENTS.md) §4.2）；
`audience`/`tags`/`depends` 是逗号分隔列表（`[a, b]` 也兼容）；flat YAML，不接受嵌套。
额外约定：pitfall 用 `severity: S1..S4` + `domain`；guardrail 用 `severity: blocker|warning` + `scope: device|server|agent|repo`。
解析器容忍 UTF-8 BOM / CRLF / 全行注释；重复键、缺失冒号等记入错误列表但不抛异常。

## 5. 路线与门禁（assess）

`route` 严格为 `A/B/C/D`；`A+` 只是文档对 A 路线的优化称呼，**不是** route ID。
`route_label` 为展示名，例如 `A · 无 Root（Termux + proot，含 A+ 优化）`。

| Gate | 判定规则 | 影响 |
|---|---|---|
| `G-A` | proot 路线可用性（架构/ptrace/probe 证据） | A 路线基础 |
| `G-B0` | `bootloader_unlocked=false` 或 `oem_unlock_policy=closed` → **fail**，B/C/D 全部不可用 | 推荐 A |
| `G-B1` | Root 管理器（Magisk/KernelSU/APatch）证据 | B 路线执行前提 |
| `G-B2` | 容器前提：`user_ns` 与 `pid_ns` 均 true **且** `cgroup_v2_delegation=true`，否则 blocked | B 容器能力 |
| `G-C` | `features.custom_kernel=true` 且 G-B0 通过 | C 研究路线 |
| `G-D` | `features.native_linux_port=true` 且 G-B0 通过 | D 原生 Linux |
| `G-RISK` | `play_integrity_required` 软门禁（不改变路线，只在 risks 提示） | 完整性风险 |

路线选择顺序：G-B0 fail/unknown → A（保守）；G-B0 pass 时：native_linux_port=true → D；
否则 root 可得或容器前提满足 → B；否则 custom_kernel=true → C；证据不足时默认 B 并降置信度。
`confidence` 是**证据完整度启发式**（0.10–0.95），不是成功概率；未知项越多越低。
`blocked` 记录被阻断的路线/能力，`alternatives` 给出降级/升级备选，`next_steps` 给出可执行动作，
`assumptions` 明确"未证实按 unknown 处理"。

## 6. index：agent-manifest.json

```powershell
python -m toolkit.repurpose index --json
```

扫描 `methodology/`、`pitfalls/`、`guardrails/`、`cases/` 下所有 `.md` 的 front matter，
生成 `repurpose.agent-manifest.v1`（默认写入仓库根，schema：
[agent-manifest.schema.json](schema/agent-manifest.schema.json)）。缺失目录记 warning 并跳过。
关键内容：`repo`（只写目录名，不含绝对路径）、`entrypoints`、`reading_order`
（方法论 → 工具 → 案例 → 护栏 → 踩坑；组内索引优先、编号升序）、`content` 四组条目
（含 `severity`/`domain`/`scope`/`oem` 检索键）、`tools`、`invariants`、`commands`、`counts`、
`warnings`/`errors`。**生成物不要手改**；内容变化后重建。

## 7. validate：内容层校验

```powershell
python -m toolkit.repurpose validate            # warning 仅提示，exit 0/4
python -m toolkit.repurpose validate --strict    # warning 也视为失败
python -m toolkit.repurpose validate --json
```

检查项：

1. 新层 Markdown（methodology/pitfalls/guardrails/cases + `toolkit/README.md`）的必需 front matter 键；
2. ID 唯一且符合 `PREFIX-000`；pitfall/guardrail 额外键约定（warning）；
3. 相对 Markdown 链接目标存在（去掉 `#anchor` 后检查；不检查 anchor 是否存在）；外部 http(s) 链接跳过；
   `#anchor` 与绝对路径按新层规范记 warning；
4. 根 JSON（`agent-manifest.json`/`backlog.json`）与内容层、toolkit、docs、scripts、android-bridge 下
   非隐私目录 JSON 可解析；manifest schema 正确；
5. `agent-manifest.json` 是否缺失/过期（内容文件比 manifest 新）/counts 与当前内容不一致。
6. 敏感值启发式（私钥/令牌片段）只记 warning，不打印内容。

## 8. 模板与 schema（新增内容先复制模板）

| 文件 | 用途 |
|---|---|
| [templates/methodology-doc.md](templates/methodology-doc.md) | MTH 方法论条目（结论先行/MUST-SHOULD-MAY/证据/验证） |
| [templates/pitfall.md](templates/pitfall.md) | PIT 踩坑（症状/触发/根因/规避修复/验证/关联/证据） |
| [templates/guardrail.md](templates/guardrail.md) | GRD 护栏（红线/为什么/允许替代/检查方式）；`severity: blocker\|warning` + `scope` |
| [templates/case-study.md](templates/case-study.md) | CASE 案例（概况/时间线/验收/限制） |
| [templates/agent-task.md](templates/agent-task.md) | Agent 任务单（目标/输入/写范围/验收/报告格式） |
| [templates/oem-profile.md](templates/oem-profile.md) | OEM 差异 profile（安装/自启/后台/权限重置/验证） |
| [templates/acceptance.md](templates/acceptance.md) | 验收清单（A1–A8，证据驱动） |
| [templates/runbook.md](templates/runbook.md) | 可执行 Runbook（前置/步骤/验证/回滚/记录） |
| [templates/device-profile.json](templates/device-profile.json) | profile 骨架（字段全、值全 unknown，可直接补证） |

> 模板使用警告：①模板 front matter 里的示例 ID（如 `MTH-011`/`PIT-021`/`GRD-015`/`CASE-003`）**只是示例、不占正式编号**，复制时必须查 manifest 改成当前未占用号；②模板正文 H2 带编号只为阅读方便，**正式 PIT/GRD 必须使用各自 README 规定的无编号固定 H2**（否则人/机器检索会不一致）；③模板中的 `<...>` 占位符只出现在演示代码块，正式文档不得保留。

| Schema | 用途 |
|---|---|
| [schema/device-profile.schema.json](schema/device-profile.schema.json) | `repurpose.device-profile.v1`（detect/probe 产物、cases profile） |
| [schema/agent-manifest.schema.json](schema/agent-manifest.schema.json) | `repurpose.agent-manifest.v1`（index 产物） |
| [schema/frontmatter.schema.json](schema/frontmatter.schema.json) | 新层 Markdown front matter 契约（含 pitfall/guardrail 额外键） |

三个 schema 都是**自描述 JSON Schema（draft-07）**，校验器不依赖 `jsonschema` 库；
模板/schema 一致性由单元测试覆盖（BL-009 最小版：front matter 必需键、类型枚举、
pitfall/guardrail 额外键、模板无待办占位/无断链占位）。

## 9. Termux 脚本（只读或安全可中断）

| 脚本 | 用途与安全边界 |
|---|---|
| [termux/healthcheck.sh](termux/healthcheck.sh) | 只读健康检查（负载/内存/磁盘/电池/温度/supervisor 状态）；`--once`/`--interval`/`--json`；不写设备 |
| [termux/soak.sh](termux/soak.sh) | 24h soak 观测：CSV 采样、失败计数、可用率摘要；`--duration/--interval/--out/--health-url/--dry-run`；Ctrl-C 落盘摘要后退出 130；HTTP 地址必须显式传入，不硬编码 IP |
| [termux/boot-starter.sh](termux/boot-starter.sh) | Termux:Boot 自启引导：等待命令可用 → 原子锁 → 启动指定命令 → 日志；`--dry-run`/`--check`/`--wait`；幂等、trap 清理锁、目标命令可由 `$SERVER_START_CMD` 或 `--command` 指定 |

脚本均不含凭据/IP/端口常量；`--log`/`--out` 只提供显式路径（默认相对当前目录）。

## 10. 测试与质量门

```powershell
python -m unittest discover -s toolkit/tests -t . -v
```

覆盖：front matter（BOM/CRLF/列表/引号/错误分支）、profile 结构校验与模板/schema 一致性、
assess 四条路线与门禁/软门禁/未知降置信度、plan 的 P0–P6 与 A/B 差异、index（临时仓库/缺失目录/
malformed front matter/检索键）、validate（重复 ID/断链/anchor/绝对路径/JSON/manifest 过期/strict）、
CLI（`--help` 退出码/subcommand help、fixture 离线 detect/probe/assess/plan/new-profile/index/validate）。
测试全部离线（fixture：[adb-haydn.json](tests/fixtures/adb-haydn.json)、
[profile-haydn-locked.json](tests/fixtures/profile-haydn-locked.json)、
[repo_builder.py](tests/fixtures/repo_builder.py)），不依赖真机与网络。

## 11. 扩展子命令/SOP（改契约必须同步）

1. 在 [cli.py](repurpose/cli.py) 增加 parser（`--help` 文本与实现一致）与 handler，遵守退出码约定；
2. 新逻辑放独立模块；需要设备访问时通过可注入 transport（禁止直接全局 `adb`）；
3. 在 `tests/` 补单元测试（成功/边界/失败分支），并跑全量 unittest；
4. 更新本 README 的 CLI 契约、字段/schema、目录表；
5. 涉及 front matter/ID/schema 时同步更新 `schema/` 与模板；
6. 运行 `validate --strict` + `index` + 全量测试；`agent-manifest.json` 与内容一致；
7. 对外契约变化在 CHANGELOG.md 记录（Lead/维护者提交），并按 [MTH-009](../methodology/08-agent-handoff.md)
   做影响传播（MTH/PIT/GRD/CASE 交叉链接）。
   > 如需"一条命令跑完所有 CI 门"，见 [backlog.json](../backlog.json) BL-003（`preflight` 子命令，尚未实现）。

## 12. 与 AGENTS / MTH / PIT / GRD / CASE 的接口约定

| 接口 | 约定 |
|---|---|
| [AGENTS.md](../AGENTS.md) | 工具是唯一机器索引/校验入口；`index` 生成 `agent-manifest.json`（生成物不手改）；DoD 命令必须全绿 |
| [MTH-000](../methodology/README.md) / [MTH-002](../methodology/01-assessment.md) | profile/assessment 字段与门禁 ID（G-A/G-B0/G-B1/G-B2/G-C/G-D）以本工具 schema 为准；文档不得另造字段 |
| [MTH-009](../methodology/08-agent-handoff.md) | 改契约的传播流程：工具 + schema + 模板 + 测试 + 文档 + manifest 同步 |
| [pitfalls/README.md](../pitfalls/README.md) | manifest 条目必须带 `severity`/`domain`，供 Agent 过滤；PIT 复现优先用工具只读命令 |
| [guardrails/README.md](../guardrails/README.md) | 工具不得通过写设备/提权"绕过"红线；验证命令只读 |
| [cases/README.md](../cases/README.md) | 案例 profile 用 `repurpose.device-profile.v1`，经 assess 验证；敏感值脱敏 |
| `agent-manifest.json` / `backlog.json` | manifest 由 `index` 重建；backlog 由维护者/Lead 维护，工具只读 |

## 13. 安全与隐私

- `detect` 默认 `serial_redacted=true`（`identity.serial=null`）；`--include-serial` 仅本地调试，
  产物必须写 gitignored 的 `profiles/`，禁止入库/进文档/进聊天；
- 输出只含结构化字段与命令名（`adb shell getprop` 等），不打印原始设备输出、不打印 token/IP；
- 所有设备命令**只读**（`getprop`/`cat`/`ls`/`df`/`dumpsys`/`wm`/`pm list`/`unshare` 临时实验/
  `test -r/-w`）；无任何写入/重启/安装/卸载操作；
- 无第三方依赖；无网络访问（除 `soak.sh --health-url` 由调用方显式提供）。

## 14. 已知限制（诚实标注）

- **尚未真机回归**：`detect`/`probe` 的字段解析以 fixture 与案例文档为基准，不同 OEM/ROM 的
  属性、`/proc` 输出、权限行为可能需要调整（对应 backlog BL-001）；fixture 结果不代表真机现状。
- `native_linux_port` / `custom_kernel` / `oem_autostart` 无法由 adb 直接检测：`detect` 保持 `null`，
  需人工/社区文档补证；`assess` 不会臆测。
- `probe` 的 12 项能力是"当前通道（ADB/root）可获取性"判定；App 层（Bridge）是否可得可能不同，
  evidence 中已注明；报告不得把 ADB 可读误写为 App 可读。
- Windows 环境无 bash，`termux/*.sh` 只做静态审查与真实 Termux 使用，未在本机执行（已保持 POSIX/bash
  兼容、只读/可中断设计）；真机/真 Termux 验证列入 backlog。
- `index` 默认写仓库根 `agent-manifest.json`（生成物）；在只读环境用 `--out` 重定向。
