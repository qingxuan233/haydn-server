#!/usr/bin/env python3
"""Haydn Web Gateway：多上游路径反向代理 + 本机控制台（Python 标准库，零第三方依赖）。

路由模型（最长前缀匹配，互不写死）：
    /console[...]  -> 内置控制台（会话鉴权 + 动作白名单 + 审计日志）
    <route.path>   -> route.upstream，可配置 strip_prefix / preserve_host / websocket / auth

每个上游一条独立路由与独立认证策略；新增服务只需在 gateway.json 增加一条 upstream，
不需要改代码，也不需要改 frpc/stunnel（公网只有一个 443 入口）。

安全边界：
- 只监听 127.0.0.1；不做任意 shell、不做文件系统浏览；
- 动作仅 supervisorctl start/stop/restart + 备份触发文件；
- 所有页面与 API 需要会话 cookie；登录失败限流；每次动作写审计日志。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import select
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

import auth
import console_actions as actions
import console_credentials as credentials
import console_ui
import lan_access
import webdav_ui

LOG = logging.getLogger("haydn.gateway")

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

# 请求体上限：控制台 API 只需要小 JSON；WebDAV 需要容纳大文件上传。
# 超限一律 413 并关闭连接，避免把未知大小请求体整体读进内存。
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_DAV_BODY_BYTES = 64 * 1024 * 1024


class BodyTooLarge(Exception):
    """请求体超过路由允许的上限。"""


DEFAULT_CONFIG = {
    "listen": "127.0.0.1:18080",
    "console": {
        "path": "/console",
        "title": "Haydn Console",
        "session_ttl_seconds": 43200,
        "cookie_secure": True,
        "login": {"max_failures": 5, "window_seconds": 900, "lock_seconds": 900},
    },
    "secret_file": "/etc/haydn-console/secret.json",
    "audit_log": "/var/log/haydn/console-audit.log",
    "lan": {
        "enabled": False,
        "listen": "0.0.0.0:18090",
        "probe_target": "223.5.5.5",
        "probe_interval_seconds": 30,
        "ticket_ttl_seconds": 60,
        "subnet_file": "/srv/haydn/run/lan-subnet",
    },
    "supervisor": {
        "conf": "/etc/supervisor/supervisord.conf",
        "ctl": "/usr/bin/supervisorctl",
        "services": [],
    },
    "logs": {},
    "telemetry_csv": "",
    "soak_file": "",
    "cert_file": "",
    "backup_trigger": "",
    "backup_log": "",
    "upstreams": [],
    # 服务入口：地址只在配置里维护；{lan_ip}/{lan_port}/{lan_root}/{public_host} 由服务端注入。
    "entries": [],
    "credentials": {
        "state_file": "/etc/haydn-console/credential-state.json",
        "export_dir": "/srv/haydn/run",
        "token_ttl_seconds": 120,
        "folder": "haydn-server",
        "password_length": 24,
        "vault": {
            "enabled": False,
            "client": "/opt/haydn/bw/bin/bw",
            "server": "http://127.0.0.1:18084",
            "appdata_dir": "/srv/haydn/run/bw-cli",
            "master_file": "/opt/haydn/secrets/vaultwarden-initial-account.txt",
            "folder": "haydn-server",
            "timeout_seconds": 60,
        },
        "services": [],
    },
}


def deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    cfg = deep_merge(DEFAULT_CONFIG, data)
    host, _, port = cfg["listen"].rpartition(":")
    cfg["_listen_host"] = host or "127.0.0.1"
    cfg["_listen_port"] = int(port)
    cfg["console"]["path"] = "/" + cfg["console"]["path"].strip("/")
    lan_host, _, lan_port = str(cfg["lan"].get("listen", "")).rpartition(":")
    cfg["lan"]["_listen_host"] = lan_host or "0.0.0.0"
    cfg["lan"]["_listen_port"] = int(lan_port) if lan_port.isdigit() else 0
    return cfg


def parse_hostport(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    return host or "127.0.0.1", int(port)


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    lan_mode = False  # True 表示这是只服务局域网网段的监听

    def __init__(self, address, handler, config):
        super().__init__(address, handler)
        self.config = config


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "haydn-gateway/1.0"
    timeout = 60
    _headers_sent = False

    # ---------- 基础设施 ----------
    def end_headers(self):
        # 统一记录“响应已开始”，异常兜底据此决定能否再写 500 头
        self._headers_sent = True
        super().end_headers()

    @property
    def cfg(self) -> dict:
        return self.server.config

    def log_message(self, fmt, *args):  # 访问日志走 stdout（supervisor 收集）
        headers = getattr(self, "headers", None)
        host = headers.get("Host", "-") if headers else "-"
        LOG.info("%s %s", host, fmt % args)

    def _json(self, code: int, payload: dict, extra_headers: list[tuple[str, str]] | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response_only(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in extra_headers or []:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _html(self, code: int, html: str, extra_headers: list[tuple[str, str]] | None = None):
        body = html.encode("utf-8")
        self.send_response_only(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self' http:; frame-ancestors 'none'; base-uri 'none'",
        )
        for name, value in extra_headers or []:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_bytes(self, code: int, body: bytes, content_type: str,
                    extra_headers: list[tuple[str, str]] | None = None):
        self.send_response_only(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in extra_headers or []:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _audit(self, action: str, target: str, result: str, detail: str = ""):
        record = {
            "ts": actions.now_utc(),
            "action": action,
            "target": target,
            "result": result,
            "detail": detail[:500],
            "peer": self.client_address[0],
            "ua": self.headers.get("User-Agent", "")[:200],
        }
        path = self.cfg.get("audit_log")
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            LOG.warning("audit write failed: %s", exc)

    # ---------- 会话 ----------
    def _session(self) -> auth.SessionManager:
        return self.server.sessions  # type: ignore[attr-defined]

    def _authenticated(self) -> bool:
        token = auth.parse_cookies(self.headers.get("Cookie")).get(auth.SESSION_COOKIE)
        return self._session().verify(token)

    def _cookie_secure(self) -> bool:
        # 局域网监听是 HTTP：带 Secure 的 cookie 浏览器不会回传，必须按监听区分
        if getattr(self.server, "lan_mode", False):
            return False
        return bool(self.cfg["console"].get("cookie_secure", True))

    def _cookie_header(self, value: str) -> str:
        parts = [f"{auth.SESSION_COOKIE}={value}", "Path=/", "HttpOnly", "SameSite=Lax"]
        if self._cookie_secure():
            parts.append("Secure")
        return "; ".join(parts)

    def _clear_cookie_header(self) -> str:
        parts = [f"{auth.SESSION_COOKIE}=", "Path=/", "HttpOnly", "SameSite=Lax", "Max-Age=0"]
        if self._cookie_secure():
            parts.append("Secure")
        return "; ".join(parts)

    # ---------- 局域网 ----------
    def _lan_snapshot(self) -> dict:
        monitor = getattr(self.server, "lan_monitor", None)
        if monitor is None:
            return {"ok": False, "lan_ip": "", "lan_prefix": 0, "lan_subnet": "", "lan_iface": "",
                    "updated_at": ""}
        return monitor.refresh_if_stale(float(self.cfg["lan"].get("probe_interval_seconds", 30)))

    def _lan_url(self, snapshot: dict, path: str = "") -> str:
        ip_text = snapshot.get("lan_ip") or ""
        port = self.cfg["lan"].get("_listen_port") or 0
        if not ip_text or not port:
            return ""
        base = f"http://{ip_text}:{port}{self.cfg['console']['path']}"
        return base + ("/" + path.lstrip("/") if path else "/")

    def _lan_allowed(self) -> bool:
        snapshot = self._lan_snapshot()
        if not snapshot.get("ok"):
            return False
        return lan_access.in_subnet(self.client_address[0], snapshot["lan_subnet"])

    # ---------- 请求体 ----------
    def _read_body(self, limit: int = MAX_BODY_BYTES) -> bytes:
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            self._body_consumed = True
            return self._read_chunked(limit)
        length = self.headers.get("Content-Length")
        if not length:
            self._body_consumed = True
            return b""
        try:
            size = int(length)
        except ValueError:
            # 无法解析的长度：不猜，交给 _serve 关闭连接
            return b""
        self._body_consumed = True
        if size <= 0:
            return b""
        if size > limit:
            # 不读取、不丢弃：直接关闭连接，避免把剩余字节当成下一个请求解析
            self.close_connection = True
            raise BodyTooLarge(f"content-length {size} > {limit}")
        return self.rfile.read(size)

    def _read_chunked(self, limit: int = MAX_BODY_BYTES) -> bytes:
        out = bytearray()
        while True:
            line = self.rfile.readline(65536)
            if not line:
                break
            size_text = line.split(b";", 1)[0].strip()
            try:
                size = int(size_text, 16)
            except ValueError:
                break
            if size == 0:
                self.rfile.readline(65536)
                break
            if len(out) + size > limit:
                # 超限时显式失败：静默截断会让上游收到坏数据且连接流错位
                self.close_connection = True
                raise BodyTooLarge(f"chunked body > {limit}")
            out.extend(self.rfile.read(size))
            self.rfile.read(2)
        return bytes(out)

    # ---------- 分发 ----------
    def _has_request_body(self) -> bool:
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            return True
        try:
            return int(self.headers.get("Content-Length") or 0) > 0
        except ValueError:
            return True

    def _serve(self):
        """统一入口：请求体未被读走时关闭连接。

        401/403/404 等早退路径不读请求体；HTTP/1.1 keep-alive 下剩余字节会被
        当成下一个请求行解析（日志出现 Bad request version，且请求体内容——
        例如登录口令——会被原样写进日志）。宁可让客户端重连，也不要流错位。
        """
        self._body_consumed = False
        try:
            self._dispatch()
        finally:
            if not self._body_consumed and self._has_request_body():
                self.close_connection = True

    def do_GET(self):
        self._serve()

    def do_HEAD(self):
        self._serve()

    def do_POST(self):
        self._serve()

    def do_PUT(self):
        self._serve()

    def do_DELETE(self):
        self._serve()

    def do_OPTIONS(self):
        self._serve()

    # WebDAV 动词（rclone serve webdav 需要）
    def do_PROPFIND(self):
        self._serve()

    def do_PROPPATCH(self):
        self._serve()

    def do_MKCOL(self):
        self._serve()

    def do_COPY(self):
        self._serve()

    def do_MOVE(self):
        self._serve()

    def do_LOCK(self):
        self._serve()

    def do_UNLOCK(self):
        self._serve()

    def _basic_authorized(self, route: dict) -> bool:
        creds = auth.parse_basic(self.headers.get("Authorization"))
        if not creds:
            return False
        path = route.get("secret_file") or f"/opt/haydn/secrets/{route.get('name', 'route')}.json"
        record = self.server.basic_cache.load(path)  # type: ignore[attr-defined]
        if not auth.verify_basic(record, creds[0], creds[1]):
            self._audit("auth.basic", route.get("name", path), "fail", f"user={creds[0][:32]}")
            return False
        return True

    def _dispatch(self):
        self._headers_sent = False
        try:
            parts = urlsplit(self.path)
            path = parts.path or "/"
            console_path = self.cfg["console"]["path"]
            if path == console_path or path.startswith(console_path + "/"):
                self._handle_console(path, parts.query, console_path)
                return
            if path == "/":
                # 根路径原为 302 字节的自检占位页（见 README §13.6），无实际用途：
                # 直接落到控制台，避免访问根路径看到空页。
                self.send_response_only(302)
                self.send_header("Location", console_path + "/")
                self.send_header("Content-Length", "0")
                self._security_headers()
                self.end_headers()
                return
            if getattr(self.server, "lan_mode", False) and not self._lan_allowed():
                self._audit("lan.access", path, "refused", "client not in detected subnet")
                self._json(403, {"error": "not in lan subnet"})
                return
            route = self._match_route(path)
            if route is None:
                self._json(404, {"error": "no route"})
                return
            prefix = "/" + str(route.get("path", "/")).strip("/")
            if prefix != "/" and path == prefix and self.command in ("GET", "HEAD", "PROPFIND", "OPTIONS"):
                # 上游可能自带 baseurl（如 rclone --baseurl /dav）：此处补齐尾斜杠，
                # 否则上游会把无斜杠的集合路径当成文件返回 405。
                location = prefix + "/" + ("?" + parts.query if parts.query else "")
                self.send_response_only(301)
                self.send_header("Location", location)
                self.send_header("Content-Length", "0")
                self._security_headers()
                self.end_headers()
                return
            policy = route.get("auth", "none")
            if policy == "session" and not self._authenticated():
                self._json(401, {"error": "authentication required"})
                return
            if policy == "basic":
                if not self._basic_authorized(route):
                    realm = route.get("auth_realm", route.get("name", "haydn"))
                    self._json(
                        401,
                        {"error": "authentication required"},
                        [("WWW-Authenticate", f'Basic realm="{realm}", charset="UTF-8"')],
                    )
                    return
            if policy not in ("none", "session", "basic"):
                self._json(500, {"error": f"unsupported auth policy: {policy}"})
                return
            if self._serve_browser_ui(route, path):
                return
            if route.get("websocket") and self.headers.get("Upgrade", "").lower() == "websocket":
                self._tunnel(route, path, parts.query)
            else:
                self._proxy(route, path, parts.query)
        except BodyTooLarge as exc:
            self._audit("request.body", self.path, "refused", str(exc))
            if self._headers_sent:
                self.close_connection = True
            else:
                self._json(413, {"error": "请求体超过允许上限"})
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:  # 兜底：不让单请求异常拖垮线程
            LOG.exception("dispatch failed")
            if self._headers_sent:
                # 响应已经开始，再写一个 500 头只会产生损坏的响应
                self.close_connection = True
                return
            try:
                self._json(500, {"error": f"gateway error: {exc}"})
            except OSError:
                self.close_connection = True

    def _match_route(self, path: str) -> dict | None:
        best = None
        best_len = -1
        for route in self.cfg.get("upstreams", []):
            if not route.get("enabled", True):
                continue
            prefix = "/" + str(route.get("path", "/")).strip("/")
            if prefix == "/":
                matched = True
            else:
                matched = path == prefix or path.startswith(prefix + "/")
            if matched and len(prefix) > best_len:
                best, best_len = route, len(prefix)
        return best

    # ---------- 控制台 ----------
    def _handle_console(self, path: str, query: str, console_path: str):
        if path == console_path:
            self.send_response_only(302)
            self.send_header("Location", console_path + "/")
            self.send_header("Content-Length", "0")
            self._security_headers()
            self.end_headers()
            return

        rel = path[len(console_path):]  # 以 "/" 开头
        host_label = self.headers.get("Host", "haydn")
        title = self.cfg["console"].get("title", "Haydn Console")
        lan_mode = getattr(self.server, "lan_mode", False)

        # 局域网监听上的通用网段闸门：非本网段一律拒绝（探测与票据端点自行判定）
        if lan_mode and rel not in ("/lan-probe", "/lan-login") and not self._lan_allowed():
            self._audit("lan.access", rel or path, "refused", f"peer={self.client_address[0]}")
            self._json(403, {"error": "当前来源不在设备所在局域网网段"})
            return

        if rel == "/lan-probe":
            self._api_lan_probe()
            return

        if rel == "/lan-login":
            self._lan_login(parse_qs(query), console_path)
            return

        if rel in ("/", "/index.html"):
            if self._authenticated():
                self._html(200, console_ui.render_app(title, console_path))
            else:
                self._html(200, console_ui.render_login(title, console_path, host_label))
            return

        if rel == "/api/login":
            self._api_login(console_path)
            return

        # 其余 API 一律需要会话
        if not self._authenticated():
            self._json(401, {"error": "authentication required"})
            return
        if rel == "/api/status" and self.command in ("GET", "HEAD"):
            self._api_status()
        elif rel == "/api/lan" and self.command in ("GET", "HEAD"):
            self._api_lan()
        elif rel == "/api/metrics" and self.command in ("GET", "HEAD"):
            self._api_metrics()
        elif rel == "/api/lan-ticket" and self.command == "POST":
            self._api_lan_ticket(console_path)
        elif rel == "/api/service" and self.command == "POST":
            self._api_service()
        elif rel == "/api/backup" and self.command == "GET":
            self._json(200, {"ok": True, "status": actions.recent_backup(self.cfg["backup_log"])})
        elif rel == "/api/backup" and self.command == "POST":
            self._api_backup()
        elif rel == "/api/entries" and self.command in ("GET", "HEAD"):
            self._api_entries()
        elif rel == "/api/credentials/token" and self.command == "POST":
            self._api_credentials_token(console_path)
        elif rel == "/api/credentials/download" and self.command in ("GET", "HEAD"):
            self._api_credentials_download(parse_qs(query))
        elif rel == "/api/credential/reveal" and self.command == "POST":
            self._api_credential_reveal()
        elif rel == "/api/rotate" and self.command == "POST":
            self._api_rotate()
        elif rel == "/api/logout" and self.command == "POST":
            if not self._csrf_ok():
                self._audit("logout", "-", "refused", "csrf/session check failed")
                self._json(403, {"error": "请求来源校验失败"})
                return
            self._audit("logout", "-", "ok")
            self._json(200, {"ok": True}, [("Set-Cookie", self._clear_cookie_header())])
        else:
            self._json(404, {"error": "unknown console endpoint"})

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")

    def _csrf_ok(self) -> bool:
        if self.headers.get("X-Haydn-Client") != "console":
            return False
        origin = self.headers.get("Origin")
        if not origin:
            return True
        allowed = {self.headers.get("Host", "")}
        try:
            host = urlsplit(origin).netloc
        except ValueError:
            return False
        return host in allowed

    def _api_login(self, console_path: str):
        limiter = self.server.limiter  # type: ignore[attr-defined]
        body = self._read_body()
        password = ""
        ctype = self.headers.get("Content-Type", "")
        try:
            if "application/json" in ctype:
                payload = json.loads(body.decode("utf-8", "replace") or "{}")
                password = str(payload.get("password", ""))
            else:
                form = parse_qs(body.decode("utf-8", "replace"))
                password = (form.get("password") or [""])[0]
        except (ValueError, TypeError):
            password = ""

        secret = self.server.secret  # type: ignore[attr-defined]
        record = secret.get("password") if isinstance(secret, dict) else None
        if not record:
            # 口令轮换期间 secret 可能被整体替换：此处不同于“未初始化”，返回 503 让客户端重试
            self._json(503, {"error": "服务端口令暂不可用，请重试"}, [("Retry-After", "1")])
            return
        if not password or not auth.verify_password(record, password):
            # 限流只拦截“失败尝试”：持有正确口令的管理员始终可以登录，
            # 避免匿名者用 5 次错误把管理员锁在门外（DoS）。
            blocked = limiter.blocked_for()
            if blocked:
                self._audit("login", "-", "blocked", f"retry after {blocked}s")
                self._json(429, {"error": f"尝试过于频繁，请 {blocked} 秒后再试"}, [("Retry-After", str(blocked))])
                return
            limiter.record_failure()
            self._audit("login", "-", "fail")
            self._json(401, {"error": "口令错误"})
            return
        limiter.reset()
        token = self._session().issue()
        self._audit("login", "-", "ok")
        self._json(200, {"ok": True}, [("Set-Cookie", self._cookie_header(token))])

    def _api_status(self):
        cfg = self.cfg
        sup = cfg["supervisor"]
        services = actions.supervisor_status(sup)
        telemetry = actions.telemetry_summary(cfg["telemetry_csv"]) if cfg.get("telemetry_csv") else {"ok": False}
        soak = actions.soak_summary(cfg["soak_file"], telemetry) if cfg.get("soak_file") else {"ok": False}
        cert = actions.cert_info(cfg["cert_file"]) if cfg.get("cert_file") else {"ok": False}
        self._json(
            200,
            {
                "ok": True,
                "now": actions.now_utc(),
                "services": services,
                "overview": actions.system_overview(),
                "telemetry": telemetry,
                "soak": soak,
                "cert": cert,
                "credentials": credentials.summary(cfg),
                "backup": actions.recent_backup(cfg["backup_log"]) if cfg.get("backup_log") else None,
            },
        )

    def _api_service(self):
        if not self._csrf_ok():
            self._audit("service", "-", "refused", "csrf/session check failed")
            self._json(403, {"error": "请求来源校验失败"})
            return
        body = self._read_body()
        try:
            payload = json.loads(body.decode("utf-8", "replace") or "{}")
            name = str(payload.get("name", ""))
            verb = str(payload.get("action", ""))
        except (ValueError, TypeError):
            self._json(400, {"error": "invalid payload"})
            return
        ok, output = actions.service_action(self.cfg["supervisor"], name, verb)
        self._audit("service." + verb, name, "ok" if ok else "fail", output)
        self._json(200 if ok else 400, {"ok": ok, "output": output})

    def _api_backup(self):
        if not self._csrf_ok():
            self._audit("backup.trigger", "-", "refused", "csrf/session check failed")
            self._json(403, {"error": "请求来源校验失败"})
            return
        self._read_body()
        path = self.cfg.get("backup_trigger", "")
        if not path:
            self._json(500, {"error": "backup trigger not configured"})
            return
        try:
            ok, message = actions.trigger_backup(path)
        except OSError as exc:
            self._audit("backup.trigger", path, "fail", str(exc))
            self._json(500, {"error": f"trigger failed: {exc}"})
            return
        self._audit("backup.trigger", path, "ok" if ok else "fail", message)
        self._json(200, {"ok": ok, "message": "已提交，设备侧将在下一个轮询周期（≤60s）执行备份"})

    # ---------- 服务入口 / 凭据 ----------
    def _api_entries(self):
        snapshot = self._lan_snapshot()
        lan_ip = snapshot.get("lan_ip", "") if snapshot.get("ok") else ""
        lan_port = self.cfg["lan"].get("_listen_port") or 0
        lan_root = f"http://{lan_ip}:{lan_port}" if lan_ip and lan_port else ""
        public_host = self.headers.get("Host", "")
        items = []
        available_map = {
            "{lan_ip}": bool(lan_ip),
            "{lan_port}": bool(lan_port),
            "{lan_root}": bool(lan_root),
            "{public_host}": bool(public_host),
        }
        for entry in self.cfg.get("entries", []):
            raw = str(entry.get("url") or "")
            resolved = (
                raw.replace("{lan_ip}", lan_ip or "")
                .replace("{lan_port}", str(lan_port) if lan_port else "")
                .replace("{lan_root}", lan_root)
                .replace("{public_host}", public_host)
            )
            # 占位符被替换成空串时会留下 "http://:18090" 这类看似可用的坏地址，
            # 必须按“每个占位符各自的取值是否为空”判断，不能只看有没有残留的 "{"。
            unresolved = [name for name, ok in available_map.items() if name in raw and not ok]
            available = bool(raw) and not unresolved
            items.append(
                {
                    "name": str(entry.get("name") or raw),
                    "url": resolved if available else "",
                    "note": str(entry.get("note") or ""),
                    "available": available,
                    "reason": "" if available else "占位符未解析（局域网地址或公网 Host 不可用）",
                }
            )
        self._json(200, {"ok": True, "entries": items, "lan_ip": lan_ip, "lan_port": lan_port})

    def _api_credentials_token(self, console_path: str):
        if not self._csrf_ok():
            self._audit("credentials.token", "-", "refused", "csrf/session check failed")
            self._json(403, {"error": "请求来源校验失败"})
            return
        self._read_body()
        tokens = getattr(self.server, "export_tokens", None)
        if tokens is None:
            self._json(503, {"error": "导出令牌服务未启用"})
            return
        token, ttl = tokens.issue()
        self._audit("credentials.token", "-", "issued", f"ttl={ttl}s")
        self._json(
            200,
            {
                "ok": True,
                "path": console_path + "/api/credentials/download?t=" + quote(token),
                "expires_in": ttl,
            },
        )

    def _api_credentials_download(self, query: dict):
        token = (query.get("t") or [""])[0]
        tokens = getattr(self.server, "export_tokens", None)
        if tokens is None or not token or not tokens.redeem(token):
            self._audit("credentials.export", "-", "refused", "token invalid or used")
            self._json(410, {"error": "链接已失效（一次性令牌已使用或过期），请重新获取"})
            return
        text, rows = credentials.build_csv(self.cfg)
        name = "haydn-credentials-" + time.strftime("%Y%m%d-%H%M%S") + ".csv"
        export_dir = str((self.cfg.get("credentials") or {}).get("export_dir") or "/srv/haydn/run")
        path = os.path.join(export_dir, name)
        try:
            credentials.write_file(path, text)
            with open(path, "rb") as fh:
                body = fh.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        self._audit("credentials.export", name, "ok", f"rows={rows}")
        self._send_bytes(
            200,
            body,
            "text/csv; charset=utf-8",
            [("Content-Disposition", f'attachment; filename="{name}"')],
        )

    def _api_credential_reveal(self):
        """按服务返回当前生效口令：仅登录态 + 同源校验可用，审计只记服务名/来源/路径，不记口令本身。"""
        if not self._csrf_ok():
            self._audit("credentials.reveal", "-", "refused", "csrf/session check failed")
            self._json(403, {"error": "请求来源校验失败"})
            return
        body = self._read_body()
        try:
            payload = json.loads(body.decode("utf-8", "replace") or "{}")
            service_id = str(payload.get("service") or "")
        except (ValueError, TypeError):
            self._audit("credentials.reveal", "-", "refused", "invalid payload")
            self._json(400, {"error": "请求格式错误"})
            return
        svc = credentials.find_service(self.cfg, service_id)
        if not svc:
            self._audit("credentials.reveal", service_id or "-", "refused", "unknown service")
            self._json(400, {"error": "未知服务"})
            return
        path = str(svc.get("plain_file") or svc.get("account_file") or "")
        password = credentials.service_password(svc)
        if not password:
            self._audit("credentials.reveal", service_id, "refused", f"no plaintext; path={path or '-'}")
            self._json(400, {"error": "该服务在设备侧没有可读取的明文口令"})
            return
        self._audit("credentials.reveal", service_id, "ok", f"path={path or '-'}")
        self._json(
            200,
            {
                "ok": True,
                "service": service_id,
                "username": credentials.service_username(svc),
                "password": password,
            },
        )

    def _api_rotate(self):
        if not self._csrf_ok():
            self._audit("credentials.rotate", "-", "refused", "csrf/session check failed")
            self._json(403, {"error": "请求来源校验失败"})
            return
        body = self._read_body()
        try:
            payload = json.loads(body.decode("utf-8", "replace") or "{}")
            service_id = str(payload.get("service", ""))
        except (ValueError, TypeError):
            self._json(400, {"error": "invalid payload"})
            return
        try:
            result = credentials.rotate(self.cfg, service_id, [self.server])
        except Exception as exc:  # 兜底：不把异常细节（可能含路径）扩展成口令泄露
            LOG.exception("rotate failed")
            self._audit("credentials.rotate", service_id, "fail", "exception")
            self._json(500, {"ok": False, "error": f"轮换异常：{type(exc).__name__}"})
            return
        ok = bool(result.get("ok"))
        detail = "; ".join(f"{s.get('name')}={'ok' if s.get('ok') else 'fail'}" for s in result.get("steps", []))
        self._audit("credentials.rotate", service_id, "ok" if ok else "fail", detail)
        if ok and result.get("vault_error"):
            self._audit("credentials.vault", service_id, "fail", str(result["vault_error"])[:300])
        self._json(200 if ok else 400, result)

    # ---------- 局域网入口 ----------
    def _api_lan(self):
        snapshot = self._lan_snapshot()
        self._json(
            200,
            {
                "ok": bool(snapshot.get("ok")),
                "lan_ip": snapshot.get("lan_ip", ""),
                "lan_prefix": snapshot.get("lan_prefix", 0),
                "lan_subnet": snapshot.get("lan_subnet", ""),
                "lan_iface": snapshot.get("lan_iface", ""),
                "lan_port": self.cfg["lan"].get("_listen_port") or 0,
                "lan_url": self._lan_url(snapshot),
                "updated_at": snapshot.get("updated_at", ""),
                "probe_interval_seconds": int(self.cfg["lan"].get("probe_interval_seconds", 30)),
                "ticket_ttl_seconds": int(self.cfg["lan"].get("ticket_ttl_seconds", 60)),
                "listener": "lan" if getattr(self.server, "lan_mode", False) else "public",
                "public_root": str(self.cfg.get("public_root") or ""),
                "error": snapshot.get("error", ""),
            },
        )

    def _api_metrics(self):
        """经会话鉴权代理 loopback 上的 node_exporter（127.0.0.1:9100），不新增对外端口。"""
        conn = HTTPConnection("127.0.0.1", 9100, timeout=6)
        try:
            conn.request("GET", "/metrics")
            upstream = conn.getresponse()
            body = upstream.read()
            if upstream.status != 200:
                self._json(503, {"error": f"node_exporter HTTP {upstream.status}"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._security_headers()
            self.end_headers()
            if self.command == "GET" and body:
                self.wfile.write(body)
        except OSError as exc:
            self._json(503, {"error": f"node_exporter 不可用（{type(exc).__name__}）"})
        finally:
            conn.close()

    def _api_lan_ticket(self, console_path: str):
        if not self._csrf_ok():
            self._audit("lan.ticket", "-", "refused", "csrf/session check failed")
            self._json(403, {"error": "请求来源校验失败"})
            return
        self._read_body()
        snapshot = self._lan_snapshot()
        if not snapshot.get("ok"):
            self._json(503, {"error": "未探测到可用的局域网地址"})
            return
        tickets = getattr(self.server, "tickets", None)
        if tickets is None:
            self._json(503, {"error": "票据服务未启用"})
            return
        token = tickets.issue(snapshot["lan_subnet"], console_path + "/")
        url = f"{self._lan_url(snapshot, 'lan-login')}?ticket={quote(token)}"
        self._audit("lan.ticket", snapshot["lan_subnet"], "issued", f"ttl={tickets.ttl}s")
        self._json(
            200,
            {
                "ok": True,
                "url": url,
                "expires_in": tickets.ttl,
                "lan_ip": snapshot.get("lan_ip", ""),
                "lan_subnet": snapshot.get("lan_subnet", ""),
                "updated_at": snapshot.get("updated_at", ""),
            },
        )

    def _api_lan_probe(self):
        """探测端点：只回答“是否同网段”。

        该端点无需登录，公网入口也可访问，因此不能回传局域网地址、网段或来源地址，
        否则等于给未鉴权访问者一个内网枚举接口。跨源读取仅用于这一个布尔值。
        """
        allowed = self._lan_allowed()
        headers = [("Access-Control-Allow-Origin", "*"), ("Timing-Allow-Origin", "*")]
        self._json(
            200 if allowed else 403,
            {"ok": True, "probe": True, "same_subnet": bool(allowed)},
            headers,
        )

    def _lan_login(self, query: dict, console_path: str):
        ticket = (query.get("ticket") or [""])[0]
        snapshot = self._lan_snapshot()
        tickets = getattr(self.server, "tickets", None)
        if tickets is None:
            self._audit("lan.ticket", "-", "unavailable")
            self._lan_error_page(503, "票据服务未启用。")
            return
        status, payload = tickets.redeem(ticket, self.client_address[0], snapshot.get("lan_subnet", ""))
        self._audit("lan.ticket", snapshot.get("lan_subnet", ""), status, f"peer={self.client_address[0]}")
        if status != "ok":
            code, text = {
                "expired": (401, "票据已过期，请回公网页面重新点击“切到局域网”。"),
                "replay": (409, "票据已被使用（重放），请回公网页面重新点击。"),
                "subnet-mismatch": (403, "来源网段与设备当前网段不符（可能已切换 Wi-Fi），请刷新公网页面重试。"),
                "bad-signature": (401, "票据无效。"),
            }.get(status, (400, "票据校验失败。"))
            self._lan_error_page(code, text)
            return
        next_path = str(payload.get("next") or console_path + "/")
        if not next_path.startswith(console_path):
            next_path = console_path + "/"
        token = self._session().issue()
        self.send_response_only(302)
        self.send_header("Location", next_path)
        self.send_header("Set-Cookie", self._cookie_header(token))
        self.send_header("Content-Length", "0")
        self._security_headers()
        self.end_headers()

    def _lan_error_page(self, code: int, text: str):
        html = (
            "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>局域网入口</title></head>"
            "<body style=\"margin:0;padding:32px;background:#0f1116;color:#d7dce5;"
            "font:15px/1.6 -apple-system,'Segoe UI',Roboto,sans-serif\">"
            "<h1 style=\"font-size:17px;margin:0 0 10px\">局域网入口不可用</h1>"
            f"<p style=\"margin:0;color:#8b96a8\">{text}</p></body></html>"
        )
        self._html(code, html)

    # ---------- 上游代理 ----------
    def _serve_browser_ui(self, route: dict, path: str) -> bool:
        """浏览器访问集合根路径时返回自建中文界面（仅 GET/HEAD + Accept: text/html）。

        最小侵入：只替换 rclone 的英文目录页，其余方法与所有客户端请求继续透传，
        WebDAV 协议语义（PROPFIND/GET/PUT/DELETE/MKCOL/MOVE）不变；认证仍走本路由 Basic。
        """
        ui = route.get("browser_ui")
        if not ui or self.command not in ("GET", "HEAD"):
            return False
        prefix = "/" + str(route.get("path", "/")).strip("/")
        if path != prefix + "/":
            return False
        if "text/html" not in (self.headers.get("Accept") or "").lower():
            return False
        title = ui.get("title") if isinstance(ui, dict) else ""
        self._html(200, webdav_ui.render_page(prefix, str(title or "Haydn WebDAV")))
        return True

    def _upstream_path(self, route: dict, path: str, query: str) -> str:
        target = path
        if route.get("strip_prefix"):
            prefix = "/" + str(route.get("path", "/")).strip("/")
            if prefix != "/" and target.startswith(prefix):
                target = target[len(prefix):] or "/"
        if query:
            target = f"{target}?{query}"
        return target

    @staticmethod
    def _strip_session_cookie(value: str) -> str:
        """转发上游前移除控制台会话 cookie，避免把 haydn_session 泄露给上游进程/日志。"""
        kept = []
        for item in (value or "").split(";"):
            item = item.strip()
            if not item or item.startswith(auth.SESSION_COOKIE + "="):
                continue
            kept.append(item)
        return "; ".join(kept)

    def _proxy(self, route: dict, path: str, query: str):
        host, port = parse_hostport(route["upstream"])
        target = self._upstream_path(route, path, query)
        prefix = "/" + str(route.get("path", "/")).strip("/")
        limit = int(route.get("max_body_bytes") or (MAX_DAV_BODY_BYTES if prefix == "/dav" else MAX_BODY_BYTES))
        body = self._read_body(limit)

        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            lower = key.lower()
            if lower in HOP_BY_HOP or lower == "host":
                continue
            if lower == "cookie":
                value = self._strip_session_cookie(value)
                if not value:
                    continue
            headers[key] = value
        if route.get("preserve_host") and self.headers.get("Host"):
            headers["Host"] = self.headers["Host"]
        else:
            headers["Host"] = f"{host}:{port}"
        headers["X-Forwarded-For"] = self.client_address[0]
        headers["X-Forwarded-Proto"] = "http" if getattr(self.server, "lan_mode", False) else "https"
        headers["X-Forwarded-Host"] = self.headers.get("Host", "")
        headers["X-Forwarded-Prefix"] = prefix

        conn = HTTPConnection(host, port, timeout=60)
        try:
            conn.request(self.command, target, body=body or None, headers=headers)
            resp = conn.getresponse()
        except OSError as exc:
            conn.close()
            self._json(502, {"error": f"upstream unreachable: {exc}"})
            return

        self.log_request(resp.status)
        self.send_response_only(resp.status, resp.reason)
        length = resp.getheader("Content-Length")
        for key, value in resp.getheaders():
            if key.lower() in HOP_BY_HOP or key.lower() in ("content-length", "date", "server"):
                continue
            self.send_header(key, value)
        self.send_header("Date", self.date_time_string())
        if length is not None:
            self.send_header("Content-Length", length)
        else:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        if self.command != "HEAD":
            try:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
        conn.close()

    def _tunnel(self, route: dict, path: str, query: str):
        """WebSocket / 任意 Upgrade 隧道：握手后在两条 socket 间双向透传。"""
        host, port = parse_hostport(route["upstream"])
        target = self._upstream_path(route, path, query)
        try:
            upstream = socket.create_connection((host, port), timeout=15)
        except OSError as exc:
            self._json(502, {"error": f"upstream unreachable: {exc}"})
            return

        lines = [f"{self.command} {target} HTTP/1.1"]
        for key, value in self.headers.items():
            if key.lower() == "host":
                host_value = self.headers["Host"] if route.get("preserve_host") else f"{host}:{port}"
                lines.append(f"Host: {host_value}")
            elif key.lower() == "x-forwarded-prefix":
                continue
            elif key.lower() == "cookie":
                value = self._strip_session_cookie(value)
                if not value:
                    continue
                lines.append(f"{key}: {value}")
            else:
                lines.append(f"{key}: {value}")
        lines.append(f"X-Forwarded-Prefix: /{str(route.get('path', '/')).strip('/')}")
        upstream.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1"))

        self.close_connection = True
        sockets = [self.connection, upstream]
        try:
            while True:
                readable, _, errored = select.select(sockets, [], sockets, 300)
                if errored:
                    break
                if not readable:
                    break
                for sock in readable:
                    try:
                        data = sock.recv(65536)
                    except OSError:
                        data = b""
                    if not data:
                        return
                    if sock is upstream:
                        self.connection.sendall(data)
                    else:
                        upstream.sendall(data)
        finally:
            upstream.close()


def build_server(cfg: dict) -> GatewayServer:
    secret = auth.load_secret(cfg["secret_file"])
    if secret is None:
        LOG.warning("secret file %s missing; console API will reject logins", cfg["secret_file"])
    console_cfg = cfg["console"]
    login_cfg = console_cfg.get("login", {})
    server = GatewayServer((cfg["_listen_host"], cfg["_listen_port"]), Handler, cfg)
    server.secret = secret  # type: ignore[attr-defined]
    key = bytes.fromhex(secret["session_key"]) if secret else os.urandom(32)
    server.sessions = auth.SessionManager(key, int(console_cfg.get("session_ttl_seconds", 43200)))  # type: ignore[attr-defined]
    server.limiter = auth.LoginLimiter(  # type: ignore[attr-defined]
        int(login_cfg.get("max_failures", 5)),
        int(login_cfg.get("window_seconds", 900)),
        int(login_cfg.get("lock_seconds", 900)),
    )
    server.basic_cache = auth.BasicSecretCache()  # type: ignore[attr-defined]
    server.lan_monitor = None  # type: ignore[attr-defined]
    if cfg["lan"].get("enabled"):
        server.lan_monitor = lan_access.LanMonitor(cfg["lan"])  # type: ignore[attr-defined]
        server.lan_monitor.start()
    server.tickets = lan_access.TicketManager(key, int(cfg["lan"].get("ticket_ttl_seconds", 60)))  # type: ignore[attr-defined]
    ttl = int((cfg.get("credentials") or {}).get("token_ttl_seconds", 120))
    server.export_tokens = credentials.ExportTokens(ttl)  # type: ignore[attr-defined]
    return server


def build_lan_server(cfg: dict, base: GatewayServer) -> GatewayServer | None:
    """局域网监听：与主监听共享会话/限流/凭据缓存，但只服务探测到的网段。"""
    if not cfg["lan"].get("enabled"):
        return None
    port = cfg["lan"].get("_listen_port") or 0
    if not port:
        LOG.warning("lan.enabled but listen port invalid; lan listener skipped")
        return None
    server = GatewayServer((cfg["lan"]["_listen_host"], port), Handler, cfg)
    server.lan_mode = True
    server.secret = base.secret  # type: ignore[attr-defined]
    server.sessions = base.sessions  # type: ignore[attr-defined]
    server.limiter = base.limiter  # type: ignore[attr-defined]
    server.basic_cache = base.basic_cache  # type: ignore[attr-defined]
    server.lan_monitor = base.lan_monitor  # type: ignore[attr-defined]
    server.tickets = base.tickets  # type: ignore[attr-defined]
    server.export_tokens = base.export_tokens  # type: ignore[attr-defined]
    return server


def cmd_init_admin(cfg: dict, force: bool) -> int:
    path = cfg["secret_file"]
    if os.path.exists(path) and not force:
        print(f"refusing: {path} already exists (use --force to rotate)")
        return 1
    password = auth.generate_password()
    secret = {
        "version": 1,
        "created": datetime.now(timezone.utc).isoformat(),
        "password": auth.hash_password(password),
        "session_key": os.urandom(32).hex(),
    }
    auth.save_secret(path, secret)
    plain_path = os.path.join(os.path.dirname(path) or ".", "admin-password.txt")
    fd = os.open(plain_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(password + "\n")
    print(f"secret written: {path}")
    print(f"initial password written: {plain_path} (read it on device, then delete the file)")
    return 0


def cmd_set_password(cfg: dict) -> int:
    password = sys.stdin.readline().rstrip("\n")
    if len(password) < 12:
        print("refusing: password must be at least 12 characters")
        return 1
    secret = auth.load_secret(cfg["secret_file"]) or {
        "version": 1,
        "created": datetime.now(timezone.utc).isoformat(),
        "session_key": os.urandom(32).hex(),
    }
    secret["password"] = auth.hash_password(password)
    auth.save_secret(cfg["secret_file"], secret)
    print(f"password updated: {cfg['secret_file']}")
    return 0


def _route_by_name(cfg: dict, name: str) -> dict | None:
    for route in cfg.get("upstreams", []):
        if route.get("name") == name:
            return route
    return None


def _route_secret_path(route: dict) -> str:
    return route.get("secret_file") or f"/opt/haydn/secrets/{route.get('name', 'route')}.json"


def _write_plain(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")


def cmd_init_basic(cfg: dict, name: str, force: bool) -> int:
    """为某个 upstream 生成随机 Basic 口令（只打印路径，不打印口令）。"""
    route = _route_by_name(cfg, name)
    if route is None:
        print(f"refusing: no upstream named {name!r}")
        return 1
    path = _route_secret_path(route)
    if os.path.exists(path) and not force:
        print(f"refusing: {path} already exists (use --force to rotate)")
        return 1
    password = auth.generate_password(24)
    record = {
        "version": 1,
        "user": route.get("auth_user", "haydn"),
        "password": auth.hash_password(password),
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    secret_dir = os.path.dirname(path) or "."
    os.makedirs(secret_dir, exist_ok=True)
    os.chmod(secret_dir, 0o700)
    auth.save_secret(path, record)
    plain_path = path.replace(".json", "-password.txt")
    _write_plain(plain_path, password)
    print(f"secret written: {path}")
    print(f"plaintext written: {plain_path} (chmod 600; 读取后请删除)")
    return 0


def cmd_set_basic(cfg: dict, name: str) -> int:
    """从 stdin 读取口令并写入指定 upstream 的 Basic 凭据文件。"""
    route = _route_by_name(cfg, name)
    if route is None:
        print(f"refusing: no upstream named {name!r}")
        return 1
    password = sys.stdin.readline().rstrip("\n")
    if len(password) < 12:
        print("refusing: password must be at least 12 characters")
        return 1
    path = _route_secret_path(route)
    record = auth.load_secret(path) or {}
    record.update(
        {
            "version": 1,
            "user": record.get("user", route.get("auth_user", "haydn")),
            "password": auth.hash_password(password),
            "updated": datetime.now(timezone.utc).isoformat(),
        }
    )
    secret_dir = os.path.dirname(path) or "."
    os.makedirs(secret_dir, exist_ok=True)
    os.chmod(secret_dir, 0o700)
    auth.save_secret(path, record)
    print(f"basic credential updated: {path}")
    return 0


def cmd_check(cfg: dict) -> int:
    print(f"listen: {cfg['_listen_host']}:{cfg['_listen_port']}")
    print(f"console: {cfg['console']['path']}")
    print(f"secret: {cfg['secret_file']} (exists={os.path.exists(cfg['secret_file'])})")
    lan_cfg = cfg["lan"]
    print(
        f"lan: enabled={bool(lan_cfg.get('enabled'))} listen={lan_cfg.get('listen')} "
        f"interval={lan_cfg.get('probe_interval_seconds')}s ttl={lan_cfg.get('ticket_ttl_seconds')}s "
        f"subnet_file={lan_cfg.get('subnet_file')}"
    )
    snapshot = lan_access.detect(str(lan_cfg.get("probe_target", "223.5.5.5")))
    print(
        f"lan-detect: ok={snapshot['ok']} iface={snapshot.get('lan_iface') or '-'} "
        f"ip={snapshot.get('lan_ip') or '-'} subnet={snapshot.get('lan_subnet') or '-'} "
        f"updated={snapshot.get('updated_at')} error={snapshot.get('error') or '-'}"
    )
    for route in cfg.get("upstreams", []):
        state = "on " if route.get("enabled", True) else "off"
        print(
            f"route[{state}] {route.get('path')} -> {route.get('upstream')} "
            f"strip={route.get('strip_prefix', False)} host={route.get('preserve_host', False)} "
            f"ws={route.get('websocket', False)} auth={route.get('auth', 'none')}"
        )
    for name, path in sorted(cfg.get("logs", {}).items()):
        print(f"log[{name}]: {path} exists={os.path.exists(path)}")
    return 0


def cmd_export_credentials(cfg: dict, path: str) -> int:
    """导出 Bitwarden 可导入 CSV（600）；只打印行数与路径，不打印任何口令。"""
    text, rows = credentials.build_csv(cfg)
    credentials.write_file(path, text)
    print(f"exported {rows} rows to {path} (mode 600; contains plaintext secrets, delete after copying)")
    print("vault: " + json.dumps(credentials.vault_status(cfg), ensure_ascii=False))
    return 0


def cmd_vault_sync(cfg: dict) -> int:
    """按 credentials.services[] 同步写入密码库并回读；只打印条目名与结果。"""
    result = credentials.sync_all(cfg)
    for item in result.get("results", []):
        state = "skipped" if item.get("skipped") else ("ok" if item.get("ok") else "fail")
        print(f"{item.get('id')}: {state} {item.get('error', '')}".rstrip())
    print("vault_sync: " + ("ok" if result.get("ok") else "failed") + " " + result.get("error", ""))
    return 0 if result.get("ok") else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Haydn Web Gateway")
    parser.add_argument("--config", default="/etc/haydn-console/gateway.json")
    parser.add_argument("--init-admin", action="store_true", help="生成初始口令与密钥（仅首次）")
    parser.add_argument("--force", action="store_true", help="配合 --init-admin 覆盖已有密钥")
    parser.add_argument("--set-password", action="store_true", help="从 stdin 读取新口令并更新")
    parser.add_argument("--init-basic", metavar="ROUTE", help="为指定 upstream 生成随机 Basic 口令")
    parser.add_argument("--set-basic", metavar="ROUTE", help="从 stdin 读取口令并更新指定 upstream 的 Basic 凭据")
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--export-credentials", metavar="PATH", help="导出 Bitwarden CSV（600，含明文，复制后删除）")
    parser.add_argument("--vault-sync", action="store_true", help="按 credentials.services 写入密码库并回读")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    cfg = load_config(args.config)

    if args.init_admin:
        return cmd_init_admin(cfg, args.force)
    if args.set_password:
        return cmd_set_password(cfg)
    if args.init_basic:
        return cmd_init_basic(cfg, args.init_basic, args.force)
    if args.set_basic:
        return cmd_set_basic(cfg, args.set_basic)
    if args.check_config:
        return cmd_check(cfg)
    if args.export_credentials:
        return cmd_export_credentials(cfg, args.export_credentials)
    if args.vault_sync:
        return cmd_vault_sync(cfg)

    server = build_server(cfg)
    lan_server = None
    try:
        lan_server = build_lan_server(cfg, server)
    except OSError as exc:  # 端口被占用等：局域网入口降级，公网入口继续服务
        LOG.error("lan listener disabled (%s)", exc)
    LOG.info("listening on %s:%s", cfg["_listen_host"], cfg["_listen_port"])
    if lan_server is not None:
        threading.Thread(
            target=lan_server.serve_forever,
            kwargs={"poll_interval": 1},
            name="lan-http",
            daemon=True,
        ).start()
        LOG.info("lan listening on %s:%s", cfg["lan"]["_listen_host"], cfg["lan"]["_listen_port"])
    try:
        server.serve_forever(poll_interval=1)
    except KeyboardInterrupt:
        LOG.info("stopping")
    finally:
        server.server_close()
        if lan_server is not None:
            lan_server.server_close()
        monitor = getattr(server, "lan_monitor", None)
        if monitor is not None:
            monitor.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
