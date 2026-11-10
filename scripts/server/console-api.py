#!/usr/bin/env python3
"""手机服务器控制台 API v2（零依赖，仅 Python 标准库）。

参考成熟项目的模式：
- Cockpit：系统概览 + 服务 + 日志
- Portainer：服务状态与启停/重启（带操作审计）
- Uptime Kuma：探活、延迟、历史可用性
- Netdata/Grafana：实时采样与趋势
- Homepage/Dashy：统一仪表盘入口

路由：
  GET  /api/health
  GET  /api/sysinfo        实时系统指标（CPU/内存/磁盘/温度/电量/网络/运行时长）
  GET  /api/history?n=    实时采样环（默认 120，最大 360）
  GET  /api/metrics?n=    历史 metrics.jsonl（看门狗每分钟写入）
  GET  /api/checks        服务探活（并行、短缓存）
  GET  /api/services      supervisord 服务状态 + 健康 + 端口
  GET  /api/overview      聚合上述数据（前端一次请求）
  GET  /api/backups
  GET  /api/logs?name=&lines=   tail 服务日志（局域网或管理 token）
  GET  /api/meta          前端需要的元信息（是否可管理、版本）
  POST /api/action        管理操作（必须有 X-Console-Token）
       {"action":"restart|start|stop|doctor|backup","service":"api"}
"""
import base64
import glob
import hashlib
import hmac
import ipaddress
import json
import os
import platform
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

START = time.time()
PORT = int(os.environ.get("API_PORT", "8000"))
API_VERSION = "2.0"

LOG_DIR = "/root/server/logs"
CONF = "/root/server/etc/supervisord.conf"
CONF_GLOB = "/root/server/etc/conf.d/*.conf"
TOKEN_FILE = "/root/server/etc/console-action.token"
AUDIT_FILE = os.path.join(LOG_DIR, "console-actions.jsonl")
OPS_AUDIT = os.path.join(LOG_DIR, "ops-audit.jsonl")
VAULT_FILE = "/root/server/etc/vault.enc"
VAULT_KEY = "/root/server/etc/vault.key"
VAULT_AUDIT = os.path.join(LOG_DIR, "vault-actions.jsonl")
VAULT_MAX_ENTRIES = 500
WATCH_METRICS = os.path.join(LOG_DIR, "metrics.jsonl")
TERMUX_METRICS = "/hosthome/server-metrics.txt"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

SERVICE_PORTS = {
    "api": 8000,
    "fileui": 8085,
    "frpc": None,
    "gitea": 3000,
    "nginx": 8080,
    "runner": None,
    "sshd": 2222,
    "syncthing": 8384,
    "webdav": 8083,
    "dsh": 3081,
    "dsh-login": 3082,
}

# 特殊日志映射（不来自 supervisord program 配置）
EXTRA_LOGS = {
    "supervisord": "supervisord.log",
    "watch": "watch.log",
    "nginx-access": "nginx_access.log",
    "nginx-error": "nginx_site_error.log",
    "boot": "boot.log",
}

_hist_lock = threading.Lock()
HISTORY = deque(maxlen=360)
LATEST = {}
_sampler_lock = threading.Lock()
_cache_lock = threading.Lock()
_checks_cache = {"at": 0.0, "data": None}
_services_cache = {"at": 0.0, "data": None}
_backups_cache = {"at": 0.0, "data": None}
_cert_cache = {}
_lanip_cache = {"at": 0.0, "ip": None}
_last_action_at = 0.0


# ----------------------------- 基础读取 -----------------------------
def read_text(path, limit=None):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            if limit:
                return "".join(fh.readlines()[-limit:])
            return fh.read()
    except OSError:
        return None


def local_lan_ip():
    """当前 Wi-Fi 局域网 IP（通过默认路由套接字取本地地址，60 秒缓存）。

    proot/App UID 读不到 netlink、/proc/net，但可以向公网/网关发起 TCP，
    getsockname() 会给出当前路由选中的本地地址（即 wlan0 的 DHCP IP）。
    """
    now = time.time()
    with _cache_lock:
        if _lanip_cache["ip"] and now - _lanip_cache["at"] < 60:
            return _lanip_cache["ip"]
    for target in (("47.97.70.99", 1210), ("223.5.5.5", 53), ("1.1.1.1", 53)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.2)
        try:
            sock.connect(target)
            ip = sock.getsockname()[0]
            if ip and ip not in ("0.0.0.0", "127.0.0.1"):
                with _cache_lock:
                    _lanip_cache["at"], _lanip_cache["ip"] = now, ip
                return ip
        except OSError:
            continue
        finally:
            try:
                sock.close()
            except OSError:
                pass
    return None

def termux_metrics():
    """读取 Termux 侧采集的 uptime / top 数据（proot 内无法直接读 /proc/stat、/proc/uptime）。"""
    text = read_text(TERMUX_METRICS) or ""
    if not text:
        return {}
    out = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    try:
        if os.path.isfile(TERMUX_METRICS) and time.time() - os.path.getmtime(TERMUX_METRICS) > 120:
            return {}
    except OSError:
        return {}
    m = re.search(r"up\s+(\d+)\s+day[s]?,\s+(\d+):(\d+)", out.get("uptime_line", ""))
    if m:
        out["uptime_s"] = int(m.group(1)) * 86400 + int(m.group(2)) * 3600 + int(m.group(3)) * 60
    else:
        m = re.search(r"up\s+(\d+)\s+min", out.get("uptime_line", ""))
        if m:
            out["uptime_s"] = int(m.group(1)) * 60
        else:
            m = re.search(r"up\s+(\d+):(\d+)", out.get("uptime_line", ""))
            if m:
                out["uptime_s"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60
    m = re.search(r"up\s+(\d+)\s+hrs?,\s+(\d+)\s+min", out.get("uptime_line", ""))
    if m and "uptime_s" not in out:
        out["uptime_s"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60
    cpu_line = out.get("cpu_line", "")
    total = re.search(r"(\d+)%cpu", cpu_line)
    idle = re.search(r"(\d+)%idle", cpu_line)
    if total and idle and int(total.group(1)) > 0:
        out["cpu_pct"] = round((1 - int(idle.group(1)) / int(total.group(1))) * 100, 1)
    return out


def parse_meminfo():
    out = {}
    data = read_text("/proc/meminfo") or ""
    for line in data.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            parts = v.split()
            if parts:
                out[k] = int(parts[0])
    return out


def parse_proc_net_dev():
    data = read_text("/proc/net/dev")
    if data is None:
        return None, None
    rx = tx = 0
    for line in data.splitlines()[2:]:
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name = name.strip()
        cols = rest.split()
        if name == "lo" or len(cols) < 9:
            continue
        try:
            rx += int(cols[0])
            tx += int(cols[8])
        except ValueError:
            pass
    return rx, tx


def parse_cpu_stat():
    data = read_text("/proc/stat") or ""
    parts = data.splitlines()[0].split() if data else []
    if len(parts) < 5 or not parts[0].startswith("cpu"):
        return None
    try:
        vals = [int(x) for x in parts[1:9]]
    except ValueError:
        return None
    total = sum(vals)
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return total, idle


def temperature_c():
    best = None
    for pattern in ("/sys/class/thermal/thermal_zone*/temp", "/sys/class/hwmon/hwmon*/temp*_input"):
        for path in glob.glob(pattern):
            try:
                with open(path) as fh:
                    raw = int(fh.read().strip())
                val = raw / 1000.0 if raw > 1500 else float(raw)
                if -20 < val < 150 and (best is None or val > best):
                    best = val
            except (OSError, ValueError):
                continue
    return round(best, 1) if best is not None else None


def battery_info():
    level = status = None
    for base in ("/sys/class/power_supply/battery", "/sys/class/power_supply/Battery"):
        cap = read_text(base + "/capacity")
        if cap:
            try:
                level = int(cap.strip())
            except ValueError:
                level = None
        st = read_text(base + "/status")
        if st:
            status = st.strip()
        if level is not None:
            break
    return level, status


def uptime_s():
    try:
        with open("/proc/uptime") as fh:
            return int(float(fh.read().split()[0]))
    except OSError:
        pass
    tm = termux_metrics()
    return tm.get("uptime_s")


def sysinfo():
    now = time.time()
    mem = parse_meminfo()
    total = mem.get("MemTotal", 0)
    avail = mem.get("MemAvailable", 0)
    used_pct = round((total - avail) / total * 100, 1) if total else None
    du = shutil.disk_usage("/")
    try:
        load = os.getloadavg()
    except OSError:
        load = (0.0, 0.0, 0.0)
    level, status = battery_info()
    tm = termux_metrics()
    up = uptime_s()
    with _hist_lock:
        latest = dict(LATEST)
    return {
        "host": platform.node(),
        "arch": platform.machine(),
        "kernel": platform.release(),
        "lan_ip": local_lan_ip(),
        "cpus": os.cpu_count(),
        "uptime_s": up,
        "boot_at": datetime.fromtimestamp(now - up, timezone.utc).isoformat(timespec="seconds") if up else None,
        "load1": round(load[0], 2),
        "load5": round(load[1], 2),
        "load15": round(load[2], 2),
        "cpu_pct": latest.get("cpu_pct") if latest.get("cpu_pct") is not None else tm.get("cpu_pct"),
        "mem_total_mb": int(round(total / 1024)) if total else None,
        "mem_available_mb": int(round(avail / 1024)) if avail else None,
        "mem_total_mb_legacy": int(round(total / 1024)) if total else None,
        "disk_total_gb": round(du.total / 2**30, 1),
        "disk_free_gb": round(du.free / 2**30, 1),
        "disk_used_pct": round(du.used / du.total * 100, 1) if du.total else None,
        "temperature_c": latest.get("temperature_c", temperature_c()),
        "battery_level": latest.get("battery_level", level),
        "battery_status": latest.get("battery_status", status),
        "net_rx_kbps": latest.get("net_rx_kbps"),
        "net_tx_kbps": latest.get("net_tx_kbps"),
    }


# ----------------------------- 采样线程 -----------------------------
def _fmt_iso(ts=None):
    return datetime.fromtimestamp(ts or time.time(), timezone.utc).isoformat(timespec="seconds")


def sampler_loop(interval=10.0):
    prev_stat = parse_cpu_stat()
    prev_net = parse_proc_net_dev()
    prev_net_at = time.time()
    while True:
        time.sleep(interval)
        try:
            stat = parse_cpu_stat()
            if stat and prev_stat:
                dt = stat[0] - prev_stat[0]
                di = stat[1] - prev_stat[1]
                cpu = round((1 - di / dt) * 100, 1) if dt > 0 else 0.0
            else:
                cpu = None
            rx, tx = parse_proc_net_dev()
            elapsed = max(0.5, time.time() - prev_net_at)
            level, status = battery_info()
            tm = termux_metrics()
            mem = parse_meminfo()
            total = mem.get("MemTotal", 0)
            avail = mem.get("MemAvailable", 0)
            sample = {
                "ts": _fmt_iso(),
                "cpu_pct": tm.get("cpu_pct") if tm else cpu,
                "mem_used_pct": round((total - avail) / total * 100, 1) if total else None,
                "mem_available_mb": round(avail / 1024) if avail else None,
                "disk_free_gb": round(shutil.disk_usage("/").free / 2**30, 1),
                "temperature_c": temperature_c(),
                "battery_level": level,
                "battery_status": status,
                "net_rx_kbps": round(max(0, rx - prev_net[0]) / elapsed / 1024, 1) if rx is not None and prev_net is not None else None,
                "net_tx_kbps": round(max(0, tx - prev_net[1]) / elapsed / 1024, 1) if tx is not None and prev_net is not None else None,
            }
            with _hist_lock:
                LATEST.update(sample)
                HISTORY.append(sample)
            prev_stat, prev_net, prev_net_at = stat, (rx, tx), time.time()
        except Exception:
            continue


def history(n=120):
    n = max(1, min(int(n), 360))
    with _hist_lock:
        return list(HISTORY)[-n:]


# ----------------------------- 探活/HTTP -----------------------------
def probe_url(url, timeout=4):
    t0 = time.time()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request(url, headers={"User-Agent": "dsh-console-probe/2.0"})
        with urlopen(req, timeout=timeout, context=ctx) as r:
            r.read(32)
            return {"code": r.status, "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        code = getattr(e, "code", 0) or 0
        return {"code": code, "ms": int((time.time() - t0) * 1000)}


def probe_tcp(host, port, timeout=3):
    t0 = time.time()
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        return {"code": 200, "ms": int((time.time() - t0) * 1000)}
    except OSError:
        return {"code": 0, "ms": int((time.time() - t0) * 1000)}
    finally:
        try:
            sock.close()
        except OSError:
            pass


def webdav_password():
    text = read_text("/root/server/webdav.yaml") or ""
    m = re.search(r"^\s*password:\s*(\S+)\s*$", text, re.M)
    return m.group(1).strip("'\"") if m else ""


def probe_webdav():
    token = base64.b64encode(f"admin:{webdav_password()}".encode()).decode()
    t0 = time.time()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request("http://127.0.0.1:8083/", method="PROPFIND",
                      headers={"Authorization": "Basic " + token, "Depth": "0"})
        with urlopen(req, timeout=4, context=ctx) as r:
            r.read(32)
            return {"code": r.status, "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        code = getattr(e, "code", 0) or 0
        return {"code": code, "ms": int((time.time() - t0) * 1000)}


def cert_days(host, port, timeout=4):
    key = f"{host}:{port}"
    now = time.time()
    with _cache_lock:
        cached = _cert_cache.get(key)
        if cached and now - cached[0] < 300:
            return cached[1]
    days = None
    try:
        pem = ssl.get_server_certificate((host, int(port)), timeout=timeout)
        out = subprocess.run(
            ["openssl", "x509", "-noout", "-enddate"],
            input=pem.encode(), capture_output=True, timeout=5,
        ).stdout.decode("utf-8", "ignore").strip()
        if out.startswith("notAfter="):
            dt = datetime.strptime(out.split("=", 1)[1], "%b %d %H:%M:%S %Y %Z")
            days = max(0, int((dt - datetime.utcnow()).total_seconds() // 86400))
    except Exception:
        days = None
    with _cache_lock:
        _cert_cache[key] = (now, days)
    return days


def checks():
    now = time.time()
    with _cache_lock:
        if _checks_cache["data"] and now - _checks_cache["at"] < 4:
            return _checks_cache["data"]
    jobs = {
        "api": ("url", "http://127.0.0.1:8000/api/health"),
        "nginx": ("url", "http://127.0.0.1:8080/health"),
        "gitea": ("url", "http://127.0.0.1:3000/api/healthz"),
        "fileui": ("url", "http://127.0.0.1:8085/login"),
        "webdav": ("webdav", None),
        "syncthing": ("tcp", ("127.0.0.1", 8384)),
        "https": ("url", "https://127.0.0.1:8443/health"),
        "public": ("url", "http://47.97.70.99:48108/health"),
        "public_https": ("url", "https://47.97.70.99:44904/health"),
        "dsh": ("url", "http://127.0.0.1:3081/"),
        "dsh_login": ("tcp", ("127.0.0.1", 3082)),
        "sshd": ("tcp", ("127.0.0.1", 2222)),
        "ssh_public": ("tcp", ("47.97.70.99", 13872)),
        "supervisord": ("tcp", ("127.0.0.1", 9001)),
        "cert_local_days": ("cert", ("127.0.0.1", 8443)),
        "cert_public_days": ("cert", ("47.97.70.99", 44904)),
    }
    data = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = {}
        for name, (kind, arg) in jobs.items():
            if kind == "url":
                futs[name] = pool.submit(probe_url, arg)
            elif kind == "tcp":
                futs[name] = pool.submit(probe_tcp, arg[0], arg[1])
            elif kind == "cert":
                futs[name] = pool.submit(cert_days, arg[0], arg[1])
            else:
                futs[name] = pool.submit(probe_webdav)
        for name, fut in futs.items():
            try:
                val = fut.result(timeout=10)
                data[name] = val if name.startswith("cert_") else val
            except Exception:
                data[name] = None if name.startswith("cert_") else {"code": 0, "ms": 0}
    data["updated"] = _fmt_iso()
    with _cache_lock:
        _checks_cache["at"], _checks_cache["data"] = now, data
    return data


# ----------------------------- supervisor/服务 -----------------------------
def supervisor_status():
    now = time.time()
    with _cache_lock:
        if _services_cache["data"] and now - _services_cache["at"] < 3:
            return _services_cache["data"]
    try:
        out = subprocess.run(
            ["supervisorctl", "-c", CONF, "status"],
            capture_output=True, text=True, timeout=6,
        ).stdout
    except Exception:
        out = ""
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\S+)\s+(\S+)\s+(.*)$", line)
        if not m:
            continue
        name, state, rest = m.group(1), m.group(2), m.group(3)
        pid = None
        up = None
        pm = re.search(r"pid\s+(\d+)", rest)
        um = re.search(r"uptime\s+([0-9:]+)", rest)
        if pm:
            pid = int(pm.group(1))
        if um:
            up = um.group(1)
        rows.append({"name": name, "state": state, "pid": pid, "uptime": up})
    with _cache_lock:
        _services_cache["at"], _services_cache["data"] = now, rows
    return rows


def service_log_map():
    text = read_text(CONF) or ""
    for path in glob.glob(CONF_GLOB):
        text += "\n" + (read_text(path) or "")
    mapping = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^\[program:([^\]]+)\]", line.strip())
        if m:
            current = m.group(1).strip()
            continue
        m = re.match(r"^\s*stdout_logfile\s*=\s*(.+)$", line)
        if m and current:
            logfile = m.group(1).strip().strip('"')
            if logfile.startswith(LOG_DIR):
                mapping[current] = logfile
            current = None
    for name, filename in EXTRA_LOGS.items():
        mapping[name] = os.path.join(LOG_DIR, filename)
    return mapping


def service_names():
    return [r["name"] for r in supervisor_status()]


def services():
    status = {r["name"]: r for r in supervisor_status()}
    chk = checks()
    health_map = {
        "api": "api",
        "fileui": "fileui",
        "gitea": "gitea",
        "nginx": "nginx",
        "webdav": "webdav",
        "syncthing": "syncthing",
        "sshd": "sshd",
        "dsh": "dsh",
        "dsh-login": "dsh_login",
    }
    logs = service_log_map()
    out = []
    for name, row in status.items():
        h = chk.get(health_map.get(name)) if health_map.get(name) in chk else None
        out.append({
            "name": name,
            "state": row["state"],
            "pid": row["pid"],
            "uptime": row["uptime"],
            "port": SERVICE_PORTS.get(name),
            "health": h,
            "log": bool(logs.get(name)),
        })
    return out


# ----------------------------- 备份/指标/日志 -----------------------------
def list_backups(limit=10):
    now = time.time()
    with _cache_lock:
        cached = _backups_cache.get("data")
        if cached and now - _backups_cache.get("at", 0) < 10:
            return cached[:limit]
    items = []
    for d in ("/sdcard/DSH/backups", "/root/server/backups"):
        for f in glob.glob(d + "/*.enc"):
            try:
                st = os.stat(f)
            except OSError:
                continue
            items.append({
                "name": os.path.basename(f),
                "mb": round(st.st_size / 1048576, 2),
                "at": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
            })
    items.sort(key=lambda x: x["at"], reverse=True)
    with _cache_lock:
        _backups_cache["at"], _backups_cache["data"] = now, items
    return items[:limit]


def load_metrics(n=60):
    n = max(1, min(int(n), 288))
    try:
        with open(WATCH_METRICS, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 128 * 1024))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-n:]:
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def load_ops_audit(n=20):
    n = max(1, min(int(n), 200))
    try:
        with open(OPS_AUDIT, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 96 * 1024))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-n:]:
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def read_log(name, lines=200):
    mapping = service_log_map()
    path = mapping.get(name)
    if not path or not os.path.isfile(path):
        return None, "没有这个服务的日志"
    lines = max(10, min(int(lines or 200), 2000))
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 512 * 1024))
            data = f.read().decode("utf-8", "ignore")
        return ANSI_RE.sub("", "\n".join(data.splitlines()[-lines:])), None
    except OSError as e:
        return None, f"读取失败: {e}"


# ----------------------------- 管理操作 -----------------------------
def action_token():
    return (read_text(TOKEN_FILE) or "").strip()


def valid_token(value):
    expected = action_token()
    if not expected or not value:
        return False
    try:
        return secrets.compare_digest(value, expected)
    except Exception:
        return False


def write_audit(entry):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _vault_master_key():
    data = read_text(VAULT_KEY)
    if data:
        try:
            raw = bytes.fromhex(data.strip())
            if len(raw) == 32:
                return raw
        except ValueError:
            pass
    raw = secrets.token_bytes(32)
    os.makedirs(os.path.dirname(VAULT_KEY), exist_ok=True)
    try:
        os.unlink(VAULT_KEY)
    except OSError:
        pass
    fd = os.open(VAULT_KEY, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, raw.hex().encode())
    finally:
        os.close(fd)
    return raw


def _vault_keys():
    master = _vault_master_key()
    enc = hmac.new(master, b"dsh-vault-enc", hashlib.sha256).digest()
    mac = hmac.new(master, b"dsh-vault-mac", hashlib.sha256).digest()
    return enc, mac


def _openssl_vault(args, data):
    p = subprocess.run(["openssl"] + args, input=data, capture_output=True, timeout=15)
    if p.returncode != 0:
        raise RuntimeError("openssl error: " + (p.stderr or b"").decode("utf-8", "ignore")[:160])
    return p.stdout


def _vault_encrypt_text(text):
    enc, mac = _vault_keys()
    iv = secrets.token_bytes(16)
    ct = _openssl_vault(["enc", "-aes-256-cbc", "-K", enc.hex(), "-iv", iv.hex(), "-nosalt"], text.encode("utf-8"))
    tag = hmac.new(mac, iv + ct, hashlib.sha256).hexdigest()
    return {"v": 1, "iv": iv.hex(), "ct": base64.b64encode(ct).decode("ascii"), "mac": tag}


def _vault_decrypt_text(wrapper):
    enc, mac = _vault_keys()
    try:
        iv = bytes.fromhex(wrapper["iv"])
        ct = base64.b64decode(wrapper["ct"])
        expected = hmac.new(mac, iv + ct, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(wrapper.get("mac", ""))):
            raise RuntimeError("vault MAC 校验失败")
        return _openssl_vault(["enc", "-d", "-aes-256-cbc", "-K", enc.hex(), "-iv", iv.hex(), "-nosalt"], ct).decode("utf-8")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("vault 解密失败: %s" % (exc,))


def _vault_load():
    raw = read_text(VAULT_FILE)
    if not raw:
        return []
    try:
        wrapper = json.loads(raw)
        text = _vault_decrypt_text(wrapper)
        data = json.loads(text)
        entries = data.get("entries")
        return entries if isinstance(entries, list) else []
    except Exception as exc:
        raise RuntimeError("保险库读取失败（密钥不匹配或文件损坏）: %s" % (exc,))


def _vault_save(entries):
    os.makedirs(os.path.dirname(VAULT_FILE), exist_ok=True)
    payload = {"version": 1, "entries": entries}
    wrapper = _vault_encrypt_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    tmp = VAULT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(wrapper, fh, ensure_ascii=False, separators=(",", ":"))
    os.chmod(tmp, 0o600)
    os.replace(tmp, VAULT_FILE)


def _vault_audit(action, entry, client_ip):
    try:
        record = {
            "at": _fmt_iso(),
            "action": action,
            "id": entry.get("id") if isinstance(entry, dict) else None,
            "title": entry.get("title") if isinstance(entry, dict) else None,
            "client": client_ip,
        }
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(VAULT_AUDIT, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _vault_clean_entry(payload, existing=None):
    existing = existing or {}
    title = str(payload.get("title") or existing.get("title") or "").strip()
    if not title:
        raise ValueError("名称不能为空")
    if len(title) > 120:
        raise ValueError("名称太长（最多 120 字）")

    def field(name, limit=2000):
        val = payload.get(name, existing.get(name, ""))
        if val is None:
            return ""
        val = str(val)
        return val[:limit]

    now = _fmt_iso()
    return {
        "id": existing.get("id") or secrets.token_hex(8),
        "title": title,
        "username": field("username", 300),
        "password": field("password", 2000),
        "url": field("url", 500),
        "tags": field("tags", 300),
        "notes": field("notes", 4000),
        "created": existing.get("created") or now,
        "updated": now,
    }


def run_cmd(args, timeout=20):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def do_action(payload, client_ip, proto):
    global _last_action_at
    name = (payload.get("action") or "").strip()
    service = (payload.get("service") or "").strip()
    if not name:
        return 400, {"ok": False, "error": "缺少 action"}
    if time.time() - _last_action_at < 1.0:
        return 429, {"ok": False, "error": "操作太快，请稍后再试"}
    _last_action_at = time.time()
    allowed = set(service_names())
    try:
        if name in ("restart", "start", "stop"):
            if service not in allowed:
                return 400, {"ok": False, "error": "不允许的服务"}
            r = run_cmd(["supervisorctl", "-c", CONF, name, service], timeout=20)
            result = ANSI_RE.sub("", (r.stdout or "").strip())[-3000:]
            ok = r.returncode == 0
        elif name == "doctor":
            r = run_cmd(["server-doctor"], timeout=40)
            result = ANSI_RE.sub("", ((r.stdout or "") + (r.stderr or ""))).strip()[-6000:]
            ok = r.returncode == 0
        elif name == "backup":
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, "console-backup.log"), "ab") as out:
                subprocess.Popen(["server-backup"], stdout=out, stderr=out, start_new_session=True)
            result = "备份任务已在后台启动（日志 console-backup.log）"
            ok = True
        else:
            return 400, {"ok": False, "error": "未知操作"}
    except subprocess.TimeoutExpired:
        return 504, {"ok": False, "error": "操作超时"}
    except Exception as e:
        return 500, {"ok": False, "error": repr(e)}
    write_audit({
        "at": _fmt_iso(), "action": name, "service": service or None,
        "ok": ok, "client": client_ip, "proto": proto,
    })
    return 200, {"ok": ok, "result": result}


# ----------------------------- HTTP -----------------------------
def _private_ip(value):
    try:
        ip = ipaddress.ip_address(value)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "dsh-api/" + API_VERSION

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _client_ip(self):
        return (self.headers.get("X-Real-IP") or self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()

    def _proto(self):
        return self.headers.get("X-Forwarded-Proto", "http")

    def _lan(self):
        return _private_ip(self._client_ip())

    def _host_private(self):
        host = (self.headers.get("Host") or "").split(":")[0].strip("[]")
        return _private_ip(host)

    def _secure_or_lan(self):
        return self._host_private() or self._proto() == "https"

    def _admin(self):
        return valid_token(self.headers.get("X-Console-Token", ""))

    def _vault_guard(self):
        if not self._admin():
            self._send(401, {"ok": False, "error": "保险库需要管理 token（先解锁管理）"})
            return False
        if not self._secure_or_lan():
            self._send(403, {"ok": False, "error": "保险库仅限 HTTPS 或局域网，请改用 https:// 入口"})
            return False
        return True

    def _vault_response(self, entries):
        entries = sorted(entries, key=lambda x: (x.get("title") or "").lower())
        self._send(200, {"ok": True, "count": len(entries), "items": entries, "updated": _fmt_iso()})

    def _read_json(self, limit=64 * 1024):
        try:
            n = int(self.headers.get("Content-Length", "0") or 0)
            if n <= 0 or n > limit:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8", "ignore"))
        except Exception:
            return {}

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path.rstrip("/") or "/api"
        try:
            if path == "/api/health":
                self._send(200, {"ok": True, "version": API_VERSION, "uptime_s": int(time.time() - START), "time": _fmt_iso()})
            elif path == "/api/sysinfo":
                self._send(200, sysinfo())
            elif path == "/api/history":
                n = (q.get("n") or ["120"])[0]
                pts = history(n)
                self._send(200, {"count": len(pts), "points": pts})
            elif path == "/api/metrics":
                n = (q.get("n") or ["60"])[0]
                pts = load_metrics(n)
                self._send(200, {"count": len(pts), "points": pts})
            elif path == "/api/checks":
                self._send(200, checks())
            elif path == "/api/services":
                self._send(200, {"items": services()})
            elif path == "/api/overview":
                self._send(200, {
                    "sysinfo": sysinfo(),
                    "checks": checks(),
                    "services": services(),
                    "history": history((q.get("n") or ["120"])[0]),
                    "backups": list_backups(),
                    "updated": _fmt_iso(),
                })
            elif path == "/api/backups":
                self._send(200, {"items": list_backups()})
            elif path == "/api/ops":
                n = (q.get("n") or ["20"])[0]
                items = load_ops_audit(n)
                self._send(200, {"count": len(items), "items": items, "updated": _fmt_iso()})
            elif path == "/api/vault":
                if not self._vault_guard():
                    return
                self._vault_response(_vault_load())
            elif path == "/api/vault/export":
                if not self._vault_guard():
                    return
                entries = sorted(_vault_load(), key=lambda x: (x.get("title") or "").lower())
                self._send(200, {"version": 1, "exported_at": _fmt_iso(), "entries": entries})
            elif path == "/api/meta":
                self._send(200, {
                    "version": API_VERSION,
                    "lan": self._lan(),
                    "lan_ip": local_lan_ip(),
                    "host_private": self._host_private(),
                    "https": self._proto() == "https",
                    "action_required": bool(action_token()),
                    "admin": self._admin(),
                    "run_id": secrets.token_hex(4),
                })
            elif path == "/api/logs":
                if not self._admin():
                    self._send(401, {"ok": False, "error": "日志需要管理 token（先解锁管理）"})
                    return
                if not self._secure_or_lan():
                    self._send(403, {"ok": False, "error": "管理接口仅限 HTTPS 或局域网，请改用 https:// 入口"})
                    return
                name = (q.get("name") or [""])[0]
                lines = (q.get("lines") or ["200"])[0]
                text, err = read_log(name, lines)
                if err:
                    self._send(404, {"ok": False, "error": err})
                else:
                    self._send(200, {"ok": True, "name": name, "text": text})
            elif path == "/api/echo":
                self._send(200, {"query": {k: v[0] if len(v) == 1 else v for k, v in q.items()}})
            else:
                self._send(404, {"ok": False, "error": "not found", "path": u.path})
        except Exception as e:
            self._send(500, {"ok": False, "error": repr(e)})

    def _vault_save_entry(self):
        if not self._vault_guard():
            return
        payload = self._read_json()
        try:
            entries = _vault_load()
        except RuntimeError as exc:
            self._send(500, {"ok": False, "error": str(exc)})
            return
        eid = str(payload.get("id") or "")
        existing = None
        for item in entries:
            if item.get("id") == eid:
                existing = item
                break
        if existing is None and len(entries) >= VAULT_MAX_ENTRIES:
            self._send(409, {"ok": False, "error": "保险库条目已达上限 (%d)" % VAULT_MAX_ENTRIES})
            return
        try:
            entry = _vault_clean_entry(payload, existing)
        except ValueError as exc:
            self._send(400, {"ok": False, "error": str(exc)})
            return
        if existing is None:
            entries.append(entry)
        else:
            entries[entries.index(existing)] = entry
        try:
            _vault_save(entries)
        except Exception as exc:
            self._send(500, {"ok": False, "error": "保存失败: %s" % (exc,)})
            return
        _vault_audit("update" if existing else "create", entry, self._client_ip())
        self._send(200, {"ok": True, "entry": entry, "count": len(entries)})

    def _vault_delete(self):
        if not self._vault_guard():
            return
        payload = self._read_json()
        eid = str(payload.get("id") or "")
        if not eid:
            self._send(400, {"ok": False, "error": "缺少 id"})
            return
        try:
            entries = _vault_load()
        except RuntimeError as exc:
            self._send(500, {"ok": False, "error": str(exc)})
            return
        target = next((x for x in entries if x.get("id") == eid), None)
        if not target:
            self._send(404, {"ok": False, "error": "条目不存在"})
            return
        entries = [x for x in entries if x.get("id") != eid]
        try:
            _vault_save(entries)
        except Exception as exc:
            self._send(500, {"ok": False, "error": "保存失败: %s" % (exc,)})
            return
        _vault_audit("delete", target, self._client_ip())
        self._send(200, {"ok": True, "count": len(entries)})

    def _vault_import(self):
        if not self._vault_guard():
            return
        payload = self._read_json(512 * 1024)
        incoming = payload.get("entries") if isinstance(payload, dict) else payload
        if not isinstance(incoming, list):
            self._send(400, {"ok": False, "error": "导入格式应为 {entries: [...]} 或数组"})
            return
        try:
            entries = _vault_load()
        except RuntimeError as exc:
            self._send(500, {"ok": False, "error": str(exc)})
            return
        imported = 0
        for item in incoming:
            if not isinstance(item, dict):
                continue
            eid = str(item.get("id") or "")
            existing = next((x for x in entries if x.get("id") == eid), None) if eid else None
            try:
                entry = _vault_clean_entry(item, existing)
            except ValueError:
                continue
            if existing is None:
                if len(entries) >= VAULT_MAX_ENTRIES:
                    break
                entries.append(entry)
            else:
                entries[entries.index(existing)] = entry
            imported += 1
        try:
            _vault_save(entries)
        except Exception as exc:
            self._send(500, {"ok": False, "error": "保存失败: %s" % (exc,)})
            return
        _vault_audit("import", {"title": "%d entries" % imported}, self._client_ip())
        self._send(200, {"ok": True, "imported": imported, "count": len(entries)})

    def do_POST(self):
        u = urlparse(self.path)
        path = u.path.rstrip("/")
        if path == "/api/vault":
            self._vault_save_entry()
            return
        if path == "/api/vault/delete":
            self._vault_delete()
            return
        if path == "/api/vault/import":
            self._vault_import()
            return
        if path != "/api/action":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not valid_token(self.headers.get("X-Console-Token", "")):
            self._send(401, {"ok": False, "error": "需要管理 token（console-action.token）"})
            return
        if not self._secure_or_lan():
            self._send(403, {"ok": False, "error": "管理接口仅限 HTTPS 或局域网，请改用 https:// 入口"})
            return
        payload = self._read_json()
        code, resp = do_action(payload, self._client_ip(), self._proto())
        self._send(code, resp)

    def log_message(self, fmt, *args):
        print("%s %s" % (self.log_date_time_string(), fmt % args), flush=True)


def main():
    thread = threading.Thread(target=sampler_loop, daemon=True)
    thread.start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.daemon_threads = True
    print(f"api v{API_VERSION} listening on 127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
