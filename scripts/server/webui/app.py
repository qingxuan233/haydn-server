#!/usr/bin/env python3
"""手机文件管理：一个中文的 Web 文件管理器，挂在 nginx 的 /files/ 下。

- 网盘 /root/webdav：可读写
- 项目 /root/server：只读（避免在浏览器里误改服务配置）

零依赖，只用标准库；由 supervisor 托管（127.0.0.1:8085）。
"""

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import posixpath
import re
import shutil
import stat
import sys
import tempfile
import traceback
import time
import unicodedata
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

HOST = os.environ.get("FILES_HOST", "127.0.0.1")
PORT = int(os.environ.get("FILES_PORT", "8085"))
HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(HERE, "static", "index.html")
LOGIN_FILE = os.path.join(HERE, "static", "login.html")

USER = os.environ.get("FILES_USER", "admin")
WEBDAV_YAML = "/root/server/webdav.yaml"

ROOTS = {
    "webdav": {"label": "网盘", "note": "可读写", "path": "/root/webdav", "rw": True},
    "server": {"label": "项目", "note": "只读", "path": "/root/server", "rw": False},
}

TEXT_SUFFIX = {
    ".txt", ".md", ".markdown", ".log", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".conf", ".cfg", ".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".css",
    ".html", ".htm", ".xml", ".csv", ".sql", ".env", ".gitignore", ".service",
    ".properties", ".rst", ".tex", ".srt", ".vtt",
}
IMAGE_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".avif"}
VIDEO_SUFFIX = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}
AUDIO_SUFFIX = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus"}
MEDIA_SUFFIX = VIDEO_SUFFIX | IMAGE_SUFFIX | AUDIO_SUFFIX


def load_password():
    env = os.environ.get("FILES_PASSWORD")
    if env:
        return env
    for path in (WEBDAV_YAML,):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        m = re.search(r"^\s*password:\s*(\S+)\s*$", text, re.M)
        if m:
            return m.group(1).strip("'\"")
    return ""


PASSWORD = load_password()


def session_value():
    """会话值：由密码派生（cookie 与 URL/header 令牌共用）。改密码后旧会话自动失效。"""
    return hashlib.sha256(("files-ui:" + PASSWORD).encode("utf-8")).hexdigest()


def token_matches(candidate):
    """常量时间比较会话令牌（兼容 cookie 被浏览器拦截的 WebView）。"""
    if not candidate or not PASSWORD:
        return False
    try:
        return hmac.compare_digest(candidate, session_value())
    except Exception:
        return False


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def human_size(n):
    if n is None:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} B"


def _safe_zip_name(name):
    """zip 文件名安全化：去路径分隔符/控制字符并限长。"""
    name = os.path.basename((name or "").replace("\\", "/")).strip()
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
    return (name or "download")[:120]


def kind_of(name):
    suffix = os.path.splitext(name)[1].lower()
    if suffix in IMAGE_SUFFIX:
        return "image"
    if suffix in VIDEO_SUFFIX:
        return "video"
    if suffix in AUDIO_SUFFIX:
        return "audio"
    if suffix in TEXT_SUFFIX:
        return "text"
    return "file"


class Handler(BaseHTTPRequestHandler):
    server_version = "files-ui/1.1"
    protocol_version = "HTTP/1.1"

    # ---------- 基础工具 ----------
    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _cookies(self):
        items = {}
        for part in (self.headers.get("Cookie") or "").split(";"):
            key, sep, value = part.strip().partition("=")
            if sep:
                items[key] = value
        return items

    def _basic_ok(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic ") or not PASSWORD:
            return False
        try:
            raw = base64.b64decode(header[6:]).decode("utf-8", "strict")
        except Exception:
            return False
        user, sep, password = raw.partition(":")
        return bool(sep) and user == USER and password == PASSWORD

    def _logged_in(self):
        return token_matches(self._cookies().get("files_session") or "")

    def _request_token(self):
        token = (self.headers.get("X-Files-Token") or "").strip()
        if token:
            return token
        try:
            qs = parse_qs(urlparse(self.path).query)
        except Exception:
            return ""
        return ((qs.get("s") or qs.get("token") or [""])[0] or "").strip()

    def _authed(self, allow_basic=True):
        return (
            self._logged_in()
            or token_matches(self._request_token())
            or (allow_basic and self._basic_ok())
        )

    def _need_login(self):
        """接口层要求登录：返回 401 JSON，不带 WWW-Authenticate，避免浏览器弹框死循环。"""
        self._json({"ok": False, "error": "需要登录", "login": True}, 401)

    def _redirect(self, location, status=303):
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _set_session(self):
        cookie = f"files_session={session_value()}; Path=/; HttpOnly; SameSite=Lax; Max-Age={30 * 86400}"
        if (self.headers.get("X-Forwarded-Proto") or "").lower() == "https":
            cookie += "; Secure"
        self.send_header("Set-Cookie", cookie)

    def _clear_session(self):
        self.send_header("Set-Cookie", "files_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, message):
        self._json({"ok": False, "error": message}, status)

    def _root(self, qs):
        key = (qs.get("root") or ["webdav"])[0]
        root = ROOTS.get(key)
        if not root:
            raise HttpError(404, "没有这个根目录")
        return key, root

    def _resolve(self, root, rel):
        rel = (rel or "").strip()
        while rel.startswith("/"):
            rel = rel[1:]
        if ".." in rel.split("/"):
            raise HttpError(400, "路径不合法")
        base = root["path"]
        full = os.path.normpath(os.path.join(base, rel))
        if full == base:
            return base
        if not full.startswith(base + os.sep):
            raise HttpError(400, "路径不合法")
        if not os.path.exists(full):
            raise HttpError(404, "文件不存在")
        return full

    def _require_rw(self, root):
        if not root["rw"]:
            raise HttpError(403, "这里是只读的")

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise HttpError(400, "请求不合法")
        if length > 2 * 1024 * 1024:
            raise HttpError(413, "内容太大")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            raise HttpError(400, "内容不是合法 JSON")

    def _safe_name(self, name):
        name = os.path.basename((name or "").replace("\\", "/")).strip()
        if not name or name in (".", "..") or "/" in name or "\x00" in name:
            raise HttpError(400, "文件名不合法")
        return name

    # ---------- GET ----------
    def do_GET(self):
        try:
            self._handle_get()
        except HttpError as exc:
            self._error(exc.status, exc.message)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # 不让异常打死线程
            self.log_message("内部错误: %r", exc)
            traceback.print_exc(file=sys.stderr)
            try:
                self._error(500, "服务器内部错误")
            except Exception:
                pass

    def _handle_get(self):
        url = urlparse(self.path)
        path = url.path.rstrip("/") or "/"
        if path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/login":
            self._serve_login()
            return
        if path == "/logout":
            self._redirect("login")
            return
        if path in ("/", "/index.html"):
            if self._authed():
                self._serve_index()
            else:
                self.log_message(
                    "page unauthed cookie=%s url_token=%s proto=%s ua=%r",
                    bool(self._cookies().get("files_session")),
                    bool(self._request_token()),
                    self.headers.get("X-Forwarded-Proto") or "-",
                    (self.headers.get("User-Agent") or "")[:90],
                )
                self._serve_login()
            return
        if not self._authed():
            self._need_login()
            return
        qs = parse_qs(url.query)
        if path == "/api/list":
            self._api_list(qs)
        elif path == "/api/roots":
            self._api_roots()
        elif path == "/api/raw":
            self._api_raw(qs)
        elif path == "/api/zip":
            self._api_zip(qs)
        else:
            raise HttpError(404, "没有这个地址")

    def _serve_login(self):
        try:
            with open(LOGIN_FILE, "rb") as fh:
                body = fh.read()
        except OSError:
            raise HttpError(500, "登录页文件缺失")
        self.send_response(200)
        # 陈旧/失效的会话 cookie 自动清掉，避免“登录成功却一直回登录页”
        if not self._logged_in() and self._cookies().get("files_session"):
            self._clear_session()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _api_login(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(min(length, 65536)) if length else b""
        try:
            form = parse_qs(body.decode("utf-8", "replace"))
        except Exception:
            form = {}
        raw_user = (form.get("username") or [""])[0]
        raw_password = (form.get("password") or [""])[0]

        def _clean(value):
            # 手机输入法常见问题：全角字符、首尾空格、零宽字符
            value = value.replace("\u200b", "").replace("\ufeff", "")
            value = unicodedata.normalize("NFKC", value)
            return value.strip()

        user = _clean(raw_user)
        password = _clean(raw_password)
        _nonascii = sum(1 for ch in raw_password if ord(ch) > 127)
        _ok = bool(PASSWORD) and user == USER and password == PASSWORD
        self.log_message(
            "login user=%r pwlen=%d nonascii=%d ok=%s cookie_in=%s proto=%s host=%s ua=%r",
            user, len(password), _nonascii, _ok,
            bool(self._cookies().get("files_session")),
            self.headers.get("X-Forwarded-Proto") or "-",
            self.headers.get("Host") or "-",
            (self.headers.get("User-Agent") or "")[:90],
        )
        if _ok:
            self.send_response(303)
            self._set_session()
            # 同时把令牌放进 Location：浏览器/WebView 拦截 cookie 时仍能进入
            self.send_header("Location", "./?s=" + session_value())
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        time.sleep(0.4)
        self.send_response(303)
        self._clear_session()
        self.send_header("Location", "login?e=1")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _api_logout(self):
        self.send_response(303)
        self._clear_session()
        self.send_header("Location", "login")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _serve_index(self):
        try:
            with open(INDEX_FILE, "rb") as fh:
                body = fh.read()
        except OSError:
            raise HttpError(500, "界面文件缺失")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _api_roots(self):
        items = []
        for key, root in ROOTS.items():
            items.append({"key": key, "label": root["label"], "note": root["note"], "rw": root["rw"]})
        try:
            usage = shutil.disk_usage(ROOTS["webdav"]["path"])
            disk = {"total": usage.total, "free": usage.free}
        except OSError:
            disk = None
        self._json({"ok": True, "roots": items, "disk": disk})

    def _api_list(self, qs):
        key, root = self._root(qs)
        rel = (qs.get("path") or [""])[0]
        full = self._resolve(root, rel)
        if not os.path.isdir(full):
            raise HttpError(400, "这不是文件夹")
        entries = []
        try:
            with os.scandir(full) as it:
                for item in it:
                    try:
                        st = item.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    is_dir = item.is_dir(follow_symlinks=False)
                    name = item.name
                    entries.append({
                        "name": name,
                        "kind": "dir" if is_dir else kind_of(name),
                        "is_dir": is_dir,
                        "size": None if is_dir else st.st_size,
                        "size_text": "" if is_dir else human_size(st.st_size),
                        "mtime": int(st.st_mtime),
                        "mtime_text": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                    })
        except PermissionError:
            raise HttpError(403, "没有权限读取这个文件夹")
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        rel_path = posixpath.join(rel.strip("/"), "") if rel else ""
        self._json({
            "ok": True, "root": key, "path": rel.strip("/"), "rw": root["rw"],
            "label": root["label"], "entries": entries,
            "free": human_size(shutil.disk_usage(root["path"]).free) if os.path.isdir(root["path"]) else "",
        })

    def _api_raw(self, qs):
        key, root = self._root(qs)
        full = self._resolve(root, (qs.get("path") or [""])[0])
        if os.path.isdir(full):
            raise HttpError(400, "这是文件夹，不能下载")
        download = (qs.get("download") or ["0"])[0] == "1"
        self._send_file(full, download)

    def _send_file(self, full, download):
        try:
            size = os.path.getsize(full)
        except OSError:
            raise HttpError(404, "文件不存在")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        suffix = os.path.splitext(full)[1].lower()
        if suffix in TEXT_SUFFIX or ctype.startswith("text/"):
            ctype = "text/plain; charset=utf-8"
        ranged = False
        start, end = 0, size - 1
        header = self.headers.get("Range")
        if header and header.startswith("bytes="):
            m = re.match(r"bytes=(\d*)-(\d*)", header)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                elif m.group(2):
                    start = max(0, size - int(m.group(2)))
                    end = size - 1
                if start <= end and start < size:
                    ranged = True
                    end = min(end, size - 1)
        if not ranged:
            start, end = 0, size - 1
        length = max(0, end - start + 1)
        self.send_response(206 if ranged else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if ranged:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download:
            name = os.path.basename(full)
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(name))
        self.end_headers()
        try:
            with open(full, "rb") as fh:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_zip(self, zip_path, download_name):
        try:
            size = os.path.getsize(zip_path)
        except OSError:
            raise HttpError(404, "打包文件不存在")
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(download_name))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            with open(zip_path, "rb") as fh:
                while True:
                    chunk = fh.read(262144)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _api_zip(self, qs):
        """把一个文件夹打包成 zip 后下载（临时文件在 /tmp，发送后删除）。"""
        key, root = self._root(qs)
        rel = (qs.get("path") or [""])[0]
        folder = self._resolve(root, rel)
        if not os.path.isdir(folder):
            raise HttpError(400, "这不是文件夹")
        base = os.path.basename(folder.rstrip(os.sep)) or root["label"]
        zip_name = _safe_zip_name(base) + ".zip"

        # 先统计大小，避免临时空间被撑爆
        total = 0
        for dirpath, dirnames, filenames in os.walk(folder, followlinks=False):
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
            for name in filenames:
                fpath = os.path.join(dirpath, name)
                if os.path.islink(fpath):
                    continue
                try:
                    st = os.stat(fpath, follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISREG(st.st_mode):
                    total += st.st_size
        try:
            free = shutil.disk_usage("/tmp").free
        except OSError:
            free = 0
        if free and total > free * 0.9:
            raise HttpError(507, "文件夹太大（约 %s），临时空间不足" % human_size(total))

        tmp = tempfile.NamedTemporaryFile(prefix="files-zip-", suffix=".zip", dir="/tmp", delete=False)
        zip_path = tmp.name
        tmp.close()
        written = 0
        try:
            with zipfile.ZipFile(zip_path, "w", allowZip64=True) as zf:
                for dirpath, dirnames, filenames in os.walk(folder, followlinks=False):
                    dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
                    rel_dir = os.path.relpath(dirpath, folder)
                    rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
                    for name in filenames:
                        fpath = os.path.join(dirpath, name)
                        if os.path.islink(fpath):
                            continue
                        try:
                            st = os.stat(fpath, follow_symlinks=False)
                        except OSError:
                            continue
                        if not stat.S_ISREG(st.st_mode):
                            continue
                        arcname = posixpath.join(rel_dir, name) if rel_dir else name
                        suffix = os.path.splitext(name)[1].lower()
                        # 音视频/图片/超大文件用 STORED，避免无意义压缩耗时
                        compress = zipfile.ZIP_STORED if (suffix in MEDIA_SUFFIX or st.st_size > 16 * 1024 * 1024) else zipfile.ZIP_DEFLATED
                        zf.write(fpath, arcname=arcname, compress_type=compress)
                        written += 1
            self.log_message("zip %s -> %s (%d entries, %s)", folder, zip_name, written, human_size(total))
            self._send_zip(zip_path, zip_name)
        finally:
            try:
                os.unlink(zip_path)
            except OSError:
                pass

    # ---------- POST ----------
    def do_POST(self):
        try:
            self._handle_post()
        except HttpError as exc:
            self._error(exc.status, exc.message)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            self.log_message("内部错误: %r", exc)
            traceback.print_exc(file=sys.stderr)
            try:
                self._error(500, "服务器内部错误")
            except Exception:
                pass

    def _handle_post(self):
        url = urlparse(self.path)
        path = url.path.rstrip("/")
        qs = parse_qs(url.query)
        if path == "/login":
            self._api_login()
            return
        if path == "/logout":
            self._api_logout()
            return
        if not self._authed():
            self._need_login()
            return
        if self.headers.get("X-Requested-With") != "dsh-files":
            raise HttpError(403, "请求来源不被接受")
        if path == "/api/upload":
            self._api_upload(qs)
        elif path == "/api/mkdir":
            self._api_mkdir()
        elif path == "/api/rename":
            self._api_rename()
        elif path == "/api/delete":
            self._api_delete()
        elif path == "/api/save":
            self._api_save()
        else:
            raise HttpError(404, "没有这个地址")

    def _api_upload(self, qs):
        key, root = self._root(qs)
        self._require_rw(root)
        folder = self._resolve(root, (qs.get("path") or [""])[0])
        if not os.path.isdir(folder):
            raise HttpError(400, "目标不是文件夹")
        name = self._safe_name((qs.get("name") or [""])[0])
        target = os.path.join(folder, name)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise HttpError(400, "请求不合法")
        if length <= 0:
            raise HttpError(400, "没有文件内容")
        parent = os.path.dirname(target)
        os.makedirs(parent, exist_ok=True) if parent != folder else None
        written = 0
        with open(target, "wb") as fh:
            while written < length:
                chunk = self.rfile.read(min(262144, length - written))
                if not chunk:
                    break
                fh.write(chunk)
                written += len(chunk)
        if written != length:
            try:
                os.remove(target)
            except OSError:
                pass
            raise HttpError(400, "上传中断")
        self._json({"ok": True, "name": name, "size_text": human_size(length)})

    def _api_mkdir(self):
        payload = self._read_json()
        key, root = self._root({"root": [payload.get("root", "webdav")]})
        self._require_rw(root)
        folder = self._resolve(root, payload.get("path", ""))
        name = self._safe_name(payload.get("name", ""))
        target = os.path.join(folder, name)
        if os.path.exists(target):
            raise HttpError(409, "已经有同名文件或文件夹")
        os.mkdir(target)
        self._json({"ok": True, "name": name})

    def _api_rename(self):
        payload = self._read_json()
        key, root = self._root({"root": [payload.get("root", "webdav")]})
        self._require_rw(root)
        source = self._resolve(root, payload.get("path", ""))
        name = self._safe_name(payload.get("name", ""))
        target = os.path.join(os.path.dirname(source), name)
        if os.path.exists(target):
            raise HttpError(409, "已经有同名文件或文件夹")
        os.rename(source, target)
        self._json({"ok": True, "name": name})

    def _api_delete(self):
        payload = self._read_json()
        key, root = self._root({"root": [payload.get("root", "webdav")]})
        self._require_rw(root)
        target = self._resolve(root, payload.get("path", ""))
        if target == root["path"]:
            raise HttpError(400, "不能删除根目录")
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
        self._json({"ok": True})

    def _api_save(self):
        payload = self._read_json()
        key, root = self._root({"root": [payload.get("root", "webdav")]})
        self._require_rw(root)
        target = self._resolve(root, payload.get("path", ""))
        if os.path.isdir(target):
            raise HttpError(400, "这是文件夹")
        content = payload.get("content", "")
        if not isinstance(content, str):
            raise HttpError(400, "内容不合法")
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        self._json({"ok": True})


def main():
    if not PASSWORD:
        print("警告：没读到 WebDAV 密码，所有请求都会被拒绝（可设 FILES_PASSWORD 环境变量）", file=sys.stderr)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"文件管理界面已启动 http://{HOST}:{PORT}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
