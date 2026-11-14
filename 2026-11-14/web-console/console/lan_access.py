#!/usr/bin/env python3
"""局域网入口：网段探测、网段文件/防火墙同步、一次性票据（仅标准库）。

设计要点：
- 探测不写死任何网段：先用 `ip route get <target>` 取默认路由接口，再读该接口的 IPv4 掩码；
  失败时回退到第一个 scope global 的非 loopback 接口。设备换 Wi-Fi / DHCP 换地址后自动跟随。
- 防火墙：网关只把探测到的 CIDR 原子写入 run/lan-subnet；宿主侧 lan-fw-loop.sh 读取该文件，
  幂等维护 `18090/tcp 仅放行该网段` 的 iptables 规则。文件缺失或内容非法即删除放行规则（fail closed）。
- 票据：HMAC 短期令牌（默认 60s、单次、绑定签发时的设备网段）；进程内 nonce 去重。
  失败原因可区分：expired / replay / subnet-mismatch / bad-signature。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import subprocess
import threading
import time
from datetime import datetime, timezone

LOG = logging.getLogger("haydn.lan")

TICKET_VERSION = "v1"
_ADDR_RE = re.compile(r"\binet (\d+\.\d+\.\d+\.\d+)/(\d+)")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def _iface_ipv4(iface: str) -> tuple[str, int] | None:
    code, out = _run(["ip", "-4", "-o", "addr", "show", "dev", iface])
    if code != 0:
        return None
    for line in out.splitlines():
        m = _ADDR_RE.search(line)
        if m:
            return m.group(1), int(m.group(2))
    return None


def _default_iface(target: str) -> str:
    code, out = _run(["ip", "route", "get", target])
    if code == 0 and out:
        tokens = out.splitlines()[0].split()
        if "dev" in tokens:
            idx = tokens.index("dev")
            if idx + 1 < len(tokens):
                return tokens[idx + 1]
    return ""


def _fallback_iface() -> str:
    code, out = _run(["ip", "-4", "-o", "addr", "show"])
    if code != 0:
        return ""
    for line in out.splitlines():
        if "scope global" not in line or " inet " not in line:
            continue
        m = re.match(r"^\d+:\s+(\S+)\s+", line)
        if not m:
            continue
        name = m.group(1).split("@", 1)[0]
        if name == "lo":
            continue
        return name
    return ""


def detect(target: str = "223.5.5.5") -> dict:
    """探测当前默认路由接口的 IPv4 地址与网段；失败返回 ok=False（不猜、不写死）。"""
    iface = _default_iface(target) or _fallback_iface()
    snapshot = {"ok": False, "lan_ip": "", "lan_prefix": 0, "lan_subnet": "", "lan_iface": iface,
                "updated_at": now_utc(), "error": ""}
    if not iface:
        snapshot["error"] = "no default-route interface"
        return snapshot
    addr = _iface_ipv4(iface)
    if addr is None:
        snapshot["error"] = f"no IPv4 address on {iface}"
        return snapshot
    ip_text, prefix = addr
    try:
        network = ipaddress.ip_network(f"{ip_text}/{prefix}", strict=False)
    except ValueError as exc:
        snapshot["error"] = f"bad address {ip_text}/{prefix}: {exc}"
        return snapshot
    snapshot.update(
        {
            "ok": True,
            "lan_ip": ip_text,
            "lan_prefix": prefix,
            "lan_subnet": str(network),
            "lan_iface": iface,
        }
    )
    return snapshot


def in_subnet(client_ip: str, subnet: str) -> bool:
    try:
        return ipaddress.ip_address(client_ip) in ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return False


class LanMonitor:
    """后台探测；网段变化时原子更新网段文件（供宿主侧防火墙同步）。"""

    def __init__(self, cfg: dict) -> None:
        self.interval = max(5, int(cfg.get("probe_interval_seconds", 30)))
        self.target = str(cfg.get("probe_target", "223.5.5.5"))
        self.subnet_file = str(cfg.get("subnet_file", ""))
        self._lock = threading.Lock()
        self._snapshot = detect(self.target)
        self._write_subnet_file(self._snapshot)
        self._stop = threading.Event()

    def _write_subnet_file(self, snapshot: dict) -> None:
        if not self.subnet_file:
            return
        try:
            os.makedirs(os.path.dirname(self.subnet_file) or ".", exist_ok=True)
            if snapshot.get("ok") and snapshot.get("lan_subnet"):
                tmp = self.subnet_file + ".tmp"
                with open(tmp, "w", encoding="ascii") as fh:
                    fh.write(snapshot["lan_subnet"] + "\n")
                os.replace(tmp, self.subnet_file)
            elif os.path.exists(self.subnet_file):
                os.remove(self.subnet_file)
        except OSError as exc:
            LOG.warning("subnet file update failed: %s", exc)

    def probe_once(self) -> dict:
        snapshot = detect(self.target)
        with self._lock:
            before = self._snapshot.get("lan_subnet", "")
            self._snapshot = snapshot
        if snapshot.get("lan_subnet") != before:
            LOG.info("LAN change: %s -> %s (%s)", before or "-", snapshot.get("lan_subnet") or "-",
                     snapshot.get("lan_iface") or "-")
        self._write_subnet_file(snapshot)
        return snapshot

    def snapshot(self, max_age: float | None = None) -> dict:
        with self._lock:
            snap = dict(self._snapshot)
        if max_age is not None and not snap.get("ok"):
            return self.probe_once()
        return snap

    def refresh_if_stale(self, seconds: float) -> dict:
        with self._lock:
            updated = self._snapshot.get("updated_at", "")
        try:
            age = time.time() - datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
        except ValueError:
            age = seconds + 1
        if age >= seconds:
            return self.probe_once()
        return self.snapshot()

    def start(self) -> None:
        thread = threading.Thread(target=self._loop, name="lan-monitor", daemon=True)
        thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.probe_once()
            except Exception:  # 探测失败不影响网关主流程
                LOG.exception("lan probe failed")

    def stop(self) -> None:
        self._stop.set()


class TicketManager:
    """短期一次性票据：HMAC 签名 + nonce 去重 + 来源网段校验。"""

    def __init__(self, key: bytes, ttl_seconds: int = 60) -> None:
        self._key = hmac.new(key, b"haydn-lan-ticket", hashlib.sha256).digest()
        self.ttl = max(5, int(ttl_seconds))
        self._used: dict[str, float] = {}
        self._lock = threading.Lock()

    def _sign(self, body: str) -> str:
        return hmac.new(self._key, body.encode("ascii"), hashlib.sha256).hexdigest()

    def _prune(self, now: float) -> None:
        for nonce in [n for n, exp in self._used.items() if exp < now]:
            self._used.pop(nonce, None)

    def issue(self, subnet: str, next_path: str = "/console/") -> str:
        payload = {
            "v": TICKET_VERSION,
            "exp": int(time.time()) + self.ttl,
            "nonce": secrets.token_urlsafe(12),
            "sn": subnet,
            "next": next_path,
        }
        body = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).decode("ascii").rstrip("=")
        return f"{body}.{self._sign(body)}"

    def redeem(self, ticket: str, client_ip: str, current_subnet: str) -> tuple[str, dict]:
        """返回 (status, payload)；status ∈ ok/expired/replay/subnet-mismatch/bad-signature。"""
        if not ticket or "." not in ticket:
            return "bad-signature", {}
        body, _, signature = ticket.rpartition(".")
        if not hmac.compare_digest(signature, self._sign(body)):
            return "bad-signature", {}
        try:
            padded = body + "=" * (-len(body) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
            expires = int(payload["exp"])
            nonce = str(payload["nonce"])
            subnet = str(payload["sn"])
        except (ValueError, KeyError, TypeError):
            return "bad-signature", {}
        now = time.time()
        if expires < now:
            return "expired", payload
        if not in_subnet(client_ip, subnet) or (current_subnet and not in_subnet(client_ip, current_subnet)):
            return "subnet-mismatch", payload
        with self._lock:
            self._prune(now)
            if nonce in self._used:
                return "replay", payload
            self._used[nonce] = now + self.ttl + 60
        return "ok", payload
