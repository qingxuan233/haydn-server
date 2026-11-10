#!/usr/bin/env python3
"""给 DSH /app/ 与 /app-login 增加 nginx 限流（幂等）。"""
import re
import sys

UP = "/etc/nginx/conf.d/dsh-upstreams.conf"
SITE = "/etc/nginx/sites-available/dsh-tls"

s = open(UP, encoding="utf-8").read()
if "limit_req_zone" not in s:
    s = s.rstrip() + """

# DSH 控制平面限流（防爆破/资源保护；拒绝码 429）
limit_req_zone $binary_remote_addr zone=dsh_app:10m rate=5r/s;
limit_req_zone $binary_remote_addr zone=dsh_login:10m rate=2r/s;
"""
    open(UP, "w", encoding="utf-8").write(s)
    print("已写入限流 zone")
else:
    print("限流 zone 已存在")

t = open(SITE, encoding="utf-8").read()


def patch(block_re, zone, burst, label):
    global t
    m = re.search(block_re, t, re.S)
    if not m:
        print("找不到 location: " + label, file=sys.stderr)
        return False
    body = m.group("body")
    if "limit_req" not in body:
        anchor = "auth_basic_user_file /root/server/etc/dsh-web.htpasswd;"
        if anchor not in body:
            print(label + " 找不到 auth 锚点", file=sys.stderr)
            return False
        body = body.replace(
            anchor,
            anchor + "\n        limit_req zone=%s burst=%d nodelay;\n        limit_req_status 429;" % (zone, burst),
            1,
        )
    elif "limit_req_status 429;" not in body:
        body = re.sub(r"(limit_req zone=[^;]+;)", r"\1\n        limit_req_status 429;", body, count=1)
    t = t[:m.start("body")] + body + t[m.end("body"):]
    return True


ok1 = patch(r"location /app/ \{(?P<body>.*?)\n    \}", "dsh_app", 10, "/app/")
ok2 = patch(r"location = /app-login \{(?P<body>.*?)\n    \}", "dsh_login", 5, "/app-login")
if ok1 and ok2:
    open(SITE, "w", encoding="utf-8").write(t)
    print("nginx 站点限流已更新（/app/ 5r/s、/app-login 2r/s，429）")
else:
    sys.exit(1)
