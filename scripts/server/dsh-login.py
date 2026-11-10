#!/usr/bin/env python3
"""DSH 稳定登录入口（仅监听 127.0.0.1:3082）。

nginx 的 /app-login 在 Basic Auth 之后反代到这里；本服务从 dsh.log 读取
最近一次 dsh web 打印的 token，302 到 /app/?token=...。
这样用户只需访问 https://<host>:8443/app/（或 /app-login），无需每次复制 token。
token 本身仍为 DSH 的一次性访问令牌，未认证请求无法拿到重定向目标。
"""
import http.server
import os
import re
import sys

LOG = os.environ.get("DSH_LOG", "/root/server/logs/dsh.log")
PORT = int(os.environ.get("DSH_LOGIN_PORT", "3082"))
TOKEN_RE = re.compile(rb"token=([A-Za-z0-9_-]{20,})")


def current_token():
    try:
        with open(LOG, "rb") as fh:
            data = fh.read()[-524288:]
    except OSError:
        return None
    found = None
    for m in TOKEN_RE.finditer(data):
        found = m.group(1).decode("ascii")
    return found


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "dsh-login/1.0"
    protocol_version = "HTTP/1.1"

    def _redirect(self):
        token = current_token()
        target = "/app/?token=" + token if token else "/app/"
        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = _redirect
    do_HEAD = _redirect

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print("dsh-login: 127.0.0.1:%d -> /app/?token=<current>" % PORT, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
