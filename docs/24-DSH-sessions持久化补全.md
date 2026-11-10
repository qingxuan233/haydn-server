# 24 · DSH sessions 持久化补全

> 日期：2026-11-10 21:12–21:15
> 范围：机器本地；无外部依赖。

## 1. 背景与问题

docs/21 的备份曾排除 `/root/.dsh/sessions`，原因是 proot `link2symlink` 生成的 `.l2s.*` 伪链接让 tar 报
`Cannot stat / Too many levels of symbolic links`。

实测该 sessions 目录：
- 普通文件 **6 个**（session.lock、session.v4.jsonl.zstd、`.l2s...tmp0001.0001` 等）
- 伪符号链接 **2 个**（`.l2s...tmp0001`）
- 总计仅 38K

结论：**只要只收集普通文件，sessions 完全可以备份**。

## 2. 实现

新增 `scripts/server/server-backup-sessions`：
- `find /root/.dsh/sessions -type f -printf '%P\n'` 只列普通文件；
- 用 `tar --verbatim-files-from -T <list>` 打包（sessions 顶层目录名以 `--root-DeepSeek...` 开头，普通 `-T` 会把行首 `--` 当选项误判）；
- 加密 + 解密/tar 自检 + sha256 + 保留 N 份；
- 输出 `sessions-<stamp>.tar.gz.enc`，与 server 备份同一目录。

并把调用追加到 `server-backup` 末尾（每日备份自动包含 sessions）：
```bash
if [ -x /root/server/bin/server-backup-sessions ]; then
  /root/server/bin/server-backup-sessions "${KEEP:-5}" || echo "警告：DSH sessions 备份失败" >&2
fi
```

## 3. 验证（本机实测）

```text
单独执行：已备份 sessions 4.0K -> /sdcard/DSH/backups/sessions-20261110-2114.tar.gz.enc
完整备份：server-20261110-2114.tar.gz.enc（6.6M）
          sessions-20261110-2115.tar.gz.enc（4.0K）
解密校验：6 个条目
```

## 4. 恢复

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -pass file:/root/server/etc/backup-pass \
  -in /sdcard/DSH/backups/sessions-<stamp>.tar.gz.enc | \
  tar xzf - -C /root/.dsh/sessions
```

> 恢复后 DSH 重启或等其自行扫描；session 历史会重新可见。

## 5. 复用（换机/新环境）

1. 复制 `scripts/server/server-backup-sessions` 到 `/root/server/bin/` 并 `chmod 755`；
2. 运行 `scripts/server/patch-server-backup-sessions.py`（把调用追加到 server-backup）；
3. `server-backup 5`，确认同时生成 `server-*.tar.gz.enc` 与 `sessions-*.tar.gz.enc`；
4. 安装器 `install-dsh-control-plane.sh` 已包含这两步。

## 6. 限制

- 只备份普通文件，不备份伪符号链接（按设计，避免 tar 错误）；session 数据文件本身包含在普通文件中。
- sessions 数据可能包含对话内容，备份是加密的；仍建议管理好备份口令。
- 外部异地副本/告警按用户要求暂不接入。

## 7. 附：DSH 版本检查

本次同时检查 npm：`@deepseek-ai/dsh` 最新 = `0.2.2-rc.1`（与当前一致），暂无升级版本；真实升级演练留待有新版本时按 docs/23 执行。
