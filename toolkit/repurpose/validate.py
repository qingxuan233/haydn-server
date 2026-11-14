"""validate：新层内容 + 治理契约 + doc-policy + manifest 分片一致性的前置校验。

检查项：
1. front matter 必需键/ID 唯一/相对链接/JSON 可解析（内容层校验）；
2. doc-policy（``toolkit/schema/doc-policy.json``）：文档行数上限、归档字节上限、
   CHANGELOG 当前窗口条目上限（≤8）、状态段落行数上限；
3. 治理契约（``governance.py``）：AGENTS.md 协议章节/版本/哨兵/体积、新层命名、
   PIT 编号与五段、ADR 文件名/状态/正文/回链/索引、CHANGELOG §4 归档索引双向一致、
   backlog schema/语义、Agent 回归 AR-02/AR-03；
4. 根 manifest（≤160 行/≤16KB、无完整 content、含 shards）与四层分片
   （≤300 行/≤32KB/≤40 条、ID 全局唯一、路径存在且相对、与 front matter 同步）；
   单层 >40 条时按层内顺序拆分为 ``<layer>-p01.json``…（单片为 ``<layer>.json``），
   并校验片数、命名与各片条目合计。

严重度：内容层错误与机器契约违反固定 error；policy/manifest 预算类违规
``--strict`` 下 error（exit 4）、非 strict 下 warning。索引一致性以内容机检
（MANIFEST_COUNTS/SHARD_CONTENT）为准；文件 mtime 不参与默认判定（CI 安全），
需要本地调试时用 ``--mtime-check`` 显式开启 MANIFEST_STALE 检查。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from math import ceil
from pathlib import Path
from typing import Any

from .docpolicy import line_count, load_policy, manifest_limits
from .frontmatter import REQUIRED_KEYS, parse_document
from .governance import collect_governance
from .indexgen import (
    CONTENT_GROUPS,
    SCHEMA_SHARD,
    SHARD_DIR,
    SHARD_REQUIRED_KEYS,
    default_shard_dir,
    scan_group,
    shard_relative_path,
)
from .util import (
    SCHEMA_VALIDATION,
    is_probably_secret,
    iso_now,
    load_json,
    parse_iso,
    relative_link_target_exists,
    rel_posix,
)

CONTENT_DIRS = ("methodology", "pitfalls", "guardrails", "cases", "adr")
EXTRA_MARKDOWN = ("toolkit/README.md",)
PROTOCOL_MARKDOWN = ("AGENTS.md",)

_JSON_SKIP_DIRS = {".git", "__pycache__", "tools", "inventory", "backup", "node_modules"}
_JSON_EXTRA_DIRS = ("android-bridge", "docs", "scripts", "toolkit", "cases", SHARD_DIR)
_JSON_ROOT_FILES = ("agent-manifest.json", "backlog.json")

_FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\((?:<([^>]+)>|([^)\s]+))\)")

STATUS_VALUES = (
    "current",
    "draft",
    "deprecated",
    "archived",
    "frozen",
    "proposed",
    "accepted",
    "superseded",
)
TYPE_VALUES = (
    "index",
    "methodology",
    "pitfall",
    "guardrail",
    "case-study",
    "oem-profile",
    "acceptance",
    "runbook",
    "agent-task",
    "tool",
    "adr",
    "request",
)
ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]{3,4}$")

PITFALL_SEVERITY = ("S1", "S2", "S3", "S4")
PITFALL_DOMAIN = ("device", "boot", "server", "bridge", "security", "ops", "docs")
GUARDRAIL_SEVERITY = ("blocker", "warning")
GUARDRAIL_SCOPE = ("device", "server", "agent", "repo")

DEFAULT_WINDOW_PATTERN = r"^\|\s*20\d{2}-\d{2}-\d{2}\s*\|"
SYNC_FIELDS = ("title", "type", "status", "tags", "agent_hint", "severity", "domain", "scope", "oem")


def _issue(level: str, code: str, path: str, message: str, line: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"level": level, "code": code, "path": path, "message": message}
    if line is not None:
        payload["line"] = line
    return payload


def _policy_issue(strict: bool, code: str, path: str, message: str, line: int | None = None) -> dict[str, Any]:
    """policy/manifest 违规：strict → error，非 strict → warning。"""
    return _issue("error" if strict else "warning", code, path, message, line)


def _is_absolute_path(path: str) -> bool:
    return bool(
        path.startswith("/")
        or path.startswith("\\")
        or re.match(r"^[A-Za-z]:[\\/]", path)
        or path.lower().startswith("file:")
    )


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


# ---------------------------------------------------------------------------
# Markdown 收集与内容层校验
# ---------------------------------------------------------------------------


def collect_content_markdown(root: Path) -> list[Path]:
    """新层内容 Markdown（需要 front matter 校验）。"""
    files: list[Path] = []
    for directory_name in CONTENT_DIRS:
        directory = root / directory_name
        if directory.is_dir():
            files.extend(sorted(directory.rglob("*.md")))
    for relative in EXTRA_MARKDOWN:
        path = root / relative
        if path.is_file():
            files.append(path)
    return files


def collect_link_markdown(root: Path) -> list[Path]:
    """需要检查相对链接的 Markdown（内容层 + 根协议文件）。"""
    files = collect_content_markdown(root)
    for relative in PROTOCOL_MARKDOWN:
        path = root / relative
        if path.is_file():
            files.append(path)
    return files


def _strip_code_blocks(text: str) -> str:
    """去掉 fenced code 与 inline code，避免把示例链接当真实链接。"""
    without_fenced = _FENCED_CODE.sub(lambda match: "\n" * match.group(0).count("\n"), text)
    return _INLINE_CODE.sub("", without_fenced)


def _extract_links(text: str) -> list[tuple[int, str]]:
    """返回 ``[(行号, 目标)]``。"""
    cleaned = _strip_code_blocks(text)
    links: list[tuple[int, str]] = []
    for match in _LINK_PATTERN.finditer(cleaned):
        target = match.group(1) or match.group(2) or ""
        links.append((_line_of(cleaned, match.start()), target))
    return links


def _is_external(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(
        ("http://", "https://", "mailto:", "tel:", "ftp://", "data:")
    ) or "://" in lowered


def validate_front_matter(paths: list[Path], root: Path) -> tuple[list[dict[str, Any]], int]:
    issues: list[dict[str, Any]] = []
    ids: dict[str, str] = {}
    for path in paths:
        relative = rel_posix(path, root)
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            issues.append(_issue("error", "READ_ERROR", relative, "无法读取文件"))
            continue
        data, errors, _body = parse_document(text)
        if not data and any("缺少 front matter" in error for error in errors):
            issues.append(_issue("error", "FM_MISSING", relative, "缺少 front matter（首行必须是 ---）"))
            continue
        for error in errors:
            issues.append(_issue("error", "FM_PARSE", relative, error))
        if not data:
            continue
        for key in REQUIRED_KEYS:
            if key not in data:
                issues.append(_issue("error", "FM_MISSING_KEY", relative, f"缺少必需键 '{key}'"))
                continue
            if not data[key]:
                issues.append(_issue("error", "FM_EMPTY_KEY", relative, f"必需键 '{key}' 为空"))
        entry_id = data.get("id")
        if isinstance(entry_id, str) and entry_id:
            if not ID_PATTERN.match(entry_id):
                issues.append(
                    _issue("warning", "ID_FORMAT", relative, f"ID '{entry_id}' 不符合 'PREFIX-000'/'PREFIX-0000' 形式")
                )
            if entry_id in ids:
                issues.append(
                    _issue("error", "ID_DUPLICATE", relative, f"ID '{entry_id}' 与 {ids[entry_id]} 重复")
                )
            else:
                ids[entry_id] = relative
        status = data.get("status")
        if isinstance(status, str) and status not in STATUS_VALUES:
            issues.append(
                _issue("warning", "STATUS_VALUE", relative, f"status '{status}' 不在约定值 {list(STATUS_VALUES)}")
            )
        data_type = data.get("type")
        if isinstance(data_type, str) and data_type not in TYPE_VALUES:
            issues.append(
                _issue("warning", "TYPE_VALUE", relative, f"type '{data_type}' 不在约定值 {list(TYPE_VALUES)}")
            )
        updated = data.get("updated")
        if isinstance(updated, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
            issues.append(_issue("warning", "UPDATED_FORMAT", relative, "updated 必须是 YYYY-MM-DD"))
        if is_probably_secret(text):
            issues.append(
                _issue("warning", "SECRET_PATTERN", relative, "文本疑似包含私钥/令牌片段（请人工确认）")
            )
        if data_type == "pitfall":
            severity = data.get("severity")
            if severity not in PITFALL_SEVERITY:
                issues.append(
                    _issue(
                        "warning",
                        "PIT_SEVERITY",
                        relative,
                        f"pitfall 的 severity 应为 {list(PITFALL_SEVERITY)}（当前：{severity!r}）",
                    )
                )
            domain = data.get("domain")
            if domain not in PITFALL_DOMAIN:
                issues.append(
                    _issue(
                        "warning",
                        "PIT_DOMAIN",
                        relative,
                        f"pitfall 的 domain 应为 {list(PITFALL_DOMAIN)}（当前：{domain!r}）",
                    )
                )
        if data_type == "guardrail":
            severity = data.get("severity")
            if severity not in GUARDRAIL_SEVERITY:
                issues.append(
                    _issue(
                        "warning",
                        "GRD_SEVERITY",
                        relative,
                        f"guardrail 的 severity 应为 {list(GUARDRAIL_SEVERITY)}（当前：{severity!r}）",
                    )
                )
            scope = data.get("scope")
            if scope not in GUARDRAIL_SCOPE:
                issues.append(
                    _issue(
                        "warning",
                        "GRD_SCOPE",
                        relative,
                        f"guardrail 的 scope 应为 {list(GUARDRAIL_SCOPE)}（当前：{scope!r}）",
                    )
                )
    return issues, len(paths)


def validate_links(paths: list[Path], root: Path) -> tuple[list[dict[str, Any]], int]:
    issues: list[dict[str, Any]] = []
    link_count = 0
    for path in paths:
        relative = rel_posix(path, root)
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        for line, target in _extract_links(text):
            if not target:
                continue
            if _is_external(target):
                continue
            link_count += 1
            if "#" in target:
                issues.append(
                    _issue("warning", "LINK_ANCHOR", relative, f"新层禁止 #anchor 链接：{target}", line)
                )
                if target.startswith("#"):
                    continue
            if _is_absolute_path(target):
                issues.append(
                    _issue("warning", "LINK_ABSOLUTE", relative, f"禁止绝对路径链接：{target}", line)
                )
                continue
            exists, _resolved = relative_link_target_exists(root, path, target)
            if not exists:
                issues.append(_issue("error", "LINK_BROKEN", relative, f"链接目标不存在：{target}", line))
    return issues, link_count


# ---------------------------------------------------------------------------
# JSON 解析
# ---------------------------------------------------------------------------


def collect_json_files(root: Path) -> list[Path]:
    """收集需要 JSON 可解析性检查的文件（排除 gitignore 隐私/工具目录）。"""
    files: list[Path] = []
    for name in _JSON_ROOT_FILES:
        path = root / name
        if path.is_file():
            files.append(path)
    for directory_name in _JSON_EXTRA_DIRS:
        directory = root / directory_name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.json"):
            parts = set(path.relative_to(root).parts[:-1])
            if parts & _JSON_SKIP_DIRS:
                continue
            files.append(path)
    return sorted(set(files))


def validate_json(root: Path) -> tuple[list[dict[str, Any]], int]:
    issues: list[dict[str, Any]] = []
    files = collect_json_files(root)
    for path in files:
        relative = rel_posix(path, root)
        try:
            payload = load_json(path)
        except Exception as exc:
            issues.append(_issue("error", "JSON_PARSE", relative, f"JSON 解析失败：{exc}"))
            continue
        if path.name == "agent-manifest.json" and isinstance(payload, dict):
            if payload.get("schema") != "repurpose.agent-manifest.v1":
                issues.append(
                    _issue("error", "JSON_SCHEMA", relative, "manifest schema 不是 repurpose.agent-manifest.v1")
                )
    return issues, len(files)


# ---------------------------------------------------------------------------
# doc-policy 校验
# ---------------------------------------------------------------------------


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None


def _status_section_violations(
    text: str, max_lines: int, tokens: list[str]
) -> list[tuple[int, str, int]]:
    """返回 ``[(标题行号, 标题, 段落非空行数)]`` 中超过上限的段落。"""
    lines = text.splitlines()
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if re.match(r"^#{1,6}\s", line):
            headings.append((index, line.strip()))
    violations: list[tuple[int, str, int]] = []
    for position, (index, heading) in enumerate(headings):
        if not any(token in heading for token in tokens):
            continue
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        body_lines = [line for line in lines[index + 1 : end] if line.strip()]
        if len(body_lines) > max_lines:
            violations.append((index + 1, heading, len(body_lines)))
    return violations


def validate_doc_policy(root: Path, policy: dict[str, Any], strict: bool) -> tuple[list[dict[str, Any]], int]:
    """按 doc-policy 检查文档体积、CHANGELOG 窗口与状态段落。"""
    issues: list[dict[str, Any]] = []
    checked = 0
    margin_cfg = policy.get("line_limit_margin") if isinstance(policy.get("line_limit_margin"), dict) else {}
    try:
        margin_within = int(margin_cfg.get("warning_within", 0))
    except (TypeError, ValueError):
        margin_within = 0
    line_limits = policy.get("line_limits") if isinstance(policy.get("line_limits"), dict) else {}
    for pattern, raw_limit in line_limits.items():
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            continue
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            text = _read_text(path)
            if text is None:
                continue
            checked += 1
            lines = line_count(text)
            if lines > limit:
                issues.append(
                    _policy_issue(
                        strict,
                        "DOC_LINES",
                        rel_posix(path, root),
                        f"{rel_posix(path, root)} 行数 {lines} 超过 doc-policy 上限 {limit}",
                    )
                )
            elif margin_within > 0 and limit - lines < margin_within:
                issues.append(
                    _issue(
                        "advisory",
                        "DOC_LINES_MARGIN",
                        rel_posix(path, root),
                        f"{rel_posix(path, root)} 行数 {lines}，距上限 {limit} 仅余 {limit - lines} 行"
                        f"（<{margin_within}）；请登记拆篇/精简计划（MTH-015 §5.4），本项不阻断质量门",
                    )
                )

    byte_limits = policy.get("byte_limits") if isinstance(policy.get("byte_limits"), dict) else {}
    for pattern, raw_limit in byte_limits.items():
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            continue
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            checked += 1
            size = path.stat().st_size
            if size > limit:
                issues.append(
                    _policy_issue(
                        strict,
                        "CHANGELOG_ARCHIVE_BYTES",
                        rel_posix(path, root),
                        f"{rel_posix(path, root)} 字节数 {size} 超过上限 {limit}（归档文件应拆分）",
                    )
                )

    archival = policy.get("archival") if isinstance(policy.get("archival"), dict) else {}
    current_name = archival.get("current_file", "CHANGELOG.md")
    current_path = root / str(current_name)
    if current_path.is_file():
        checked += 1
        text = _read_text(current_path) or ""
        try:
            max_entries = int(archival.get("max_current_entries", 8))
        except (TypeError, ValueError):
            max_entries = 8
        pattern_text = str(archival.get("window_row_pattern", DEFAULT_WINDOW_PATTERN))
        try:
            window_pattern = re.compile(pattern_text)
        except re.error:
            window_pattern = re.compile(DEFAULT_WINDOW_PATTERN)
        rows = [line for line in text.splitlines() if window_pattern.search(line)]
        if len(rows) > max_entries:
            issues.append(
                _policy_issue(
                    strict,
                    "CHANGELOG_WINDOW",
                    rel_posix(current_path, root),
                    f"CHANGELOG 当前窗口有 {len(rows)} 条数据行，超过上限 {max_entries}；"
                    "请按 MTH-015 归档最旧条目到 changelog/YYYY-MM.md",
                )
            )

    status = policy.get("status_sections") if isinstance(policy.get("status_sections"), dict) else {}
    if status:
        try:
            max_lines = int(status.get("max_lines", 8))
        except (TypeError, ValueError):
            max_lines = 8
        tokens = [str(token) for token in status.get("match_headings", ["当前状态", "现状", "Status"])]
        for relative in status.get("files", ["AGENTS.md", "README.md"]):
            path = root / str(relative)
            if not path.is_file():
                continue
            checked += 1
            text = _read_text(path)
            if text is None:
                continue
            for line_number, heading, count in _status_section_violations(text, max_lines, tokens):
                issues.append(
                    _policy_issue(
                        strict,
                        "STATUS_SECTION",
                        rel_posix(path, root),
                        f"状态段落 '{heading}' 有 {count} 行，超过上限 {max_lines}（应只留结论与链接）",
                        line_number,
                    )
                )
    return issues, checked


# ---------------------------------------------------------------------------
# manifest（根摘要 + 分片）一致性校验
# ---------------------------------------------------------------------------


def _read_manifest_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = load_json(path)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_sync_value(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, bool):
        return value
    if value is None:
        return ""
    return value


def _shard_entries_issues(
    root: Path,
    shard_path: str,
    entries: list[Any],
    actual_by_id: dict[str, dict[str, Any]],
    all_ids: dict[str, str],
    strict: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            issues.append(_policy_issue(strict, "SHARD_ENTRY", shard_path, "分片 entries 元素必须是 object"))
            continue
        for key in SHARD_REQUIRED_KEYS:
            if not entry.get(key):
                issues.append(
                    _policy_issue(strict, "SHARD_ENTRY", shard_path, f"分片条目缺少必需字段 '{key}'")
                )
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            continue
        if entry_id in all_ids:
            issues.append(
                _policy_issue(
                    strict,
                    "SHARD_ID_DUPLICATE",
                    shard_path,
                    f"分片 ID '{entry_id}' 与 {all_ids[entry_id]} 重复（ID 必须全局唯一）",
                )
            )
        else:
            all_ids[entry_id] = shard_path
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            continue
        if _is_absolute_path(relative):
            issues.append(
                _policy_issue(strict, "SHARD_ABSOLUTE_PATH", shard_path, f"分片 path 禁止绝对路径：{relative}")
            )
            continue
        if not (root / relative).is_file():
            issues.append(
                _policy_issue(strict, "SHARD_PATH", shard_path, f"分片 path 指向的文件不存在：{relative}")
            )
        actual = actual_by_id.get(entry_id)
        if actual is None:
            issues.append(
                _policy_issue(
                    strict, "SHARD_CONTENT", shard_path, f"分片条目 '{entry_id}' 在内容 front matter 中不存在"
                )
            )
            continue
        if actual.get("path") != relative:
            issues.append(
                _policy_issue(
                    strict,
                    "SHARD_CONTENT",
                    shard_path,
                    f"分片条目 '{entry_id}' 的 path 与 front matter 不一致（{relative} != {actual.get('path')}）",
                )
            )
        for field in SYNC_FIELDS:
            expected = _normalize_sync_value(actual.get(field, ""))
            found = _normalize_sync_value(entry.get(field, ""))
            if expected != found:
                issues.append(
                    _policy_issue(
                        strict,
                        "SHARD_CONTENT",
                        shard_path,
                        f"分片条目 '{entry_id}' 的 {field} 与 front matter 不一致（请重跑 index）",
                    )
                )
    return issues


def validate_manifest_bundle(
    root: Path,
    content_paths: list[Path],
    policy: dict[str, Any],
    strict: bool,
    *,
    mtime_check: bool = False,
) -> tuple[list[dict[str, Any]], bool, int]:
    """校验根摘要与分片；返回 ``(issues, manifest_found, shard_count)``。

    ``mtime_check`` 默认 False：索引一致性由内容机检（MANIFEST_COUNTS/SHARD_CONTENT）
    保证，不依赖文件 mtime（CI/新 checkout 的 mtime 必然晚于提交的 generated_at，
    否则会假失败）。仅本地调试显式开启时才检查 MANIFEST_STALE。
    """
    issues: list[dict[str, Any]] = []
    limits = manifest_limits(policy)
    manifest_path = root / "agent-manifest.json"
    if not manifest_path.is_file():
        if content_paths:
            issues.append(
                _policy_issue(
                    strict,
                    "MANIFEST_MISSING",
                    "agent-manifest.json",
                    "manifest 不存在：请运行 python -m toolkit.repurpose index",
                )
            )
        return issues, False, 0

    try:
        raw = manifest_path.read_bytes()
        text = raw.decode("utf-8-sig", errors="replace")
    except OSError:
        return issues, True, 0
    manifest = _read_manifest_json(manifest_path)
    if manifest is None:
        return issues, True, 0  # JSON_PARSE / MANIFEST_TYPE 由 validate_json 或下方处理

    lines = line_count(text)
    size = len(raw)
    if lines > limits["root_max_lines"]:
        issues.append(
            _policy_issue(
                strict,
                "MANIFEST_SIZE",
                "agent-manifest.json",
                f"根 manifest 行数 {lines} 超过上限 {limits['root_max_lines']}（应只保留摘要）",
            )
        )
    if size > limits["root_max_bytes"]:
        issues.append(
            _policy_issue(
                strict,
                "MANIFEST_SIZE",
                "agent-manifest.json",
                f"根 manifest 字节数 {size} 超过上限 {limits['root_max_bytes']}",
            )
        )
    if "content" in manifest:
        issues.append(
            _policy_issue(
                strict,
                "MANIFEST_LEGACY_CONTENT",
                "agent-manifest.json",
                "根 manifest 仍含完整 content 条目数组（旧格式）；请重跑 index 生成根摘要+分片",
            )
        )

    required_root_keys = (
        "schema",
        "generated_at",
        "repo",
        "entrypoints",
        "reading_order",
        "counts",
        "shards",
        "tools",
        "invariants",
        "commands",
        "warnings",
        "errors",
    )
    for key in required_root_keys:
        if key not in manifest:
            issues.append(
                _policy_issue(strict, "MANIFEST_KEYS", "agent-manifest.json", f"根 manifest 缺少键 '{key}'")
            )

    generated_at = parse_iso(manifest.get("generated_at"))
    if generated_at is None:
        issues.append(
            _policy_issue(
                strict,
                "MANIFEST_TIME",
                "agent-manifest.json",
                "根 manifest 缺少可解析的 generated_at（UTC ISO-8601）",
            )
        )

    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    shards = manifest.get("shards") if isinstance(manifest.get("shards"), dict) else None
    if shards is None:
        issues.append(
            _policy_issue(strict, "MANIFEST_SHARDS", "agent-manifest.json", "根 manifest 缺少 shards 映射")
        )
        shards = {}

    actual_entries: dict[str, list[dict[str, Any]]] = {}
    actual_by_layer_id: dict[str, dict[str, dict[str, Any]]] = {}
    for layer, directory_name in CONTENT_GROUPS.items():
        entries, _warnings, _errors = scan_group(root, directory_name)
        actual_entries[layer] = entries
        actual_by_layer_id[layer] = {entry["id"]: entry for entry in entries}

    actual_counts = {layer: len(actual_entries[layer]) for layer in CONTENT_GROUPS}
    actual_total = sum(actual_counts.values())
    for layer in CONTENT_GROUPS:
        if counts.get(layer) != actual_counts[layer]:
            issues.append(
                _policy_issue(
                    strict,
                    "MANIFEST_COUNTS",
                    "agent-manifest.json",
                    f"counts.{layer}={counts.get(layer)} 与当前内容 {actual_counts[layer]} 不一致：请重跑 index",
                )
            )
    if counts.get("total_entry_docs") not in (None, actual_total):
        issues.append(
            _policy_issue(
                strict,
                "MANIFEST_COUNTS",
                "agent-manifest.json",
                f"counts.total_entry_docs={counts.get('total_entry_docs')} 与当前内容 {actual_total} 不一致",
            )
        )

    reading = manifest.get("reading_order")
    reading_ids: list[Any] = []
    if isinstance(reading, list):
        for group in reading:
            if isinstance(group, dict) and isinstance(group.get("ids"), list):
                reading_ids.extend(group["ids"])
    if counts.get("reading_order") not in (None, len(reading_ids)):
        # 仅当结构可解析时比较，避免误报
        if isinstance(reading, list):
            issues.append(
                _policy_issue(
                    strict,
                    "MANIFEST_COUNTS",
                    "agent-manifest.json",
                    f"counts.reading_order={counts.get('reading_order')} 与 reading_order ids {len(reading_ids)} 不一致",
                )
            )
    entrypoints = manifest.get("entrypoints")
    if isinstance(entrypoints, list) and counts.get("entrypoints") not in (None, len(entrypoints)):
        issues.append(
            _policy_issue(
                strict,
                "MANIFEST_COUNTS",
                "agent-manifest.json",
                f"counts.entrypoints={counts.get('entrypoints')} 与 entrypoints {len(entrypoints)} 不一致",
            )
        )

    shard_count = 0
    all_ids: dict[str, str] = {}
    referenced: set[str] = set()
    shard_max_entries = limits["shard_max_entries"]
    for layer in CONTENT_GROUPS:
        mapping = shards.get(layer)
        parts = mapping.get("parts") if isinstance(mapping, dict) else None
        if not isinstance(parts, list) or not parts:
            issues.append(
                _policy_issue(
                    strict,
                    "SHARD_MAPPING",
                    "agent-manifest.json",
                    f"shards 映射缺少层 '{layer}' 或 parts 数组非法（四层必须齐全）",
                )
            )
            continue
        if mapping.get("count") not in (None, actual_counts[layer]):
            issues.append(
                _policy_issue(
                    strict,
                    "SHARD_MAPPING",
                    "agent-manifest.json",
                    f"shards.{layer}.count={mapping.get('count')} 与当前内容 {actual_counts[layer]} 不一致：请重跑 index",
                )
            )
        expected_parts = max(1, ceil(actual_counts[layer] / shard_max_entries))
        if len(parts) != expected_parts:
            issues.append(
                _policy_issue(
                    strict,
                    "SHARD_SPLIT",
                    "agent-manifest.json",
                    f"shards.{layer} 应有 {expected_parts} 片（每片 ≤{shard_max_entries} 条），实际 {len(parts)} 片：请重跑 index",
                )
            )
        total_from_parts = 0
        for part_index, part in enumerate(parts, start=1):
            if not isinstance(part, dict) or not isinstance(part.get("path"), str):
                issues.append(
                    _policy_issue(
                        strict,
                        "SHARD_MAPPING",
                        "agent-manifest.json",
                        f"shards.{layer}.parts[{part_index - 1}] 缺少合法 path",
                    )
                )
                continue
            shard_relative = part["path"]
            if shard_relative != shard_relative_path(layer, part_index, len(parts)):
                issues.append(
                    _policy_issue(
                        strict,
                        "SHARD_NAMING",
                        shard_relative,
                        "分片命名不符合契约（单片 <layer>.json，多片 <layer>-p01..pNN.json）",
                    )
                )
            if _is_absolute_path(shard_relative):
                issues.append(
                    _policy_issue(strict, "SHARD_ABSOLUTE_PATH", "agent-manifest.json", f"分片 path 禁止绝对路径：{shard_relative}")
                )
                continue
            referenced.add(shard_relative)
            shard_path = root / shard_relative
            if not shard_path.is_file():
                issues.append(
                    _policy_issue(strict, "SHARD_MISSING", shard_relative, "shards 映射指向的分片文件不存在")
                )
                continue
            shard_count += 1
            shard_raw = shard_path.read_bytes()
            shard_text = shard_raw.decode("utf-8-sig", errors="replace")
            shard = _read_manifest_json(shard_path)
            if shard is None:
                issues.append(_policy_issue(strict, "SHARD_SCHEMA", shard_relative, "分片 JSON 无法解析"))
                continue
            shard_lines = line_count(shard_text)
            shard_size = len(shard_raw)
            if shard_lines > limits["shard_max_lines"]:
                issues.append(
                    _policy_issue(
                        strict,
                        "SHARD_SIZE",
                        shard_relative,
                        f"分片行数 {shard_lines} 超过上限 {limits['shard_max_lines']}",
                    )
                )
            if shard_size > limits["shard_max_bytes"]:
                issues.append(
                    _policy_issue(
                        strict,
                        "SHARD_SIZE",
                        shard_relative,
                        f"分片字节数 {shard_size} 超过上限 {limits['shard_max_bytes']}",
                    )
                )
            if shard.get("schema") != SCHEMA_SHARD:
                issues.append(
                    _policy_issue(strict, "SHARD_SCHEMA", shard_relative, f"分片 schema 不是 {SCHEMA_SHARD}")
                )
            if shard.get("layer") != layer:
                issues.append(
                    _policy_issue(strict, "SHARD_SCHEMA", shard_relative, f"分片 layer={shard.get('layer')!r} 与映射 {layer!r} 不一致")
                )
            entries = shard.get("entries")
            if not isinstance(entries, list):
                issues.append(_policy_issue(strict, "SHARD_SCHEMA", shard_relative, "分片缺少 entries 数组"))
                continue
            if len(entries) > shard_max_entries:
                issues.append(
                    _policy_issue(
                        strict,
                        "SHARD_ENTRIES",
                        shard_relative,
                        f"分片条目数 {len(entries)} 超过上限 {shard_max_entries}（应按 ≤{shard_max_entries} 条拆分）",
                    )
                )
            if part_index < len(parts) and len(entries) != shard_max_entries:
                issues.append(
                    _policy_issue(
                        strict,
                        "SHARD_SPLIT",
                        shard_relative,
                        f"非末片条目数 {len(entries)} 应恰为 {shard_max_entries}（按层内顺序满片切分）",
                    )
                )
            part_count = part.get("count")
            if part_count is not None and part_count != len(entries):
                issues.append(
                    _policy_issue(
                        strict,
                        "SHARD_MAPPING",
                        shard_relative,
                        f"shards 映射 count={part_count} 与分片条目数 {len(entries)} 不一致",
                    )
                )
            total_from_parts += len(entries)
            issues.extend(
                _shard_entries_issues(
                    root,
                    shard_relative,
                    entries,
                    actual_by_layer_id[layer],
                    all_ids,
                    strict,
                )
            )
        if total_from_parts != actual_counts[layer]:
            issues.append(
                _policy_issue(
                    strict,
                    "MANIFEST_COUNTS",
                    "agent-manifest.json",
                    f"shards.{layer} 各分片条目合计 {total_from_parts} 与当前内容 {actual_counts[layer]} 不一致：请重跑 index",
                )
            )

    # 分片目录中的孤儿文件（本工具生成但未被根映射引用）
    shard_dir = default_shard_dir(root)
    if shard_dir.is_dir():
        for path in sorted(shard_dir.glob("*.json")):
            relative = rel_posix(path, root)
            if relative in referenced:
                continue
            payload = _read_manifest_json(path)
            if isinstance(payload, dict) and payload.get("schema") == SCHEMA_SHARD:
                issues.append(
                    _policy_issue(
                        strict,
                        "SHARD_ORPHAN",
                        relative,
                        "分片文件未被根 manifest.shards 引用（可能是旧层残留）：请重跑 index 清理",
                    )
                )

    # 索引是否过期（仅 --mtime-check：默认关闭，CI/新 checkout 的 mtime 不可信）
    if mtime_check:
        newest_source = 0.0
        for path in content_paths:
            try:
                newest_source = max(newest_source, path.stat().st_mtime)
            except OSError:
                continue
        if generated_at is not None and newest_source and generated_at.timestamp() + 1.0 < newest_source:
            issues.append(
                _policy_issue(
                    strict,
                    "MANIFEST_STALE",
                    "agent-manifest.json",
                    "manifest 可能已过期（内容文件 mtime 比 manifest 新；--mtime-check 本地调试项）：请重新运行 index",
                )
            )
    return issues, True, shard_count


# ---------------------------------------------------------------------------
# TOOL 登记表一致性 / updated 新鲜度
# ---------------------------------------------------------------------------

TOOL_REGISTRY_HEADING = re.compile(r"^##\s+3\.1\s+工具登记表", re.MULTILINE)
TOOL_ROW = re.compile(r"^\|\s*(TOOL-\d{3})\s*\|")
TOOL_CLI_CMD = re.compile(r"python -m toolkit\.repurpose\s+([a-z][a-z0-9-]*)")
REGISTRY_LINK = re.compile(r"\[[^\]]*\]\((?!https?:)([^)\s]+)\)")
DATE_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FRESHNESS_PREFIXES = ("methodology/", "pitfalls/", "guardrails/")


def _cli_subcommands() -> set[str]:
    """从 cli.py 的实际 argparse 子命令读取 CLI 契约（不在文档里抄写命令表）。"""
    from .cli import build_parser

    parser = build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def _registry_rows(text: str) -> list[tuple[str, str]]:
    """解析 toolkit/README §3.1 登记表，返回 ``[(TOOL-ID, 命令列)]``。"""
    heading = TOOL_REGISTRY_HEADING.search(text)
    if not heading:
        return []
    section = text[heading.end() :]
    end = re.search(r"^##\s", section, re.MULTILINE)
    if end:
        section = section[: end.start()]
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        if not TOOL_ROW.match(line):
            continue
        columns = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(columns) >= 3:
            rows.append((columns[0], columns[2]))
    return rows


def validate_tool_registry(
    root: Path, strict: bool
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """校验登记表 ↔ 实际 CLI 子命令 ↔ 根 manifest tools 的一致性。

    数据源唯一：CLI 从 ``cli.build_parser()`` 读取，登记表从 ``toolkit/README`` §3.1
    读取，tools 从根 manifest 读取；三者不一致即报错（strict 下为 error）。
    缺 ``toolkit/README.md``（如最小 fixture 仓库）时跳过，不产生噪音。
    """
    issues: list[dict[str, Any]] = []
    readme = root / "toolkit/README.md"
    checked: dict[str, Any] = {"tool_registry": 0, "tool_cli_commands": 0}
    if not readme.is_file():
        return issues, checked
    text = readme.read_text(encoding="utf-8-sig", errors="replace")
    rows = _registry_rows(text)
    checked["tool_registry"] = len(rows)
    if not rows:
        issues.append(
            _policy_issue(strict, "TOOL_REGISTRY", "toolkit/README.md", "缺少 §3.1 工具登记表或表格为空")
        )
        return issues, checked
    ids = [tool_id for tool_id, _command in rows]
    expected_ids = [f"TOOL-{index:03d}" for index in range(1, len(rows) + 1)]
    if ids != expected_ids:
        issues.append(
            _policy_issue(
                strict,
                "TOOL_REGISTRY",
                "toolkit/README.md",
                f"TOOL 编号应从 TOOL-001 连续编号（当前：{', '.join(ids)}）",
            )
        )
    registered: dict[str, str] = {}
    script_targets: set[str] = set()
    for tool_id, command_column in rows:
        for sub in TOOL_CLI_CMD.findall(command_column):
            if sub in registered:
                issues.append(
                    _policy_issue(
                        strict,
                        "TOOL_REGISTRY",
                        "toolkit/README.md",
                        f"CLI 子命令 {sub} 重复登记（{registered[sub]} 与 {tool_id}）",
                    )
                )
                continue
            registered[sub] = tool_id
        for target in REGISTRY_LINK.findall(command_column):
            if target.startswith("#") or "://" in target:
                continue
            script_targets.add(target)
            if not (root / "toolkit" / target).exists():
                issues.append(
                    _policy_issue(
                        strict,
                        "TOOL_REGISTRY",
                        "toolkit/README.md",
                        f"{tool_id} 指向的脚本不存在：toolkit/{target}",
                    )
                )
    actual = _cli_subcommands()
    checked["tool_cli_commands"] = len(actual)
    missing = sorted(actual - set(registered))
    if missing:
        issues.append(
            _policy_issue(
                strict,
                "TOOL_COMMAND",
                "toolkit/README.md",
                f"CLI 子命令未在登记表登记：{', '.join(missing)}",
            )
        )
    unknown = sorted(set(registered) - actual)
    if unknown:
        issues.append(
            _policy_issue(
                strict,
                "TOOL_COMMAND",
                "toolkit/README.md",
                f"登记表的 CLI 子命令不存在于 cli.py：{', '.join(unknown)}",
            )
        )
    manifest_path = root / "agent-manifest.json"
    if not manifest_path.is_file():
        return issues, checked
    manifest = _read_manifest_json(manifest_path)
    if manifest is None:
        return issues, checked
    tools = manifest.get("tools")
    if not isinstance(tools, list) or not tools:
        issues.append(
            _policy_issue(strict, "TOOL_MANIFEST", "agent-manifest.json", "manifest 缺少非空 tools 数组")
        )
        return issues, checked
    tool_paths = {tool.get("path") for tool in tools if isinstance(tool, dict)}
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        path = tool.get("path")
        if isinstance(path, str) and not (root / path).exists():
            issues.append(
                _policy_issue(
                    strict, "TOOL_MANIFEST", "agent-manifest.json", f"tools 条目路径不存在：{path}"
                )
            )
    for target in sorted(script_targets):
        if f"toolkit/{target}" not in tool_paths:
            issues.append(
                _policy_issue(
                    strict,
                    "TOOL_MANIFEST",
                    "agent-manifest.json",
                    f"登记表脚本 toolkit/{target} 未出现在 manifest tools 中",
                )
            )
    cli_tools = [tool for tool in tools if isinstance(tool, dict) and tool.get("kind") == "cli"]
    if len(cli_tools) != 1:
        issues.append(
            _policy_issue(
                strict,
                "TOOL_MANIFEST",
                "agent-manifest.json",
                f"manifest tools 应有且仅有一个 kind=cli 条目（当前 {len(cli_tools)} 个）",
            )
        )
    else:
        commands = cli_tools[0].get("commands")
        command_set = set(commands) if isinstance(commands, list) else set()
        if command_set != actual:
            issues.append(
                _policy_issue(
                    strict,
                    "TOOL_MANIFEST",
                    "agent-manifest.json",
                    "manifest tools[cli].commands 与 CLI 子命令不一致："
                    + ", ".join(sorted(command_set ^ actual)),
                )
            )
    for item in manifest.get("commands") or []:
        command = item.get("cmd") if isinstance(item, dict) else None
        if not isinstance(command, str):
            continue
        for sub in TOOL_CLI_CMD.findall(command):
            if sub not in actual:
                issues.append(
                    _policy_issue(
                        strict,
                        "TOOL_COMMAND",
                        "agent-manifest.json",
                        f"manifest commands 引用了不存在的 CLI 子命令：{sub}",
                    )
                )
    return issues, checked


def validate_updated_freshness(root: Path, paths: list[Path]) -> tuple[list[dict[str, Any]], int]:
    """advisory：front matter ``updated`` 早于该文件最近一次提交日期时提示补日期。

    规则：以 git 提交日期（``%cs``，仓库时区无关的 YYYY-MM-DD）为"最后一次改动"，
    ``updated < 提交日期`` 即报告 ``DOC_UPDATED_STALE``。误报控制：
    - 只读 git 历史，不用文件 mtime（checkout/CI 不可信）；
    - 无 ``.git``、非 git 仓库、git 不可用、未跟踪文件、浅克隆缺历史时静默跳过；
    - 永远是 advisory（不计入 error/warning，不使 strict/preflight 失败）；
    - 只覆盖已提交改动：工作区里"改了内容但没提交"的情况无法判定，由提交前自检负责；
    - 适用边界：只检查活跃规范层（methodology/pitfalls/guardrails）；cases/ 为冻结证据、
      adr/ 为历史决策，均不检查，避免为链接/结构维护改写其元数据。
    """
    if not (root / ".git").exists() or not paths:
        return [], 0
    scoped = [path for path in paths if rel_posix(path, root).startswith(FRESHNESS_PREFIXES)]
    if not scoped:
        return [], 0
    relatives = sorted(rel_posix(path, root) for path in scoped)
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "log", "--format=@@%cs", "--name-only", "--no-renames", "--", *relatives],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return [], 0
    if result.returncode != 0:
        return [], 0
    latest: dict[str, str] = {}
    current = ""
    for line in result.stdout.splitlines():
        if line.startswith("@@"):
            current = line[2:].strip()
            continue
        path = line.strip()
        if path and current and path not in latest:
            latest[path] = current
    issues: list[dict[str, Any]] = []
    checked = 0
    for path in scoped:
        relative = rel_posix(path, root)
        commit_date = latest.get(relative)
        if not commit_date:
            continue
        try:
            document = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        data, _errors, _body = parse_document(document)
        if not data:
            continue
        updated = data.get("updated")
        if not isinstance(updated, str) or not DATE_VALUE.fullmatch(updated):
            continue
        checked += 1
        if updated < commit_date:
            issues.append(
                _issue(
                    "advisory",
                    "DOC_UPDATED_STALE",
                    relative,
                    f"updated={updated} 早于最近改动提交 {commit_date}：若本次变更改动了内容，请同步 updated",
                )
            )
    return issues, checked


# ---------------------------------------------------------------------------
# 顶层入口
# ---------------------------------------------------------------------------


def validate_repo(
    root: str | Path,
    strict: bool = False,
    policy_path: str | Path | None = None,
    *,
    mtime_check: bool = False,
) -> dict[str, Any]:
    """执行全部校验，返回 ``repurpose.validation.v1`` 报告。

    ``mtime_check`` 默认 False：索引一致性以内容机检为准，不依赖文件 mtime
    （CI/新 checkout 安全）；传 True 才报告 MANIFEST_STALE。
    """
    repo_root = Path(root)
    policy, policy_warnings = load_policy(policy_path)
    content_paths = collect_content_markdown(repo_root)
    link_paths = collect_link_markdown(repo_root)

    fm_issues, markdown_count = validate_front_matter(content_paths, repo_root)
    link_issues, link_count = validate_links(link_paths, repo_root)
    json_issues, json_count = validate_json(repo_root)
    policy_issues: list[dict[str, Any]] = []
    policy_files = 0
    for code, message in policy_warnings:
        policy_issues.append(
            _policy_issue(strict, code, "toolkit/schema/doc-policy.json", message)
        )
    doc_issues, policy_files = validate_doc_policy(repo_root, policy, strict)
    governance_issues, governance_checked = collect_governance(repo_root, policy, strict)
    manifest_issues, manifest_found, shard_count = validate_manifest_bundle(
        repo_root, content_paths, policy, strict, mtime_check=mtime_check
    )
    tool_issues, tool_checked = validate_tool_registry(repo_root, strict)
    updated_issues, updated_checked = validate_updated_freshness(repo_root, content_paths)

    issues = (
        fm_issues
        + link_issues
        + json_issues
        + policy_issues
        + doc_issues
        + governance_issues
        + manifest_issues
        + tool_issues
        + updated_issues
    )
    errors = [item for item in issues if item["level"] == "error"]
    warnings = [item for item in issues if item["level"] == "warning"]
    advisories = [item for item in issues if item["level"] == "advisory"]
    failed = bool(errors) or (strict and bool(warnings))
    checked: dict[str, Any] = {
        "markdown_files": markdown_count,
        "link_files": len(link_paths),
        "links": link_count,
        "json_files": json_count,
        "manifest": manifest_found,
        "shards": shard_count,
        "policy_files": policy_files,
        "updated_checked": updated_checked,
    }
    checked.update(governance_checked)
    checked.update(tool_checked)
    return {
        "schema": SCHEMA_VALIDATION,
        "generated_at": iso_now(),
        "root": ".",
        "strict": strict,
        "ok": not failed,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "advisory_count": len(advisories),
        "checked": checked,
        "issues": issues,
    }


def format_validation_human(report: dict[str, Any]) -> str:
    """人类可读校验输出；不打印文件内容/敏感值。"""
    status = "OK" if report["ok"] else "FAIL"
    checked = report["checked"]
    lines = [
        f"validate 结果：{status}",
        "- 检查：Markdown {markdown_files} 个（链接文件 {link_files} 个）/ 相对链接 {links} 条 / "
        "JSON {json_files} 个 / manifest {manifest}（分片 {shards}）/ policy 文件 {policy_files}".format(
            **checked
        ),
        "- 治理：协议 {protocol_lines} 行（{protocol_tier}）/ 命名 {naming_files} 个 / "
        "PIT {pitfall_files} 条 / ADR {adr_files} 篇 / backlog {backlog_items} 条 / "
        "归档 {changelog_archive_rows} 条 / 回归 {agent_regression_checks} 项 / "
        "TOOL 登记 {tool_registry} 条（CLI {tool_cli_commands}）/ updated 新鲜度 {updated_checked} 篇".format(
            **checked
        ),
        f"- 错误：{report['error_count']}；警告：{report['warning_count']}；"
        f"预警：{report.get('advisory_count', 0)}（不阻断）；strict={report['strict']}",
    ]
    if report["issues"]:
        lines.append("")
        shown = 0
        for issue in report["issues"]:
            if report["strict"] or issue["level"] == "error" or shown < 40:
                location = issue["path"]
                if issue.get("line"):
                    location += f":{issue['line']}"
                lines.append(f"  [{issue['level']}] {issue['code']} {location} - {issue['message']}")
                shown += 1
            if not report["strict"] and issue["level"] == "warning" and shown >= 40:
                break
        if len(report["issues"]) > shown:
            lines.append(f"  ... 其余 {len(report['issues']) - shown} 条见 --json")
    return "\n".join(lines)
