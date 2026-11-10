#!/usr/bin/env python3
"""把 DSH profile/sessions/storages 与 server bin/ops 纳入 server-backup（幂等）。

适用：Ubuntu/proot 内的 /root/server/bin/server-backup。
- 不备份 /root/.dsh/sessions：proot link2symlink 的 .l2s.* 伪链接会让 tar stat 失败。
- profiles/web 的 node_modules 排除（可用 pnpm 重装）。
"""
p = "/root/server/bin/server-backup"
s = open(p, encoding="utf-8").read()


def anchor():
    lines = s.splitlines(True)
    for i, line in enumerate(lines):
        if line.strip() == "done" and i >= 3 and "/gitea/data/$d" in "".join(lines[i - 3:i]):
            return i
    raise SystemExit("找不到 gitea PATHS 锚点")


# 1) PATHS 增加 ops + bin
if "PATHS+=(ops bin)" not in s:
    if "PATHS+=(ops)" in s:
        s = s.replace("PATHS+=(ops)", "PATHS+=(ops bin)", 1)
    else:
        idx = anchor()
        lines = s.splitlines(True)
        lines.insert(idx + 1, "PATHS+=(ops bin)\n")
        s = "".join(lines)

# 2) EXTRA_PATHS（排除 sessions）
if "EXTRA_PATHS=" not in s:
    idx = anchor()
    lines = s.splitlines(True)
    lines.insert(idx + 1, "EXTRA_PATHS=(.dsh/storages .dsh/profiles/server .dsh/profiles/web)\n")
    s = "".join(lines)

# 3) tar：排除 node_modules；-C /root 取 extra（-C / 在 proot 下不可靠）
old = 'tar czf "$TMP/payload.tar.gz" --exclude=\'*.log\' -C /root/server "${PATHS[@]}" -C "$TMP" gitea-data'
new = 'tar czf "$TMP/payload.tar.gz" --exclude=\'*.log\' --exclude=\'node_modules\' -C /root/server "${PATHS[@]}" -C /root "${EXTRA_PATHS[@]}" -C "$TMP" gitea-data'
if old in s:
    s = s.replace(old, new, 1)
elif new in s:
    pass
else:
    raise SystemExit("找不到 tar 命令（可能版本不同）")

# 4) dry-run 显示 extra
if 'printf "  %s\\n" "${PATHS[@]}"' in s and '"${EXTRA_PATHS[@]}"' not in s:
    s = s.replace('printf "  %s\\n" "${PATHS[@]}"', 'printf "  %s\\n" "${PATHS[@]}" "${EXTRA_PATHS[@]}"', 1)

open(p, "w", encoding="utf-8").write(s)
print("server-backup 已更新：ops/bin + .dsh storages/profiles（排除 sessions/node_modules）")
