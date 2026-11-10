#!/usr/bin/env python3
# 给 server-backup 末尾追加 sessions 备份调用（幂等）
p = "/root/server/bin/server-backup"
s = open(p, encoding="utf-8").read()
if "server-backup-sessions" not in s:
    if not s.endswith("\n"):
        s += "\n"
    s += """
# DSH sessions 独立备份（仅普通文件，排除 proot link2symlink 伪链接）
if [ -x /root/server/bin/server-backup-sessions ]; then
  /root/server/bin/server-backup-sessions "${KEEP:-5}" || echo "警告：DSH sessions 备份失败" >&2
fi
"""
    open(p, "w", encoding="utf-8").write(s)
    print("已追加 sessions 备份调用")
else:
    print("已存在 sessions 备份调用")
