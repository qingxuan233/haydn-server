#!/usr/bin/env python3
"""DSH 稳定登录入口（仅监听 127.0.0.1:3082）。

流程：
1. 从 /root/server/logs/dsh.log 读取当前 token；
2. 用与浏览器相同的 Host 请求 DSH 的 token 入口，拿到 DSH 种下的会话 cookie；
3. 302 到 /app/，同时把 cookie 以浏览器最兼容的属性返回：
   Path=/app; SameSite=Lax; HttpOnly（不再带 Secure，避免自签证书/浏览器策略拒绝）。

这样浏览器只需访问 /app/ 或 /app-login 即可完成登录，不再经历
"/app/ 无 cookie -> DSH 302 token -> 303 ./ -> 无 cookie" 的循环。
"""
import http.client
import http.server
import os
import re
import sys

LOG = os.environ.get("DSH_LOG", "/root/server/logs/dsh.log")
PORT = int(os.environ.get("DSH_LOGIN_PORT", "3082"))
DSH_HOST = os.environ.get("DSH_HOST", "127.0.0.1")
DSH_PORT = int(os.environ.get("DSH_PORT", "3081"))
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


def dsh_cookie(browser_host, token):
    """用浏览器 Host 请求 token 入口，返回 (cookie_name_value, status)。"""
    conn = http.client.HTTPConnection(DSH_HOST, DSH_PORT, timeout=6)
    try:
        conn.putrequest("GET", "/?token=" + token, skip_host=True)
        conn.putheader("Host", browser_host or (DSH_HOST + ":" + str(DSH_PORT)))
        conn.putheader("X-Forwarded-Proto", "https")
        conn.putheader("X-Forwarded-Host", browser_host or "")
        conn.endheaders()
        resp = conn.getresponse()
        set_cookies = [v for (k, v) in resp.getheaders() if k.lower() == "set-cookie"]
        try:
            resp.read(256)
        except Exception:
            pass
        if set_cookies:
            nameval = set_cookies[0].split(";", 1)[0].strip()
            if "=" in nameval:
                return nameval, resp.status
        return None, resp.status
    finally:
        conn.close()


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "dsh-login/2.0"
    protocol_version = "HTTP/1.1"

    def _redirect(self):
        token = current_token()
        cookie = None
        if token:
            try:
                cookie, _status = dsh_cookie(self.headers.get("Host", ""), token)
            except Exception as exc:  # DSH 未起来等
                sys.stderr.write("dsh-login: token exchange failed: %r\n" % (exc,))
        if cookie:
            # Path=/app 只随 /app 前缀发送；SameSite=Lax 兼容浏览器跳转；不带 Secure 兼容自签证书页面
            self.send_response(302)
            self.send_header("Location", "/app/")
            self.send_header("Set-Cookie", cookie + "; Path=/app; Max-Age=2592000; HttpOnly; SameSite=Lax")
            # 清掉浏览器里同名的旧 Path=/ cookie（此前 DSH 直接种下的 Strict/Secure 版本），避免双份 cookie 混淆
            name = cookie.split("=", 1)[0]
            self.send_header("Set-Cookie", name + "=; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax")
        else:
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
    print("dsh-login: 127.0.0.1:%d -> broker login for /app/" % PORT, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
