#!/usr/bin/env python3
"""控制台动作层：全部为白名单动作，禁止任意 shell、禁止文件系统浏览。

- 服务启停：只对配置中的服务名执行固定参数 supervisorctl，不拼接 shell；
- 日志：只读配置中登记的日志文件尾；
- 备份：只写一个约定的触发文件，由设备侧 backup-loop 执行真实脚本；
- 证书/磁盘/内存/遥测：只读。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

MAX_LOG_BYTES = 128 * 1024
ALLOWED_VERBS = {"start", "stop", "restart"}


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace").strip()
    except FileNotFoundError:
        return 127, f"missing executable: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def supervisor_status(sup: dict) -> list[dict]:
    code, out = _run([sup["ctl"], "-c", sup["conf"], "status"], timeout=15)
    services = []
    for line in out.splitlines():
        m = re.match(r"^(\S+)\s+(\S+)\s*(.*)$", line.strip())
        if not m:
            continue
        name, state, rest = m.group(1), m.group(2), m.group(3)
        pid = None
        pid_match = re.search(r"pid (\d+)", rest)
        if pid_match:
            pid = int(pid_match.group(1))
        uptime = None
        up_match = re.search(r"uptime ([0-9:]+)", rest)
        if up_match:
            uptime = up_match.group(1)
        services.append(
            {
                "name": name,
                "state": state,
                "pid": pid,
                "uptime": uptime,
                "detail": rest.strip(),
                "actionable": name in set(sup.get("services", [])),
            }
        )
    if code != 0 and not services:
        services.append({"name": "(supervisorctl)", "state": "ERROR", "detail": out, "actionable": False})
    return services


def service_action(sup: dict, name: str, verb: str) -> tuple[bool, str]:
    if verb not in ALLOWED_VERBS:
        return False, f"refused: verb {verb!r} not allowed"
    if name not in set(sup.get("services", [])):
        return False, f"refused: service {name!r} not in whitelist"
    code, out = _run([sup["ctl"], "-c", sup["conf"], verb, name], timeout=40)
    return code == 0, out or f"exit {code}"


def tail_file(path: str, lines: int = 200) -> str:
    lines = max(1, min(int(lines), 2000))
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        start = max(0, size - MAX_LOG_BYTES)
        fh.seek(start)
        data = fh.read()
    text = data.decode("utf-8", "replace")
    if start > 0:
        text = text.split("\n", 1)[-1]
        text = "[... 仅显示末尾 128 KiB ...]\n" + text
    chunks = text.splitlines()
    return "\n".join(chunks[-lines:])


def cert_info(path: str) -> dict:
    code, out = _run(["openssl", "x509", "-in", path, "-noout", "-enddate", "-subject"], timeout=10)
    if code != 0:
        return {"ok": False, "error": out or "openssl failed"}
    end_raw = None
    subject = None
    for line in out.splitlines():
        if line.startswith("notAfter="):
            end_raw = line.split("=", 1)[1].strip()
        elif line.startswith("subject="):
            subject = line.split("=", 1)[1].strip()
    if not end_raw:
        return {"ok": False, "error": "notAfter not found"}
    try:
        expires = parsedate_to_datetime(end_raw)
    except (TypeError, ValueError):
        return {"ok": False, "error": f"unparsable date: {end_raw}"}
    now = datetime.now(timezone.utc)
    seconds = (expires - now).total_seconds()
    return {
        "ok": True,
        "subject": subject,
        "not_after": expires.astimezone(timezone.utc).isoformat(),
        "days_left": int(seconds // 86400),
        "expired": seconds <= 0,
    }


def system_overview() -> dict:
    data: dict = {}
    try:
        with open("/proc/uptime", "r", encoding="ascii") as fh:
            data["uptime_seconds"] = float(fh.read().split()[0])
    except (OSError, ValueError, IndexError):
        data["uptime_seconds"] = None
    try:
        with open("/proc/meminfo", "r", encoding="ascii") as fh:
            mem = {}
            for line in fh:
                key, _, value = line.partition(":")
                mem[key] = int(value.strip().split()[0]) * 1024
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", 0)
        data["memory"] = {
            "total": total,
            "available": available,
            "used": max(total - available, 0),
            "used_percent": round((total - available) / total * 100, 1) if total else None,
        }
    except (OSError, ValueError):
        data["memory"] = None
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        data["disk"] = {
            "total": total,
            "free": free,
            "used": total - free,
            "used_percent": round((total - free) / total * 100, 1) if total else None,
        }
    except (OSError, AttributeError):
        data["disk"] = None
    try:
        data["load"] = [round(x, 2) for x in os.getloadavg()]
    except (OSError, AttributeError):
        data["load"] = None
    return data


def _read_text(path: str, limit: int = 256 * 1024) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read(limit)


def telemetry_summary(csv_path: str) -> dict:
    try:
        text = _read_text(csv_path, 8 * 1024 * 1024)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {"ok": False, "error": "no samples"}
    header = lines[0].split(",")
    rows = []
    for line in lines[1:]:
        values = line.split(",")
        if len(values) != len(header):
            continue
        rows.append(dict(zip(header, values)))
    if not rows:
        return {"ok": False, "error": "no parsable samples"}
    last = rows[-1]
    uptimes = []
    reboots = 0
    for row in rows:
        try:
            value = float(row.get("uptime_s", "0"))
        except ValueError:
            continue
        if uptimes and value < uptimes[-1] - 60:
            reboots += 1
        uptimes.append(value)
    up_rows = sum(1 for r in rows if r.get("supervisord") == "up" and r.get("chroot_http") == "up")
    return {
        "ok": True,
        "samples": len(rows),
        "first_ts": rows[0].get("ts"),
        "last_ts": last.get("ts"),
        "reboots": reboots,
        "availability_percent": round(up_rows / len(rows) * 100, 2),
        "last": {
            "uptime_s": last.get("uptime_s"),
            "load1": last.get("load1"),
            "mem_avail_kb": last.get("mem_avail_kb"),
            "batt_level": last.get("batt_level"),
            "batt_status": last.get("batt_status"),
            "batt_temp_raw": last.get("batt_temp_raw"),
            "thermal_max_raw": last.get("thermal_max_raw"),
            "supervisord": last.get("supervisord"),
            "chroot_http": last.get("chroot_http"),
        },
    }


def soak_summary(soak_file: str, telemetry: dict) -> dict:
    """只读解析 soak 起点文件；验收口径以文件与 CASE-003 为准，控制台不宣称通过。"""
    try:
        text = _read_text(soak_file)
    except OSError:
        return {"ok": False}
    info: dict = {"ok": True}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        token = value.strip().split()[0] if value.strip() else ""
        if key in ("start_utc", "expected_end_utc", "active_slot"):
            info[key] = token
        elif key == "csv_lines_at_start":
            try:
                info["csv_lines_at_start"] = int(token)
            except ValueError:
                pass
    start = info.get("start_utc")
    end = info.get("expected_end_utc")
    if start:
        try:
            started = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            info["elapsed_seconds"] = int(elapsed)
            if end:
                expected = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                info["remaining_seconds"] = int((expected - datetime.now(timezone.utc)).total_seconds())
                info["target_seconds"] = int((expected - started).total_seconds())
            base = info.get("csv_lines_at_start")
            if telemetry.get("ok") and base is not None:
                # csv_lines_at_start 含表头，数据行数 = base - 1
                info["samples_since_start"] = max(telemetry["samples"] - (base - 1), 0)
        except ValueError:
            info["ok"] = False
    return info


def trigger_backup(path: str) -> tuple[bool, str]:
    """写触发文件（原子替换）；真实备份由设备侧 backup-loop 在下一个轮询周期执行。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"requested_at": datetime.now(timezone.utc).isoformat()}))
    os.replace(tmp, path)
    return True, f"trigger written: {path}"


def secrets_summary(directory: str) -> list[dict]:
    """只暴露凭据文件的存在性与轮换时间，不读取/返回任何口令或哈希。"""
    items: list[dict] = []
    try:
        names = sorted(n for n in os.listdir(directory) if n.endswith(".json"))
    except OSError:
        return items
    for name in names:
        path = os.path.join(directory, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        updated = None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                updated = json.load(fh).get("updated")
        except (OSError, ValueError, AttributeError):
            updated = None
        items.append(
            {
                "name": name[: -len(".json")],
                "exists": True,
                "updated": updated or datetime.fromtimestamp(st.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "mode": oct(st.st_mode & 0o777)[2:],
            }
        )
    return items


def recent_backup(backup_log: str) -> dict:
    try:
        tail = tail_file(backup_log, 60)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    lines = [ln for ln in tail.splitlines() if ln.strip()]
    last_done = next((ln for ln in reversed(lines) if "DONE ok" in ln), None)
    last_fail = next((ln for ln in reversed(lines) if " FAIL " in ln), None)
    last_start = next((ln for ln in reversed(lines) if "START device-side backup" in ln), None)
    return {
        "ok": True,
        "last_start": last_start,
        "last_done": last_done,
        "last_fail": last_fail,
        "now": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def uptime_from_proc() -> float | None:
    try:
        with open("/proc/uptime", "r", encoding="ascii") as fh:
            return float(fh.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)
