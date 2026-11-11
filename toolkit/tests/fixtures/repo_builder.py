"""临时仓库生成器：为 index/validate 测试构造可控的 Markdown 仓库。

所有生成器只写调用方传入的临时目录（unittest 的 TemporaryDirectory），
不触碰真实仓库；测试退出后目录自动清理。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

DEFAULT_UPDATED = "2026-11-11"


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


def build_sample_repo(root: Path, *, with_toolkit_readme: bool = True) -> Path:
    """生成一个结构完整、front matter 合法、链接有效的最小新层仓库。"""
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
    write_doc(
        root,
        "pitfalls/PIT-001-demo.md",
        entry_id="PIT-001",
        title="示例踩坑",
        doc_type="pitfall",
        severity="S2",
        domain="server",
        body="# 示例踩坑\n\n关联 [护栏](../guardrails/README.md)。\n",
    )
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
    if with_toolkit_readme:
        write_doc(
            root,
            "toolkit/README.md",
            entry_id="TOOL-000",
            title="工具链",
            doc_type="index",
            body="# 工具链\n\n无第三方依赖。\n",
        )
        # 让 manifest.tools 能找到包装/脚本（内容为空不影响 index；validate 不检查 .ps1/.sh）。
        stubs = {
            "toolkit/repurpose.ps1": "# stub ps1\n",
            "toolkit/termux/healthcheck.sh": "#!/usr/bin/env bash\n",
            "toolkit/termux/soak.sh": "#!/usr/bin/env bash\n",
            "toolkit/termux/boot-starter.sh": "#!/usr/bin/env bash\n",
        }
        for relative, content in stubs.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    return root


def add_valid_json(root: Path, relative: str, payload_text: str) -> Path:
    """写入任意 JSON 文本（用于 JSON 解析校验测试）。"""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload_text, encoding="utf-8", newline="\n")
    return path
