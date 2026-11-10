# Server Operations Policy (for DSH agents)

本机是手机上的 Linux 服务器；DSH 是外部管理入口。为避免误操作：

1. **状态/日志/健康检查**：优先使用 `/root/server/bin/server-ops`：
   - `server-ops status`
   - `server-ops health`
   - `server-ops logs dsh --lines 200`
   - `server-ops backups`
2. **变更操作**（重启服务、改 nginx、备份、升级）：先说明计划并征得人工确认；不要擅自执行破坏性命令。
3. **禁止**：
   - 不操作 Android 宿主（不得 `am kill-all`、卸载系统包、改 Android 设置）；
   - 不执行 `rm -rf`、格式化、删除备份、restore/升级等 Tier3 操作；
   - 不把 Basic 密码、DSH token、备份口令等敏感信息输出到聊天/日志；
   - 不修改 `/root/server` 以外的系统配置。
4. 任何操作前先看 `server-ops status`；变更后必须验证（健康检查/日志）。
5. 危险操作只允许人工通过 SSH 执行，并要求双重确认。
