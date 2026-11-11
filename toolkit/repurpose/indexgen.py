"""indexgen：扫描新层 Markdown 的 front matter，生成 ``agent-manifest.json``。

目录缺失时跳过并记 warning（不失败）；front matter 解析错误也记 warning/error，
不中断生成——校验职责在 ``validate`` 子命令。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .frontmatter import parse_document
from .util import (
    SCHEMA_MANIFEST,
    iso_now,
    rel_posix,
    write_json,
)

CONTENT_GROUPS = {
    "methodology": "methodology",
    "pitfalls": "pitfalls",
    "guardrails": "guardrails",
    "case_studies": "cases",
}
"""manifest.content 分组 → 仓库相对目录。"""

GROUP_REASONS = {
    "methodology": "方法论规范（先读——定义做什么与怎么做）",
    "tools": "工具与契约（再读——知道用什么命令做事）",
    "case_studies": "案例证据（看真实设备如何落地）",
    "guardrails": "红线（动手前必须确认不能做什么）",
    "pitfalls": "踩坑证据（避免重复历史错误）",
}
"""阅读顺序中每类的理由。"""

READING_GROUP_ORDER = ("methodology", "tools", "case_studies", "guardrails", "pitfalls")

INVARIANTS = [
    "不 Root/不刷机/不解锁 BL：除非用户对具体设备明确授权且评估门禁通过",
    "不卸载系统包：只允许 disable-user 并维护保护名单",
    "禁止 am kill-all 或随意 force-stop 服务器相关进程",
    "任何写操作先备份/快照并给出回滚路径；恢复未演练等价于没有回滚",
    "Tier2 写操作必须显式确认 + 快照 + 审计；Tier3 仅人工",
    "token/口令/私钥/证书/备份口令不进入仓库、日志、文档、聊天",
    "网络最小暴露：仅 loopback/局域网；ADB 维护后关闭",
    "不伪造验收：未实测不标完成，文档声称不算证据",
    "构建路径必须 ASCII（aapt2 不支持中文路径）",
]


def _entry_id(data: dict[str, Any]) -> str:
    value = data.get("id")
    return value if isinstance(value, str) else ""


def _entry(data: dict[str, Any], path: str) -> dict[str, Any]:
    """把 front matter 转成 manifest 条目（缺失字段用空值占位）。

    除必需键外保留检索键 severity/domain/scope/oem：pitfalls/README.md 明确
    承诺 agent-manifest 含 severity/domain，Agent 可据此过滤。
    """
    audience = data.get("audience")
    tags = data.get("tags")
    depends = data.get("depends")
    entry: dict[str, Any] = {
        "id": _entry_id(data),
        "title": data.get("title") if isinstance(data.get("title"), str) else "",
        "type": data.get("type") if isinstance(data.get("type"), str) else "",
        "status": data.get("status") if isinstance(data.get("status"), str) else "",
        "audience": audience if isinstance(audience, list) else [],
        "tags": tags if isinstance(tags, list) else [],
        "updated": data.get("updated") if isinstance(data.get("updated"), str) else "",
        "agent_hint": data.get("agent_hint") if isinstance(data.get("agent_hint"), str) else "",
        "depends": depends if isinstance(depends, list) else [],
        "path": path,
    }
    for optional_key in ("severity", "domain", "scope", "oem"):
        value = data.get(optional_key)
        if isinstance(value, str) and value:
            entry[optional_key] = value
    return entry


def _sort_key(entry: dict[str, Any]) -> tuple[int, int, str]:
    """组内排序：索引（type=index 或 id 以 -000 结尾）优先，其次按数字前缀/文件名。"""
    entry_id = entry.get("id") or ""
    filename = Path(entry.get("path") or "").name
    index_first = 0 if entry.get("type") == "index" or entry_id.endswith("-000") else 1
    number = 9999
    for token in filename.replace(".md", "").split("-"):
        if token.isdigit():
            number = int(token)
            break
    return (index_first, number, filename.lower())


def scan_group(root: Path, directory_name: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """扫描一个内容目录，返回 ``(entries, warnings, errors)``。"""
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    directory = root / directory_name
    if not directory.is_dir():
        warnings.append(f"目录不存在，已跳过：{directory_name}/")
        return entries, warnings, errors
    markdown_files = sorted(directory.rglob("*.md"))
    if not markdown_files:
        warnings.append(f"目录中没有 .md 文件：{directory_name}/")
        return entries, warnings, errors
    for path in markdown_files:
        relative = rel_posix(path, root)
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            errors.append(f"无法读取：{relative}")
            continue
        data, parse_errors, _body = parse_document(text)
        for parse_error in parse_errors:
            warnings.append(f"{relative}: {parse_error}")
        if not data:
            warnings.append(f"{relative}: 缺少 front matter，未纳入索引")
            continue
        entry = _entry(data, relative)
        if not entry["id"]:
            warnings.append(f"{relative}: front matter 缺少 id，未纳入索引")
            continue
        entries.append(entry)
    entries.sort(key=_sort_key)
    return entries, warnings, errors


def _build_tools(root: Path, warnings: list[str]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = [
        {
            "name": "repurpose",
            "kind": "cli",
            "path": "toolkit/README.md",
            "entry": "python -m toolkit.repurpose",
            "commands": [
                "detect",
                "probe",
                "assess",
                "plan",
                "new-profile",
                "index",
                "validate",
            ],
        },
    ]
    wrappers = (
        ("repurpose-ps1", "wrapper", "toolkit/repurpose.ps1", "PowerShell 包装（转发到 python -m）"),
        ("termux-healthcheck", "termux", "toolkit/termux/healthcheck.sh", "只读健康检查"),
        ("termux-soak", "termux", "toolkit/termux/soak.sh", "24h soak 观测（可中断）"),
        (
            "termux-boot-starter",
            "termux",
            "toolkit/termux/boot-starter.sh",
            "Termux:Boot 自启引导（幂等/可 dry-run）",
        ),
    )
    for name, kind, relative, description in wrappers:
        if (root / relative).is_file():
            tools.append({"name": name, "kind": kind, "path": relative, "description": description})
        else:
            warnings.append(f"工具文件缺失，未纳入 manifest.tools：{relative}")
    return tools


def _build_commands() -> list[dict[str, str]]:
    return [
        {
            "name": "detect",
            "cmd": "python -m toolkit.repurpose detect --out profiles/<codename>.json",
            "note": "只读采集 profile 骨架（默认脱敏；无设备时用 --adb-fixture 回放）",
        },
        {
            "name": "probe",
            "cmd": "python -m toolkit.repurpose probe --base profiles/<codename>.json --out profiles/<codename>-probed.json",
            "note": "补齐 12 项 capabilities/verdicts",
        },
        {
            "name": "assess",
            "cmd": "python -m toolkit.repurpose assess --profile profiles/<codename>-probed.json --json",
            "note": "离线路线评估（A/B/C/D + 门禁）",
        },
        {
            "name": "plan",
            "cmd": "python -m toolkit.repurpose plan --profile profiles/<codename>-probed.json --format md",
            "note": "生成 P0–P6 阶段计划",
        },
        {
            "name": "index",
            "cmd": "python -m toolkit.repurpose index",
            "note": "重建 agent-manifest.json",
        },
        {
            "name": "validate",
            "cmd": "python -m toolkit.repurpose validate --strict",
            "note": "front matter/ID/断链/JSON/manifest 校验",
        },
        {
            "name": "unittest",
            "cmd": "python -m unittest discover -s toolkit/tests -t . -v",
            "note": "工具链单元测试（离线、无真机）",
        },
        {
            "name": "healthcheck",
            "cmd": "bash toolkit/termux/healthcheck.sh --once",
            "note": "Termux 侧只读健康检查",
        },
        {
            "name": "soak",
            "cmd": "bash toolkit/termux/soak.sh --duration 24h --interval 300 --out soak.csv",
            "note": "24h soak 观测（可 Ctrl-C 中断并落盘汇总）",
        },
    ]


def build_manifest(root: str | Path, generated_at: str | None = None) -> dict[str, Any]:
    """构建 agent-manifest 对象（不写文件）。"""
    repo_root = Path(root)
    warnings: list[str] = []
    errors: list[str] = []
    content: dict[str, list[dict[str, Any]]] = {group: [] for group in CONTENT_GROUPS}
    for group, directory_name in CONTENT_GROUPS.items():
        entries, group_warnings, group_errors = scan_group(repo_root, directory_name)
        content[group] = entries
        warnings.extend(group_warnings)
        errors.extend(group_errors)

    toolkit_entries: list[dict[str, Any]] = []
    toolkit_readme = repo_root / "toolkit" / "README.md"
    if toolkit_readme.is_file():
        try:
            text = toolkit_readme.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            warnings.append("无法读取 toolkit/README.md")
        else:
            data, parse_errors, _body = parse_document(text)
            for parse_error in parse_errors:
                warnings.append(f"toolkit/README.md: {parse_error}")
            if data.get("id"):
                toolkit_entries = [_entry(data, "toolkit/README.md")]
            else:
                warnings.append("toolkit/README.md: front matter 缺少 id，未纳入索引")
    else:
        warnings.append("toolkit/README.md 不存在，工具入口未纳入索引")

    # 阅读顺序：方法论 → 工具 → 案例 → 护栏 → 踩坑；组内索引优先、编号升序。
    reads_by_group: dict[str, list[dict[str, Any]]] = {
        "methodology": content["methodology"],
        "tools": toolkit_entries,
        "case_studies": content["case_studies"],
        "guardrails": content["guardrails"],
        "pitfalls": content["pitfalls"],
    }
    reading_order: list[dict[str, Any]] = []
    step = 0
    for group in READING_GROUP_ORDER:
        for entry in reads_by_group[group]:
            step += 1
            reading_order.append(
                {
                    "step": step,
                    "id": entry["id"],
                    "path": entry["path"],
                    "title": entry["title"],
                    "reason": GROUP_REASONS[group],
                }
            )

    entrypoints: list[dict[str, Any]] = []
    for entry in reading_order:
        if entry["id"] == "MTH-000" or entry["path"] == "toolkit/README.md":
            entrypoints.append(entry)
    for entry in reading_order:
        if entry["id"].endswith("-000") and entry not in entrypoints:
            entrypoints.append(entry)
    if not entrypoints:
        warnings.append("未找到任何索引/入口文档（*-000），manifest.entrypoints 为空")

    tools = _build_tools(repo_root, warnings)
    counts = {
        "methodology": len(content["methodology"]),
        "pitfalls": len(content["pitfalls"]),
        "guardrails": len(content["guardrails"]),
        "case_studies": len(content["case_studies"]),
        "tools": len(tools),
        "entrypoints": len(entrypoints),
        "reading_order": len(reading_order),
        "total_entry_docs": sum(len(entries) for entries in content.values()),
    }

    manifest: dict[str, Any] = {
        "schema": SCHEMA_MANIFEST,
        "generated_at": generated_at or iso_now(),
        "repo": {
            "name": repo_root.resolve().name,
            "root": ".",
        },
        "entrypoints": entrypoints,
        "reading_order": reading_order,
        "content": content,
        "tools": tools,
        "invariants": INVARIANTS,
        "commands": _build_commands(),
        "counts": counts,
        "warnings": warnings,
        "errors": errors,
    }
    protocol = [
        relative
        for relative in ("AGENTS.md", "backlog.json", "README.md")
        if (repo_root / relative).is_file()
    ]
    if protocol:
        manifest["repo"]["protocol"] = protocol  # type: ignore[index]
    return manifest


def default_manifest_path(root: str | Path) -> Path:
    """index 默认写入 ``<root>/agent-manifest.json``。"""
    return Path(root) / "agent-manifest.json"


def write_manifest(
    root: str | Path, out: str | Path | None = None, *, generated_at: str | None = None
) -> tuple[Path, dict[str, Any]]:
    """生成并写入 manifest，返回 ``(输出路径, manifest)``。"""
    manifest = build_manifest(root, generated_at=generated_at)
    target = Path(out) if out else default_manifest_path(root)
    write_json(target, manifest)
    return target, manifest


def format_index_summary(manifest: dict[str, Any], target: Path | None = None) -> str:
    """人类可读的 index 摘要（--json 之外的默认输出）。"""
    lines = ["agent-manifest 生成完成"]
    if target is not None:
        try:
            display = target.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except (ValueError, OSError):
            display = target.name
        lines.append(f"- 输出：{display}")
    lines.append(f"- schema：{manifest.get('schema')}")
    lines.append(f"- generated_at：{manifest.get('generated_at')}")
    counts = manifest.get("counts") or {}
    lines.append(
        "- 计数：methodology={} pitfalls={} guardrails={} case_studies={} entrypoints={} reading_order={}".format(
            counts.get("methodology", 0),
            counts.get("pitfalls", 0),
            counts.get("guardrails", 0),
            counts.get("case_studies", 0),
            counts.get("entrypoints", 0),
            counts.get("reading_order", 0),
        )
    )
    warnings = manifest.get("warnings") or []
    errors = manifest.get("errors") or []
    if warnings:
        lines.append(f"- warnings（{len(warnings)}）：")
        lines.extend(f"  - {item}" for item in warnings)
    if errors:
        lines.append(f"- errors（{len(errors)}）：")
        lines.extend(f"  - {item}" for item in errors)
    if not warnings and not errors:
        lines.append("- 无 warnings/errors")
    return "\n".join(lines)
