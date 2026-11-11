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
| 当前方法/规范/边界 | `methodology/`（MTH-001..011） |
| 红线与必须检查项 | `guardrails/`（GRD-001..014） |
| 踩坑证据与修复 | `pitfalls/`（PIT-001..020） |
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
| 2026-11-11 | v1.51 | **文档归档与 Agent 上下文预算治理**：CHANGELOG 改为当前窗口 ≤8 条 + 按月归档到 `changelog/`（默认不读、只读）；新增 [MTH-011 文档生命周期与上下文预算](methodology/10-document-lifecycle.md)、[changelog/README.md](changelog/README.md)；AGENTS/README 增加阅读预算、分层加载与停止条件；`agent-manifest.json` 拆为根摘要 + `agent-manifest.d/` 按层分片；toolkit `validate` 依据 [doc-policy](toolkit/schema/doc-policy.json) 检查体积/窗口上限 |
| 2026-11-11 | v1.50 | **Agent 可读性独立审计修复**：权威优先级调整为 用户 > AGENTS > 红线 > 方法论 > PIT > toolkit > 案例；新增 [toolkit/README.md](toolkit/README.md) TOOL-001..010 工具登记表（新增工具先登记）；backlog 增加 requires/owner/updated/result 与 BL-015 机器校验项；统一 front matter 表述（头部而非首尾）、depends 可选、PIT/GRD 额外必需键（strict 校验）；修正 README fixture 示例、案例"部分验收"口径、`scripts/dev/check-links.py` 冻结例外；模板增加"示例 ID 不占号/正式 H2 无编号"警告 |
| 2026-11-11 | v1.49 | **仓库升级为「安卓手机改造通用方法论」v2.0**：新增 `methodology/`（MTH-001..010）、`pitfalls/`（PIT-001..020）、`guardrails/`（GRD-001..014）、`toolkit/`（零依赖 Python CLI + schema/模板/Termux 脚本/单元测试）、`cases/haydn-k40pro/`（案例 `profile.json` + OEM profile）、根 [AGENTS.md](AGENTS.md)（Agent 工作协议）、[backlog.json](backlog.json)（机器可读待办）、`agent-manifest.json`（生成式内容索引）；旧 `docs/scripts/android-bridge` 保留为案例冻结证据；[scripts/dev/check-links.py](scripts/dev/check-links.py) 扫描范围扩展至新层；`.gitignore` 增加 `/profiles/` 与全局密钥兜底 |
| 2026-11-11 | v1.48 | **仓库与文档结构重构**：仓库更名为 `haydn-server`（原目录名含中文导致 aapt2 构建失败）→ `docs` 按主题分组（`00-overview`/`10-device`/`20-server`/`30-dsh`/`40-console`/`50-bridge`/`90-archive`/`assets`）→ `scripts` 按运行侧分组（`adb`/`termux`/`server`/`dev`）→ `android-bridge/build.ps1` 去 ASCII junction（自动探测 JDK/SDK、非 ASCII 路径直接报错）→ 新增 [当前状态](docs/00-overview/当前状态.md) 与变更记录（本文件）、README/docs 索引重写、旧编号/范围引用与坏链接修复；重构评审与遗留见 [29 §8](docs/00-overview/29-项目文档评审报告.md) |
| 2026-11-11 | v1.47 | **release 升级**（`debuggable=false`/token 保留）+ **Phase 2 字段**（屏幕/锁屏/亮度/前台应用/网络累计/uptime）接入 API/UI；记录 MIUI 权限重置（POST_NOTIFICATIONS→ignore、GET_USAGE_STATS→default）；1/1 release 重启通过；**24h soak 未完成** |
| 2026-11-11 | v1.46 | **Console 改版**：总览摘要 + `?view=details` 详情页（服务/检查/审计/账号/备份/入口/运维），导航/回滚/截图；新增 [34 总览详情改版](docs/40-console/34-Console总览详情改版.md) |
| 2026-11-11 | v1.45 | **Bridge MVP 实施完成（debug）**：SDK/构建、APK、MIUI 自启动、服务器 `bridge_client`/API/server-ops、5/5 重启 + 安全/回退验证；新增 [33 MVP 实施记录](docs/50-bridge/33-Android-Bridge-MVP实施记录.md)（历史快照：debug 签名） |
| 2026-11-11 | v1.44 | 用户批准 **D1–D10** 推荐；Bridge Phase 0/1 开工；[28 规范](docs/00-overview/28-全栈整体方案规范.md) v1.2、[31 拍板事项](docs/10-device/31-拍板事项决策分析与Root升级路线.md) 决策状态更新 |

## 4. 归档索引

| 月份 | 条目 | 文件 |
|---|---|---|
| 2026-11 | 44 条（v1.0–v1.43，记录日期 2026-11-10） | [changelog/2026-11.md](changelog/2026-11.md) |
