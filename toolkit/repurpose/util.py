"""公共工具：路径、时间、JSON I/O、嵌套取值、错误类型、输出格式化。

本模块是 toolkit 内所有子模块的地基，必须保持零第三方依赖，且兼容 Python 3.10+。
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

TOOLKIT_ROOT = Path(__file__).resolve().parent.parent
"""toolkit/ 目录绝对路径。"""

REPO_ROOT = TOOLKIT_ROOT.parent
"""仓库根目录（toolkit/ 的上一级）。"""

TEMPLATES_DIR = TOOLKIT_ROOT / "templates"
SCHEMA_DIR = TOOLKIT_ROOT / "schema"
TERMUX_DIR = TOOLKIT_ROOT / "termux"

SCHEMA_PROFILE = "repurpose.device-profile.v1"
SCHEMA_ASSESSMENT = "repurpose.assessment.v1"
SCHEMA_ROOTCHECK = "repurpose.rootcheck.v1"
SCHEMA_RESCUE_KIT = "repurpose.rescue-kit.v1"
SCHEMA_RESCUE_KIT_VERIFY = "repurpose.rescue-kit-verify.v1"
SCHEMA_PLAN = "repurpose.plan.v1"
SCHEMA_MANIFEST = "repurpose.agent-manifest.v1"
SCHEMA_VALIDATION = "repurpose.validation.v1"
SCHEMA_FIXTURE = "repurpose.adb-fixture.v1"


class RepurposeError(Exception):
    """工具链错误基类（可读信息，不含敏感值）。"""

    exit_code = 1


class UsageError(RepurposeError):
    """用法 / 输入错误 → 退出码 2。"""

    exit_code = 2


class PreconditionError(RepurposeError):
    """前置条件不满足（无 adb / 无设备 / 无 fixture）→ 退出码 3。"""

    exit_code = 3


class JsonFileError(RepurposeError):
    """JSON 读写失败（内部使用，由调用方翻译成 UsageError 等）。"""

    exit_code = 2


def now_utc() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def iso_now() -> str:
    """当前 UTC 时间的 ISO-8601 秒级字符串，例如 ``2026-11-11T02:30:00Z``。"""
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: Any) -> datetime | None:
    """解析 ISO-8601 时间字符串；失败返回 None，不抛异常。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def ensure_parent(path: Path) -> Path:
    """确保文件父目录存在。"""
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: Path | str, *, encoding: str = "utf-8") -> str:
    """以宽松编码读取文本（UTF-8 损坏时按替换符处理，避免直接崩溃）。"""
    p = Path(path)
    try:
        raw = p.read_text(encoding=encoding, errors="replace")
    except OSError as exc:
        raise JsonFileError(f"无法读取文件：{_display_path(p)}（{exc.__class__.__name__}）") from exc
    return raw


def load_json(path: Path | str) -> Any:
    """读取 JSON 文件；失败抛 JsonFileError（含路径，不含文件内容）。"""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        raise JsonFileError(f"无法读取 JSON 文件：{_display_path(p)}（{exc.__class__.__name__}）") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise JsonFileError(
            f"JSON 解析失败：{_display_path(p)}（第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}）"
        ) from exc


def write_json(path: Path | str, payload: Any, *, indent: int = 2) -> Path:
    """原子写入 JSON（先写临时文件再 ``os.replace``），UTF-8 无 BOM、LF。"""
    p = Path(path)
    ensure_parent(p)
    text = json.dumps(payload, ensure_ascii=False, indent=indent) + "\n"
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="._tmp_", dir=str(p.parent))
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp_path, p)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return p


def write_text(path: Path | str, text: str) -> Path:
    """原子写入文本（UTF-8、LF）。"""
    p = Path(path)
    ensure_parent(p)
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="._tmp_", dir=str(p.parent))
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp_path, p)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return p


def merge_dict(base: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    """递归合并两个 dict；返回新对象，不修改入参。patch 中的 dict 递归合并。"""
    result: dict[str, Any] = dict(base)
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = merge_dict(result[key], value)  # type: ignore[arg-type]
        else:
            result[key] = value
    return result


def get_nested(obj: Any, dotted: str, default: Any = None) -> Any:
    """按 ``a.b.c`` 取值；任一层缺失返回 default。"""
    current: Any = obj
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def as_bool(value: Any) -> bool | None:
    """把多个来源的布尔值归一：true/false 字符串、1/0；未知返回 None。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on", "unlocked"}:
            return True
        if lowered in {"0", "false", "no", "n", "off", "locked"}:
            return False
    return None


def as_int(value: Any) -> int | None:
    """把字符串/数字归一为 int；失败或非数字返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("_", "")
        if re.fullmatch(r"[+-]?\d+", text):
            try:
                return int(text)
            except ValueError:
                return None
    return None


def as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


_MULTI_SPACE = re.compile(r"\s+")


def compact(value: Any, limit: int = 160) -> str:
    """压缩任意值为单行短文本（用于人类摘要，cb 超长截断）。"""
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        text = str(value)
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = _MULTI_SPACE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def _display_path(path: Path | str) -> str:
    """把路径压缩成仓库相对形式，避免输出绝对路径。"""
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return p.name


def rel_posix(path: Path | str, root: Path | str) -> str:
    """返回相对 root 的 POSIX 路径；无法相对化时返回文件名。"""
    p = Path(path)
    try:
        return p.resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return p.name


def relative_link_target_exists(root: Path, doc_path: Path, target: str) -> tuple[bool, Path]:
    """判断 Markdown 相对链接目标（去掉 anchor/query）是否存在。

    返回 ``(exists, resolved_path)``；不处理 ``http(s)`` 等外部链接。
    """
    cleaned = target.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1]
    cleaned = cleaned.split("#", 1)[0].split("?", 1)[0]
    cleaned = cleaned.replace("\\", "/")
    if not cleaned:
        return True, doc_path.parent
    decoded = _unquote_path(cleaned)
    candidate = (doc_path.parent / decoded)
    try:
        candidate = candidate.resolve()
    except OSError:
        return False, candidate
    return candidate.exists(), candidate


def _unquote_path(value: str) -> str:
    """最小化 URL 解码：只处理 %20 与常见中文路径百分号编码，避免额外依赖。"""
    try:
        from urllib.parse import unquote

        return unquote(value)
    except Exception:  # pragma: no cover - urllib 永远可用
        return value


def format_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """生成对齐的简单文本表格（中文按字符宽度不精确对齐，可读优先）。"""
    norm_rows = [[compact(cell, 60) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in norm_rows:
        for index, cell in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], len(cell))
    lines = ["  ".join(header.ljust(widths[i]) for i, header in enumerate(headers))]
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in norm_rows:
        cells = []
        for index, cell in enumerate(row[: len(headers)]):
            cells.append(cell.ljust(widths[index]))
        lines.append("  ".join(cells))
    return "\n".join(lines)


def find_repo_root(explicit: str | None) -> Path:
    """解析 ``--root``：显式路径优先，否则仓库根；不存在或不是目录抛 UsageError。"""
    candidate = Path(explicit).resolve() if explicit else REPO_ROOT
    if not candidate.is_dir():
        raise UsageError(f"--root 不是已存在的目录：{candidate.name}")
    return candidate


def is_probably_secret(text: str) -> bool:
    """粗粒度敏感值启发式（用于校验器提示，不打印明文）。"""
    patterns = (
        r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"ghp_[A-Za-z0-9]{20,}",
        r"AKIA[0-9A-Z]{16,}",
        r"eyJhbGciOi[A-Za-z0-9_-]{10,}",
    )
    return any(re.search(pattern, text) for pattern in patterns)
