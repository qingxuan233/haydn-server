#!/usr/bin/env python3
"""把服务器现有账号/密码/口令导入控制台加密保险库。

安全说明：
- 只在服务器内运行，通过 127.0.0.1 API 导入；
- 不打印任何密码/token/口令；
- 条目标题固定，重复运行按标题更新（不会重复堆积）；
- 凭据来源：CREDENTIALS.txt、webdav.yaml、dsh-web-creds.txt、
  supervisord.conf、backup-pass、console-action.token、runner/.runner。
"""
import hashlib
import json
import os
import re
import urllib.request

API = "http://127.0.0.1:8000"
TOKEN_FILE = "/root/server/etc/console-action.token"
CRED = "/root/server/CREDENTIALS.txt"
WEBDAV = "/root/server/webdav.yaml"
DSH_CREDS = "/root/server/etc/dsh-web-creds.txt"
SUPERVISOR = "/root/server/etc/supervisord.conf"
BACKUP_PASS = "/root/server/etc/backup-pass"
RUNNER_FILE = "/root/server/runner/.runner"
SSH_KEY_NOTE = "密钥：backup/ssh/id_haydn；局域网 ssh -p 2222 root@<当前IP>；公网 ssh -p 13872 root@47.97.70.99"


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def token():
    return read(TOKEN_FILE).strip()


def api(path, payload=None, with_token=True):
    data = None
    method = "GET"
    headers = {"Cache-Control": "no-store"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    if with_token:
        headers["X-Console-Token"] = token()
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def lan_ip():
    try:
        meta = api("/api/meta", with_token=False)
        ip = meta.get("lan_ip") or ""
        return ip or "127.0.0.1"
    except Exception:
        return "127.0.0.1"


def value_after(line):
    for sep in ("：", ":"):
        if sep in line:
            return line.split(sep, 1)[1].strip()
    return None


def trim_secret(v):
    if v is None:
        return ""
    v = v.strip()
    for cut in ("（", "(", "\t", " "):
        idx = v.find(cut)
        if idx > 0:
            v = v[:idx]
    return v.strip()


def section_entries():
    text = read(CRED)
    sections = []
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^(\d+\.\d+)\s+(.+)$", line)
        if m:
            cur = {"num": m.group(1), "title": m.group(2), "account": None, "password": None, "lines": []}
            sections.append(cur)
            continue
        if not cur:
            continue
        cur["lines"].append(line)
        if cur["account"] is None and re.search(r"(账号|用户名|username)", line, re.I):
            val = value_after(line)
            if val:
                cur["account"] = trim_secret(val)
        if cur["password"] is None and re.search(r"(密码|password)", line, re.I):
            val = value_after(line)
            if val:
                cur["password"] = trim_secret(val)

    def kind(title):
        t = title.lower()
        if "文件" in title or "webdav" in t:
            return "fileui"
        if "gitea" in t:
            return "gitea"
        if "syncthing" in t:
            return "syncthing"
        if "supervisor" in t:
            return "supervisor"
        if "dsh" in t:
            return "dsh"
        return "other"

    out = {}
    for s in sections:
        if not (s["account"] and s["password"]):
            continue
        k = kind(s["title"])
        if k == "other" and "备份" in s["title"]:
            # 3.6 备份口令由直接文件 /root/server/etc/backup-pass 生成，避免重复
            continue
        title, url, tags, notes = {
            "fileui": ("文件管理 / WebDAV", "https://47.97.70.99:44904/files/", "server, webdav", "来源 CREDENTIALS.txt 3.1 / webdav.yaml；WebDAV 挂载 /dav/；LAN 入口 http://<当前IP>:8080/files/"),
            "gitea": ("Gitea 代码库", "https://47.97.70.99:44904/git/", "server, git", "来源 CREDENTIALS.txt 3.2；注册已关闭"),
            "syncthing": ("Syncthing 同步", f"http://{LAN_IP}:8384/", "server, sync", "来源 CREDENTIALS.txt 3.3；管理界面仅局域网"),
            "supervisor": ("Supervisor 控制面板", "", "server, supervisor", "来源 CREDENTIALS.txt 3.4 / supervisord.conf；管理口 127.0.0.1:9001，仅本机"),
            "dsh": ("DSH 控制台 Basic Auth", "https://47.97.70.99:44904/app-login", "server, dsh", "来源 CREDENTIALS.txt 3.5 / dsh-web-creds.txt"),
            "other": ("服务器 · " + s["title"], "", "server, imported", "来源 CREDENTIALS.txt"),
        }[k]
        out[title] = {"title": title, "username": s["account"], "password": s["password"], "url": url, "tags": tags, "notes": notes}
    return out


LAN_IP = lan_ip()
entries = {}

# 1) CREDENTIALS.txt 分节：文件管理/WebDAV、Gitea、Syncthing、supervisor、DSH
entries.update(section_entries())

# 2) 直接文件兜底/补充
webdav = read(WEBDAV)
m = re.search(r"admin:\s*\n\s*password:\s*(\S+)", webdav)
if m:
    entries.setdefault("文件管理 / WebDAV", {"title": "文件管理 / WebDAV", "username": "admin", "password": m.group(1).strip("'\""), "url": "https://47.97.70.99:44904/files/", "tags": "server, webdav", "notes": "来源 webdav.yaml；WebDAV /dav/"})

dsh = read(DSH_CREDS)
m = re.search(r"username:\s*(\S+).*?password:\s*(\S+)", dsh, re.S)
if m:
    entries["DSH 控制台 Basic Auth"] = {"title": "DSH 控制台 Basic Auth", "username": m.group(1), "password": m.group(2), "url": "https://47.97.70.99:44904/app-login", "tags": "server, dsh", "notes": "来源 dsh-web-creds.txt"}

sup = read(SUPERVISOR)
m = re.search(r"\[inet_http_server\].*?username=(\S+).*?password=(\S+)", sup, re.S)
if m:
    entries["Supervisor 控制面板"] = {"title": "Supervisor 控制面板", "username": m.group(1), "password": m.group(2), "url": "", "tags": "server, supervisor", "notes": "来源 supervisord.conf；127.0.0.1:9001 仅本机"}

backup_pass = read(BACKUP_PASS).strip()
if backup_pass:
    entries["服务器备份加密口令"] = {"title": "服务器备份加密口令", "username": "backup-pass", "password": backup_pass, "url": "", "tags": "server, backup, secret", "notes": "来源 /root/server/etc/backup-pass；丢失将无法恢复加密备份"}

console_token = read(TOKEN_FILE).strip()
if console_token:
    entries["控制台管理 token"] = {"title": "控制台管理 token", "username": "X-Console-Token", "password": console_token, "url": "https://47.97.70.99:44904/", "tags": "server, token, admin", "notes": "控制台「解锁管理」需要；请求头 X-Console-Token；请定期轮换"}

runner = {}
try:
    runner = json.loads(read(RUNNER_FILE) or "{}")
except Exception:
    runner = {}
if runner.get("token"):
    entries["Gitea Runner 注册 token"] = {"title": "Gitea Runner 注册 token", "username": runner.get("name") or "phone-runner", "password": runner.get("token"), "url": "http://127.0.0.1:3000", "tags": "server, gitea, runner, token", "notes": "来源 runner/.runner；runner 可按需启停 server-runner on/off"}

entries["SSH 登录（仅密钥）"] = {"title": "SSH 登录（仅密钥）", "username": "root", "password": "", "url": f"ssh://root@{LAN_IP}:2222", "tags": "server, ssh, key", "notes": SSH_KEY_NOTE}

# 3) 按标题复用已有 id，避免重复堆积
existing = api("/api/vault").get("items", [])
by_title = {x.get("title"): x.get("id") for x in existing}
items = []
for title, e in entries.items():
    e = dict(e)
    e["id"] = by_title.get(title) or "import-" + hashlib.sha256(title.encode("utf-8")).hexdigest()[:12]
    items.append(e)

resp = api("/api/vault/import", {"entries": items})
print("IMPORTED", resp.get("imported"), "TOTAL", resp.get("count"))
for title in sorted(entries.keys()):
    print("-", title)
