"""governance：协议/命名/PIT/ADR/CHANGELOG 归档/backlog/Agent 回归的机器契约检查。

本模块把 frozen 契约（``inventory/agent-harness-plan.md`` §3.1–§3.7）落成
**零第三方依赖**的校验函数，由 :mod:`toolkit.repurpose.validate` 接入
``validate_repo``。检查项：

====================  ====================================================
检查码                 含义（全部为 error：机器契约违反，strict 与否都失败）
====================  ====================================================
PROTOCOL_SECTION      AGENTS.md 缺少必需 H2 章节关键字（§3.1）
PROTOCOL_VERSION      AGENTS.md 缺少 ``| 协议版本 | vMAJOR.MINOR |`` 行
PROTOCOL_SENTINEL     AGENTS.md 末个非空行不是 ``<!-- END-OF-PROTOCOL -->``
PROTOCOL_SIZE         AGENTS.md 行数超过 ``protocol.hard_max_lines``（默认 320）
DOC_NAMING            新层文件名违反 ASCII 小写 kebab-case / 前缀 / 禁止状态词（§3.2）
PIT_ID_GAP            PIT 编号跳号/重复，或 front matter id 与文件名编号不一致（§3.3）
PIT_SECTION           PIT 正文 H2 缺少 症状/根因/规避/验证/证据
PIT_COUNT             PIT 条目数超过 ``governance.pitfall_max_entries``（默认 40）
ADR_FILENAME          ADR 文件名不是 ``NNNN-slug.md``（§3.4）
ADR_ID                ADR front matter id/type 与文件名/契约不一致
ADR_STATUS            ADR status 不在 ``proposed/accepted/superseded``
ADR_SECTION           ADR 正文 H2 缺少 状态/背景/决策/后果
ADR_SUPERSEDED        ``status: superseded`` 却缺少/指向不存在的 ``superseded_by``
ADR_INDEX             ``adr/README.md`` 索引缺失、id 不是 ADR-000、或存在孤儿 ADR（未登记）
CHANGELOG_ARCHIVE     CHANGELOG §4 归档索引与 ``changelog/*.md`` 不一致（§3.5）
BACKLOG_SCHEMA        ``backlog.json`` 结构违反 ``toolkit/schema/backlog.schema.json``（§3.6）
BACKLOG_SEMANTIC      backlog ID 跳号/重复、active 状态缺 owner/updated/result、depends 断链等
AGENT_REGRESSION      AR-02 红线缺 GRD 链接 / AR-03 manifest.invariants 缺关键红线词（§3.7）
====================  ====================================================

所有检查函数签名统一为 ``(root: Path, policy: dict, strict: bool) -> (issues, checked)``，
issue 结构与 :func:`toolkit.repurpose.validate._issue` 一致
（``level/code/path/message[, line]``）；policy 段缺失时回退本模块内置默认值，
因此旧仓库/临时 fixture 仓库**缺文件时降级为跳过**（不误报 error），但真实仓库必须全绿。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .frontmatter import parse_document
from .util import SCHEMA_DIR, load_json, rel_posix

# ---------------------------------------------------------------------------
# 内置默认策略（与 toolkit/schema/doc-policy.json 的 protocol/naming/governance/
# backlog 段保持一致；policy 文件缺失/损坏时回退）
# ---------------------------------------------------------------------------

DEFAULT_PROTOCOL_POLICY: dict[str, Any] = {
    "recommended_max_lines": 200,
    "hard_max_lines": 320,
    "version_pattern": r"^\|\s*协议版本\s*\|\s*v\d+\.\d+\s*\|",
    "sentinel": "<!-- END-OF-PROTOCOL -->",
    "required_headings": ["启动清单", "红线", "任务协议", "完成定义", "机器可读接口", "本文件的维护"],
}
"""§3.1 协议检查默认策略：>推荐值只记 tier（healthy/warning/debt），>硬上限报 PROTOCOL_SIZE。"""

DEFAULT_NAMING_POLICY: dict[str, Any] = {
    "enforce_dirs": ["methodology", "pitfalls", "guardrails", "cases", "adr", "toolkit/templates"],
    "exempt_basenames": ["README.md", "CHANGELOG.md"],
    "forbidden_tokens": ["final", "final2", "latest", "new", "v2", "copy", "副本", "最终版"],
}
"""§3.2 命名检查默认策略。"""

DEFAULT_GOVERNANCE_POLICY: dict[str, Any] = {
    "pitfall_max_entries": 40,
    "pitfall_required_sections": ["症状", "根因", "规避", "验证", "证据"],
    "adr_required_sections": ["状态", "背景", "决策", "后果"],
    "adr_filename_pattern": r"^\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$",
}
"""§3.3/§3.4 默认策略（PIT/ADR）。"""

DEFAULT_BACKLOG_POLICY: dict[str, Any] = {
    "schema_file": "toolkit/schema/backlog.schema.json",
}
"""§3.6 默认策略：backlog schema 文件（缺失时回退内置最小 schema）。"""

DEFAULT_BACKLOG_SCHEMA: dict[str, Any] = {
    "schema": "repurpose.backlog.v1",
    "type": "object",
    "required": ["schema", "updated", "items"],
    "properties": {
        "schema": {"type": "string", "const": "repurpose.backlog.v1"},
        "updated": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "items": {"type": "array", "items": {"$ref": "#/definitions/item"}},
    },
    "definitions": {
        "item": {
            "type": "object",
            "required": [
                "id",
                "title",
                "priority",
                "area",
                "status",
                "acceptance",
                "outputs",
                "depends",
                "notes",
                "agent_hint",
            ],
            "properties": {
                "id": {"type": "string", "pattern": r"^BL-[0-9]{3}$"},
                "title": {"type": "string", "minLength": 1},
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                "area": {"type": "string", "minLength": 1},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "done", "blocked"],
                },
                "acceptance": {"type": "string", "minLength": 1},
                "outputs": {"type": "array", "items": {"type": "string"}},
                "depends": {
                    "type": "array",
                    "items": {"type": "string", "pattern": r"^BL-[0-9]{3}$"},
                },
                "notes": {"type": "string"},
                "agent_hint": {"type": "string", "minLength": 1},
                "requires": {"type": "string"},
                "owner": {"type": "string"},
                "updated": {"type": "string", "pattern": r"^(?:\d{4}-\d{2}-\d{2}|)$"},
                "result": {"type": "string"},
                "risk": {"type": "string", "enum": ["L", "M", "H"]},
            },
        }
    },
}
"""内置最小 backlog schema（schema 文件缺失/损坏时的回退；与 schema/backlog.schema.json 同步）。"""


# ---------------------------------------------------------------------------
# issue 结构（与 validate._issue/_policy_issue 一致）；不直接 import validate
#（validate 反向 import 本模块，避免循环依赖）
# ---------------------------------------------------------------------------


def _issue(level: str, code: str, path: str, message: str, line: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"level": level, "code": code, "path": path, "message": message}
    if line is not None:
        payload["line"] = line
    return payload


def _contract_issue(code: str, path: str, message: str, line: int | None = None) -> dict[str, Any]:
    """机器契约违反：固定 error（不是 doc-policy 预算，strict 与否都失败）。"""
    return _issue("error", code, path, message, line)


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^#{1,6}\s+")
_H2 = re.compile(r"^##\s+(.*)$")
_LINK = re.compile(r"!?\[[^\]]*\]\((?:<([^>]+)>|([^)\s]+))\)")


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None


def _policy_section(policy: dict[str, Any], key: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """取 policy 段并逐键回退内置默认值（policy 文件可只写部分键）。"""
    section = policy.get(key) if isinstance(policy.get(key), dict) else {}
    merged = dict(defaults)
    for name, value in section.items():
        merged[name] = value
    return merged


def _h2_titles(text: str) -> list[str]:
    return [match.group(1).strip() for line in text.splitlines() if (match := _H2.match(line))]


def _heading_lines(text: str) -> list[int]:
    return [index for index, line in enumerate(text.splitlines()) if _HEADING.match(line)]


def _section_body(text: str, keyword: str, *, max_line: int | None = None) -> tuple[int, list[str]] | None:
    """返回第一个标题（任意级别）包含 ``keyword`` 的章节正文 ``(起始行号1-based, 正文行)``。"""
    lines = text.splitlines()
    for position, line in enumerate(lines):
        if not _HEADING.match(line) or keyword not in line:
            continue
        start = position + 1
        end = len(lines)
        for next_position in range(start + 1, len(lines)):
            if _HEADING.match(lines[next_position]):
                end = next_position
                break
        if max_line is not None:
            end = min(end, start + max_line)
        return start, lines[start:end]
    return None


def _has_section(titles: list[str], keyword: str) -> bool:
    return any(keyword in title for title in titles)


def _is_absolute(value: str) -> bool:
    return bool(
        value.startswith("/")
        or value.startswith("\\")
        or re.match(r"^[A-Za-z]:[\\/]", value)
        or value.lower().startswith("file:")
    )


def _extract_links(text: str) -> list[str]:
    targets = []
    for match in _LINK.finditer(text):
        targets.append(match.group(1) or match.group(2) or "")
    return targets


# ---------------------------------------------------------------------------
# §3.1 协议检查（AGENTS.md）
# ---------------------------------------------------------------------------


def protocol_metrics(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    """协议文件只读指标（供 validate checked 汇总；不产生 issue）。"""
    section = _policy_section(policy, "protocol", DEFAULT_PROTOCOL_POLICY)
    path = Path(root) / "AGENTS.md"
    text = _read(path) if path.is_file() else None
    if text is None:
        return {"present": False, "lines": 0, "tier": "missing"}
    try:
        recommended = int(section.get("recommended_max_lines", 200))
    except (TypeError, ValueError):
        recommended = 200
    try:
        hard = int(section.get("hard_max_lines", 320))
    except (TypeError, ValueError):
        hard = 320
    lines = len(text.splitlines())
    if lines <= recommended:
        tier = "healthy"
    elif lines <= hard:
        tier = "warning"
    else:
        tier = "debt"
    return {"present": True, "lines": lines, "tier": tier}


def check_protocol(root: Path, policy: dict[str, Any], strict: bool) -> tuple[list[dict[str, Any]], int]:
    """§3.1：必需 H2 章节 / 协议版本行 / 末行哨兵 / 硬行数上限。"""
    _ = strict  # 机器契约违反固定 error，与 strict 无关
    section = _policy_section(policy, "protocol", DEFAULT_PROTOCOL_POLICY)
    path = Path(root) / "AGENTS.md"
    text = _read(path) if path.is_file() else None
    if text is None:
        return [], 0  # 缺文件：临时 fixture 降级为跳过；真实仓库由 DoD 保证存在

    issues: list[dict[str, Any]] = []
    relative = rel_posix(path, root)
    titles = _h2_titles(text)

    required_headings = section.get("required_headings")
    if not isinstance(required_headings, list) or not required_headings:
        required_headings = DEFAULT_PROTOCOL_POLICY["required_headings"]
    for keyword in required_headings:
        if not _has_section(titles, str(keyword)):
            issues.append(
                _contract_issue(
                    "PROTOCOL_SECTION",
                    relative,
                    f"缺少必需 H2 章节（关键字：{keyword}）；协议必备章节见 §3.1",
                )
            )

    version_pattern = section.get("version_pattern") or DEFAULT_PROTOCOL_POLICY["version_pattern"]
    try:
        version_re = re.compile(str(version_pattern), re.MULTILINE)
    except re.error:
        version_re = re.compile(str(DEFAULT_PROTOCOL_POLICY["version_pattern"]), re.MULTILINE)
    version_line = None
    for index, line in enumerate(text.splitlines(), start=1):
        if version_re.search(line):
            version_line = index
            break
    if version_line is None:
        issues.append(
            _contract_issue(
                "PROTOCOL_VERSION",
                relative,
                "缺少协议版本行（形如 `| 协议版本 | v1.2 |`）；版本语义见 §5.4",
            )
        )

    sentinel = str(section.get("sentinel") or DEFAULT_PROTOCOL_POLICY["sentinel"]).strip()
    non_empty = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_empty or non_empty[-1] != sentinel:
        issues.append(
            _contract_issue(
                "PROTOCOL_SENTINEL",
                relative,
                f"文件最后一个非空行必须是哨兵 `{sentinel}`（用于截断自检）",
            )
        )

    hard = int(section.get("hard_max_lines", 320))
    lines = len(text.splitlines())
    if lines > hard:
        issues.append(
            _contract_issue(
                "PROTOCOL_SIZE",
                relative,
                f"行数 {lines} 超过协议硬上限 {hard}；>推荐值 {section.get('recommended_max_lines', 200)}"
                "只记录 tier（healthy/warning/debt），>硬上限必须分流（§3.1/§4.6）",
            )
        )
    return issues, 1


# ---------------------------------------------------------------------------
# §3.2 命名检查
# ---------------------------------------------------------------------------

_GENERIC_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
_PREFIX_PATTERNS: dict[str, re.Pattern[str]] = {
    "methodology": re.compile(r"^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$"),
    "pitfalls": re.compile(r"^PIT-\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$"),
    "guardrails": re.compile(r"^GRD-\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$"),
    "adr": re.compile(r"^\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$"),
}
"""目录 → 文件名前缀/语法规则；其余 enforce_dirs（cases/toolkit/templates）用通用 kebab-case。"""


def _naming_violations(relative: str, parts: tuple[str, ...], policy: dict[str, Any]) -> list[str]:
    """返回某文件相对路径的命名违规说明列表（空列表＝通过）。"""
    basename = parts[-1]
    exempt = [str(item) for item in policy.get("exempt_basenames", [])]
    if basename in exempt:
        return []
    problems: list[str] = []
    directory = parts[0] if len(parts) > 1 else ""
    if directory in _PREFIX_PATTERNS:
        pattern = _PREFIX_PATTERNS[directory]
        if not pattern.match(basename):
            problems.append(f"文件名 '{basename}' 不符合 {directory}/ 前缀/语法规则")
    else:
        if not _GENERIC_KEBAB.match(basename):
            problems.append(f"文件名 '{basename}' 不是 ASCII 小写 kebab-case（^[a-z0-9]+(?:-[a-z0-9]+)*.md$）")
    if not basename.isascii():
        problems.append(f"文件名 '{basename}' 含非 ASCII 字符")
    elif not basename.islower() and directory not in _PREFIX_PATTERNS:
        # 前缀目录的固定大写前缀（PIT/GRD）已由各自 pattern 覆盖
        problems.append(f"文件名 '{basename}' 含大写字母（约定入口 README/CHANGELOG 除外）")
    stem = basename[:-3] if basename.endswith(".md") else basename
    forbidden = {str(token) for token in policy.get("forbidden_tokens", [])}
    for token in stem.split("-"):
        if token in forbidden:
            problems.append(f"文件名含被禁止的状态词 token '{token}'（用 front matter status/ADR/CHANGELOG 表达）")
    # 目录部分：只要求 ASCII（cases 子目录允许任意 ascii slug）；禁止中文/空格
    for part in parts[:-1]:
        if not part.isascii() or " " in part:
            problems.append(f"路径段 '{part}' 必须为 ASCII 且不含空格")
    _ = relative
    return problems


def check_naming(root: Path, policy: dict[str, Any], strict: bool) -> tuple[list[dict[str, Any]], int]:
    """§3.2：新层 Markdown 文件命名（ASCII 小写 kebab-case / 前缀 / 禁止状态词）。"""
    _ = strict
    naming = _policy_section(policy, "naming", DEFAULT_NAMING_POLICY)
    enforce_dirs = naming.get("enforce_dirs")
    if not isinstance(enforce_dirs, list):
        enforce_dirs = DEFAULT_NAMING_POLICY["enforce_dirs"]
    issues: list[dict[str, Any]] = []
    checked = 0
    for directory in enforce_dirs:
        base = Path(root) / str(directory)
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if not path.is_file():
                continue
            checked += 1
            parts = path.relative_to(Path(root)).parts
            for problem in _naming_violations(rel_posix(path, root), parts, naming):
                issues.append(
                    _contract_issue("DOC_NAMING", rel_posix(path, root), problem)
                )
    return issues, checked


# ---------------------------------------------------------------------------
# §3.3 PIT 检查
# ---------------------------------------------------------------------------

_PIT_FILENAME = re.compile(r"^PIT-(\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


def check_pitfalls(root: Path, policy: dict[str, Any], strict: bool) -> tuple[list[dict[str, Any]], int]:
    """§3.3：PIT 编号连续 / 正文五段关键字 / 条目数上限（不强制旧条目补新字段）。"""
    _ = strict
    governance = _policy_section(policy, "governance", DEFAULT_GOVERNANCE_POLICY)
    directory = Path(root) / "pitfalls"
    if not directory.is_dir():
        return [], 0
    required = governance.get("pitfall_required_sections")
    if not isinstance(required, list) or not required:
        required = DEFAULT_GOVERNANCE_POLICY["pitfall_required_sections"]
    try:
        max_entries = int(governance.get("pitfall_max_entries", 40))
    except (TypeError, ValueError):
        max_entries = 40

    issues: list[dict[str, Any]] = []
    entries: list[tuple[int, Path]] = []
    for path in sorted(directory.glob("*.md")):
        match = _PIT_FILENAME.match(path.name)
        if not match:
            continue
        entries.append((int(match.group(1)), path))
    checked = len(entries)

    numbers = [number for number, _path in entries]
    expected = list(range(1, len(entries) + 1))
    if numbers != expected:
        duplicates = sorted(number for number in set(numbers) if numbers.count(number) > 1)
        missing = sorted(set(expected) - set(numbers))
        detail: list[str] = []
        if missing:
            detail.append("跳号：" + "、".join(f"PIT-{number:03d}" for number in missing))
        if duplicates:
            detail.append("重复：" + "、".join(f"PIT-{number:03d}" for number in duplicates))
        if not missing and not duplicates:
            detail.append(f"实际编号 {numbers[0]}..{numbers[-1]} 与连续区间 1..{len(entries)} 不一致")
        issues.append(
            _contract_issue("PIT_ID_GAP", "pitfalls", "；".join(detail) + "（编号只增不复用、必须连续）")
        )

    for number, path in entries:
        relative = rel_posix(path, root)
        text = _read(path) or ""
        data, _errors, body = parse_document(text)
        entry_id = data.get("id") if isinstance(data, dict) else None
        if entry_id != f"PIT-{number:03d}":
            issues.append(
                _contract_issue(
                    "PIT_ID_GAP",
                    relative,
                    f"front matter id {entry_id!r} 与文件名编号 PIT-{number:03d} 不一致",
                )
            )
        titles = _h2_titles(body)
        for keyword in required:
            if not _has_section(titles, str(keyword)):
                issues.append(
                    _contract_issue(
                        "PIT_SECTION",
                        relative,
                        f"正文缺少 H2 章节关键字 '{keyword}'（必需："
                        + "/".join(str(item) for item in required)
                        + "；新条目七段格式见 pitfalls/README.md）",
                    )
                )
    if len(entries) > max_entries:
        issues.append(
            _contract_issue(
                "PIT_COUNT",
                "pitfalls",
                f"PIT 条目数 {len(entries)} 超过上限 {max_entries}（需按触发标准去重/合并/退役）",
            )
        )
    return issues, checked


# ---------------------------------------------------------------------------
# §3.4 ADR 检查
# ---------------------------------------------------------------------------

ADR_STATUS_VALUES = ("proposed", "accepted", "superseded")


def check_adr(root: Path, policy: dict[str, Any], strict: bool) -> tuple[list[dict[str, Any]], int]:
    """§3.4：ADR 文件名/id/status/正文四段/superseded 回链/索引无孤儿。"""
    _ = strict
    governance = _policy_section(policy, "governance", DEFAULT_GOVERNANCE_POLICY)
    directory = Path(root) / "adr"
    if not directory.is_dir():
        return [], 0
    issues: list[dict[str, Any]] = []
    try:
        filename_re = re.compile(str(governance.get("adr_filename_pattern", "")))
    except re.error:
        filename_re = re.compile(str(DEFAULT_GOVERNANCE_POLICY["adr_filename_pattern"]))
    required = governance.get("adr_required_sections")
    if not isinstance(required, list) or not required:
        required = DEFAULT_GOVERNANCE_POLICY["adr_required_sections"]

    entries: list[tuple[str, Path]] = []
    for path in sorted(directory.glob("*.md")):
        if path.name == "README.md":
            continue
        entries.append((path.name, path))

    # 编号连续性：adr/NNNN-slug.md 从 0001 起连续、不跳号
    numbers = [
        int(match.group(1))
        for filename, _path in entries
        if (match := re.match(r"^(\d{4})-", filename))
    ]
    if numbers != list(range(1, len(entries) + 1)):
        issues.append(
            _contract_issue(
                "ADR_FILENAME",
                "adr",
                "ADR 编号必须从 0001 起连续、不跳号（当前："
                + "、".join(f"{number:04d}" for number in numbers)
                + "）",
            )
        )

    index_path = directory / "README.md"
    index_text = _read(index_path) if index_path.is_file() else None
    if index_text is None:
        issues.append(
            _contract_issue("ADR_INDEX", "adr/README.md", "ADR 索引文件缺失（id 应为 ADR-000，登记每篇 ADR）")
        )
        index_text = ""
    else:
        data, _errors, _body = parse_document(index_text)
        index_id = data.get("id") if isinstance(data, dict) else None
        if index_id != "ADR-000":
            issues.append(
                _contract_issue(
                    "ADR_INDEX",
                    "adr/README.md",
                    f"索引 front matter id 应为 ADR-000（当前：{index_id!r}）",
                )
            )
    linked = {Path(target.split("#", 1)[0].strip()).name for target in _extract_links(index_text)}

    for filename, path in entries:
        relative = rel_posix(path, root)
        if not filename_re.match(filename):
            issues.append(
                _contract_issue(
                    "ADR_FILENAME",
                    relative,
                    f"文件名 '{filename}' 不是 'NNNN-slug.md'（四位序号 + ASCII 小写 kebab-case）",
                )
            )
        number_match = re.match(r"^(\d{4})", filename)
        expected_id = f"ADR-{number_match.group(1)}" if number_match else None
        text = _read(path) or ""
        data, _errors, body = parse_document(text)
        entry_id = data.get("id") if isinstance(data, dict) else None
        if expected_id is not None and entry_id != expected_id:
            issues.append(
                _contract_issue(
                    "ADR_ID",
                    relative,
                    f"front matter id {entry_id!r} 与文件名编号 {expected_id} 不一致",
                )
            )
        if isinstance(data, dict):
            if data.get("type") != "adr":
                issues.append(
                    _contract_issue("ADR_ID", relative, f"front matter type 应为 adr（当前：{data.get('type')!r}）")
                )
        status = data.get("status") if isinstance(data, dict) else None
        if status not in ADR_STATUS_VALUES:
            issues.append(
                _contract_issue(
                    "ADR_STATUS",
                    relative,
                    f"status 应为 {list(ADR_STATUS_VALUES)}（当前：{status!r}）",
                )
            )
        titles = _h2_titles(body)
        for keyword in required:
            if not _has_section(titles, str(keyword)):
                issues.append(
                    _contract_issue(
                        "ADR_SECTION",
                        relative,
                        f"正文缺少 H2 章节关键字 '{keyword}'（必需："
                        + "/".join(str(item) for item in required)
                        + "）",
                    )
                )
        if status == "superseded":
            target = data.get("superseded_by") if isinstance(data, dict) else None
            target_text = str(target).strip() if isinstance(target, str) else ""
            resolved = False
            if target_text:
                candidates = []
                id_match = re.match(r"^ADR-(\d{4})$", target_text)
                if id_match:
                    candidates.append(id_match.group(1))
                name_match = re.match(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$", Path(target_text).name)
                if name_match:
                    candidates.append(name_match.group(1))
                resolved = any(
                    filename.startswith(f"{number}-") for number in candidates for filename, _p in entries
                )
            if not target_text:
                issues.append(
                    _contract_issue(
                        "ADR_SUPERSEDED",
                        relative,
                        "status=superseded 但缺少 superseded_by（必须指向取代它的 ADR）",
                    )
                )
            elif not resolved:
                issues.append(
                    _contract_issue(
                        "ADR_SUPERSEDED",
                        relative,
                        f"superseded_by {target_text!r} 未指向存在的 ADR 文件（adr/NNNN-slug.md）",
                    )
                )
        if filename not in linked:
            issues.append(
                _contract_issue(
                    "ADR_INDEX",
                    relative,
                    "该 ADR 未在 adr/README.md 索引中登记（禁止孤儿 ADR）",
                )
            )
    return issues, len(entries)


# ---------------------------------------------------------------------------
# §3.5 CHANGELOG 归档索引检查
# ---------------------------------------------------------------------------

_ARCHIVE_ROW_COUNT = re.compile(r"(\d+)\s*条")
_ARCHIVE_MONTH = re.compile(r"^\|\s*(\d{4}-\d{2})\s*\|")
_VERSION_TOKEN = re.compile(r"v(\d+)\.(\d+)")
_ARCHIVE_RANGE = re.compile(r"v(\d+)\.(\d+)\s*(?:[–—~-]|to)\s*v(\d+)\.(\d+)")


def _version_tuple(match: re.Match[str]) -> tuple[int, int]:
    return (int(match.group(1)), int(match.group(2)))


def _archive_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.md") if re.fullmatch(r"\d{4}-\d{2}\.md", path.name))


def _changelog_archive_section(text: str) -> list[str] | None:
    located = _section_body(text, "归档索引")
    if located is None:
        return None
    return [line for line in located[1] if line.strip()]


def check_changelog_archive(
    root: Path, policy: dict[str, Any], strict: bool
) -> tuple[list[dict[str, Any]], int]:
    """§3.5：CHANGELOG §4 归档索引 ↔ changelog/*.md 双向一致（行数 / 版本范围 / 文件存在）。"""
    _ = strict
    archival = _policy_section(policy, "archival", _archival_defaults())
    current_name = str(archival.get("current_file", "CHANGELOG.md"))
    archive_directory = Path(root) / str(archival.get("archive_dir", "changelog"))
    path = Path(root) / current_name
    text = _read(path) if path.is_file() else None
    if text is None:
        return [], 0

    issues: list[dict[str, Any]] = []
    relative = rel_posix(path, root)
    rows = _changelog_archive_section(text) or []
    data_rows = [line for line in rows if _ARCHIVE_ROW_COUNT.search(line) or _LINK.search(line)]
    header_like = [line for line in data_rows if "月份" in line or "条数" in line]
    data_rows = [line for line in data_rows if line not in header_like]

    pattern_text = str(archival.get("window_row_pattern", r"^\|\s*20\d{2}-\d{2}-\d{2}\s*\|"))
    try:
        window_re = re.compile(pattern_text)
    except re.error:
        window_re = re.compile(r"^\|\s*20\d{2}-\d{2}-\d{2}\s*\|")

    declared_files: set[str] = set()
    for row in data_rows:
        month_match = _ARCHIVE_MONTH.search(row)
        count_match = _ARCHIVE_ROW_COUNT.search(row)
        link_match = _LINK.search(row)
        if not (month_match and count_match and link_match):
            issues.append(
                _contract_issue(
                    "CHANGELOG_ARCHIVE",
                    relative,
                    f"归档索引行格式不符（需要 月份 / N 条 / 文件相对链接）：{row.strip()[:120]}",
                )
            )
            continue
        month = month_match.group(1)
        declared = int(count_match.group(1))
        target = link_match.group(1) or link_match.group(2) or ""
        archive_path = (path.parent / target).resolve()
        try:
            archive_relative = archive_path.relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            archive_relative = target
        declared_files.add(Path(target).name)
        if not archive_path.is_file():
            issues.append(
                _contract_issue(
                    "CHANGELOG_ARCHIVE",
                    relative,
                    f"§4 声明 {month} 归档 {declared} 条，但文件不存在：{target}",
                )
            )
            continue
        archive_text = _read(archive_path) or ""
        archive_rows = [line for line in archive_text.splitlines() if window_re.search(line)]
        if len(archive_rows) != declared:
            issues.append(
                _contract_issue(
                    "CHANGELOG_ARCHIVE",
                    archive_relative,
                    f"窗口数据行 {len(archive_rows)} 条与 §4 声明的 {declared} 条不一致",
                )
            )
        range_match = _ARCHIVE_RANGE.search(row)
        if range_match:
            low = (int(range_match.group(1)), int(range_match.group(2)))
            high = (int(range_match.group(3)), int(range_match.group(4)))
            # 只取窗口数据行的**版本列**（避免把行内引用的其他版本号误当归档范围）
            versions: list[tuple[int, int]] = []
            for archive_row in archive_rows:
                column = re.match(
                    r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*v(\d+)\.(\d+)\s*\|",
                    archive_row,
                )
                if column:
                    versions.append((int(column.group(1)), int(column.group(2))))
            if not versions:
                versions = [_version_tuple(match) for match in _VERSION_TOKEN.finditer(archive_text)]
            if versions:
                actual_low, actual_high = min(versions), max(versions)
                if (actual_low, actual_high) != (low, high):
                    issues.append(
                        _contract_issue(
                            "CHANGELOG_ARCHIVE",
                            archive_relative,
                            "归档文件版本范围 v{}.{}–v{}.{} 与声明 v{}.{}–v{}.{} 不一致".format(
                                actual_low[0],
                                actual_low[1],
                                actual_high[0],
                                actual_high[1],
                                low[0],
                                low[1],
                                high[0],
                                high[1],
                            ),
                        )
                    )

    for archive_path in _archive_files(archive_directory):
        if archive_path.name not in declared_files:
            issues.append(
                _contract_issue(
                    "CHANGELOG_ARCHIVE",
                    rel_posix(archive_path, root),
                    "changelog/ 归档文件未在 CHANGELOG §4 归档索引登记（双向索引不得遗漏）",
                )
            )
    return issues, len(data_rows)


def _archival_defaults() -> dict[str, Any]:
    return {
        "current_file": "CHANGELOG.md",
        "archive_dir": "changelog",
        "window_row_pattern": r"^\|\s*20\d{2}-\d{2}-\d{2}\s*\|",
    }


# ---------------------------------------------------------------------------
# §3.6 backlog 检查（读取 toolkit/schema/backlog.schema.json 的内置小校验器）
# ---------------------------------------------------------------------------


def load_backlog_schema(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    """读取 backlog schema：优先仓库内 policy 指定文件，其次 toolkit 包内 schema，最后内置默认。"""
    backlog_policy = _policy_section(policy, "backlog", DEFAULT_BACKLOG_POLICY)
    relative = str(backlog_policy.get("schema_file", DEFAULT_BACKLOG_POLICY["schema_file"]))
    candidates = [Path(root) / relative, SCHEMA_DIR / Path(relative).name]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            payload = load_json(candidate)
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("schema") == "repurpose.backlog.v1":
            return payload
    return DEFAULT_BACKLOG_SCHEMA


def _resolve_ref(ref: Any, root_schema: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(ref, str) or not ref.startswith("#/definitions/"):
        return None
    name = ref.split("/")[-1]
    definition = (root_schema.get("definitions") or {}).get(name)
    return definition if isinstance(definition, dict) else None


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _validate_against_schema(
    value: Any,
    spec: Any,
    location: str,
    root_schema: dict[str, Any],
    errors: list[str],
) -> None:
    """内置 JSON-Schema 子集校验（type/required/properties/enum/const/pattern/minLength/items/$ref）。"""
    if not isinstance(spec, dict):
        return
    ref_spec = _resolve_ref(spec.get("$ref"), root_schema)
    if ref_spec is not None:
        _validate_against_schema(value, ref_spec, location, root_schema, errors)
    expected_type = spec.get("type")
    if isinstance(expected_type, str) and not _type_matches(value, expected_type):
        errors.append(f"{location} 应为 {expected_type}")
        return
    if "const" in spec and value != spec["const"]:
        errors.append(f"{location} 应为常量 {spec['const']!r}")
    enum = spec.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append(f"{location} 不在允许枚举 {enum} 中（当前：{value!r}）")
    if isinstance(value, str):
        pattern = spec.get("pattern")
        if isinstance(pattern, str):
            try:
                if not re.search(pattern, value):
                    errors.append(f"{location} 不符合正则 {pattern!r}（当前：{value!r}）")
            except re.error:
                pass
        min_length = spec.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{location} 长度不足 {min_length}（当前：{value!r}）")
    if isinstance(value, dict):
        required = spec.get("required")
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{location} 缺少必需字段 '{key}'")
        properties = spec.get("properties")
        if isinstance(properties, dict):
            for key, child in properties.items():
                if key in value:
                    _validate_against_schema(value[key], child, f"{location}.{key}", root_schema, errors)
    if isinstance(value, list) and isinstance(spec.get("items"), dict):
        for index, item in enumerate(value):
            _validate_against_schema(item, spec["items"], f"{location}[{index}]", root_schema, errors)


def check_backlog(root: Path, policy: dict[str, Any], strict: bool) -> tuple[list[dict[str, Any]], int]:
    """§3.6：backlog.json 结构与语义（缺字段/非法枚举/active 状态字段/ID 连续/depends 断链）。"""
    _ = strict
    path = Path(root) / "backlog.json"
    if not path.is_file():
        return [], 0  # 缺文件：临时 fixture 降级跳过；真实仓库由 DoD 保证存在
    relative = rel_posix(path, root)
    issues: list[dict[str, Any]] = []
    try:
        payload = load_json(path)
    except Exception as exc:
        issues.append(_contract_issue("BACKLOG_SCHEMA", relative, f"JSON 无法解析：{exc}"))
        return issues, 1
    if not isinstance(payload, dict):
        issues.append(_contract_issue("BACKLOG_SCHEMA", relative, "顶层必须是 JSON object"))
        return issues, 1

    schema = load_backlog_schema(Path(root), policy)
    schema_errors: list[str] = []
    _validate_against_schema(payload, schema, "$", schema, schema_errors)
    for message in schema_errors:
        issues.append(_contract_issue("BACKLOG_SCHEMA", relative, message))

    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    checked = len(items)
    ids = [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]
    expected = [f"BL-{index:03d}" for index in range(1, len(items) + 1)]
    if ids != expected:
        duplicates = sorted(identifier for identifier in set(ids) if ids.count(identifier) > 1)
        missing = sorted(set(expected) - set(ids))
        detail: list[str] = []
        if missing:
            detail.append("跳号：" + "、".join(missing))
        if duplicates:
            detail.append("重复：" + "、".join(duplicates))
        if not missing and not duplicates:
            detail.append("ID 序列与 BL-001..BL-%03d 不一致" % len(items))
        issues.append(
            _contract_issue("BACKLOG_SEMANTIC", relative, "；".join(detail) + "（ID 只增不复用、必须连续）")
        )
        ids_set = set(ids)
    else:
        ids_set = set(expected)

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        location = f"items[{index}]"
        entry_id = item.get("id")
        status = item.get("status")
        if status in ("in_progress", "done"):
            for key in ("owner", "updated", "result"):
                value = item.get(key)
                if not isinstance(value, str) or not value.strip():
                    issues.append(
                        _contract_issue(
                            "BACKLOG_SEMANTIC",
                            relative,
                            f"{entry_id}（{location}）status={status} 必须填写非空 {key}",
                        )
                    )
            updated = item.get("updated")
            if isinstance(updated, str) and updated.strip() and not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", updated.strip()
            ):
                issues.append(
                    _contract_issue(
                        "BACKLOG_SEMANTIC",
                        relative,
                        f"{entry_id}（{location}）的 updated 必须是 YYYY-MM-DD（当前：{updated!r}）",
                    )
                )
        depends = item.get("depends")
        if isinstance(depends, list):
            for dependency in depends:
                if isinstance(dependency, str) and dependency not in ids_set:
                    issues.append(
                        _contract_issue(
                            "BACKLOG_SEMANTIC",
                            relative,
                            f"{entry_id}（{location}）depends 指向不存在的 {dependency}",
                        )
                    )
        outputs = item.get("outputs")
        if isinstance(outputs, list):
            for output in outputs:
                if isinstance(output, str) and _is_absolute(output):
                    issues.append(
                        _contract_issue(
                            "BACKLOG_SEMANTIC",
                            relative,
                            f"{entry_id}（{location}）outputs 必须是相对路径（当前：{output!r}）",
                        )
                    )
    return issues, checked


# ---------------------------------------------------------------------------
# §3.7 Agent 回归（AR-01..AR-10 中可机检部分：AR-01 见 check_protocol，
# AR-02 / AR-03 在此；AR-04/05 由测试实现，AR-07..AR-10 复用其余检查）
# ---------------------------------------------------------------------------

_INVARIANT_KEYWORD_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("不 Root", ("不 Root", "不Root", "不 root")),
    ("不卸载系统包", ("不卸载系统包",)),
    ("kill-all", ("kill-all", "kill all")),
    ("备份", ("备份", "快照")),
    ("凭据", ("凭据", "口令", "私钥", "证书", "token")),
    ("不伪造验收", ("不伪造验收", "不伪造")),
)
"""AR-03 关键红线关键词组（等价说法任一命中即可；manifest.invariants 需覆盖全部组）。"""


def _redline_items(text: str) -> list[str] | None:
    located = _section_body(text, "红线")
    if located is None:
        return None
    items: list[str] = []
    for line in located[1]:
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            items.append(stripped)
    return items


def check_agent_regression(root: Path, policy: dict[str, Any], strict: bool) -> tuple[list[dict[str, Any]], int]:
    """§3.7：AR-02（红线区每条含 GRD 链接、≥9 条）与 AR-03（manifest.invariants 关键红线词）。"""
    _ = strict
    issues: list[dict[str, Any]] = []
    checked = 0

    # AR-02：AGENTS.md 红线区
    agents_path = Path(root) / "AGENTS.md"
    agents_text = _read(agents_path) if agents_path.is_file() else None
    if agents_text is not None:
        checked += 1
        relative = rel_posix(agents_path, root)
        items = _redline_items(agents_text)
        if items is None:
            issues.append(
                _contract_issue("AGENT_REGRESSION", relative, "AR-02：缺少红线章节（H2 含关键字 '红线'）")
            )
        else:
            if len(items) < 9:
                issues.append(
                    _contract_issue(
                        "AGENT_REGRESSION",
                        relative,
                        f"AR-02：红线条目 {len(items)} 条少于 9 条（AGENTS §3 至少覆盖 9 条高频红线）",
                    )
                )
            for index, item in enumerate(items, start=1):
                if not re.search(r"\]\([^)]*GRD-[^)]*\)", item):
                    issues.append(
                        _contract_issue(
                            "AGENT_REGRESSION",
                            relative,
                            f"AR-02：第 {index} 条红线缺少 GRD 链接（每条红线必须给护栏文件链接）",
                        )
                    )

    # AR-03：manifest.invariants
    manifest_path = Path(root) / "agent-manifest.json"
    if manifest_path.is_file():
        try:
            manifest = load_json(manifest_path)
        except Exception:
            manifest = None
        if isinstance(manifest, dict):
            checked += 1
            relative = rel_posix(manifest_path, root)
            invariants = manifest.get("invariants")
            if not isinstance(invariants, list) or not invariants:
                issues.append(
                    _contract_issue("AGENT_REGRESSION", relative, "AR-03：manifest.invariants 必须非空")
                )
            else:
                invariant_text = "\n".join(str(item) for item in invariants if isinstance(item, str))
                for label, spellings in _INVARIANT_KEYWORD_GROUPS:
                    if not any(spelling in invariant_text for spelling in spellings):
                        issues.append(
                            _contract_issue(
                                "AGENT_REGRESSION",
                                relative,
                                f"AR-03：manifest.invariants 缺少关键红线关键词 '{label}'（请重跑 index 同步）",
                            )
                        )
    return issues, checked


# ---------------------------------------------------------------------------
# 汇总入口（validate_repo 调用）
# ---------------------------------------------------------------------------

GOVERNANCE_CHECKS = (
    check_protocol,
    check_naming,
    check_pitfalls,
    check_adr,
    check_changelog_archive,
    check_backlog,
    check_agent_regression,
)
"""validate 接入的治理检查顺序（也是报告 checked 的字段来源）。"""


def collect_governance(
    root: Path, policy: dict[str, Any], strict: bool
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """运行全部治理检查，返回 ``(issues, checked_extras)``。

    checked_extras 是报告 ``checked`` 的可读计数（协议行数/tier、命名文件数、
    PIT 条目数、ADR 篇数、backlog 条目数、归档行数、回归检查数）。
    """
    issues: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for check in GOVERNANCE_CHECKS:
        check_issues, checked = check(Path(root), policy, strict)
        issues.extend(check_issues)
        counts[check.__name__] = checked
    metrics = protocol_metrics(Path(root), policy)
    return issues, {
        "protocol": metrics["present"],
        "protocol_lines": metrics["lines"],
        "protocol_tier": metrics["tier"],
        "naming_files": counts.get("check_naming", 0),
        "pitfall_files": counts.get("check_pitfalls", 0),
        "adr_files": counts.get("check_adr", 0),
        "backlog": (Path(root) / "backlog.json").is_file(),
        "backlog_items": counts.get("check_backlog", 0),
        "changelog_archive_rows": counts.get("check_changelog_archive", 0),
        "agent_regression_checks": counts.get("check_agent_regression", 0),
    }
