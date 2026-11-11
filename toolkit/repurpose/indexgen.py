"""indexgen：生成"根摘要 + 按层分片"的机器索引。

产物：
- ``agent-manifest.json``（schema ``repurpose.agent-manifest.v1``）：≤160 行摘要，
  Agent 先读它，再按需读一个分片；
- ``agent-manifest.d/{methodology,pitfalls,guardrails,case-studies}.json``
  （schema ``repurpose.manifest-shard.v1``）：每层一个文件，默认目录 gitignored 之外的
  生成物，每片 ≤300 行 / ≤32KB / ≤40 条（上限来自 toolkit/schema/doc-policy.json）。

内容缺失/半成品（Lead 并行编辑）时：目录缺失或 front matter 解析错误只记 warning/error，
不中断生成。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .docpolicy import load_policy, manifest_limits
from .frontmatter import parse_document
from .util import (
    SCHEMA_MANIFEST,
    iso_now,
    load_json,
    rel_posix,
    write_text,
)

SCHEMA_SHARD = "repurpose.manifest-shard.v1"
SHARD_DIR = "agent-manifest.d"
MANIFEST_FILENAME = "agent-manifest.json"

CONTENT_GROUPS = {
    "methodology": "methodology",
    "pitfalls": "pitfalls",
    "guardrails": "guardrails",
    "case_studies": "cases",
}
"""根 counts / shards 的层键 → 仓库相对目录。"""

SHARD_FILENAMES = {
    "methodology": "methodology.json",
    "pitfalls": "pitfalls.json",
    "guardrails": "guardrails.json",
    "case_studies": "case-studies.json",
}
"""层键 → 分片文件名（ASCII，固定）。"""

SHARD_REQUIRED_KEYS = ("id", "title", "path", "type", "status", "tags", "agent_hint")
SHARD_OPTIONAL_KEYS = ("severity", "domain", "scope", "oem")
"""分片条目字段：必需 + pitfall/guardrail/oem 的检索键。"""

READING_GROUP_ORDER = ("methodology", "tools", "case_studies", "guardrails", "pitfalls")
GROUP_REASONS = {
    "methodology": "方法论规范（先读——定义做什么与怎么做）",
    "tools": "工具与契约（再读——知道用什么命令做事）",
    "case_studies": "案例证据（看真实设备如何落地）",
    "guardrails": "红线（动手前必须确认不能做什么）",
    "pitfalls": "踩坑证据（避免重复历史错误）",
}

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


def default_manifest_path(root: str | Path) -> Path:
    """根摘要默认路径：``<root>/agent-manifest.json``。"""
    return Path(root) / MANIFEST_FILENAME


def default_shard_dir(root: str | Path) -> Path:
    """分片默认目录：``<root>/agent-manifest.d``。"""
    return Path(root) / SHARD_DIR


def shard_relative_path(layer: str) -> str:
    """分片的仓库相对 POSIX 路径。"""
    return f"{SHARD_DIR}/{SHARD_FILENAMES[layer]}"


# ---------------------------------------------------------------------------
# 扫描内容层
# ---------------------------------------------------------------------------


def _sort_key(entry: dict[str, Any]) -> tuple[int, int, str]:
    """组内排序：索引（type=index 或 id 以 -000 结尾）优先，其次按编号/文件名。

    编号优先取文件名中的数字前缀；目录型 README（如 cases/<codename>/README.md）
    没有数字时回退到 ID 尾号（CASE-001 先于 CASE-002），保证阅读顺序稳定。
    """
    entry_id = entry.get("id") or ""
    filename = Path(entry.get("path") or "").name
    index_first = 0 if entry.get("type") == "index" or entry_id.endswith("-000") else 1
    number = 9999
    for token in filename.replace(".md", "").split("-"):
        if token.isdigit():
            number = int(token)
            break
    if number == 9999:
        match = re.search(r"-([0-9]{3})$", entry_id)
        if match:
            number = int(match.group(1))
    return (index_first, number, filename.lower())


def _full_entry(data: dict[str, Any], path: str) -> dict[str, Any]:
    """front matter → 内部完整条目（用于生成根/分片的最小字段）。"""
    audience = data.get("audience")
    tags = data.get("tags")
    depends = data.get("depends")
    entry: dict[str, Any] = {
        "id": data.get("id") if isinstance(data.get("id"), str) else "",
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
    for optional_key in SHARD_OPTIONAL_KEYS:
        value = data.get(optional_key)
        if isinstance(value, str) and value:
            entry[optional_key] = value
    return entry


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
        entry = _full_entry(data, relative)
        if not entry["id"]:
            warnings.append(f"{relative}: front matter 缺少 id，未纳入索引")
            continue
        entries.append(entry)
    entries.sort(key=_sort_key)
    return entries, warnings, errors


def _scan_toolkit_entry(root: Path, warnings: list[str]) -> dict[str, Any] | None:
    """扫描 toolkit/README.md 作为工具入口（TOOL-000）。"""
    toolkit_readme = root / "toolkit" / "README.md"
    if not toolkit_readme.is_file():
        warnings.append("toolkit/README.md 不存在，工具入口未纳入索引")
        return None
    try:
        text = toolkit_readme.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        warnings.append("无法读取 toolkit/README.md")
        return None
    data, parse_errors, _body = parse_document(text)
    for parse_error in parse_errors:
        warnings.append(f"toolkit/README.md: {parse_error}")
    if not data.get("id"):
        warnings.append("toolkit/README.md: front matter 缺少 id，未纳入索引")
        return None
    return _full_entry(data, "toolkit/README.md")


def _collect(root: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any] | None, list[str], list[str]]:
    content: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    errors: list[str] = []
    for layer, directory_name in CONTENT_GROUPS.items():
        entries, group_warnings, group_errors = scan_group(root, directory_name)
        content[layer] = entries
        warnings.extend(group_warnings)
        errors.extend(group_errors)
    toolkit_entry = _scan_toolkit_entry(root, warnings)
    return content, toolkit_entry, warnings, errors


# ---------------------------------------------------------------------------
# 根摘要 / 分片构建
# ---------------------------------------------------------------------------


def _build_tools(root: Path, warnings: list[str]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = [
        {
            "name": "repurpose",
            "kind": "cli",
            "path": "toolkit/README.md",
            "entry": "python -m toolkit.repurpose",
            "commands": ["detect", "probe", "assess", "plan", "new-profile", "index", "validate"],
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
            "note": "重建根摘要 agent-manifest.json + agent-manifest.d/ 四层分片",
        },
        {
            "name": "validate",
            "cmd": "python -m toolkit.repurpose validate --strict",
            "note": "front matter/ID/断链/JSON/doc-policy 体积与 manifest 一致性",
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


def _shard_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """分片条目只保留机器检索所需字段（体积预算）。"""
    output = {key: entry.get(key, "") for key in SHARD_REQUIRED_KEYS}
    for optional_key in SHARD_OPTIONAL_KEYS:
        value = entry.get(optional_key)
        if isinstance(value, str) and value:
            output[optional_key] = value
    return output


def _reading_groups(content: dict[str, list[dict[str, Any]]], toolkit_entry: dict[str, Any] | None) -> list[dict[str, Any]]:
    entries_by_group = {
        "methodology": content.get("methodology", []),
        "tools": [toolkit_entry] if toolkit_entry else [],
        "case_studies": content.get("case_studies", []),
        "guardrails": content.get("guardrails", []),
        "pitfalls": content.get("pitfalls", []),
    }
    groups: list[dict[str, Any]] = []
    for group in READING_GROUP_ORDER:
        entries = entries_by_group[group]
        if not entries:
            continue
        groups.append(
            {
                "layer": group,
                "count": len(entries),
                "ids": [entry["id"] for entry in entries],
                "reason": GROUP_REASONS[group],
            }
        )
    return groups


def _entrypoints(reading_groups: list[dict[str, Any]], content: dict[str, list[dict[str, Any]]], toolkit_entry: dict[str, Any] | None) -> list[dict[str, Any]]:
    entrypoints: list[dict[str, Any]] = []
    ids_by_layer: dict[str, list[dict[str, Any]]] = {
        layer: entries for layer, entries in content.items()
    }
    if toolkit_entry:
        ids_by_layer["tools"] = [toolkit_entry]
    wanted = {"MTH-000", "TOOL-000", "CASE-000", "GRD-000", "PIT-000"}
    for group in READING_GROUP_ORDER:
        for entry in ids_by_layer.get(group, []):
            if entry["id"] in wanted:
                entrypoints.append(
                    {
                        "id": entry["id"],
                        "title": entry["title"],
                        "path": entry["path"],
                        "type": entry["type"],
                    }
                )
    # 若某层索引 ID 命名变化，至少有工具入口兜底
    if not entrypoints and toolkit_entry:
        entrypoints.append(
            {
                "id": toolkit_entry["id"],
                "title": toolkit_entry["title"],
                "path": toolkit_entry["path"],
                "type": toolkit_entry["type"],
            }
        )
    return entrypoints


def _protocol_files(root: Path) -> list[str]:
    return [
        relative
        for relative in ("AGENTS.md", "backlog.json", "README.md")
        if (root / relative).is_file()
    ]


def render_root_manifest(manifest: dict[str, Any]) -> str:
    """渲染根摘要：顶层一键一行，reading_order 按层分组（每组一行）以控制行数。"""
    return _render_json_object(manifest, item_list_keys=("reading_order",))


def render_shard(shard: dict[str, Any]) -> str:
    """渲染分片：entries 每条一行（保证 ≤300 行且便于 diff）。"""
    return _render_json_object(shard, item_list_keys=("entries",))


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _render_json_object(payload: dict[str, Any], *, item_list_keys: tuple[str, ...] = ()) -> str:
    """生成 JSON 文本：顶层键一行一个；指定列表键按 item 一行一个（item 紧凑）。

    约束：仅支持 dict/list 顶层值；保证输出是合法 JSON（由测试 json.loads 校验）。
    """
    lines = ["{"]
    items = list(payload.items())
    for index, (key, value) in enumerate(items):
        comma = "," if index < len(items) - 1 else ""
        key_text = json.dumps(key, ensure_ascii=False)
        if key in item_list_keys and isinstance(value, list):
            if not value:
                lines.append(f"  {key_text}: []{comma}")
                continue
            lines.append(f"  {key_text}: [")
            for item_index, item in enumerate(value):
                item_comma = "," if item_index < len(value) - 1 else ""
                lines.append(f"    {_compact(item)}{item_comma}")
            lines.append(f"  ]{comma}")
        else:
            lines.append(f"  {key_text}: {_compact(value)}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_bundle(
    root: str | Path,
    generated_at: str | None = None,
    extra_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """构建根摘要与分片（不写文件），返回 bundle。

    bundle 键：root（根 manifest）、root_text、root_lines、root_bytes、
    shards（layer → {data,text,path,lines,bytes}）、limits、warnings、errors、policy_warnings。
    """
    repo_root = Path(root)
    warnings: list[str] = list(extra_warnings or [])
    errors: list[str] = []
    timestamp = generated_at or iso_now()

    content, toolkit_entry, scan_warnings, scan_errors = _collect(repo_root)
    warnings.extend(scan_warnings)
    errors.extend(scan_errors)

    policy, policy_warnings = load_policy()
    for code, message in policy_warnings:
        warnings.append(f"{code}: {message}")
    limits = manifest_limits(policy)

    shards: dict[str, dict[str, Any]] = {}
    warnings_from_policy: list[str] = []
    for layer in CONTENT_GROUPS:
        entries = content[layer]
        shard = {
            "schema": SCHEMA_SHARD,
            "layer": layer,
            "generated_at": timestamp,
            "count": len(entries),
            "entries": [_shard_entry(entry) for entry in entries],
        }
        if len(entries) > limits["shard_max_entries"]:
            errors.append(
                f"分片超限：{shard_relative_path(layer)} 条目数 {len(entries)} 超过上限 "
                f"{limits['shard_max_entries']}（需要拆分策略扩展）"
            )
        text = render_shard(shard)
        lines = len(text.splitlines())
        size = len(text.encode("utf-8"))
        if lines > limits["shard_max_lines"]:
            errors.append(
                f"分片超限：{shard_relative_path(layer)} 行数 {lines} 超过上限 {limits['shard_max_lines']}"
            )
        if size > limits["shard_max_bytes"]:
            errors.append(
                f"分片超限：{shard_relative_path(layer)} 字节数 {size} 超过上限 {limits['shard_max_bytes']}"
            )
        shards[layer] = {
            "data": shard,
            "text": text,
            "path": shard_relative_path(layer),
            "lines": lines,
            "bytes": size,
        }

    shards_mapping = {
        layer: {
            "path": shards[layer]["path"],
            "count": shards[layer]["data"]["count"],
            "lines": shards[layer]["lines"],
            "bytes": shards[layer]["bytes"],
        }
        for layer in CONTENT_GROUPS
    }

    reading_groups = _reading_groups(content, toolkit_entry)
    counts = {
        **{layer: len(content[layer]) for layer in CONTENT_GROUPS},
        "tools": len(_build_tools(repo_root, [])),
        "entrypoints": len(_entrypoints(reading_groups, content, toolkit_entry)),
        "reading_order": sum(group["count"] for group in reading_groups),
        "total_entry_docs": sum(len(content[layer]) for layer in CONTENT_GROUPS),
    }

    manifest: dict[str, Any] = {
        "schema": SCHEMA_MANIFEST,
        "generated_at": timestamp,
        "repo": {
            "name": repo_root.resolve().name,
            "root": ".",
        },
        "entrypoints": _entrypoints(reading_groups, content, toolkit_entry),
        "reading_order": reading_groups,
        "counts": counts,
        "shards": shards_mapping,
        "tools": _build_tools(repo_root, warnings),
        "invariants": INVARIANTS,
        "commands": _build_commands(),
        "warnings": warnings,
        "errors": errors,
    }
    protocol = _protocol_files(repo_root)
    if protocol:
        manifest["repo"]["protocol"] = protocol  # type: ignore[index]

    root_text = render_root_manifest(manifest)
    root_lines = len(root_text.splitlines())
    root_bytes = len(root_text.encode("utf-8"))
    if root_lines > limits["root_max_lines"]:
        manifest["errors"].append(
            f"根 manifest 行数 {root_lines} 超过上限 {limits['root_max_lines']}"
        )
    if root_bytes > limits["root_max_bytes"]:
        manifest["errors"].append(
            f"根 manifest 字节数 {root_bytes} 超过上限 {limits['root_max_bytes']}"
        )
    if manifest["errors"]:
        root_text = render_root_manifest(manifest)
        root_lines = len(root_text.splitlines())
        root_bytes = len(root_text.encode("utf-8"))

    return {
        "root": manifest,
        "root_text": root_text,
        "root_lines": root_lines,
        "root_bytes": root_bytes,
        "shards": shards,
        "limits": limits,
        "warnings": warnings,
        "errors": errors,
        "policy_warnings": policy_warnings,
    }


def build_manifest(root: str | Path, generated_at: str | None = None) -> dict[str, Any]:
    """只构建根摘要对象（不写文件、不清理）；用于测试/调用方内省。"""
    return build_bundle(root, generated_at=generated_at)["root"]


# ---------------------------------------------------------------------------
# 旧分片清理与写盘
# ---------------------------------------------------------------------------


def cleanup_stale_shards(root: str | Path) -> tuple[list[str], list[str]]:
    """清理 agent-manifest.d/ 中不属于当前四层、且确认由本工具生成的旧分片。

    安全规则：只删除带 ``repurpose.manifest-shard.v1`` schema 标记的 JSON（即本工具
    生成物）；无法解析或未知文件不删除，只记 warning。
    """
    shard_dir = default_shard_dir(root)
    removed: list[str] = []
    warnings: list[str] = []
    if not shard_dir.is_dir():
        return removed, warnings
    expected = {SHARD_FILENAMES[layer] for layer in CONTENT_GROUPS}
    for path in sorted(shard_dir.glob("*.json")):
        if path.name in expected:
            continue
        relative = rel_posix(path, root)
        try:
            payload = load_json(path)
        except Exception:
            warnings.append(f"分片目录存在无法解析的 JSON，未自动删除：{relative}")
            continue
        if isinstance(payload, dict) and payload.get("schema") == SCHEMA_SHARD:
            try:
                path.unlink()
            except OSError:
                warnings.append(f"旧分片删除失败（权限/占用）：{relative}")
            else:
                removed.append(relative)
        else:
            warnings.append(f"分片目录存在非本工具生成的 JSON，未删除：{relative}")
    return removed, warnings


def write_bundle(
    root: str | Path,
    out: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """生成并写盘（根摘要 + 四层分片），返回统计信息。"""
    repo_root = Path(root)
    removed, cleanup_warnings = cleanup_stale_shards(repo_root)
    bundle = build_bundle(repo_root, generated_at=generated_at, extra_warnings=cleanup_warnings)
    root_target = Path(out) if out is not None else default_manifest_path(repo_root)
    write_text(root_target, bundle["root_text"])

    written_shards: dict[str, dict[str, Any]] = {}
    for layer in CONTENT_GROUPS:
        shard_info = bundle["shards"][layer]
        target = repo_root / shard_info["path"]
        write_text(target, shard_info["text"])
        written_shards[layer] = {
            "path": shard_info["path"],
            "entries": shard_info["data"]["count"],
            "lines": shard_info["lines"],
            "bytes": shard_info["bytes"],
        }

    return {
        "root_path": root_target,
        "manifest": bundle["root"],
        "root": {
            "path": rel_posix(root_target, repo_root),
            "lines": bundle["root_lines"],
            "bytes": bundle["root_bytes"],
            "max_lines": bundle["limits"]["root_max_lines"],
            "max_bytes": bundle["limits"]["root_max_bytes"],
        },
        "shards": written_shards,
        "limits": bundle["limits"],
        "removed_shards": removed,
        "warnings": bundle["root"].get("warnings", []),
        "errors": bundle["root"].get("errors", []),
    }


def write_manifest(
    root: str | Path,
    out: str | Path | None = None,
    *,
    generated_at: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """兼容接口：写盘后返回 ``(根摘要路径, 根 manifest)``。"""
    info = write_bundle(root, out=out, generated_at=generated_at)
    return Path(info["root_path"]), info["manifest"]


def format_index_summary(info: dict[str, Any]) -> str:
    """人类可读 index 摘要。"""
    manifest = info.get("manifest") or {}
    root = info.get("root") or {}
    lines = ["agent-manifest 生成完成（根摘要 + 分层分片）"]
    lines.append(
        "- 根：{}（{} 行 / {} 字节；上限 {}/{}）".format(
            root.get("path", MANIFEST_FILENAME),
            root.get("lines", "?"),
            root.get("bytes", "?"),
            root.get("max_lines", 160),
            root.get("max_bytes", 16384),
        )
    )
    shards = info.get("shards") or {}
    if shards:
        lines.append("- 分片：")
        for layer, shard in shards.items():
            lines.append(
                "  - {layer}: {path}（{entries} 条 / {lines} 行 / {bytes} 字节）".format(
                    layer=layer, **shard
                )
            )
    if info.get("removed_shards"):
        lines.append("- 已清理旧分片：" + "、".join(info["removed_shards"]))
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
    warnings = info.get("warnings") or []
    errors = info.get("errors") or []
    if warnings:
        lines.append(f"- warnings（{len(warnings)}）：")
        lines.extend(f"  - {item}" for item in warnings)
    if errors:
        lines.append(f"- errors（{len(errors)}）：")
        lines.extend(f"  - {item}" for item in errors)
    if not warnings and not errors:
        lines.append("- 无 warnings/errors")
    return "\n".join(lines)
