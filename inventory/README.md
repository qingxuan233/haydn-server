# inventory 采集快照

本目录保存**设备/服务器采集产物**（时间戳快照 + `latest` 指针副本）。除本说明文件外，目录内容被 `.gitignore` 的 `/inventory/*` 忽略、**不入库**（`.gitignore` 已用 `!/inventory/README.md` 让本 README 例外入库）。

> 用途：给文档（设备档案、优化方案、风险复盘）提供**可追溯的实测证据**，避免"文档里的数字没有出处"。当前状态数字只维护在 [当前状态](../docs/00-overview/当前状态.md)，本目录是证据，不是状态源。

| 文档 ID | `HB-DATA-001` |
|---|---|
| 版本 | v1.0（2026-11-11 新建） |
| 状态 | 现行 |
| 关联 | [scripts 索引](../scripts/README.md) · [当前状态](../docs/00-overview/当前状态.md) · [tools 说明](../tools/README.md) |

## 1. 命名规则

- 时间戳：`YYYYMMDD-HHMMSS`（本地时间 Asia/Shanghai），例：`device-info-20261110-101046.json`。
- 命名：`<类型>-<时间戳>.<扩展名>`；同类型多次采集会得到多个历史快照。
- **latest 指针**：多数采集脚本在写时间戳快照的同时，覆盖写一份 `<类型>-latest.<扩展名>`，供文档引用"最新一份"。**只有部分类型有 latest**（见 §2 表）。
- 一次采集可能成对产出 `.json`（结构化/可回滚）与 `.md`/`.txt`（可读/原始输出），互为补充。
- 档位型类型带档位名：`debloat-safe-*`、`debloat-aggressive-*`（由 `-Tier` 决定）。

**规则：`latest` 由脚本覆盖写，时间戳快照只读。** 不要手工创建/改名/移动/编辑任何快照文件。

## 2. 快照类型与用途

| 类型（`<前缀>-<时间戳>.<ext>`） | 扩展名 | 生成脚本 | 用途 | 有 latest |
|---|---|---|---|---|
| `device-info-*` | `.json` | [collect-device-info.ps1](../scripts/adb/collect-device-info.ps1) | 结构化设备档案：身份/构建/安全/硬件/内存/存储/电池/网络/包数/温度；含 `transport.serial` 等隐私字段 | ✅ |
| `device-raw-*` | `.txt` | collect-device-info.ps1 | 采集时的原始命令输出（getprop/dumpsys 等），用于追溯字段来源 | ✅ |
| `packages-*` | `.txt` | collect-device-info.ps1 | 当前用户包清单（包名/版本/路径），用于 debloat 前后对比与 UAD 比对 | ❌ |
| `capability-probe-*` | `.txt` | [probe-device.ps1](../scripts/adb/probe-device.ps1) | 内核能力探测：namespace/cgroup/overlayfs/seccomp/netfilter、充电控制节点、zram、温控、boot 分区；结论落在 [02 可行性分析](../docs/10-device/02-可行性分析.md) | ✅ |
| `deep-probe-*` | `.md` | [adb-deep-probe.ps1](../scripts/adb/adb-deep-probe.ps1) | 安卓/小米深度只读探查报告（能力矩阵与限制证据） | ❌ |
| `apply-a-plus-*` | `.json` + `.md` | [apply-a-plus.ps1](../scripts/adb/apply-a-plus.ps1) | A+ 优化变更日志：原值/新值/恢复命令；`apply-a-plus-latest.json` 是 `-Restore` 的回滚依据 | ✅ |
| `debloat-safe-*`、`debloat-aggressive-*` | `.json` + `.md` | `debloat-server-mode.ps1`（**历史脚本，aggressive 已废弃**） | 清理计划/结果/回滚记录；事故后禁止再用 aggressive 路线 | ✅（`debloat-latest.json`） |
| `optimize-profile-*` | `.json` | [optimize-server-profile.ps1](../scripts/adb/optimize-server-profile.ps1) | 重置后安全优化批次日志（保护名单、disable/uninstall 清单、回滚命令） | ✅ |
| `phone-health-*` | `.md` | [phone-health.ps1](../scripts/adb/phone-health.ps1) | 手机服务器健康检查报告：温度/负载/内存/磁盘/服务状态 | ✅ |
| `uad-compare-*` | `.md` | [uad-compare.py](../scripts/adb/uad-compare.py) | UAD-NG 清单与已装包的**只读**比对（不卸载/不禁用） | ❌ |
| `env-verify-*` | `.md` | [verify-research-env.ps1](../scripts/adb/verify-research-env.ps1) | 研究平台环境验证（ADB + SSH 只读） | ❌ |
| `final-cleanup-*` | `.json` | （历史一次性收尾操作） | 清理收尾记录，历史证据 | ❌ |
| `packages-full-*` | `.txt` | （历史一次性全量采集） | 早期全量包清单，历史对照 | ❌ |

## 3. 隐私与安全（重要）

- 快照含**设备序列号**（`transport.serial`）、fingerprint、WiFi IP/BSSID、已装应用清单、账号/服务相关路径等隐私信息。
- 目录整体 gitignored：**不要提交、不要公开上传、不要整包外发**；截图/引用时先裁剪或打码。
- 需要分享时用 `*-latest` 摘要或裁剪后的副本，不要给整目录。
- 这里不放 token/密码/私钥；如果发现误写入，删除该快照并重新采集（不要提交修复）。

## 4. 重新生成 / 更新快照

| 想要的东西 | 跑的脚本 | 备注 |
|---|---|---|
| 设备档案（device-info / device-raw / packages） | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\adb\collect-device-info.ps1` | 需 ADB 连接；**最常用** |
| 内核能力探测（capability-probe） | `... -File scripts\adb\probe-device.ps1` | 需要 ADB |
| 健康检查（phone-health） | `... -File scripts\adb\phone-health.ps1` | 需要 ADB + SSH |
| A+ 优化变更（apply-a-plus） | `... -File scripts\adb\apply-a-plus.ps1 -Apply` | 先 DryRun 确认 |
| 安全优化（optimize-profile） | `... -File scripts\adb\optimize-server-profile.ps1 -Apply` | 分批执行，每批重启验证 |
| UAD 比对（uad-compare） | `python scripts\adb\uad-compare.py` | 只读 |

全部脚本与参数见 [scripts/README.md](../scripts/README.md)。

## 5. 不要手改历史

- 本目录是**证据链**：历史快照只读，**不改、不删、不重命名**。
- 采集错了/设备变了 → **重新跑脚本生成新时间戳快照**，不要修正旧文件。
- `*-latest.*` 由脚本覆盖写，不要手工编辑（否则会破坏 `-Restore` 依据）。
- 需要在文档里"修订结论" → 改文档 + 附新快照时间戳，而不是改旧快照。
- `backup/` 是个人加密备份目录，**不归本目录管理，不要修改**。
