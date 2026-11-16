---
id: TOOL-000
title: 通用改造工具链 toolkit（CLI / schema / 模板 / Termux 脚本 / 测试）
type: index
status: current
audience: human, agent
tags: toolkit, cli, schema, templates, termux, index, validate, governance, preflight, offline-fixture
depends: MTH-000, MTH-002
updated: 2026-11-14
agent_hint: 改工具前先读本页契约与 [AGENTS](../AGENTS.md) §7；任何子命令/字段/schema 变更必须同步 tests + schema + 本 README，并重跑 preflight（index→validate --strict→unittest→check-links→check-secrets，退出码 0/3/4）
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
python -m toolkit.repurpose index --check       # 只读校验生成物是否与内容一致（不一致 exit 4）
python -m toolkit.repurpose validate --strict  # front matter/协议/命名/PIT/ADR/backlog/归档/断链/manifest
python -m unittest discover -s toolkit/tests -t . -v

# 5) 统一质量门（一次串联四道门；退出码 0=全绿 / 3=有跳过 / 4=失败）
python -m toolkit.repurpose preflight
python -m toolkit.repurpose preflight --no-index --skip-tests  # 本地快速裁剪（跳过步骤计 SKIPPED；CI 请用完整 preflight）

# 6) Windows 包装（等价命令）
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
│   ├── rootcheck.py / rescuekit.py  # Root 姿态检查 / 救援包 SHA-256 清单（G-L1）
│   ├── profile.py         # profile 结构校验 + new-profile 生成
│   ├── frontmatter.py     # flat YAML front matter 解析（容 BOM/CRLF）
│   ├── docpolicy.py       # 读取 doc-policy（体积/协议/命名/治理/归档/分片上限，缺失回退默认）
│   ├── indexgen.py        # 生成根摘要 + agent-manifest.d/ 分片；check_bundle（index --check）
│   ├── governance.py      # 协议/命名/PIT/ADR/CHANGELOG 归档/backlog/Agent 回归机检
│   ├── validate.py        # 内容层 + 治理契约 + doc-policy + 根/分片一致性校验（退出码 4）
│   ├── util.py            # JSON I/O/时间/错误类型/路径工具
│   └── __init__.py
├── templates/             # 模板（front matter 示例合法；占位符只在代码块）
├── schema/                # 自描述 JSON Schema + doc-policy.json + backlog.schema.json
├── termux/                # Termux 侧脚本（只读/安全可中断）
└── tests/                 # unittest + fixtures（离线、无真机；repo_builder 生成完整最小仓库）

# 仓库根生成物（由 index 生成，不手改）
agent-manifest.json        # 根摘要（≤160 行/≤16KB，含 shards 映射）
agent-manifest.d/          # <layer>.json；单层 >40 条时拆为 <layer>-p01.json…<layer>-pNN.json
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
| `rootcheck` | `--profile`（必填）、`--json`、`--strict` | 人类摘要 | 离线检查 Root 实验设备技术姿态（`repurpose.rootcheck.v1`）：bootloader/AVB/verity/SELinux/管理器/唯一性/内核前提/分区/ARB + 授权/救援/演练/数据/固件/网络人工项；不改变 assess 路线顺序；`--strict` 非 `tech-ready` 时 exit 4 |
| `rescue-kit` | `--dir`（必填）、`--init`/`--verify`（二选一）、`--notes`、`--force`、`--json` | 人类摘要 | 对救援包目录生成/校验 `rescue-manifest.json`（相对路径+sha256）；已有清单默认拒绝覆盖（`--force` 需先核对来源/版本）；`--verify` 缺失/清单外新增/哈希不一致时 exit 4；只读写本地目录 |
| `new-profile` | `--codename`（必填）、`--out` | 打印 profile JSON | 从模板生成可编辑骨架（含 unknowns 提示），后续人工补证 |
| `index` | `--root`、`--out`、`--check`、`--json` | 人类摘要 | 扫描四层 front matter，生成根摘要 + `agent-manifest.d/` 分片；单层 >40 条按层内顺序自动拆为 `<layer>-p01.json`…（每片 ≤40 条）；目录缺失跳过不失败；旧分片自动清理。`--check` 只读重建并与磁盘生成物比较（规范化 generated_at；一致 exit 0 / 不一致 exit 4，不写盘） |
| `validate` | `--root`、`--strict`、`--mtime-check`、`--json` | 人类摘要 | 检查 front matter/ID/相对链接/JSON、AGENTS.md 协议（章节/版本/哨兵/320 行硬上限）、新层命名、PIT/ADR/CHANGELOG 归档/backlog schema、manifest 一致性、TOOL 登记表↔CLI↔manifest 一致性、`updated` 新鲜度（advisory）；`--strict` 下 warning 也失败；索引一致性以内容机检为准，`--mtime-check` 才按文件 mtime 判过期（默认关闭，CI 安全） |
| `preflight` | `--root`、`--no-index`、`--skip-tests`、`--skip-links`、`--skip-secrets`、`--json` | 步骤表 | 串联 index → validate --strict → unittest → check-links → check-secrets；输出步骤 name/status/耗时/摘要；`--json` 为 `repurpose.preflight.v1`（ok/steps/skipped/failed）；退出码 **0 全绿 / 3 有 SKIPPED / 4 任一步 FAILED**；index 步幂等（内容未变保留原 `generated_at`，不产生时间戳变更） |

**退出码**（与 `--help` epilog 一致）：

| 码 | 含义 | 触发场景 |
|---|---|---|
| 0 | 成功 | 命令完成且无失败（preflight 全绿） |
| 2 | 用法/输入错误 | argparse 参数错误、profile 结构不合法、`--route` 非法 |
| 3 | 前置条件不满足 / 步骤被跳过 | 无 adb、无在线设备、fixture 不可用、probe 无 base 且无设备；**preflight 存在 SKIPPED**（`--skip-tests/--skip-links/--skip-secrets/--no-index` 或 check-links/check-secrets 脚本缺失，CI 可消费） |
| 4 | 校验失败 | `validate` 发现 error；`rootcheck --strict` 非 `tech-ready`；`rescue-kit --verify` 不一致；**`index --check` 生成物不一致**；**`preflight` 任一步 FAILED**（含 check-secrets 命中）；`--strict` 下 warning 也算失败 |
| 130 | 被中断 | Ctrl-C（脚本类：termux 脚本明确可中断；Python 命令不写设备） |

`index`/`preflight` 是仅有的会更新仓库根生成物的命令。默认路径且内容未变化时 `index` **不重写**（保留原 `generated_at`），因此 `preflight` 全绿后工作区不会产生"仅时间戳"变更；仅内容变化、显式 `--out` 或显式传入 `generated_at` 时才写盘。`index --check` 与 `preflight --no-index` 只读；其余探测命令只读设备。
`index --json` 会报告根/分片的行数、字节数、条数与清理结果；`--out <path>` 只重定向根摘要（分片仍写默认目录，便于 CI 对比）。

## 3.1 工具登记表（TOOL-001..013，新增工具先在这里登记）

| ID | 能力 | 入口 | 设备/环境 |
|---|---|---|---|
| TOOL-001 | 设备身份探测（默认脱敏） | `python -m toolkit.repurpose detect` | 真机或 `--adb-fixture` |
| TOOL-002 | 能力矩阵探测（NS/cgroup/分区/FBE/权限） | `python -m toolkit.repurpose probe` | 真机或 `--adb-fixture` |
| TOOL-003 | 路线评估与门禁判定 | `python -m toolkit.repurpose assess` | 离线（消费 profile） |
| TOOL-004 | P0–P6 阶段计划 | `python -m toolkit.repurpose plan` | 离线 |
| TOOL-005 | 新设备档案脚手架 | `python -m toolkit.repurpose new-profile` | 离线 |
| TOOL-006 | Agent 机器索引生成（根摘要 `agent-manifest.json` + `agent-manifest.d/` 四层分片） | `python -m toolkit.repurpose index` | 离线（仓库内） |
| TOOL-007 | 内容与治理契约校验（front matter/ID/断链/JSON/协议/命名/PIT/ADR/backlog/归档/doc-policy/分片/TOOL 登记表/updated 新鲜度） | `python -m toolkit.repurpose validate` | 离线（仓库内） |
| TOOL-008 | 服务器只读健康检查 | [termux/healthcheck.sh](termux/healthcheck.sh) | proot 服务器内 |
| TOOL-009 | 24h soak 观测记录（可中断） | [termux/soak.sh](termux/soak.sh) | proot 服务器内 |
| TOOL-010 | Termux:Boot 自启引导（幂等/dry-run） | [termux/boot-starter.sh](termux/boot-starter.sh) | Termux 内 |
| TOOL-011 | Root 实验设备技术姿态检查（含人工确认项） | `python -m toolkit.repurpose rootcheck` | 离线（消费 profile） |
| TOOL-012 | 救援包 SHA-256 清单生成/校验（G-L1） | `python -m toolkit.repurpose rescue-kit` | 离线（本地目录） |
| TOOL-013 | 统一质量门（index→validate --strict→unittest→check-links→check-secrets，三态退出码 0/3/4） | `python -m toolkit.repurpose preflight` | 离线（仓库内；外部步骤用 `sys.executable`） |
| TOOL-014 | 秘密/凭据模式扫描（私钥块、云/平台固定格式令牌、授权码、URL 内嵌口令等；只报路径:行号，不输出原文） | `python scripts/dev/check-secrets.py` | 离线（仓库内，只读；已并入 TOOL-013） |

> 规则：①新增能力**先登记** `TOOL-<下一个号>` 再实现；ID 只增不复用。②`agent-manifest.json` 的 `tools` 是**物理入口视图**（当前 5 个：CLI/包装器/3 个 Termux 脚本），不替代本登记表。③`toolkit/templates/*` 中的 `TOOL-*`/示例 ID 只是排版示例，不占正式编号。④改契约必须同步实现 + tests + 本表 + schema + README，并重跑 `preflight`（§10 质量门）。

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
必需键：`id,title,type,status,audience,tags,updated,agent_hint`（详见 [AGENTS.md](../AGENTS.md) §4.1 与 [MTH-009](../methodology/08-agent-handoff.md) §4）；
`audience`/`tags`/`depends` 是逗号分隔列表（`[a, b]` 也兼容）；flat YAML，不接受嵌套。
额外约定：pitfall 用 `severity: S1..S4` + `domain`；guardrail 用 `severity: blocker|warning` + `scope: device|server|agent|repo`；
`type` 另含 `adr`/`request`，`status` 另含 `accepted`/`superseded`（ADR）；ADR 用 4 位 ID（如 `ADR-0001`），`id` 正则允许 3/4 位数字。
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

**`rootcheck` 与 assess 的关系**：`assess` 回答"走哪条路线"（A/B/C/D 与 G-A/G-B0…）；
`rootcheck` 只回答"这台已授权实验设备的 Root 技术姿态是否可进入人工复核/验收"，
输出 `repurpose.rootcheck.v1`（`RC-T01..T09` 技术项 + `RC-M01..M07` 人工项），
**不新增/不改变 assess 的路线与门禁顺序**，也不替代 GRD-015 的授权、救援与演练人工确认。

`repurpose.rootcheck.v1` 字段：`schema/generated_at`、`profile{schema,generated_at,source_mode}`、`verdict`（`tech-ready`/`blocked`/`insufficient-evidence`）、`tech_ready`（技术项全 pass 才 true，unknown 不当作通过）、`manual_review_required`（固定 true）、`summary{pass,fail,unknown,total,manual}`、`checks[]`/`manual_checks[]`（`{id,name,status,blocking,reason,action[,required]}`）、`blocking_failures[]`/`blocking_unknowns[]`、`next_steps[]`。

## 6. index：根摘要 + 分层分片（Agent 分层加载）

> 解决"一次性读 50KB manifest"的上下文膨胀：**根摘要 ≤160 行/≤16KB**，完整条目按四层分片；
> Agent 先读根，需要某层时**只读一个**分片，再读单篇主题文档（读序见 [AGENTS.md](../AGENTS.md) §0）。

```powershell
python -m toolkit.repurpose index            # 重建根摘要 + 四层分片（内容未变化时不重写）
python -m toolkit.repurpose index --json     # 查看 root/shards 行数、字节、条数、清理结果
python -m toolkit.repurpose index --check    # 只读一致性校验：内存重建 vs 磁盘生成物（CI 用）
```

`index` 幂等：默认目标（未显式 `--out`/`--generated-at`）且磁盘生成物已与当前内容一致时**不重写**，保留原
`generated_at`——它表示"生成物内容最后一次变更时间"，不是"最后一次执行 index 的时间"。显式 `--out` 或外部调用
显式传入 `generated_at` 时仍强制写盘（便于测试/导出）。因此本地跑 `preflight`（内含 index 步）不会产生"仅时间戳"
的 git 变更；内容变化时照常重写并刷新 `generated_at`。`--json` 输出新增 `written`（true/false）。

`index --check` 不写盘：规范化两边 `generated_at`（时间戳不同不算差异）后逐 JSON 比较根摘要与四层分片；
一致 exit 0（打印"index 一致"），不一致打印差异文件清单并 exit 4（`--json` 为 `repurpose.index-check.v1`）。
**索引一致性以内容机检（`MANIFEST_COUNTS`/`SHARD_CONTENT`）为准，不依赖文件 mtime**——新 clone/CI 的
checkout 时间必然晚于提交的 `generated_at`，若按 mtime 判定会假失败；本地排查可用 `validate --mtime-check`。

产物（schema：[agent-manifest.schema.json](schema/agent-manifest.schema.json) /
[manifest-shard.schema.json](schema/manifest-shard.schema.json)）：

| 产物 | schema | 内容/上限 |
|---|---|---|
| `agent-manifest.json` | `repurpose.agent-manifest.v1` | 根摘要：generated_at、repo、entrypoints、reading_order（按层分组的 id 列表）、counts、shards 映射、tools、invariants、commands、warnings/errors；**不含 content 条目数组**；≤160 行/≤16KB |
| `agent-manifest.d/<layer>.json` | `repurpose.manifest-shard.v1` | 单片层（≤40 条）：layer/generated_at/count/entries；entries 含 id,title,path,type,status,tags,agent_hint（pitfall/guardrail 带 severity/domain 或 scope，可选 oem）；每片 ≤300 行/≤32KB/≤40 条 |
| `agent-manifest.d/<layer>-pNN.json` | 同上 | 拆分片（单层 >40 条）：按层内既有顺序每 40 条一片（`p01..pNN`，末片 1..40 条）；≤40 条的层仍用单文件名，不出现 `-pNN` |

缺目录/front matter 半成品：记 warning 并跳过，不中断生成；不属于当前分片集合且带本工具 schema 标记的旧分片会被清理
（未知文件不删、只记 warning）。单层 >40 条时 index 自动拆分（不再报错）；片数、`-pNN` 命名与非末片满片由 validate 强制。

Agent 示例（只读）：

```powershell
# ① 先读根摘要（≤160 行）
Get-Content agent-manifest.json

# ② 只按需读一个分片（例如找与网络/服务相关的红线）
python -c "import json;d=json.load(open('agent-manifest.d/guardrails.json',encoding='utf-8'));print(d['count']);[print(e['id'],e['title']) for e in d['entries']]"

# ③ 再读单篇主题文档（不要一次加载全部四个分片）
```

## 7. validate：内容层 + 治理契约 + doc-policy + 分片一致性

```powershell
python -m toolkit.repurpose validate            # warning 仅提示（exit 0/4）
python -m toolkit.repurpose validate --strict    # warning 也视为失败（DoD 基线）
python -m toolkit.repurpose validate --json
python -m toolkit.repurpose validate --mtime-check  # 本地排查才用：按 mtime 判 manifest 过期
```

检查项：

1. **front matter**：新层 Markdown（methodology/pitfalls/guardrails/cases/**adr** + `toolkit/README.md`）必需键；
2. **ID/链接/JSON**：ID 唯一且符合 `PREFIX-000`/`PREFIX-0000`（ADR）；相对 Markdown 链接目标存在（不检查 anchor；
   `#anchor`/绝对路径按新层规范记 warning）；根 JSON、内容层、toolkit、docs、scripts、android-bridge 非隐私 JSON 可解析；
3. **协议契约**（`governance.py` §3.1）：AGENTS.md 必需 H2（启动清单/红线/任务协议/完成定义/机器可读接口/本文件的维护）、
   `| 协议版本 | vX.Y |` 行、末行哨兵 `<!-- END-OF-PROTOCOL -->`、320 行硬上限（>320 error，201~320 只记 `checked.protocol_tier=warning`，strict 不失败）；
4. **治理契约**（`governance.py` §3.2–§3.7）：
   - 命名：methodology/pitfalls/guardrails/cases/adr/toolkit-templates 的 ASCII 小写 kebab-case、前缀与禁止状态词（README 豁免）；
   - PIT：编号连续/正文五段（症状/根因/规避/验证/证据）/条目数 ≤40（不强制旧条目补新字段）；
   - ADR：`NNNN-slug.md` 连续、id/type/status（proposed/accepted/superseded）、四段、`superseded_by` 回链、索引无孤儿；
   - CHANGELOG §4 归档索引 ↔ `changelog/*.md` 双向一致（文件存在/条数/版本范围）；
   - backlog：按 [backlog.schema.json](schema/backlog.schema.json) 校验结构，并检查 ID 连续/active 状态字段/depends 断链；active done 超过 5 条报 `BACKLOG_DONE_WINDOW`；[backlog-archive.json](../backlog-archive.json) 按 [backlog-archive.schema.json](schema/backlog-archive.schema.json) 校验（只许 done、保留 owner/updated/result、与 active 无重复），并集 ID 必须连续；
   - Agent 回归 AR-02（红线区每条含 GRD 链接且 ≥9 条）/ AR-03（manifest.invariants 覆盖关键红线词）；
   - 缺新结构文件的临时 fixture 仓库会**降级跳过**（不误报 error）；真实仓库必须全绿。
5. **doc-policy**（[schema/doc-policy.json](schema/doc-policy.json)，schema `repurpose.doc-policy.v1`）：
   - 行数上限：`AGENTS.md`≤320、`README.md`≤280、`methodology/*.md`≤300、`pitfalls/PIT-*.md`≤90、
     `pitfalls/README.md`≤150、`guardrails/GRD-*.md`≤90、`guardrails/README.md`≤130、`cases/*/README.md`≤280、
     `cases/*/oem-profile.md`≤200、`toolkit/README.md`≤440、`toolkit/templates/*.md`≤130、`adr/*.md`≤120、`adr/README.md`≤90、`backlog.json`≤600、`backlog-archive.json`≤640；
   - `changelog/*.md`≤256KB；CHANGELOG **当前窗口数据行**（`| 2026-11-11 | vX.Y | … |` 形式）≤8；
     `changelog/` 归档默认不读、只读，仅追溯时读单个文件（见 [MTH-015](../methodology/15-archive-and-context-budget.md)）；
   - `AGENTS.md`/`README.md` 的"状态段落"≤8 行（只留结论与链接）；
   - **余量预警**：行数未超上限但距上限不足 `line_limit_margin.warning_within`（当前 15）行时报
     `DOC_LINES_MARGIN`，级别为 `advisory`：照常打印但**不计入 error/warning**，`--strict` 与 `preflight` 不因此失败；
   - 策略文件缺失/损坏时回退内置默认策略并记 `POLICY_MISSING`/`POLICY_INVALID` warning。
6. **manifest 根/分片一致性**：根 ≤160 行/≤16KB 且不含完整 content；四层 `shards` 映射完整；
   分片 ≤300 行/≤32KB/≤40 条；counts 与分片/当前内容一致；分片 entry 的 ID 全局唯一、path 存在且相对、
   与内容 front matter 字段同步；旧格式/孤儿分片/过期索引都会提示重跑 index。
7. **TOOL 登记表一致性**（`validate_tool_registry`）：`toolkit/README.md` §3.1 登记表 ↔
   `cli.build_parser()` 实际子命令 ↔ 根 manifest `tools`/`commands` 三方比对——编号断号/重复、
   脚本链接缺失、CLI↔登记表双向不一致报 `TOOL_REGISTRY`/`TOOL_COMMAND`，manifest 漂移报
   `TOOL_MANIFEST`（strict 下均 error）；缺 `toolkit/README.md` 的 fixture 仓库静默跳过。
8. **`updated` 新鲜度**（`validate_updated_freshness`）：以 `git log --format=%cs` 取每文件最近
   提交日期，`updated < 提交日期` 报 `DOC_UPDATED_STALE`（**advisory，不使 strict 失败**）；只覆盖
   methodology/pitfalls/guardrails，无 `.git`/未跟踪/浅克隆/无 git 时跳过，不用文件 mtime。
9. **敏感值启发式**（私钥/令牌片段）只记 warning，不打印内容。

内容层错误与机器契约违反固定 error；policy/manifest 预算类违规在 `--strict` 下 exit 4、非 strict 下仅 warning；
`DOC_LINES_MARGIN`、`DOC_UPDATED_STALE` 为 `advisory` 级（只提示、不参与失败判定）；`MANIFEST_STALE` 仅 `--mtime-check` 开启时报告。若违规来自 Lead/维护者负责的文档，validate 只报告，不自动改那些文件。


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
| [templates/adr.md](templates/adr.md) | ADR 决策记录（状态/背景/决策/后果 + 备选方案对比） |
| [templates/request-card.md](templates/request-card.md) | 需求基线卡（目标/非目标/验收/DRI/风险） |
| [templates/device-profile.json](templates/device-profile.json) | profile 骨架（字段全、值全 unknown，可直接补证） |

> 模板使用警告：①模板 front matter 里的示例 ID（如 `MTH-011`/`PIT-021`/`GRD-015`/`CASE-003`）**只是示例、不占正式编号**，复制时必须查 manifest 改成当前未占用号；②模板正文 H2 带编号只为阅读方便，**正式 PIT/GRD 必须使用各自 README 规定的无编号固定 H2**（否则人/机器检索会不一致）；③模板中的 `<...>` 占位符只出现在演示代码块，正式文档不得保留。

| Schema / 策略 | 用途 |
|---|---|
| [schema/device-profile.schema.json](schema/device-profile.schema.json) | `repurpose.device-profile.v1`（detect/probe 产物、cases profile） |
| [schema/agent-manifest.schema.json](schema/agent-manifest.schema.json) | `repurpose.agent-manifest.v1` 根摘要（含 shards、无 content） |
| [schema/manifest-shard.schema.json](schema/manifest-shard.schema.json) | `repurpose.manifest-shard.v1` 按层分片（entries 字段/≤40 条） |
| [schema/frontmatter.schema.json](schema/frontmatter.schema.json) | 新层 Markdown front matter 契约（含 pitfall/guardrail 额外键、adr/request 类型） |
| [schema/backlog.schema.json](schema/backlog.schema.json) | `repurpose.backlog.v1` backlog.json 字段/枚举/正则 + 语义规则（governance 内置小校验器读取） |
| [schema/backlog-archive.schema.json](schema/backlog-archive.schema.json) | `repurpose.backlog-archive.v1` backlog-archive.json（归档只许 done、与 active 并集 ID 连续） |
| [schema/doc-policy.json](schema/doc-policy.json) | `repurpose.doc-policy.v1` 文档行数/协议/命名/治理/归档窗口/manifest 上限策略（validate/index 读取） |

Schema 均为**自描述 JSON Schema（draft-07）**，校验器不依赖 `jsonschema` 库；
模板/schema/doc-policy 一致性由单元测试覆盖（front matter 必需键、类型枚举、pitfall/guardrail 额外键、
根/分片上限、模板无待办占位/无断链占位）。

## 9. Termux 脚本（只读或安全可中断）

| 脚本 | 用途与安全边界 |
|---|---|
| [termux/healthcheck.sh](termux/healthcheck.sh) | 只读健康检查（负载/内存/磁盘/电池/温度/supervisor 状态）；`--once`/`--interval`/`--json`；不写设备 |
| [termux/soak.sh](termux/soak.sh) | 24h soak 观测：CSV 采样、失败计数、可用率摘要；`--duration/--interval/--out/--health-url/--dry-run`；Ctrl-C 落盘摘要后退出 130；HTTP 地址必须显式传入，不硬编码 IP |
| [termux/boot-starter.sh](termux/boot-starter.sh) | Termux:Boot 自启引导：等待命令可用 → 原子锁 → 启动指定命令 → 日志；`--dry-run`/`--check`/`--wait`；幂等、trap 清理锁、目标命令可由 `$SERVER_START_CMD` 或 `--command` 指定 |

脚本均不含凭据/IP/端口常量；`--log`/`--out` 只提供显式路径（默认相对当前目录）。

## 10. 测试与质量门

```powershell
python -m unittest discover -s toolkit/tests -t . -v   # 当前 293 项，全绿
python -m toolkit.repurpose preflight                   # 一次跑完四道门（0/3/4 三态）
```

覆盖范围（front matter/profile/assess/plan/index/validate/governance/preflight/CLI/rootcheck/rescue-kit）与 fixture 说明见 [tests/README.md](tests/README.md)；测试全部离线，不依赖真机与网络。

## 11. 扩展子命令/SOP（改契约必须同步）

1. 在 [cli.py](repurpose/cli.py) 增加 parser（`--help` 文本与实现一致）与 handler，遵守退出码约定；
2. 新逻辑放独立模块；需要设备访问时通过可注入 transport（禁止直接全局 `adb`）；
3. 在 `tests/` 补单元测试（成功/边界/失败分支），并跑全量 unittest；
4. 更新本 README 的 CLI 契约、字段/schema、目录表；
5. 涉及 front matter/ID/schema 时同步更新 `schema/` 与模板；
6. 运行 `python -m toolkit.repurpose preflight`（index + validate --strict + 全量测试 + check-links，退出码 0 才算完成）；
   `agent-manifest.json` + `agent-manifest.d/` 与内容一致（`index --check` exit 0；根摘要 ≤160 行、分片 ≤300 行/≤40 条、doc-policy 全部在限内）；
7. 对外契约变化在 CHANGELOG.md 当前窗口记录（Lead/维护者提交；窗口将超 8 条时先按 MTH-015 归档），并按
   [MTH-017](../methodology/17-expansion-and-cli-contract.md) §2 做影响传播（MTH/PIT/GRD/CASE 交叉链接）。
   > "一条命令跑所有 CI 门"即 TOOL-013 `preflight`；CI 调 `index --check` + **完整** `preflight`（不要用 `--no-index`，会因 SKIPPED 退 3）。

## 12. 与 AGENTS / MTH / PIT / GRD / CASE 的接口约定

| 接口 | 约定 |
|---|---|
| [AGENTS.md](../AGENTS.md) | 工具是唯一机器索引/校验入口；`index` 生成根摘要 + 四层分片（生成物不手改）；DoD 命令必须全绿 |
| [MTH-000](../methodology/README.md) / [MTH-002](../methodology/01-assessment.md) | profile/assessment 字段与门禁 ID（G-A/G-B0/G-B1/G-B2/G-C/G-D）以本工具 schema 为准；文档不得另造字段 |
| [MTH-017](../methodology/17-expansion-and-cli-contract.md) | 改契约的传播流程：工具 + schema + 模板 + 测试 + 文档 + manifest 同步；统一 CLI 契约 |
| [MTH-018](../methodology/18-assessment-execution.md) | 评估执行清单（detect/probe/assess/plan）与失败处理；字段/门禁口径回指 MTH-002 |
| [MTH-011](../methodology/10-document-lifecycle.md) | 文档归属、命名、索引、ADR 与变更联动规则 |
| [MTH-015](../methodology/15-archive-and-context-budget.md) | 文档窗口/归档/上下文预算/机检上限规则；doc-policy.json 是它的机器可执行投影 |
| [pitfalls/README.md](../pitfalls/README.md) | manifest 条目必须带 `severity`/`domain`，供 Agent 过滤；PIT 复现优先用工具只读命令 |
| [guardrails/README.md](../guardrails/README.md) | 工具不得通过写设备/提权"绕过"红线；验证命令只读 |
| [cases/README.md](../cases/README.md) | 案例 profile 用 `repurpose.device-profile.v1`，经 assess 验证；敏感值脱敏 |
| `agent-manifest.json` / `backlog.json` | manifest 由 `index` 重建（`index --check` 只读比对）；backlog 由维护者/Lead 维护，`validate` 按 [backlog.schema.json](schema/backlog.schema.json) 机检结构/语义 |

## 13. 安全与隐私

- `detect` 默认 `serial_redacted=true`（`identity.serial=null`）；`--include-serial` 仅本地调试，
  产物必须写 gitignored 的 `profiles/`，禁止入库/进文档/进聊天；
- 输出只含结构化字段与命令名（`adb shell getprop` 等），不打印原始设备输出、不打印 token/IP；
- 所有设备命令**只读**（`getprop`/`cat`/`ls`/`df`/`dumpsys`/`wm`/`pm list`/`unshare` 临时实验/
  `test -r/-w`）；无任何写入/重启/安装/卸载操作；
- `rootcheck`/`rescue-kit` 均为离线检查：`rootcheck` 不连接/不写设备；`rescue-kit` 只读写本地目录、清单仅存相对 POSIX 路径与 SHA-256；两者输出不含序列号/绝对路径/凭据；
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
- `rootcheck` 只消费 profile 已采集字段：`unknown` 按未通过处理；ARB 检查仅为 `.500/.501/.503` 启发式（以厂商公告为准）；`manual_checks` 不会自动判定完成；真机姿态仍需按 [MTH-012](../methodology/11-root-lab.md) 实测补证。
- `rescue-kit --verify` 只证明"目录与清单一致"，不证明镜像版本匹配/可救援；已有清单默认拒绝覆盖（`--force` 前必须核对来源与版本，否则只是"洗白"错误状态）；清单外新增文件判失败。
- `index` 默认写仓库根 `agent-manifest.json`（生成物）+ `agent-manifest.d/` 四层分片；在只读环境用
  `--out` 重定向根摘要（分片仍写默认目录，便于 CI 对比）。
- `--out` 指向其他仓库根之外时仍按默认 shards 相对路径生成；跨仓库对比请用独立临时目录。
- **单层 >40 条时的拆分策略尚未实现**：当前四层均 ≤40，超限时 index 记 error、validate 报 `SHARD_ENTRIES`；
  若未来某层持续增长，需扩展为 `{layer}-{n}.json` 多分片并同步根 `shards` 映射（schema/契约变更）。
- **旧格式迁移**：旧根 manifest 含完整 `content` 数组；重跑 `index` 即自动迁移为根摘要+分片，
  validate 会对未迁移的旧格式报 `MANIFEST_LEGACY_CONTENT`（warning；`--strict` 下失败）。
- **索引一致性不依赖 mtime**：`validate` 默认不按文件 mtime 判 manifest 过期（CI/新 clone 会假失败）；
  一致性由 `MANIFEST_COUNTS`/`SHARD_CONTENT` 与 `index --check` 保证；本地排查才加 `--mtime-check`。
- **preflight 三态退出码**：0 全绿 / 3 存在 SKIPPED（`--skip-*`/`--no-index`/check-links 脚本缺失）/ 4 任一步 FAILED。
  CI 请用**完整** `preflight`（exit 0）+ `index --check`；若本地用 `--no-index` 裁剪，需显式接受退出码 3。
- **doc-policy 违规只报告不自动改**：`AGENTS.md`/`README.md`/`CHANGELOG.md`/新层文档由 Lead/维护者负责；
  validate 仅列出具体错误（例如窗口超 8 条），由对应负责人修复后重跑。
