# Server Operations Policy (for DSH agents)

本目录是**服务器（proot Ubuntu）侧**运维脚本与配置的仓库源副本（部署到 `/root/server/...`、`/etc/nginx/...` 后生效）。本机是手机上的 Linux 服务器，DSH 是外部管理入口。为避免误操作：

## 1. Tier1 只读（优先、免确认）

优先使用 `/root/server/bin/server-ops`：

- `server-ops status`
- `server-ops health`
- `server-ops logs dsh --lines 200`
- `server-ops backups`
- `server-ops backup-verify`
- `server-ops bridge status`（只读：Bridge 来源/版本/新鲜度）
- `server-ops audit [lines]`

## 2. Tier2 受控写（必须 `--confirm` + 快照 + 审计）

必须使用 `server-ops` 且带 `--confirm`，并**先向人工说明计划、获得同意**：

- `restart <service> --confirm` / `start|stop <service> --confirm`
- `nginx test --confirm` / `nginx reload --confirm`
- `backup --confirm` / `rotate --confirm`
- 允许服务：`api fileui frpc gitea nginx runner sshd syncthing webdav dsh dsh-login dsh-guard`

写操作会自动生成 `/root/server/config-snapshots/` 快照并写审计 `/root/server/logs/ops-audit.jsonl`；失败时从快照回滚。

## 3. Tier3 人工（禁止通过 DSH 执行）

Tier3 = restore / 升级 / 删除数据 / 改系统配置。只能由**人工 SSH + 双重确认**执行，DSH 不得越权代办。

## 4. Bridge 边界（重要）

- DSH **不得持有 Bridge token 或证书私钥**，**不得直连** Bridge（`127.0.0.1:3099` 属于服务器内部凭据面）。
- 手机状态只能通过 Server API 只读获取：`/api/sysinfo`（含 `bridge_*` 合并字段）+ `server-ops bridge status`。
- DSH **不能启动/停止 Android App**（proot 内无 ADB）；不要尝试、也不要建议用 ADB/`run-as` 拉起 Bridge。Bridge 不可用时，提示人工检查手机端自启/权限，而不是代操作。
- Bridge 故障的降级路径是 Server 回退 Termux 采集并在 `bridge_source` 标注，不需要（也不允许）DSH 介入。

## 5. 其他禁止项

- 操作 Android 宿主：`am kill-all`、卸载系统包、改 Android 设置；
- `rm -rf`、格式化、删除备份；
- 把 Basic 密码 / DSH token / 备份口令 / Bridge token 等敏感值输出到聊天或日志；
- 修改 `/root/server` 以外的系统配置。

## 6. 操作纪律

任何操作前先看 `server-ops status`；变更后必须验证（health/logs）；高风险操作先备份。

## 文档入口

- 当前状态（唯一权威状态源）：[当前状态](../../docs/00-overview/当前状态.md)
- 新会话接手指南（读序/护栏/验收）：[30 接手指南](../../docs/00-overview/30-新会话接手指南.md)
- DSH 控制平面与受控写：[21 落地手册](../../docs/30-dsh/21-DSH控制平面落地手册.md) · [22 Tier2 受控写](../../docs/30-dsh/22-DSH-Tier2受控写落地.md)
- 全部脚本索引：[scripts/README.md](../README.md)
