#!/usr/bin/env python3
"""鉴权、会话与登录限流（标准库实现，无第三方依赖）。

- 口令只以 PBKDF2-HMAC-SHA256 派生值存在于设备侧 secret.json（600），仓库不含任何口令；
- 会话 cookie 为 HMAC 签名令牌，密钥随机生成并只存设备；
- 登录失败按全局窗口限流（链路经 stunnel，远端地址恒为 loopback，无法按 IP 区分）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import deque

PBKDF2_ITERATIONS = 200_000
SESSION_COOKIE = "haydn_session"
TOKEN_VERSION = "v1"


def hash_password(password: str, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> dict:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {"salt": salt.hex(), "hash": digest.hex(), "iterations": iterations}


def verify_password(record: dict, password: str) -> bool:
    try:
        salt = bytes.fromhex(record["salt"])
        expected = record["hash"]
        iterations = int(record["iterations"])
    except (KeyError, ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest.hex(), expected)


def load_secret(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def save_secret(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def generate_password(length: int = 20) -> str:
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class SessionManager:
    """HMAC 签名的无状态会话令牌。"""

    def __init__(self, key: bytes, ttl_seconds: int) -> None:
        self._key = key
        self.ttl = ttl_seconds

    def issue(self) -> str:
        expires = int(time.time()) + self.ttl
        nonce = secrets.token_urlsafe(12)
        message = f"{TOKEN_VERSION}.{expires}.{nonce}"
        signature = hmac.new(self._key, message.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{message}.{signature}"

    def verify(self, token: str | None) -> bool:
        if not token:
            return False
        parts = token.split(".")
        if len(parts) != 4:
            return False
        version, expires, nonce, signature = parts
        if version != TOKEN_VERSION:
            return False
        try:
            if int(expires) < time.time():
                return False
        except ValueError:
            return False
        message = f"{version}.{expires}.{nonce}"
        expected = hmac.new(self._key, message.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)


class LoginLimiter:
    """全局失败窗口 + 锁定期；进程内状态即可（单实例）。"""

    def __init__(self, max_failures: int, window_seconds: int, lock_seconds: int) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self.lock_seconds = lock_seconds
        self._failures: deque[float] = deque()
        self._locked_until = 0.0

    def _prune(self, now: float) -> None:
        while self._failures and now - self._failures[0] > self.window:
            self._failures.popleft()

    def blocked_for(self) -> int:
        remaining = int(self._locked_until - time.time())
        return remaining if remaining > 0 else 0

    def record_failure(self) -> None:
        now = time.time()
        self._prune(now)
        self._failures.append(now)
        if len(self._failures) >= self.max_failures:
            self._locked_until = now + self.lock_seconds
            self._failures.clear()

    def reset(self) -> None:
        self._failures.clear()
        self._locked_until = 0.0


def parse_basic(header: str | None) -> tuple[str, str] | None:
    """解析 Authorization: Basic，返回 (user, password)；格式不对返回 None。"""
    if not header or not header.lower().startswith("basic "):
        return None
    try:
        raw = base64.b64decode(header.split(None, 1)[1].strip())
    except (IndexError, ValueError):
        return None
    text = raw.decode("utf-8", "replace")
    if ":" not in text:
        return None
    user, _, password = text.partition(":")
    return user, password


def verify_basic(record: dict | None, username: str, password: str) -> bool:
    if not record:
        return False
    if not hmac.compare_digest(str(record.get("user", "")), username):
        return False
    return verify_password(record.get("password") or {}, password)


class BasicSecretCache:
    """按 mtime 缓存的 Basic 凭据文件读取，避免每请求都读盘。"""

    def __init__(self) -> None:
        self._path = ""
        self._mtime = 0.0
        self._record: dict | None = None

    def load(self, path: str) -> dict | None:
        try:
            mtime = os.stat(path).st_mtime
        except OSError:
            self._path, self._record = path, None
            return None
        if path != self._path or mtime != self._mtime:
            self._path, self._mtime = path, mtime
            self._record = load_secret(path)
        return self._record


def parse_cookies(header: str | None) -> dict[str, str]:
    cookies: dict[str, str] = {}
    if not header:
        return cookies
    for part in header.split(";"):
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        cookies[name.strip()] = value.strip()
    return cookies
