"""rescue-kit：离线生成/校验救援包 SHA-256 清单（G-L1 的辅助工具）。

边界：
- 只读文件、只写救援包目录内的 `rescue-manifest.json`；不连接设备、不刷写、不修改镜像；
- 清单只存**相对路径**，不存绝对路径/宿主名/凭据；
- 校验失败不等于镜像损坏：可能只是清单过期；以 G-L1 的人工核对为准。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .util import (
    SCHEMA_RESCUE_KIT,
    SCHEMA_RESCUE_KIT_VERIFY,
    JsonFileError,
    UsageError,
    iso_now,
    load_json,
    write_json,
)

MANIFEST_NAME = "rescue-manifest.json"
"""救援包清单文件名（与被校验文件同目录）。"""

HASH_ALGORITHM = "sha256"
CHUNK_SIZE = 1024 * 1024


def _iter_files(root: Path) -> list[Path]:
    """列出救援包中应纳入清单的普通文件（跳过清单自身、符号链接与 .git）。"""
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if path.name == MANIFEST_NAME:
            continue
        if ".git" in path.parts:
            continue
        files.append(path)
    return files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: str | Path, *, notes: str = "") -> dict[str, Any]:
    """扫描目录并生成清单对象（不写文件）。"""
    base = Path(root)
    if not base.exists() or not base.is_dir():
        raise UsageError(f"救援包目录不存在或不是目录：{base}")
    entries = []
    for path in _iter_files(base):
        relative = path.relative_to(base).as_posix()
        entries.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                HASH_ALGORITHM: _sha256(path),
            }
        )
    if not entries:
        raise UsageError("救援包目录为空（没有可纳入清单的文件）")
    return {
        "schema": SCHEMA_RESCUE_KIT,
        "generated_at": iso_now(),
        "algorithm": HASH_ALGORITHM,
        "files": entries,
        "notes": notes,
    }


def write_manifest(
    root: str | Path,
    *,
    notes: str = "",
    force: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """生成并写入 `<root>/rescue-manifest.json`，返回 (路径, 清单)。

    已存在清单时默认拒绝覆盖：清单是"当时目录内容"的证据，盲目重建会掩盖变更。
    """
    base = Path(root)
    target_path = base / MANIFEST_NAME
    if target_path.exists() and not force:
        raise UsageError(
            f"{MANIFEST_NAME} 已存在：先核对来源/版本，确认要重建时加 --force"
        )
    manifest = build_manifest(base, notes=notes)
    target = write_json(target_path, manifest)
    return target, manifest


def _load_manifest(root: Path) -> dict[str, Any]:
    try:
        payload = load_json(root / MANIFEST_NAME)
    except JsonFileError as exc:
        raise UsageError(f"无法加载救援包清单：{exc}") from exc
    if not isinstance(payload, dict):
        raise UsageError("救援包清单顶层必须是 JSON object")
    if payload.get("schema") != SCHEMA_RESCUE_KIT:
        raise UsageError(f"救援包清单 schema 必须为 {SCHEMA_RESCUE_KIT}")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise UsageError("救援包清单 files 必须是非空数组")
    expected: dict[str, str] = {}
    for item in files:
        if not isinstance(item, dict):
            raise UsageError("救援包清单 files 元素必须是 object")
        rel = item.get("path")
        digest = item.get(HASH_ALGORITHM)
        if not isinstance(rel, str) or not rel or rel.startswith("/") or "\\" in rel:
            raise UsageError(f"救援包清单 path 非法（必须是相对 POSIX 路径）：{rel!r}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise UsageError(f"救援包清单 {rel} 缺少合法 sha256")
        if rel in expected:
            raise UsageError(f"救援包清单 path 重复：{rel}")
        expected[rel] = digest.lower()
    payload["_expected"] = expected  # 仅供本次校验使用，不落盘
    return payload


def verify_manifest(root: str | Path) -> dict[str, Any]:
    """校验目录与清单是否一致；返回报告（不抛错，除输入/清单错误）。"""
    base = Path(root)
    if not base.exists() or not base.is_dir():
        raise UsageError(f"救援包目录不存在或不是目录：{base}")
    manifest = _load_manifest(base)
    expected: dict[str, str] = manifest["_expected"]
    actual_paths = {path.relative_to(base).as_posix(): path for path in _iter_files(base)}
    missing = sorted(set(expected) - set(actual_paths))
    extra = sorted(set(actual_paths) - set(expected))
    changed: list[dict[str, str]] = []
    errors: list[str] = []
    for relative in sorted(set(expected) & set(actual_paths)):
        path = actual_paths[relative]
        try:
            actual = _sha256(path)
        except OSError as exc:
            errors.append(f"{relative}: 读取失败（{exc.__class__.__name__}）")
            continue
        if actual != expected[relative]:
            changed.append({"path": relative, "expected": expected[relative], "actual": actual})
    ok = not missing and not extra and not changed and not errors
    return {
        "schema": SCHEMA_RESCUE_KIT_VERIFY,
        "generated_at": iso_now(),
        "algorithm": HASH_ALGORITHM,
        "manifest_generated_at": manifest.get("generated_at"),
        "ok": ok,
        "checked": len(expected),
        "missing": missing,
        "extra": extra,
        "changed": changed,
        "errors": errors,
    }


def format_manifest_human(manifest: dict[str, Any]) -> str:
    return (
        f"救援包清单已生成：{len(manifest['files'])} 个文件，算法 {manifest['algorithm']}\n"
        f"清单文件：{MANIFEST_NAME}（与救援包同目录；请离线保存两份）"
    )


def format_verify_human(report: dict[str, Any]) -> str:
    lines = [
        f"救援包校验：{'OK' if report['ok'] else 'FAIL'}（清单 {report['checked']} 个文件）",
        f"清单生成时间：{report.get('manifest_generated_at')}",
    ]
    for title, items in (
        ("缺失", report["missing"]),
        ("清单外新增", report["extra"]),
        ("哈希不一致", [item["path"] for item in report["changed"]]),
        ("读取错误", report["errors"]),
    ):
        if items:
            lines.append(f"{title}：")
            lines.extend(f"  - {item}" for item in items)
    if report["ok"]:
        lines.append("结论：目录内容与清单一致；仍需人工核对版本/来源与救援演练记录（G-L1/G-R3）。")
    else:
        lines.append("结论：不可视为救援包就绪；先补齐/重新生成清单并复核来源与版本。")
    return "\n".join(lines)
