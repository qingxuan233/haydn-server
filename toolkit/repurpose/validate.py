"""validate：新层内容的前置校验（front matter / ID 唯一 / 相对链接 / JSON / manifest 过期）。

退出码：发现问题 exit 4（CLI 层）；``--strict`` 时 warning 也视为失败。
不检查 Markdown anchor 指向的标题是否存在，但新层禁止 ``#anchor``（记 warning）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .frontmatter import REQUIRED_KEYS, parse_document
from .util import (
    SCHEMA_VALIDATION,
    is_probably_secret,
    iso_now,
    load_json,
    parse_iso,
    relative_link_target_exists,
    rel_posix,
)
from .indexgen import CONTENT_GROUPS, scan_group

CONTENT_DIRS = ("methodology", "pitfalls", "guardrails", "cases")
EXTRA_MARKDOWN = ("toolkit/README.md",)
PROTOCOL_MARKDOWN = ("AGENTS.md",)

_JSON_SKIP_DIRS = {".git", "__pycache__", "tools", "inventory", "backup", "node_modules"}
_JSON_EXTRA_DIRS = ("android-bridge", "docs", "scripts", "toolkit", "cases")
_JSON_ROOT_FILES = ("agent-manifest.json", "backlog.json")

_FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\((?:<([^>]+)>|([^)\s]+))\)")

STATUS_VALUES = ("current", "draft", "deprecated", "archived", "frozen", "proposed")
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
)
ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]{3}$")

PITFALL_SEVERITY = ("S1", "S2", "S3", "S4")
PITFALL_DOMAIN = ("device", "boot", "server", "bridge", "security", "ops", "docs")
GUARDRAIL_SEVERITY = ("blocker", "warning")
GUARDRAIL_SCOPE = ("device", "server", "agent", "repo")


def _issue(level: str, code: str, path: str, message: str, line: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"level": level, "code": code, "path": path, "message": message}
    if line is not None:
        payload["line"] = line
    return payload


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


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


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


def _is_absolute(target: str) -> bool:
    return (
        target.startswith("/")
        or target.startswith("\\")
        or bool(re.match(r"^[A-Za-z]:[\\/]", target))
        or target.lower().startswith("file:")
    )


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
                    _issue("warning", "ID_FORMAT", relative, f"ID '{entry_id}' 不符合 'PREFIX-000' 形式")
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
            if _is_absolute(target):
                issues.append(
                    _issue("warning", "LINK_ABSOLUTE", relative, f"禁止绝对路径链接：{target}", line)
                )
                continue
            exists, _resolved = relative_link_target_exists(root, path, target)
            if not exists:
                issues.append(_issue("error", "LINK_BROKEN", relative, f"链接目标不存在：{target}", line))
    return issues, link_count


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


def validate_manifest(root: Path, content_paths: list[Path]) -> tuple[list[dict[str, Any]], bool]:
    issues: list[dict[str, Any]] = []
    manifest_path = root / "agent-manifest.json"
    if not manifest_path.is_file():
        if content_paths:
            issues.append(
                _issue(
                    "warning",
                    "MANIFEST_MISSING",
                    "agent-manifest.json",
                    "manifest 不存在：请运行 python -m toolkit.repurpose index",
                )
            )
        return issues, False
    try:
        manifest = load_json(manifest_path)
    except Exception:
        return issues, True  # JSON_PARSE 已由 validate_json 报告
    if not isinstance(manifest, dict):
        issues.append(_issue("error", "MANIFEST_TYPE", "agent-manifest.json", "manifest 顶层不是 object"))
        return issues, True

    generated_at = parse_iso(manifest.get("generated_at"))
    newest_source = 0.0
    for path in content_paths:
        try:
            newest_source = max(newest_source, path.stat().st_mtime)
        except OSError:
            continue
    if generated_at is not None and newest_source and generated_at.timestamp() + 1.0 < newest_source:
        issues.append(
            _issue(
                "warning",
                "MANIFEST_STALE",
                "agent-manifest.json",
                "manifest 已过期（内容文件比 manifest 新）：请重新运行 index",
            )
        )
    if generated_at is None:
        issues.append(_issue("error", "MANIFEST_TIME", "agent-manifest.json", "manifest 缺少可解析的 generated_at"))

    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    try:
        actual = {group: len(scan_group(root, directory)[0]) for group, directory in CONTENT_GROUPS.items()}
    except Exception:
        actual = {}
    count_keys = ("methodology", "pitfalls", "guardrails", "case_studies")
    for key in count_keys:
        if key in counts and actual and counts.get(key) != actual.get(key):
            issues.append(
                _issue(
                    "warning",
                    "MANIFEST_COUNTS",
                    "agent-manifest.json",
                    f"counts.{key}={counts.get(key)} 与当前内容 {actual.get(key)} 不一致：请重新运行 index",
                )
            )
    return issues, True


def validate_repo(root: str | Path, strict: bool = False) -> dict[str, Any]:
    """执行全部校验，返回 ``repurpose.validation.v1`` 报告。"""
    repo_root = Path(root)
    content_paths = collect_content_markdown(repo_root)
    link_paths = collect_link_markdown(repo_root)
    fm_issues, markdown_count = validate_front_matter(content_paths, repo_root)
    link_issues, link_count = validate_links(link_paths, repo_root)
    json_issues, json_count = validate_json(repo_root)
    manifest_issues, manifest_found = validate_manifest(repo_root, content_paths)

    issues = fm_issues + link_issues + json_issues + manifest_issues
    errors = [item for item in issues if item["level"] == "error"]
    warnings = [item for item in issues if item["level"] == "warning"]
    failed = bool(errors) or (strict and bool(warnings))
    return {
        "schema": SCHEMA_VALIDATION,
        "generated_at": iso_now(),
        "root": ".",
        "strict": strict,
        "ok": not failed,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "checked": {
            "markdown_files": markdown_count,
            "link_files": len(link_paths),
            "links": link_count,
            "json_files": json_count,
            "manifest": manifest_found,
        },
        "issues": issues,
    }


def format_validation_human(report: dict[str, Any]) -> str:
    """人类可读校验输出；不打印文件内容/敏感值。"""
    status = "OK" if report["ok"] else "FAIL"
    checked = report["checked"]
    lines = [
        f"validate 结果：{status}",
        "- 检查：Markdown {markdown_files} 个（链接文件 {link_files} 个）/ 相对链接 {links} 条 / JSON {json_files} 个 / manifest {manifest}".format(
            **checked
        ),
        f"- 错误：{report['error_count']}；警告：{report['warning_count']}；strict={report['strict']}",
    ]
    if report["issues"]:
        lines.append("")
        shown = 0
        for issue in report["issues"]:
            if report["strict"] or issue["level"] == "error" or shown < 30:
                location = issue["path"]
                if issue.get("line"):
                    location += f":{issue['line']}"
                lines.append(f"  [{issue['level']}] {issue['code']} {location} - {issue['message']}")
                shown += 1
            if not report["strict"] and issue["level"] == "warning" and shown >= 30:
                break
        if len(report["issues"]) > shown:
            lines.append(f"  ... 其余 {len(report['issues']) - shown} 条见 --json")
    return "\n".join(lines)
