# 变更记录（CHANGELOG）

> 本文件是**当前迭代对外可感知变更摘要**，不是工作日志。当前窗口最多 **8 条**；更早条目按月归档到 `changelog/YYYY-MM.md`（**归档默认不读**，只在追溯时读单个文件）。
> 记录边界、归档与 Agent 上下文预算规则见 [MTH-011](methodology/10-document-lifecycle.md)；归档索引见 §4。

| 项目 | 内容 |
|---|---|
| 文档 ID | HB-CHANGELOG-001 |
| 版本 | v2.0（2026-11-11 归档规范化） |
| 状态 | 现行 |
| 关联 | [MTH-011](methodology/10-document-lifecycle.md) · [changelog/README.md](changelog/README.md) · [当前状态](docs/00-overview/当前状态.md) · [README](README.md) · [AGENTS](AGENTS.md) |

## 1. 记录边界

| 内容 | 唯一位置 |
|---|---|
| 当前方法/规范/边界 | `methodology/`（MTH-001..014） |
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
| 2026-11-13 | v1.55 | **对齐 Agent-Harness v1.3（定向采纳）**：AGENTS 协议 v1.2（容量分级/哨兵/机器可读摘要/停止条件 7 条）、新增 [ADR 决策层](adr/README.md)（ADR-0001/0002 与 [GRD-016](guardrails/GRD-016-agent-protocol-regression.md) 回归红线）、[MTH-013 交付治理](methodology/12-delivery-governance.md)、[MTH-014 Agent SOP](methodology/13-agent-sop.md)、模板扩充与 backlog schema；toolkit 新增 `preflight`、`index --check` 与协议/命名/PIT/ADR/backlog/归档回归机检（validate --strict 覆盖）；同步 README/backlog/manifest/CI workflow；验证：preflight 全绿（index 重建无 warnings（内容未变时*不重写*、保留原 generated_at）、validate --strict 0 error/0 warning、282 项单测 OK、check-links 0 missing）、index --check 一致、CI 首跑 success（GitHub Actions run #43465049307）；未完成：真实割接 Go/No-Go 演练（BL-027）与 secret scan（BL-010）。 |
| 2026-11-11 | v1.54 | **Root 工具配套**：新增 `rootcheck` 子命令（`repurpose.rootcheck.v1`：9 项技术检查+7 项人工确认，`--strict` 非 tech-ready 退 4）与 `rescue-kit`（救援包相对路径+SHA-256 清单 `--init/--verify`，不一致退 4）；均离线、不连接设备；新增 ready/预研/边界 fixture 与测试，更新 [toolkit/README.md](toolkit/README.md)、[MTH-012](methodology/11-root-lab.md)、[MTH-008](methodology/07-validation.md)；[BL-021](backlog.json) 完成（验证：198 项单测、validate --strict、check-links、index 全绿） |
| 2026-11-11 | v1.53 | **Root 实验轨预研与规范**：用户确认下一部一加 Ace Pro 作为可解锁/Root 平台（接受清数据/失保/硬砖风险，生产 haydn 保持无 Root）；新增 [MTH-012 Root 实验设备方法论](methodology/11-root-lab.md)（采购准入、G-L0..G-L6、KernelSU LKM/APatch 选型、特权能力目录、OTA/ARB、救援、验收、割接）、[GRD-015 受控操作边界](guardrails/GRD-015-root-lab-controlled.md)、[PIT-022](pitfalls/PIT-022-oem-unlock-quota.md)/[PIT-023](pitfalls/PIT-023-oneplus-arb-hard-brick.md)/[PIT-024](pitfalls/PIT-024-flash-tool-supply-chain.md)/[PIT-025](pitfalls/PIT-025-root-module-regression.md)、[CASE-003/004 预研案例](cases/ace-pro-pgp110/README.md)（**draft/未实测**）；同步 AGENTS 红线例外、MTH-002/003/004/007/008/009/010、README 索引、toolkit manifest invariants 文案（验证：validate --strict 0 error、check-links 0 missing、164 项单测通过、index 无 warnings） |
| 2026-11-11 | v1.52 | **网络方案改为动态地址/多 Wi-Fi**：删除"必须固定 IP/DHCP 租约"假设，改为动态地址 + 发现兜底（页面/扫码/mDNS/广播发现，受控隧道需授权）；新增 [PIT-021](pitfalls/PIT-021-dhcp-lease-assumption.md)、[GRD-007](guardrails/GRD-007-network-least-exposure.md) R7；[MTH-002](methodology/01-assessment.md) §5.3.1 / [MTH-004](methodology/03-server-stack.md) §4.1 / [MTH-008](methodology/07-validation.md) F13 补网络决策与验收；toolkit 网络建模列入 [BL-019](backlog.json)（验证：validate --strict、check-links、163 项单测） |
| 2026-11-11 | v1.51 | **文档归档与 Agent 上下文预算治理**：CHANGELOG 改为当前窗口 ≤8 条 + 按月归档到 `changelog/`（默认不读、只读）；新增 [MTH-011 文档生命周期与上下文预算](methodology/10-document-lifecycle.md)、[changelog/README.md](changelog/README.md)；AGENTS/README 增加阅读预算、分层加载与停止条件；`agent-manifest.json` 拆为根摘要 + `agent-manifest.d/` 按层分片；toolkit `validate` 依据 [doc-policy](toolkit/schema/doc-policy.json) 检查体积/窗口上限（验证：163 项单测、validate --strict 0 error、check-links 0 missing） |
| 2026-11-11 | v1.50 | **Agent 可读性独立审计修复**：权威优先级调整为 用户 > AGENTS > 红线 > 方法论 > PIT > toolkit > 案例；新增 [toolkit/README.md](toolkit/README.md) TOOL-001..010 工具登记表（新增工具先登记）；backlog 增加 requires/owner/updated/result 与 BL-015 机器校验项；统一 front matter 表述（头部而非首尾）、depends 可选、PIT/GRD 额外必需键（strict 校验）；修正 README fixture 示例、案例"部分验收"口径、`scripts/dev/check-links.py` 冻结例外；模板增加"示例 ID 不占号/正式 H2 无编号"警告（验证：validate --strict、check-links、单测全绿） |
| 2026-11-11 | v1.49 | **仓库升级为「安卓手机改造通用方法论」v2.0**：新增 `methodology/`（MTH-001..010）、`pitfalls/`（PIT-001..020）、`guardrails/`（GRD-001..014）、`toolkit/`（零依赖 Python CLI + schema/模板/Termux 脚本/单元测试）、`cases/haydn-k40pro/`（案例 `profile.json` + OEM profile）、根 [AGENTS.md](AGENTS.md)（Agent 工作协议）、[backlog.json](backlog.json)（机器可读待办）、`agent-manifest.json`（生成式内容索引）；旧 `docs/scripts/android-bridge` 保留为案例冻结证据；[scripts/dev/check-links.py](scripts/dev/check-links.py) 扫描范围扩展至新层；`.gitignore` 增加 `/profiles/` 与全局密钥兜底 |
| 2026-11-11 | v1.48 | **仓库与文档结构重构**：仓库更名为 `haydn-server`（原目录名含中文导致 aapt2 构建失败）→ `docs` 按主题分组（`00-overview`/`10-device`/`20-server`/`30-dsh`/`40-console`/`50-bridge`/`90-archive`/`assets`）→ `scripts` 按运行侧分组（`adb`/`termux`/`server`/`dev`）→ `android-bridge/build.ps1` 去 ASCII junction（自动探测 JDK/SDK、非 ASCII 路径直接报错）→ 新增 [当前状态](docs/00-overview/当前状态.md) 与变更记录（本文件）、README/docs 索引重写、旧编号/范围引用与坏链接修复；重构评审与遗留见 [29 §8](docs/00-overview/29-项目文档评审报告.md) |

## 4. 归档索引

| 月份 | 条目 | 文件 |
|---|---|---|
| 2026-11 | 48 条（v1.0–v1.47，记录日期 2026-11-10/11） | [changelog/2026-11.md](changelog/2026-11.md) |
