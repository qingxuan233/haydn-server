"""doc-policy：文档体积、归档窗口与 manifest 分片上限策略。

策略文件位于 ``toolkit/schema/doc-policy.json``（schema ``repurpose.doc-policy.v1``）。
文件缺失/损坏时使用内置默认策略并返回 warning（不阻断 index/validate），
保证离线与迁移场景可回退。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .util import SCHEMA_DIR, JsonFileError, load_json, merge_dict

SCHEMA_DOC_POLICY = "repurpose.doc-policy.v1"
POLICY_RELATIVE = "toolkit/schema/doc-policy.json"

DEFAULT_POLICY: dict[str, Any] = {
    "schema": SCHEMA_DOC_POLICY,
    "archival": {
        "current_file": "CHANGELOG.md",
        "archive_dir": "changelog",
        "pattern": "YYYY-MM.md",
        "max_current_entries": 8,
        "default_read": False,
        "archive_read_only": True,
        "window_row_pattern": r"^\|\s*20\d{2}-\d{2}-\d{2}\s*\|",
    },
    "status_sections": {
        "max_lines": 8,
        "files": ["AGENTS.md", "README.md"],
        "match_headings": ["当前状态", "现状", "当前阶段", "Status"],
    },
    "line_limits": {
        "AGENTS.md": 340,
        "README.md": 280,
        "methodology/*.md": 300,
        "pitfalls/*.md": 90,
        "guardrails/*.md": 90,
        "cases/*/README.md": 280,
        "cases/*/oem-profile.md": 200,
        "toolkit/README.md": 380,
        "backlog.json": 400,
    },
    "byte_limits": {
        "changelog/*.md": 262144,
    },
    "manifest": {
        "root_max_lines": 160,
        "root_max_bytes": 16384,
        "shard_max_lines": 300,
        "shard_max_bytes": 32768,
        "shard_max_entries": 40,
    },
    "reading_budget": {
        "root_max_lines": 160,
        "shard_max_entries": 40,
        "note": "先读根 agent-manifest.json（≤160 行摘要），需要某层时只读一个 agent-manifest.d 分片，再读单篇主题文档",
    },
}
"""内置默认策略（与 toolkit/schema/doc-policy.json 保持一致，作为缺失/损坏时回退）。"""


def default_policy() -> dict[str, Any]:
    """返回默认策略的深拷贝（调用方可安全修改）。"""
    return copy.deepcopy(DEFAULT_POLICY)


def load_policy(path: str | Path | None = None) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """读取 doc-policy。

    返回 ``(policy, warnings)``；warnings 为 ``[(code, message)]``：
    - ``POLICY_MISSING``：策略文件不存在，使用内置默认策略；
    - ``POLICY_INVALID``：JSON 无法解析/schema 不符，使用内置默认策略。
    """
    policy_path = Path(path) if path is not None else SCHEMA_DIR / "doc-policy.json"
    warnings: list[tuple[str, str]] = []
    if not policy_path.is_file():
        warnings.append(
            (
                "POLICY_MISSING",
                f"未找到 {policy_path.name}，使用内置默认策略（{POLICY_RELATIVE} 应由 toolkit 提供）",
            )
        )
        return default_policy(), warnings
    try:
        raw = load_json(policy_path)
    except JsonFileError as exc:
        warnings.append(("POLICY_INVALID", f"doc-policy 读取失败：{exc}；使用内置默认策略"))
        return default_policy(), warnings
    if not isinstance(raw, dict):
        warnings.append(("POLICY_INVALID", "doc-policy 顶层必须是 JSON object；使用内置默认策略"))
        return default_policy(), warnings
    if raw.get("schema") != SCHEMA_DOC_POLICY:
        warnings.append(
            (
                "POLICY_INVALID",
                f"doc-policy schema 应为 {SCHEMA_DOC_POLICY}（当前：{raw.get('schema')!r}）；仍与默认策略合并",
            )
        )
    policy = merge_dict(default_policy(), raw)
    policy["schema"] = SCHEMA_DOC_POLICY
    return policy, warnings


def manifest_limits(policy: dict[str, Any]) -> dict[str, int]:
    """返回 manifest 分片上限（缺失字段回退默认值）。"""
    defaults = DEFAULT_POLICY["manifest"]
    manifest = policy.get("manifest") if isinstance(policy.get("manifest"), dict) else {}
    limits = {
        key: int(manifest.get(key, defaults[key]))
        for key in (
            "root_max_lines",
            "root_max_bytes",
            "shard_max_lines",
            "shard_max_bytes",
            "shard_max_entries",
        )
    }
    return limits


def line_count(text: str) -> int:
    """按可视行计数（忽略文件末尾换行；等价于 len(text.splitlines())）。"""
    return len(text.splitlines())


_ = json  # 保留导入语义：policy 文件按 JSON 读取
