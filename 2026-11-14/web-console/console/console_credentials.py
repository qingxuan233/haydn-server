#!/usr/bin/env python3
"""凭据清单、一次性导出与轮换（单一事实来源）。

设计约束：
- 服务凭据定义只来自 gateway.json 的 `credentials.services`；CSV 与密码库条目
  都从同一份定义生成，避免各写一套后漂移；
- 明文只读设备侧 600 文件；审计/日志/异常信息一律不含口令；
- 轮换流程：生成 -> 写入 -> 重载/回读 -> 生效验证 -> 一次性返回 -> 记录时间戳；
  任一步失败按快照回滚，并如实报告失败步骤；
- Vaultwarden 主密码端到端加密，服务端只能提示用户在客户端修改条目，不能代改。
"""

from __future__ import annotations

import base64
import csv
import http.client
import io
import json
import os
import secrets
import subprocess
import time
from datetime import datetime, timezone

import auth

CSV_HEADER = ["folder", "name", "login_uri", "login_username", "login_password", "notes"]
DEFAULT_STATE = {"version": 1, "services": {}}


class RotationError(RuntimeError):
    """轮换失败（消息中不得包含口令）。"""


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- 文件 ----------
def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def read_plain(path: str) -> str:
    return _read_text(path).strip() if path else ""


def write_plain(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    os.chmod(path, 0o600)


def write_file(path: str, data: str | bytes) -> None:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(raw)
    os.chmod(path, 0o600)


def _snapshot(path: str) -> bytes | None:
    if not path:
        return None
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _restore(path: str, data: bytes | None) -> None:
    if not path:
        return
    if data is None:
        try:
            os.unlink(path)
        except OSError:
            pass
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.chmod(path, 0o600)


# ---------- 状态 ----------
def load_state(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("services"), dict):
            return data
    except (OSError, ValueError):
        pass
    return dict(DEFAULT_STATE)


def save_state(path: str, state: dict) -> None:
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    write_file(tmp, json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


# ---------- 密码库状态（与“上次轮换”分开记录） ----------
def vault_reason(error: str) -> str:
    """把底层错误折叠成不含口令/条目内容的短原因，用于页面展示。"""
    text = (error or "").strip()
    if not text:
        return ""
    mapping = (
        ("未找到客户端", "写库客户端不可用"),
        ("client unavailable", "写库客户端不可用"),
        ("设置服务器地址失败", "写库客户端不可用（服务器地址配置失败）"),
        ("缺少主密码/账号文件", "缺少主密码文件"),
        ("登录失败", "写库登录失败（主密码不匹配或账号不存在）"),
        ("解锁失败", "写库解锁失败"),
        ("创建密码库 folder 失败", "创建密码库分组失败"),
        ("设备侧无明文口令", "设备侧无明文口令"),
        ("未启用", "密码库写入未启用"),
    )
    for key, value in mapping:
        if key in text:
            return value
    return text[:120]


def stamp_vault_state(state: dict, service_id: str, ok: bool, skipped: bool, error: str) -> None:
    """记录“最近一次密码库写入/同步”的结果；成功即清除历史失败标记。"""
    entry = state.setdefault("services", {}).setdefault(str(service_id), {})
    entry["vault"] = {
        "at": now_utc(),
        "ok": bool(ok),
        "skipped": bool(skipped),
        "error": "" if ok else vault_reason(error),
    }


# ---------- 定义解析 ----------
def services(cfg: dict) -> list[dict]:
    return list((cfg.get("credentials") or {}).get("services") or [])


def find_service(cfg: dict, service_id: str) -> dict | None:
    for svc in services(cfg):
        if svc.get("id") == service_id:
            return svc
    return None


def _account_file(path: str) -> dict:
    info: dict[str, str] = {}
    for line in _read_text(path).splitlines():
        key, sep, value = line.partition("=") if "=" in line else line.partition(":")
        if sep:
            info[key.strip().lower()] = value.strip()
    email = info.get("email") or info.get("username") or ""
    password = info.get("password") or info.get("master_password") or ""
    return {"email": email, "password": password}


def service_password(svc: dict) -> str:
    if svc.get("plain_file"):
        value = read_plain(svc["plain_file"])
        if value:
            return value
    if svc.get("account_file"):
        value = _account_file(svc["account_file"]).get("password", "")
        if value:
            return value
    return str(svc.get("password_literal") or "")


def service_username(svc: dict) -> str:
    if svc.get("username"):
        return str(svc["username"])
    if svc.get("account_file"):
        return _account_file(svc["account_file"]).get("email", "")
    return ""


# ---------- CSV ----------
def _csv_rows(cfg: dict, state: dict) -> list[list[str]]:
    folder_default = str((cfg.get("credentials") or {}).get("folder") or "haydn-server")
    rows: list[list[str]] = []
    for svc in services(cfg):
        password = service_password(svc)
        notes = str(svc.get("notes") or "")
        rotated = ((state.get("services") or {}).get(svc.get("id", "")) or {}).get("rotated_at")
        if rotated:
            notes = (notes + "；" if notes else "") + f"上次轮换 {rotated}"
        if not password:
            notes = (notes + "；" if notes else "") + "设备侧暂无明文口令，需先在控制台轮换一次"
        rows.append(
            [
                str(svc.get("folder") or folder_default),
                str(svc.get("name") or svc.get("id") or ""),
                str(svc.get("login_uri") or ""),
                service_username(svc),
                password,
                notes,
            ]
        )
    return rows


def build_csv(cfg: dict) -> tuple[str, int]:
    state = load_state(str((cfg.get("credentials") or {}).get("state_file") or ""))
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    rows = _csv_rows(cfg, state)
    writer.writerows(rows)
    return buf.getvalue(), len(rows)


# ---------- 一次性导出令牌 ----------
class ExportTokens:
    """进程内一次性令牌：下载一次即失效；TTL 到期同样失效。"""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl = max(10, int(ttl_seconds))
        self._tokens: dict[str, float] = {}

    def issue(self) -> tuple[str, int]:
        self._prune()
        token = secrets.token_urlsafe(24)
        self._tokens[token] = time.time() + self.ttl
        return token, self.ttl

    def redeem(self, token: str) -> bool:
        self._prune()
        expires = self._tokens.pop(token, None)
        return bool(expires and expires >= time.time())

    def _prune(self) -> None:
        now = time.time()
        for key in [k for k, v in self._tokens.items() if v < now]:
            self._tokens.pop(key, None)


# ---------- HTTP 生效验证 ----------
def _request(host: str, port: int, method: str, path: str, headers: dict | None = None,
             body: bytes | None = None, timeout: int = 10) -> int:
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        return conn.getresponse().status
    except OSError:
        return 0
    finally:
        conn.close()


def _basic_header(user: str, password: str) -> dict:
    raw = f"{user}:{password}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def _verify_console(cfg: dict, password: str) -> tuple[bool, str]:
    path = cfg["console"]["path"] + "/api/login"
    body = json.dumps({"password": password}).encode("utf-8")
    code = _request(
        cfg["_listen_host"], cfg["_listen_port"], "POST", path,
        {"Content-Type": "application/json", "X-Haydn-Client": "console"}, body,
    )
    return code == 200, ("console 连接失败" if code == 0 else f"console login HTTP {code}")


def _verify_basic(route: dict, user: str, password: str) -> tuple[bool, str]:
    host, _, port_text = str(route.get("upstream", "")).rpartition(":")
    port = int(port_text or 0)
    headers = _basic_header(user, password)
    headers["Depth"] = "0"
    # rclone 以 --baseurl 服务时只接受带前缀的路径（如 /dav/），不能再用根路径探测
    prefix = "/" + str(route.get("path", "/")).strip("/")
    path = "/" if prefix == "/" else prefix + "/"
    code = _request(host or "127.0.0.1", port, "PROPFIND", path, headers)
    return code in (200, 207), ("webdav 连接失败" if code == 0 else f"webdav propfind HTTP {code}")


def _verify_forgejo(port: int, user: str, password: str) -> tuple[bool, str]:
    headers = _basic_header(user, password)
    code = _request("127.0.0.1", port, "GET", "/api/v1/user", headers)
    return code == 200, ("forgejo 连接失败" if code == 0 else f"forgejo api HTTP {code}")


def _forgejo_port(cfg: dict, svc: dict) -> int:
    name = svc.get("upstream_name") or "forgejo"
    for route in cfg.get("upstreams", []):
        if route.get("name") == name:
            return int(str(route.get("upstream", "")).rpartition(":")[2] or 0)
    return 18083


def _change_forgejo(svc: dict, password: str) -> None:
    binary = svc.get("binary") or "/opt/haydn/bin/forgejo"
    conf = svc.get("server_config") or "/etc/haydn/forgejo/app.ini"
    cmd = [binary, "admin", "user", "change-password", "-c", conf,
           "--username", str(svc.get("username") or ""), "--password", password,
           "--must-change-password=false"]
    run_as = svc.get("run_as")
    if run_as:
        cmd = ["setpriv", "--reuid", run_as, "--regid", run_as, "--clear-groups"] + cmd
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RotationError(f"forgejo 命令执行失败：{type(exc).__name__}") from exc
    if proc.returncode != 0:
        tail = proc.stdout.decode("utf-8", "replace").strip().splitlines()[-3:]
        raise RotationError("forgejo 改密失败：" + " | ".join(tail)[:300])


# ---------- 密码库（bw CLI） ----------
def vault_status(cfg: dict) -> dict:
    vcfg = (cfg.get("credentials") or {}).get("vault") or {}
    if not vcfg.get("enabled"):
        return {"enabled": False, "ready": False, "reason": "密码库写入未启用（credentials.vault.enabled=false）"}
    client = vcfg.get("client") or "/usr/bin/bw"
    master = _account_file(str(vcfg.get("master_file") or ""))
    if not os.path.exists(client):
        return {"enabled": True, "ready": False, "reason": f"未找到客户端 {client}"}
    if not master.get("email") or not master.get("password"):
        return {"enabled": True, "ready": False, "reason": "设备侧缺少主密码/账号文件"}
    return {"enabled": True, "ready": True, "reason": ""}


def _bw(cfg: dict, args: list[str], session: str = "", payload: dict | None = None) -> tuple[int, str]:
    vcfg = (cfg.get("credentials") or {}).get("vault") or {}
    client = vcfg.get("client") or "/usr/bin/bw"
    appdata = vcfg.get("appdata_dir") or "/srv/haydn/run/bw-cli"
    os.makedirs(appdata, mode=0o700, exist_ok=True)
    env = os.environ.copy()
    env["BITWARDENCLI_APPDATA_DIR"] = appdata
    env["HOME"] = appdata
    extra_path = str(vcfg.get("extra_path") or "").strip()
    if extra_path:
        env["PATH"] = extra_path + ":" + env.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    for key, value in (vcfg.get("extra_env") or {}).items():
        env[str(key)] = str(value)
    env.pop("BW_SESSION", None)
    if session:
        env["BW_SESSION"] = session
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    try:
        proc = subprocess.run([client] + args, input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=int(vcfg.get("timeout_seconds", 60)),
                              env=env, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 124, "client unavailable or timeout"
    out = proc.stdout.decode("utf-8", "replace").strip()
    err = proc.stderr.decode("utf-8", "replace").strip()
    return proc.returncode, out or err


def _vault_session(cfg: dict) -> tuple[str, str]:
    """返回 (session, 错误)。调用方负责 lock。"""
    vcfg = (cfg.get("credentials") or {}).get("vault") or {}
    account = _account_file(str(vcfg.get("master_file") or ""))
    server = str(vcfg.get("server") or "http://127.0.0.1:18084")
    if not account.get("email") or not account.get("password"):
        return "", "设备侧缺少主密码/账号文件"
    code, out = _bw(cfg, ["status"])
    authenticated = code == 0 and "unauthenticated" not in out.replace(" ", "")
    if not authenticated:
        code, _ = _bw(cfg, ["config", "server", server])
        if code != 0:
            return "", "设置服务器地址失败"
        code, out = _bw(cfg, ["login", account["email"], account["password"], "--raw"])
        if code != 0:
            return "", "登录失败（主密码不匹配或账号不存在）"
    code, out = _bw(cfg, ["unlock", account["password"], "--raw"])
    if code != 0 or not out:
        return "", "解锁失败（主密码不匹配或客户端未登录）"
    return out.splitlines()[-1], ""


def _b64json(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def _vault_folder(cfg: dict, session: str) -> str:
    name = str(((cfg.get("credentials") or {}).get("vault") or {}).get("folder") or "haydn-server")
    code, out = _bw(cfg, ["list", "folders"], session)
    if code == 0 and out:
        try:
            for folder in json.loads(out):
                if folder.get("name") == name and folder.get("id"):
                    return str(folder["id"])
        except ValueError:
            pass
    code, out = _bw(cfg, ["create", "folder", _b64json({"name": name})], session)
    if code != 0:
        raise RotationError("创建密码库 folder 失败")
    try:
        return str(json.loads(out).get("id"))
    except ValueError as exc:
        raise RotationError("创建密码库 folder 返回不可解析") from exc


def _vault_upsert_in(cfg: dict, session: str, folder_id: str, svc: dict, password: str) -> tuple[bool, str]:
    """在已解锁会话内写入单条并回读；调用方负责 lock。"""
    name = str(svc.get("name") or svc.get("id"))
    uri = str(svc.get("login_uri") or "")
    username = service_username(svc)
    code, out = _bw(cfg, ["list", "items", "--search", name], session)
    if code != 0:
        return False, "读取密码库条目失败"
    try:
        items = json.loads(out or "[]")
    except ValueError:
        return False, "密码库条目列表不可解析"
    existing = next((i for i in items if i.get("name") == name), None)
    if existing:
        code, out = _bw(cfg, ["get", "item", str(existing.get("id"))], session)
        if code != 0:
            return False, "读取条目详情失败"
        try:
            item = json.loads(out)
        except ValueError:
            return False, "条目详情不可解析"
        item.setdefault("login", {})
        item["folderId"] = folder_id
        item["login"]["password"] = password
        item["login"]["username"] = username
        code, _ = _bw(cfg, ["edit", "item", str(item.get("id")), _b64json(item)], session)
        if code != 0:
            return False, "更新条目失败"
        item_id = str(item.get("id"))
    else:
        item = {
            "folderId": folder_id, "type": 1, "name": name,
            "notes": str(svc.get("notes") or ""), "favorite": False,
            "login": {"username": username, "password": password,
                      "uris": ([{"uri": uri}] if uri else [])},
        }
        code, out = _bw(cfg, ["create", "item", _b64json(item)], session)
        if code != 0:
            return False, "创建条目失败"
        try:
            item_id = str(json.loads(out).get("id"))
        except ValueError:
            return False, "创建条目返回不可解析"
    code, out = _bw(cfg, ["get", "item", item_id], session)
    if code != 0:
        return False, "回读条目失败"
    try:
        if str(json.loads(out).get("login", {}).get("password", "")) != password:
            return False, "回读条目口令不一致"
    except ValueError:
        return False, "回读条目不可解析"
    return True, ""


def _vault_upsert(cfg: dict, svc: dict, password: str) -> tuple[bool, str]:
    session, error = _vault_session(cfg)
    if not session:
        return False, error
    try:
        folder_id = _vault_folder(cfg, session)
        return _vault_upsert_in(cfg, session, folder_id, svc, password)
    except RotationError as exc:
        return False, str(exc)
    finally:
        _bw(cfg, ["lock"], session)


def sync_all(cfg: dict) -> dict:
    """按 credentials.services[] 逐条写入密码库并回读；一次解锁、最后 lock。

    每次运行都把每个服务的“密码库同步”状态刷成本次结果（成功即清除失败标记），
    与“上次轮换”分开记录。
    """
    state_path = str((cfg.get("credentials") or {}).get("state_file") or "")
    state = load_state(state_path) if state_path else None
    session, error = _vault_session(cfg)
    if not session:
        reason = vault_reason(error)
        if state is not None:
            for svc in services(cfg):
                stamp_vault_state(state, str(svc.get("id") or ""), False, False, error)
            save_state(state_path, state)
        return {"ok": False, "error": reason, "results": []}
    results: list[dict] = []
    try:
        folder_id = _vault_folder(cfg, session)
        for svc in services(cfg):
            password = service_password(svc)
            if not password:
                results.append({"id": svc.get("id"), "ok": False, "skipped": True,
                                "error": "设备侧无明文口令"})
                if state is not None:
                    stamp_vault_state(state, str(svc.get("id") or ""), False, True,
                                      "设备侧无明文口令")
                continue
            ok, detail = _vault_upsert_in(cfg, session, folder_id, svc, password)
            results.append({"id": svc.get("id"), "ok": ok, "skipped": False,
                            "error": vault_reason(detail)})
            if state is not None:
                stamp_vault_state(state, str(svc.get("id") or ""), ok, False, detail)
    except RotationError as exc:
        if state is not None:
            save_state(state_path, state)
        return {"ok": False, "error": vault_reason(str(exc)), "results": results}
    finally:
        _bw(cfg, ["lock"], session)
    if state is not None:
        save_state(state_path, state)
    return {"ok": all(r["ok"] or r.get("skipped") for r in results), "error": "", "results": results}


# ---------- 轮换 ----------
def _console_apply(cfg: dict, svc: dict, password: str) -> None:
    path = svc.get("secret_file") or cfg["secret_file"]
    secret = auth.load_secret(path) or {}
    secret["password"] = auth.hash_password(password)
    secret["updated"] = now_utc()
    auth.save_secret(path, secret)
    if svc.get("plain_file"):
        write_plain(svc["plain_file"], password)


def _console_reload(cfg: dict, servers: list) -> None:
    path = cfg["secret_file"]
    secret = auth.load_secret(path)
    if not secret:
        return
    for server in servers:
        current = getattr(server, "secret", None)
        if isinstance(current, dict):
            current.clear()
            current.update(secret)


def _basic_apply(cfg: dict, svc: dict, password: str) -> None:
    path = svc["secret_file"]
    record = auth.load_secret(path) or {}
    record.update({
        "version": 1,
        "user": record.get("user") or svc.get("username") or "haydn",
        "password": auth.hash_password(password),
        "updated": now_utc(),
    })
    secret_dir = os.path.dirname(path) or "."
    os.makedirs(secret_dir, exist_ok=True)
    os.chmod(secret_dir, 0o700)
    auth.save_secret(path, record)
    if svc.get("plain_file"):
        write_plain(svc["plain_file"], password)


def rotate(cfg: dict, service_id: str, servers: list | None = None) -> dict:
    svc = find_service(cfg, service_id)
    if svc is None:
        return {"ok": False, "error": f"未知服务 {service_id}"}
    mode = str(svc.get("rotate") or "none")
    if mode == "none":
        return {"ok": False, "error": "该服务不支持服务端轮换（见说明）", "service": service_id}
    length = int(((cfg.get("credentials") or {}).get("password_length")) or 24)
    password = auth.generate_password(length)
    old_plain = read_plain(str(svc.get("plain_file") or ""))
    secret_path = str(svc.get("secret_file") or "")
    old_secret = _snapshot(secret_path) if secret_path else None
    old_plain_bytes = _snapshot(str(svc.get("plain_file") or "")) if svc.get("plain_file") else None
    steps: list[dict] = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"name": name, "ok": ok, "detail": detail})

    try:
        if mode == "console":
            _console_apply(cfg, svc, password)
            _console_reload(cfg, servers or [])
            step("写入凭据文件", True)
            record = auth.load_secret(secret_path or cfg["secret_file"])
            ok = bool(record) and auth.verify_password(record["password"], password)
            step("回读凭据文件", ok)
            if not ok:
                raise RotationError("回读校验失败")
            ok, detail = _verify_console(cfg, password)
            step("登录验证", ok, detail)
            if not ok:
                raise RotationError("新口令登录验证失败")
        elif mode.startswith("basic:"):
            route_name = mode.split(":", 1)[1]
            route = next((r for r in cfg.get("upstreams", []) if r.get("name") == route_name), None)
            if route is None:
                raise RotationError(f"未找到 upstream {route_name}")
            _basic_apply(cfg, svc, password)
            step("写入凭据文件", True)
            ok, detail = _verify_basic(route, service_username(svc), password)
            step("Basic 验证", ok, detail)
            if not ok:
                raise RotationError("新口令 Basic 验证失败")
        elif mode == "forgejo":
            _change_forgejo(svc, password)
            if svc.get("plain_file"):
                write_plain(svc["plain_file"], password)
            step("写入服务账号", True)
            ok, detail = _verify_forgejo(_forgejo_port(cfg, svc), str(svc.get("username") or ""), password)
            step("API 验证", ok, detail)
            if not ok:
                raise RotationError("新口令 API 验证失败")
        else:
            raise RotationError(f"未实现的轮换方式 {mode}")
    except RotationError as exc:
        rolled = _rollback(cfg, svc, mode, old_secret, old_plain_bytes, old_plain, servers or [])
        status = "已回滚" if rolled else "回滚未完成（旧明文未知，请人工核对）"
        state_path = str((cfg.get("credentials") or {}).get("state_file") or "")
        if state_path:
            state = load_state(state_path)
            entry = state.setdefault("services", {}).setdefault(service_id, {})
            entry["rotation"] = {"at": now_utc(), "ok": False, "error": str(exc)[:120]}
            save_state(state_path, state)
        return {"ok": False, "service": service_id, "error": str(exc), "steps": steps,
                "rolled_back": rolled, "rollback": status}

    state_path = str((cfg.get("credentials") or {}).get("state_file") or "")
    vault_result = {"ok": False, "skipped": True, "error": ""}
    if ((cfg.get("credentials") or {}).get("vault") or {}).get("enabled"):
        ok, error = _vault_upsert(cfg, svc, password)
        vault_result = {"ok": ok, "skipped": False, "error": error}
        step("写入密码库", ok, vault_reason(error))
    else:
        vault_result = {"ok": False, "skipped": True,
                        "error": "密码库写入未启用（credentials.vault.enabled=false）"}
    if state_path:
        state = load_state(state_path)
        entry = state.setdefault("services", {}).setdefault(service_id, {})
        entry["rotated_at"] = now_utc()
        entry["rotation"] = {"at": now_utc(), "ok": True, "error": ""}
        stamp_vault_state(state, service_id, vault_result["ok"], vault_result["skipped"],
                          vault_result.get("error", ""))
        save_state(state_path, state)
    return {
        "ok": True,
        "service": service_id,
        "name": svc.get("name") or service_id,
        "password": password,
        "steps": steps,
        "vault": vault_result,
        "vault_error": vault_reason(vault_result.get("error", "")),
        "rotated_at": now_utc(),
    }


def _rollback(cfg: dict, svc: dict, mode: str, old_secret: bytes | None,
              old_plain_bytes: bytes | None, old_plain: str, servers: list) -> bool:
    restored = True
    try:
        if mode == "console":
            _restore(str(svc.get("secret_file") or cfg["secret_file"]), old_secret)
            _restore(str(svc.get("plain_file") or ""), old_plain_bytes)
            _console_reload(cfg, servers)
        elif mode.startswith("basic:"):
            _restore(str(svc.get("secret_file") or ""), old_secret)
            _restore(str(svc.get("plain_file") or ""), old_plain_bytes)
        elif mode == "forgejo":
            if not old_plain:
                return False
            _change_forgejo(svc, old_plain)
            _restore(str(svc.get("plain_file") or ""), old_plain_bytes)
    except (RotationError, OSError):
        restored = False
    return restored


def summary(cfg: dict) -> dict:
    state = load_state(str((cfg.get("credentials") or {}).get("state_file") or ""))
    items = []
    for svc in services(cfg):
        entry = (state.get("services") or {}).get(svc.get("id", "")) or {}
        rotation = entry.get("rotation") if isinstance(entry.get("rotation"), dict) else {}
        raw_vault = entry.get("vault")
        if isinstance(raw_vault, dict):
            vault_state = "ok" if raw_vault.get("ok") else ("skipped" if raw_vault.get("skipped") else "fail")
            vault_at = str(raw_vault.get("at") or "")
            vault_error = str(raw_vault.get("error") or "")
        else:
            # 兼容旧状态（vault 为 "ok"/"fail"/"skipped" 字符串）
            vault_state = str(raw_vault or "")
            if vault_state not in ("ok", "fail", "skipped"):
                vault_state = ""
            vault_at = ""
            vault_error = vault_reason(str(entry.get("vault_error") or ""))
        items.append({
            "id": svc.get("id"),
            "name": svc.get("name") or svc.get("id"),
            "username": service_username(svc),
            "rotate": svc.get("rotate") or "none",
            "rotatable": (svc.get("rotate") or "none") != "none",
            "has_password": bool(service_password(svc)),
            "rotated_at": rotation.get("at") or entry.get("rotated_at", ""),
            "rotation_ok": rotation.get("ok"),
            "rotation_error": str(rotation.get("error") or ""),
            "vault": vault_state,
            "vault_at": vault_at,
            "vault_error": vault_error,
            "notes": svc.get("notes", ""),
        })
    return {"services": items, "vault": vault_status(cfg)}
