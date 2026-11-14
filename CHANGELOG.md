# 变更记录（CHANGELOG）

> 本文件是**当前迭代对外可感知变更摘要**，不是工作日志。当前窗口最多 **8 条**；更早条目按月归档到 `changelog/YYYY-MM.md`（**归档默认不读**，只在追溯时读单个文件）。
> 记录边界见 [MTH-011](methodology/10-document-lifecycle.md)，归档窗口与上下文预算规则见 [MTH-015](methodology/15-archive-and-context-budget.md)；归档索引见 §4。

| 项目 | 内容 |
|---|---|
| 文档 ID | HB-CHANGELOG-001 |
| 版本 | v2.0（2026-11-11 归档规范化） |
| 状态 | 现行 |
| 关联 | [MTH-011](methodology/10-document-lifecycle.md) · [MTH-015](methodology/15-archive-and-context-budget.md) · [changelog/README.md](changelog/README.md) · [当前状态](docs/00-overview/当前状态.md) · [README](README.md) · [AGENTS](AGENTS.md) |

## 1. 记录边界

| 内容 | 唯一位置 |
|---|---|
| 当前方法/规范/边界 | `methodology/`（MTH-001..018） |
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
| 2026-11-14 | v1.70 | **CASE-003 结构拆分 + PIT-026 + curl RST 结案 + 设备权限收敛**：①[CASE-003](cases/ace-pro-pgp110/README.md) §6.1–§6.7 明细**原样下沉**为附录 [APP-003 execution-log.md](cases/ace-pro-pgp110/execution-log.md)（用户授权，事实/结论/未验证项未改写），README 274→173 行（余量 107，`DOC_LINES_MARGIN` 消除），§9 与状态行指针同步；②新增 [PIT-026](pitfalls/PIT-026-tailscale-state-dump.md)（S1/ops）：诊断 tailscale 身份时 `strings tailscaled.state` 使节点私钥与 network-lock 密钥进入终端输出——写明正确途径（`status --json`/`debug prefs`/`whois`）、禁止读状态文件、打码要求、已 dump 即轮换节点 key 与 `grep 'privkey:\|tskey-'` 自查命令，并登记 [pitfalls/README](pitfalls/README.md) §5；③[frp-public-mapping](2026-11-14/frp-public-mapping/outputs/frp-public-mapping.md) §11.4 把「curl RST 待核对」改为**已定位（外部环境限制）**并附证据（同四元组 RST 后仍有 ACK 518、RST 的 TTL/IP-ID 与真实服务器不符、RST 早于本地 stunnel、Chrome 通 vs curl 失败、长度非判据）；④设备侧 `rootfs/etc/supervisor/conf.d/haydn.conf` 权限 666→644（仅 chmod，内容/服务未动）；验证：`index` 无 warnings、preflight 结果见下；v1.62 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条）；未完成：B 能否启动仍未知、禁止 dump `tailscaled.state` 纪律待观察执行。 |
| 2026-11-14 | v1.69 | **CASE-003 B 槽 liblp 元数据被覆盖与恢复**：定位到 B 槽不可启动根因——§6.6 的 fastbootd 逻辑分区写按 `Metadata slot count: 3` 把 A 表复制进 metadata slot 1（pre-align 为完整 B 表 7020 B/17 个 `_b` + 2 个 `_b-cow`，写后为 A 表副本 7096 B 且与 slot 0 完全相同；super 前 2 MB 与末 512 KB 无 `system_b`/`vendor_b`，B 物理分区哈希仍等于 payload）；用户授权下先整段备份 metadata 区（`super-head-512k.bin` sha256 `ae91a2d7…`）并做写入-还原演练，自建 liblp 序列化器 A 表 round-trip 7096 B 逐字节一致后重建 B 表 7020 B，raw dd 写 slot1 primary `0x13000`/backup `0x43000`；双回读：slot0 与 `lpdump --slot 0` 摘要不变、slot1 恢复 B 表且与 pre-align 逐行仅差 `Current slot`；登记硬约束（单槽模式、禁止 `--set-active=b`、A 槽再跑 fastbootd 会重复覆盖 slot 1、下次 OTA 前评估非激活槽影响）；同步 [CASE-003](cases/ace-pro-pgp110/README.md) §6.7/§9 与 [BL-022](backlog.json)/[BL-032](backlog.json)；v1.61 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条）；验证：`lpdump` 双回读与备份切片哈希、`index` 重建无 warnings、preflight exit=0（validate errors=0/warnings=0，仅 CASE-003 README 274/280 触发 `DOC_LINES_MARGIN` advisory）；未完成：**B 能否启动未知**（数据区被 A extents 覆盖 99.3%，用户决定不做启动验证、维持单槽）、CASE-003 README 余量 6 行待拆附录。 |
| 2026-11-14 | v1.68 | **CASE-003 A 槽整套对齐与 A 槽首次可启动**：仅动 A 槽（`boot_a` 未刷保 KSU 补丁，B 槽/`vbmeta_b`/userdata 未写）——官方全量包 metadata 与设备逐项一致（payload 无 `super` 镜像，20 个分区零依赖提取且整镜像哈希全部通过）；预检 super 空闲仅 1.0 MiB → fastbootd 删 `system_a-cow`（678.2 MiB）后 15 个逻辑分区 resize+flash 全部 OKAY，`partition-size` 回读 15/15 一致、`snapshot-update-status` none；5 个物理分区（vendor_boot/dtbo/vbmeta×3）快照后刷写全部 OKAY；A 槽启动成功（slot `_a`、内核 5.10.236…、ksud 3.3.1、su uid=0、8/8 服务 RUNNING、四端口 loopback、HTTP 200、INPUT DROP、`boot_a`=`boot_b`=`2cdcc6f5…a047`），resize 后 super 空闲 607.66 MiB；soak run #3 以 2026-11-14T09:43:00Z 为新起点；同步 [CASE-003](cases/ace-pro-pgp110/README.md) §6.6/§9 与 [BL-022](backlog.json)；v1.60 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条）；验证：`lpdump` 账本自洽、15/15 尺寸回读、启动全项核对；未完成：`my_preload_a`/`my_company_a` 未对齐、引导链/基带未刷（与 B 是否一致未知）、B 槽未回确实测、`rollback-index` 未知、24h 满期 soak。 |
| 2026-11-14 | v1.67 | **CASE-003 备份轮询修复与包基线**：`backup-loop` 判活改为 `pidfile=pid+boot_id` 且校验 `/proc/<pid>/cmdline`（修复重启后 PID 复用导致轮询静默退出），`service.sh` 仅在进程存活时记 `backup loop started`、失败记 `FAILED`、`done` 移至末尾；清陈旧 pidfile 后重启（pid 20257）、二次启动去重通过；手动全链路备份跑通（快照→加密→解密自检→上传→DONE，KEEP=7 未触发轮转）；`oplus.ota.autoinstall.time` 恢复 3:41；包基线 387 个（system 373/third-party 14/disabled 13）落 `inventory/package-baseline-20261114.txt`（gitignored）；同步 [CASE-003](cases/ace-pro-pgp110/README.md) §6.5/§9 与 [BL-022](backlog.json)；验证：preflight 全绿；v1.59 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条）；未完成：03:30 自动触发待观察、24h 满期 soak、slot A 不可启动、rollback-index 未知。 |
| 2026-11-14 | v1.66 | **CASE-003 恢复链演练与 SOTA 回写**：soak run #2 按用户决定提前中止（6.88h/83 采样/0 断档/可用率 100%，明确非满期通过，数据留设备复查）；`boot_b` 回刷演练完成（fastboot 37.0.3、三方 SHA-256 一致、bootloader 只读查询 current-slot=b 与 slot-unbootable:a=yes/b=no、`fastboot flash boot_b` 成功、重启后 boot_completed=1 且哈希不变；`rollback-index` 变量不支持仍待验证）；重启后逐项验证通过（KernelSU/模块/6 服务/HTTP 200/tailscale/遥测/Wi‑Fi 守护/backup-loop；输入法实敲上屏且 appops+iptables uid 规则实测生效，此前为推断）；SOTA（C20P01(BRB1CN01)，14 APK/649,471,952 B）安装成功并自动重启一次，14/14 versionCode 一致、已删应用未回归；slot A 仍不可启动（未修）；同步 [CASE-003](cases/ace-pro-pgp110/README.md) §6.4/§9 与 [BL-022](backlog.json)；验证：preflight 全绿；v1.58 归档至 [changelog/2026-11.md](changelog/2026-11.md)（窗口 8 条）；未完成：24h 满期 soak、chroot 基准、服务迁移、割接。 |
| 2026-11-14 | v1.65 | **机检补齐（BL-015 + updated 新鲜度）**：`validate` 新增 TOOL 登记表一致性（`toolkit/README` §3.1 ↔ `cli.build_parser()` 子命令 ↔ 根 manifest `tools`/`commands`；`TOOL_REGISTRY`/`TOOL_COMMAND`/`TOOL_MANIFEST`，strict 下 error）与 front matter `updated` 新鲜度（git `%cs` 比对最近提交日；`DOC_UPDATED_STALE` advisory，只覆盖 methodology/pitfalls/guardrails，无 `.git`/未跟踪/浅克隆/git 不可用时静默跳过）；新增 9 项单测（一致/漏登记/多登记/断号/manifest 漂移/缺 README 跳过/新鲜/滞后/未跟踪），并把 14 篇活跃层文档 `updated` 同步为 2026-11-14；同步 [toolkit/README](toolkit/README.md)、[tests/README](toolkit/tests/README.md)、[MTH-011](methodology/10-document-lifecycle.md) §2.3、[MTH-015](methodology/15-archive-and-context-budget.md) §5、`backlog-archive` BL-015 result；v1.57 归档至 `changelog/2026-11.md`（窗口 8 条）；验证：preflight 全绿（validate --strict 0/0/0、全部单测、check-links、index 一致）；未完成：无。 |
| 2026-11-14 | v1.64 | **manifest 分片自动拆分（BL-017）**：`index` 单层 >40 条时按层内既有顺序每 40 条一片，拆为 `<layer>-p01.json`…（≤40 条仍用 `<layer>.json`，非末片满片、末片 1..40 条），根 `shards` 改为 `{count, parts[]}`；`validate` 新增 `SHARD_SPLIT`/`SHARD_NAMING` 校验片数、命名、非末片满片与各片合计；新增 40 不拆/41 拆、拆分完整性、单文件↔多片切换清理测试（297 项）；同步 [toolkit/README](toolkit/README.md)、[根 schema](toolkit/schema/agent-manifest.schema.json)、[分片 schema](toolkit/schema/manifest-shard.schema.json)、[MTH-015](methodology/15-archive-and-context-budget.md)；验证：preflight 全绿（validate 0/0/0、297 单测、check-links、index 一致）；未完成：无。 |
| 2026-11-14 | v1.63 | **附录编号归位（误用编号回收）**：`cases/ace-pro-pgp110/p1-config.md` 与 `cases/haydn-k40pro/reuse-guide.md` 改为普通附录（`APP-001`/`APP-002`，文件位置与内容不变），不再占用 CASE 编号、不进入案例登记表，当前最大案例编号回到 CASE-004、005/006 可复用；新增 `APP` 前缀并记入 [AGENTS](AGENTS.md) §4.1 与 [MTH-009](methodology/08-agent-handoff.md) §4.2（协议 v1.3→v1.4，MINOR），同步两篇案例 README 指针、[cases/README](cases/README.md)、[backlog](backlog.json) BL-036 记录与 manifest；验证：validate --strict 0 error/0 warning/0 advisory、preflight 全绿；v1.55 归档至 `changelog/2026-11.md`（窗口 8 条）；未完成：无。 |

## 4. 归档索引

| 月份 | 条目 | 文件 |
|---|---|---|
| 2026-11 | 63 条（v1.0–v1.62） | [changelog/2026-11.md](changelog/2026-11.md) |
