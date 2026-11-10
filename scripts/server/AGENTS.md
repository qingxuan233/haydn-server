# Server Operations Policy (for DSH agents)

本机是手机上的 Linux 服务器；DSH 是外部管理入口。为避免误操作：

1. **状态/日志/健康检查**（Tier1，只读）：优先使用 `/root/server/bin/server-ops`：
   - `server-ops status`
   - `server-ops health`
   - `server-ops logs dsh --lines 200`
   - `server-ops backups`
   - `server-ops backup-verify`
2. **受控写操作（Tier2）**：必须使用 `server-ops` 且带 `--confirm`，并**先向人工说明计划、获得同意**：
   - `restart <service> --confirm` / `start|stop <service> --confirm`
   - `nginx test --confirm` / `nginx reload --confirm`
   - `backup --confirm` / `rotate --confirm`
   - 允许服务：api fileui frpc gitea nginx runner sshd syncthing webdav dsh dsh-login dsh-guard
   - 写操作会自动生成 `/root/server/config-snapshots/` 快照并写审计；失败时从快照回滚。
3. **Tier3 禁止**（restore/升级/删除数据/改系统）：只能人工 SSH + 双重确认；不得通过 DSH 执行。
4. **禁止**：操作 Android 宿主（不得 `am kill-all`、卸载系统包、改 Android 设置）；执行 `rm -rf`、格式化、删除备份；把 Basic 密码/DSH token/备份口令等输出到聊天或日志；修改 `/root/server` 以外的系统配置。
5. 任何操作前先看 `server-ops status`；变更后必须验证（health/logs）；高风险操作先备份。
