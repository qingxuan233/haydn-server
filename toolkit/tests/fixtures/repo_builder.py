"""临时仓库生成器：为 index/validate/governance/preflight 测试构造可控仓库。

所有生成器只写调用方传入的临时目录（unittest 的 TemporaryDirectory），
不触碰真实仓库；测试退出后目录自动清理。

``build_sample_repo`` 生成**结构完整**的最小仓库：四层内容 + toolkit 入口 +
AGENTS.md（协议版本行/必需 H2/哨兵/9 条带 GRD 链接的红线）+ backlog.json +
CHANGELOG.md（当前窗口 + §4 归档索引）+ adr/README.md + adr/0001。
这样 ``validate --strict`` 能全绿，新治理检查不会误伤既有测试。
各 ``write_*`` 辅助函数供测试构造违规样本（缺章节/非法枚举/跳号/归档数不符等）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DEFAULT_UPDATED = "2026-11-11"

AGENTS_REQUIRED_SECTIONS: tuple[str, ...] = (
    "启动清单",
    "红线",
    "任务协议",
    "完成定义",
    "机器可读接口",
    "本文件的维护",
)
"""AGENTS.md 协议必需 H2 章节关键字（顺序即 fixture 章节顺序）。"""

PITFALL_REQUIRED_SECTIONS: tuple[str, ...] = ("症状", "根因", "规避", "验证", "证据")
ADR_REQUIRED_SECTIONS: tuple[str, ...] = ("状态", "背景", "决策", "后果")


def make_front_matter(
    *,
    entry_id: str,
    title: str,
    doc_type: str,
    status: str = "current",
    audience: str = "human, agent",
    tags: str = "test",
    depends: str = "",
    updated: str = DEFAULT_UPDATED,
    agent_hint: str = "测试用文档：按 front matter 约定生成",
    extra: Mapping[str, str] | None = None,
    omit_keys: Iterable[str] = (),
    override: Mapping[str, str] | None = None,
    **extra_fields: str,
) -> str:
    """生成 flat YAML front matter（不含正文）。未知键按额外字段写入。"""
    rows: dict[str, str] = {
        "id": entry_id,
        "title": title,
        "type": doc_type,
        "status": status,
        "audience": audience,
        "tags": tags,
        "depends": depends,
        "updated": updated,
        "agent_hint": agent_hint,
    }
    for omitted in omit_keys:
        rows.pop(omitted, None)
    for key, value in (override or {}).items():
        rows[key] = value
    for key, value in (extra or {}).items():
        rows[key] = value
    for key, value in extra_fields.items():
        rows[key] = str(value)
    lines = ["---"]
    for key, value in rows.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def write_doc(
    root: Path,
    relative: str,
    *,
    entry_id: str,
    title: str,
    doc_type: str,
    body: str = "# 测试文档\n\n正文。\n",
    **kwargs,
) -> Path:
    """在临时仓库写入一篇带 front matter 的 Markdown。"""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    front = make_front_matter(entry_id=entry_id, title=title, doc_type=doc_type, **kwargs)
    path.write_text(front + "\n" + body, encoding="utf-8", newline="\n")
    return path


def write_text(root: Path, relative: str, text: str) -> Path:
    """写入任意文本文件（自动建父目录、UTF-8、LF）。"""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


# ---------------------------------------------------------------------------
# AGENTS.md（协议检查 / AR-02 样本）
# ---------------------------------------------------------------------------


def write_agents_md(
    root: Path,
    *,
    protocol_version: str = "v1.2",
    omit_version_row: bool = False,
    omit_sections: Iterable[str] = (),
    redline_count: int = 9,
    redline_link: str = "guardrails/GRD-001-demo.md",
    sentinel: bool = True,
    padding_lines: int = 0,
) -> Path:
    """写 AGENTS.md fixture：版本行 + 必需 H2 + 9 条带 GRD 链接红线 + 哨兵。

    - ``omit_version_row=True``：版本行非法/缺失（PROTOCOL_VERSION）。
    - ``omit_sections``：去掉指定必需章节（PROTOCOL_SECTION）。
    - ``redline_count``：红线数量（AR-02 要求 ≥9）；``sentinel=False`` 去掉末行哨兵。
    - ``padding_lines``：追加 padding 注释行控制文件体积（PROTOCOL_SIZE）。
    """
    lines = [
        "# AGENTS.md（fixture 协议）",
        "",
        "> toolkit 单元测试临时仓库的最小 Agent 协议；结构与真实 AGENTS.md 对齐。",
        "",
        "| 项目 | 内容 |",
        "|---|---|",
    ]
    if not omit_version_row:
        lines.append(f"| 协议版本 | {protocol_version} |")
    lines.extend(["| 用途 | 单元测试 fixture |", "", "---", ""])
    for index, section in enumerate(AGENTS_REQUIRED_SECTIONS):
        if section in omit_sections:
            continue
        lines.append(f"## {index}. {section}")
        lines.append("")
        if section == "红线":
            for redline_index in range(1, redline_count + 1):
                lines.append(
                    f"{redline_index}. **fixture 红线 {redline_index}**："
                    f"见 [GRD-001]({redline_link})。"
                )
        elif section == "机器可读接口":
            lines.extend(
                [
                    "```yaml",
                    "exit_codes: {0: VERIFIED_ALL, 3: SKIPPED, 4: FAILED}",
                    "```",
                ]
            )
        else:
            lines.append("- fixture 章节：真实仓库按 AGENTS.md 约定展开。")
        lines.append("")
    for index in range(padding_lines):
        lines.append(f"<!-- fixture padding {index + 1} -->")
    if padding_lines:
        lines.append("")
    if sentinel:
        lines.append("<!-- END-OF-PROTOCOL -->")
    return write_text(root, "AGENTS.md", "\n".join(lines) + "\n")


# -------------------------------------------------------------------
# backlog.json（BACKLOG_SCHEMA / BACKLOG_SEMANTIC 样本）
# -------------------------------------------------------------------


def make_backlog_item(entry_id: str = "BL-001", **overrides: object) -> dict[str, object]:
    """生成一条合法 backlog item；``overrides`` 可删除键（值传 ``None``）或改值。"""
    item: dict[str, object] = {
        "id": entry_id,
        "title": f"fixture 任务 {entry_id}",
        "priority": "P1",
        "area": "toolkit",
        "status": "pending",
        "acceptance": "单元测试通过",
        "outputs": ["toolkit/README.md"],
        "depends": [],
        "notes": "",
        "agent_hint": "先跑 validate --strict",
        "requires": "",
        "owner": "",
        "updated": "",
        "result": "",
    }
    for key, value in overrides.items():
        if value is None:
            item.pop(key, None)
        else:
            item[key] = value
    return item


def write_backlog(
    root: Path,
    items: Sequence[Mapping[str, object]] | None = None,
    *,
    schema: str = "repurpose.backlog.v1",
    updated: str = DEFAULT_UPDATED,
    omit_keys: Iterable[str] = (),
) -> Path:
    """写 backlog.json；默认两条合法条目（BL-001 pending / BL-002 done）。"""
    if items is None:
        items = [
            make_backlog_item("BL-001"),
            make_backlog_item(
                "BL-002",
                status="done",
                owner="toolkit",
                updated=DEFAULT_UPDATED,
                result="已完成：fixture 基线",
                depends=["BL-001"],
            ),
        ]
    payload: dict[str, object] = {
        "schema": schema,
        "updated": updated,
        "owner": "lead",
        "notes": "fixture backlog",
        "items": list(items),
    }
    for key in omit_keys:
        payload.pop(key, None)
    return write_text(root, "backlog.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def write_backlog_raw(root: Path, text: str) -> Path:
    """写入任意 backlog 文本（用于 JSON 解析失败测试）。"""
    return write_text(root, "backlog.json", text)


def write_backlog_archive(
    root: Path,
    items: Sequence[Mapping[str, object]],
    *,
    schema: str = "repurpose.backlog-archive.v1",
    updated: str = DEFAULT_UPDATED,
    omit_keys: Iterable[str] = (),
) -> Path:
    """写 backlog-archive.json（归档条目默认按传入顺序；调用方负责 ID 升序与 status=done）。"""
    payload: dict[str, object] = {
        "schema": schema,
        "updated": updated,
        "items": list(items),
    }
    for key in omit_keys:
        payload.pop(key, None)
    return write_text(
        root, "backlog-archive.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )


# -------------------------------------------------------------------
# CHANGELOG.md + changelog/YYYY-MM.md（CHANGELOG_ARCHIVE 样本）
# -------------------------------------------------------------------

ARCHIVE_SECTION_HEADER = (
    "## 4. 归档索引",
    "",
    "| 月份 | 条数 | 文件 |",
    "|---|---|---|",
)


def write_changelog(
    root: Path,
    *,
    window_rows: int = 1,
    archive_rows: Sequence[str] | None = None,
) -> Path:
    """写 CHANGELOG.md；``archive_rows`` 为 §4 数据行（缺省空索引）。"""
    lines = [
        "# 变更记录（fixture CHANGELOG）",
        "",
        "## 3. 当前变更（当前窗口 ≤8 条）",
        "",
        "| 日期 | 版本 | 变更 |",
        "|---|---|---|",
    ]
    for index in range(window_rows):
        lines.append(f"| 2026-11-{index + 1:02d} | v0.{index + 1} | fixture 变更条目 |")
    lines.extend(["", *ARCHIVE_SECTION_HEADER])
    for row in archive_rows or ():
        lines.append(row)
    lines.append("")
    return write_text(root, "CHANGELOG.md", "\n".join(lines) + "\n")


def write_changelog_archive(
    root: Path,
    *,
    month: str = "2026-10",
    rows: int = 5,
    version_base: str = "v0.1",
    version_step: int = 1,
) -> Path:
    """写 changelog/<month>.md 归档文件（窗口数据行 + 版本号）。"""
    lines = [f"# {month} 归档", ""]
    major, minor = version_base.lstrip("v").split(".")
    start = int(minor)
    for index in range(rows):
        version = f"v{major}.{start + index * version_step}"
        lines.append(f"| 2026-{month[5:]}-{(index % 27) + 1:02d} | {version} | 归档条目 |")
    lines.append("")
    return write_text(root, f"changelog/{month}.md", "\n".join(lines) + "\n")


def write_changelog_with_archive(
    root: Path,
    *,
    month: str = "2026-10",
    rows: int = 5,
    declared_count: int | None = None,
    declared_range: tuple[str, str] = ("v0.1", "v0.5"),
    link: bool = True,
    window_rows: int = 1,
) -> Path:
    """同时写归档文件与 §4 索引行（默认一切一致；参数可制造不一致样本）。"""
    archive_path = write_changelog_archive(root)
    declared = rows if declared_count is None else declared_count
    range_text = f"{declared_range[0]}–{declared_range[1]}"
    target = f"changelog/{month}.md"
    if link:
        row = f"| {month} | {declared} 条（{range_text}） | [{target}]({target}) |"
    else:
        row = f"| {month} | {declared} 条（{range_text}） | {target} |"
    return write_changelog(root, window_rows=window_rows, archive_rows=[row])


def write_unindexed_archive(root: Path, *, month: str = "2026-10", rows: int = 2) -> Path:
    """只写归档文件、不登记 §4（用于"归档文件未登记"反例）。"""
    archive_path = write_changelog_archive(root, month=month, rows=rows)
    write_changelog(root, window_rows=1)
    return archive_path


# -------------------------------------------------------------------
# adr/（ADR_FILENAME / ADR_ID / ADR_STATUS / ADR_SECTION / ADR_INDEX 样本）
# -------------------------------------------------------------------


def write_adr_index(root: Path, *, filenames: Sequence[str] | None = None) -> Path:
    """写 adr/README.md 索引；``filenames=None`` 时扫描现有 adr/*.md 并全部登记。"""
    if filenames is None:
        directory = root / "adr"
        filenames = sorted(
            path.name
            for path in directory.glob("*.md")
            if path.name != "README.md" and path.is_file()
        ) if directory.is_dir() else []
    body_lines = ["# 决策索引", "", "状态枚举：proposed / accepted / superseded。", ""]
    for filename in filenames:
        body_lines.append(f"- [ADR-{filename[:4]}]({filename})")
    body_lines.append("")
    return write_doc(
        root,
        "adr/README.md",
        entry_id="ADR-000",
        title="决策记录索引",
        doc_type="index",
        body="\n".join(body_lines),
        tags="adr, index",
    )


def write_adr(
    root: Path,
    number: int = 1,
    slug: str = "demo",
    *,
    entry_id: str | None = None,
    status: str = "accepted",
    doc_type: str = "adr",
    sections: Sequence[str] = ADR_REQUIRED_SECTIONS,
    superseded_by: str | None = None,
    extra_body: str = "",
) -> Path:
    """写一篇 ADR；参数可制造 id/status/章节/superseded 违规样本。"""
    filename = f"{number:04d}-{slug}.md"
    resolved_id = entry_id if entry_id is not None else f"ADR-{number:04d}"
    body_lines = [f"# ADR-{number:04d} · {slug}", ""]
    for section in sections:
        body_lines.extend([f"## {section}", "", f"{section}：fixture 内容。", ""])
    if extra_body:
        body_lines.append(extra_body)
    extra: dict[str, str] = {}
    if superseded_by is not None:
        extra["superseded_by"] = superseded_by
    return write_doc(
        root,
        f"adr/{filename}",
        entry_id=resolved_id,
        title=f"ADR fixture {slug}",
        doc_type=doc_type,
        status=status,
        body="\n".join(body_lines),
        extra=extra,
    )


# -------------------------------------------------------------------
# pitfalls（PIT_ID_GAP / PIT_SECTION / PIT_COUNT 样本）
# -------------------------------------------------------------------


def make_pitfall_body(entry_id: str, *, sections: Sequence[str] = PITFALL_REQUIRED_SECTIONS) -> str:
    lines = [f"# 踩坑 {entry_id}", ""]
    for section in sections:
        lines.extend([f"## {section}", "", f"{section}：fixture 内容。", ""])
    return "\n".join(lines)


def write_pitfall(
    root: Path,
    number: int,
    slug: str = "demo",
    *,
    entry_id: str | None = None,
    sections: Sequence[str] = PITFALL_REQUIRED_SECTIONS,
    severity: str = "S2",
    domain: str = "server",
    body: str | None = None,
) -> Path:
    """写一条 PIT 条目；``sections`` 可裁剪、``entry_id`` 可制造 id 不一致样本。"""
    resolved_id = entry_id if entry_id is not None else f"PIT-{number:03d}"
    return write_doc(
        root,
        f"pitfalls/PIT-{number:03d}-{slug}.md",
        entry_id=resolved_id,
        title=f"fixture 踩坑 {number}",
        doc_type="pitfall",
        severity=severity,
        domain=domain,
        body=body if body is not None else make_pitfall_body(resolved_id, sections=sections),
    )


# -------------------------------------------------------------------
# preflight 外部步骤 stub（临时仓库内，避免触碰真实仓库）
# -------------------------------------------------------------------


def write_preflight_harness(
    root: Path,
    *,
    tests_pass: bool = True,
    links_ok: bool = True,
    with_tests: bool = True,
    with_check_links: bool = True,
) -> None:
    """写 preflight 外部步骤的最小 stub（临时仓库内）：

    - ``toolkit/__init__.py`` + ``toolkit/tests/``：可被 unittest discover 的冒烟测试；
    - ``scripts/dev/check-links.py``：退出码 0/1 的 stub（不访问真实 scripts/）。
    """
    if with_tests:
        write_text(root, "toolkit/__init__.py", '"""fixture toolkit 包（preflight 测试用）。"""\n')
        write_text(root, "toolkit/tests/__init__.py", "")
        verdict = "self.assertTrue(True)" if tests_pass else 'self.fail("forced failure")'
        write_text(
            root,
            "toolkit/tests/test_smoke.py",
            '"""fixture 冒烟测试（preflight unittest 步骤）。"""\n\n'
            "import unittest\n\n\n"
            "class SmokeTests(unittest.TestCase):\n"
            "    def test_smoke(self):\n"
            f"        {verdict}\n",
        )
    if with_check_links:
        exit_code = 0 if links_ok else 1
        write_text(
            root,
            "scripts/dev/check-links.py",
            '"""fixture 相对链接检查 stub（不触碰真实仓库）。"""\n\n'
            "import sys\n\n"
            'print("fixture check-links: ok")\n'
            f"sys.exit({exit_code})\n",
        )


# -------------------------------------------------------------------
# 完整最小仓库
# -------------------------------------------------------------------


def build_sample_repo(
    root: Path,
    *,
    with_toolkit_readme: bool = True,
    with_governance_files: bool = True,
) -> Path:
    """生成一个结构完整、front matter 合法、链接有效的最小新层仓库。

    ``with_governance_files=False`` 时不写 AGENTS.md/backlog.json/CHANGELOG.md/adr/
    （用于验证"缺新结构时治理检查降级跳过、不误报 error"）。
    """
    root.mkdir(parents=True, exist_ok=True)
    write_doc(
        root,
        "methodology/README.md",
        entry_id="MTH-000",
        title="方法论索引",
        doc_type="index",
        body=("# 方法论索引\n\n关联：[工具入口](../toolkit/README.md)、[基础](00-foundations.md)。\n"
              if with_toolkit_readme
              else "# 方法论索引\n\n关联：[基础](00-foundations.md)。\n"),
    )
    write_doc(
        root,
        "methodology/00-foundations.md",
        entry_id="MTH-001",
        title="基础",
        doc_type="methodology",
        tags="foundations, test",
        depends="MTH-000",
        body="# 基础\n\n返回 [索引](README.md)。\n",
    )
    write_doc(
        root,
        "pitfalls/README.md",
        entry_id="PIT-000",
        title="踩坑索引",
        doc_type="pitfall",
        severity="S4",
        domain="docs",
        body="# 踩坑索引\n\n- [PIT-001](PIT-001-demo.md)\n",
    )
    write_pitfall(root, 1, "demo")
    write_doc(
        root,
        "guardrails/README.md",
        entry_id="GRD-000",
        title="护栏索引",
        doc_type="guardrail",
        severity="warning",
        scope="repo",
        body="# 护栏索引\n\n- [GRD-001](GRD-001-demo.md)\n",
    )
    write_doc(
        root,
        "guardrails/GRD-001-demo.md",
        entry_id="GRD-001",
        title="示例护栏",
        doc_type="guardrail",
        severity="blocker",
        scope="device",
        body="# 示例护栏\n\n关联 [踩坑](../pitfalls/README.md)。\n",
    )
    write_doc(
        root,
        "cases/README.md",
        entry_id="CASE-000",
        title="案例索引",
        doc_type="index",
        body="# 案例索引\n\n- [示例案例](demo/README.md)\n",
    )
    write_doc(
        root,
        "cases/demo/README.md",
        entry_id="CASE-001",
        title="示例案例",
        doc_type="case-study",
        body="# 示例案例\n\nprofile 路径见 `cases/demo/profile.json`。\n",
    )
    if with_governance_files:
        write_agents_md(root)
        write_backlog(root)
        write_changelog(root, window_rows=1)
        write_adr(root, 1, "demo")
        write_adr_index(root)
    if with_toolkit_readme:
        # §3.1 工具登记表与 cli.build_parser() 的 10 个子命令一致，
        # 脚本链接指向下方 stub，保证 TOOL 登记表一致性机检在 fixture 中全绿。
        registry = ["# 工具链\n\n零第三方依赖。\n", "## 3.1 工具登记表（fixture）\n",
                    "| ID | 能力 | 入口 | 设备/环境 |", "|---|---|---|---|"]
        cli_commands = (
            "detect", "probe", "assess", "plan", "rootcheck",
            "rescue-kit", "new-profile", "index", "validate", "preflight",
        )
        for index, command in enumerate(cli_commands, start=1):
            registry.append(
                f"| TOOL-{index:03d} | {command} | `python -m toolkit.repurpose {command}` | 离线 |"
            )
        scripts = (
            ("healthcheck.sh", "termux/healthcheck.sh"),
            ("soak.sh", "termux/soak.sh"),
            ("boot-starter.sh", "termux/boot-starter.sh"),
        )
        for index, (name, relative) in enumerate(scripts, start=len(cli_commands) + 1):
            registry.append(f"| TOOL-{index:03d} | {name} | [{relative}]({relative}) | 离线 |")
        write_doc(
            root,
            "toolkit/README.md",
            entry_id="TOOL-000",
            title="工具链",
            doc_type="index",
            body="\n".join(registry) + "\n",
        )
        # 让 manifest.tools 能找到包装/脚本（内容为空不影响 index；validate 不检查 .ps1/.sh）。
        stubs = {
            "toolkit/repurpose.ps1": "# stub ps1\n",
            "toolkit/termux/healthcheck.sh": "#!/usr/bin/env bash\n",
            "toolkit/termux/soak.sh": "#!/usr/bin/env bash\n",
            "toolkit/termux/boot-starter.sh": "#!/usr/bin/env bash\n",
        }
        for relative, content in stubs.items():
            write_text(root, relative, content)
    return root


def add_valid_json(root: Path, relative: str, payload_text: str) -> Path:
    """写入任意 JSON 文本（用于 JSON 解析校验测试）。"""
    return write_text(root, relative, payload_text)
