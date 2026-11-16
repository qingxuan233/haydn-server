"""DSH 上游凭据注入：让控制台网关代浏览器与 DSH Web UI 完成鉴权。

背景：DSH（`dsh web`）对**每个请求**校验一个 authority 绑定的签名 cookie
（`dsh-auth-<b64url(sha256(authority))>`，值 = `v1.<b64url(payload)>.<b64url(hmac)>`）。
令牌（launch token）是每进程随机的，但**签名密钥是持久**的（存于 DSH 凭据库
`DSH_HOME/.credentials.yaml` 的 `client-connection/browser-session` 记录），
因此网关可以据此为当前请求的 authority 铸造 cookie，使用户在控制台登录后
直接访问 `/ui` 而不必再手动打开 DSH 打印的 token URL。

安全约束：
- 只读密钥，**绝不**打印/记录 secret 或 cookie 值；
- 只在控制台会话鉴权（`auth: session`）通过后由网关内部注入，浏览器不参与；
- 上游若不可用/密钥缺失，注入失败应作为显式 5xx 暴露，而不是静默让用户撞 DSH 的 401。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time

COOKIE_PREFIX = "dsh-auth-"
AUTH_RECORD_KEY = "client-connection/browser-session"
SECRET_BYTES = 32
COOKIE_PAYLOAD_VERSION = 1
COOKIE_TTL_DAYS_DEFAULT = 30


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def read_secret(path: str) -> bytes:
    """从 DSH 凭据库读取 browser-session 签名密钥（32 字节）。

    凭据文件结构稳定（`version`/`records`/`<record key>`/`kind`/`payload`/`version`/`secret`），
    逐行解析即可，不引入 yaml 依赖；格式不符时抛 ValueError 而不是猜测。
    """
    inside = False
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith(AUTH_RECORD_KEY + ":"):
                inside = True
                continue
            if inside:
                if line.startswith((" ", "\t")):
                    match = re.match(r"secret:\s*(\S+)\s*$", stripped)
                    if match:
                        value = match.group(1).strip("\"'")
                        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
                        if len(raw) != SECRET_BYTES:
                            raise ValueError(
                                f"DSH browser-session secret 长度异常：{len(raw)}（应为 {SECRET_BYTES}）"
                            )
                        return raw
                elif stripped:
                    break
    raise ValueError(f"未在 {AUTH_RECORD_KEY} 记录中找到 secret")


def cookie_name(authority: str) -> str:
    """DSH 的 cookie 名对 authority 做 sha256，协议/端口差异会得到不同名字。"""
    return COOKIE_PREFIX + b64url(hashlib.sha256(authority.encode("utf-8")).digest())


def mint(secret: bytes, authority: str, max_age_days: int = COOKIE_TTL_DAYS_DEFAULT) -> str:
    """铸造与 DSH 校验规则一致的 cookie 值（只含 version=1 浏览器 payload）。"""
    now = int(time.time() * 1000)
    payload = {
        "version": COOKIE_PAYLOAD_VERSION,
        "authority": authority,
        "issuedAt": now,
        "expiresAt": now + max_age_days * 86_400_000,
    }
    body = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest()
    return f"v{COOKIE_PAYLOAD_VERSION}.{body}.{b64url(signature)}"


class DshCookieMinter:
    """按 authority 铸造 cookie；密钥按文件 mtime 缓存，避免每请求读盘。"""

    def __init__(self, credentials: str, max_age_days: int = COOKIE_TTL_DAYS_DEFAULT) -> None:
        self.credentials = credentials
        self.max_age_days = max_age_days
        self._secret: bytes | None = None
        self._stamp: tuple[int, int] | None = None

    def _load(self) -> bytes:
        try:
            stat = os.stat(self.credentials)
        except OSError as exc:
            raise ValueError(f"DSH 凭据文件不可读：{self.credentials}") from exc
        stamp = (stat.st_mtime_ns, stat.st_size)
        if self._secret is not None and stamp == self._stamp:
            return self._secret
        secret = read_secret(self.credentials)
        self._secret, self._stamp = secret, stamp
        return secret

    def cookie_pair(self, authority: str) -> str:
        """返回可直接放进 Cookie 请求头的 `name=value`。"""
        if not authority:
            raise ValueError("缺少 authority（网关未拿到转发 Host）")
        return f"{cookie_name(authority)}={mint(self._load(), authority, self.max_age_days)}"

    @staticmethod
    def merge_cookie_header(existing: str, injected: str) -> str:
        """合并 Cookie 头：先移除浏览器带来的旧 dsh-auth-*，再追加本次注入的那条。"""
        kept = []
        for item in (existing or "").split(";"):
            item = item.strip()
            if not item or item.startswith(COOKIE_PREFIX):
                continue
            kept.append(item)
        kept.append(injected)
        return "; ".join(kept)
