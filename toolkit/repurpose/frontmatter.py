"""flat YAML front matter 解析。

约束（与 AGENTS.md §4.2 对齐）：
- 文件首行（允许 UTF-8 BOM）为 ``---``，到下一行 ``---`` 结束；
- 只支持 flat ``key: value``，不支持嵌套 / 多行块 / YAML 锚点；
- 空行与整行 ``#`` 注释被忽略；
- 列表支持 ``[a, b]`` 与逗号分隔两种写法；``tags`` / ``audience`` / ``depends``
  等列表键在无方括号时也按逗号拆分；
- 值去掉包裹的单/双引号。

不使用任何第三方 YAML 库；解析失败不抛异常，而是返回 ``(data, errors)``。
"""

from __future__ import annotations

import re

from .util import read_text

REQUIRED_KEYS = (
    "id",
    "title",
    "type",
    "status",
    "audience",
    "tags",
    "updated",
    "agent_hint",
)
"""新层 Markdown 必须提供的 front matter 键（与 AGENTS.md 一致）。"""

LIST_KEYS = frozenset(
    {
        "tags",
        "audience",
        "depends",
        "related",
        "aliases",
        "outputs",
    }
)
"""语义上为列表的键；无方括号时按逗号拆分。"""

BOM = "\ufeff"


def _normalize_text(text: str) -> str:
    """去除 BOM 并统一换行为 LF（容忍 CRLF / 单独 CR）。"""
    if text.startswith(BOM):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse(text: str) -> tuple[dict[str, object], list[str]]:
    """解析 front matter，返回 ``(data, errors)``。

    找不到起始/结束 ``---`` 时返回空 dict 与错误信息；不会抛异常。
    """
    data, errors, _body = parse_document(text)
    return data, errors


def parse_document(text: str) -> tuple[dict[str, object], list[str], str]:
    """解析 front matter 并返回 ``(data, errors, body)``；body 不含 front matter。"""
    normalized = _normalize_text(text)
    lines = normalized.split("\n")

    # 允许文件开头有空行（例如保存工具自动追加），但起始标记必须是第一个非空行。
    start_index = None
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if line.strip() == "---":
            start_index = index
        break
    if start_index is None:
        return {}, ["缺少 front matter 起始标记 ---（应位于文件首行）"], normalized

    end_index = None
    for index in range(start_index + 1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, ["front matter 未闭合：缺少结束标记 ---"], normalized

    data: dict[str, object] = {}
    errors: list[str] = []
    body_start_line = end_index + 2  # 1-based 行号，指向 front matter 之后的正文
    for offset, raw_line in enumerate(lines[start_index + 1 : end_index], start=start_index + 2):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            errors.append(f"第 {offset} 行：不是合法的 'key: value' 格式")
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not key:
            errors.append(f"第 {offset} 行：键名为空")
            continue
        if re.search(r"\s", key):
            errors.append(f"第 {offset} 行：键名包含空白字符（不支持嵌套/复杂键）")
            continue
        if key in data:
            errors.append(f"第 {offset} 行：重复的键 '{key}'（保留后出现的值）")
        value = raw_value.strip()
        parsed = _parse_value(key, value, offset, errors)
        data[key] = parsed

    body = "\n".join(lines[end_index + 1 :])
    _ = body_start_line  # 保留变量说明行号语义（正文从 end_index+2 行开始）
    return data, errors, body


def _parse_value(key: str, value: str, line_number: int, errors: list[str]) -> object:
    """解析单个值：去引号、方括号列表、逗号列表。"""
    if value == "":
        return [] if key in LIST_KEYS else ""
    if value in ('""', "''"):
        return [] if key in LIST_KEYS else ""

    if value.startswith("["):
        if not value.endswith("]"):
            errors.append(f"第 {line_number} 行：列表值缺少收尾的 ']'")
            inner = value[1:]
        else:
            inner = value[1:-1]
        items = [_unquote(item.strip()) for item in inner.split(",") if item.strip()]
        return [item for item in items if item != ""]

    if key in LIST_KEYS:
        items = [_unquote(item.strip()) for item in value.split(",") if item.strip()]
        return [item for item in items if item != ""]

    return _unquote(value)


def _unquote(value: str) -> str:
    """去掉包裹值的成对单/双引号。"""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_file(path) -> tuple[dict[str, object], list[str], str]:
    """读取文件并解析 front matter；返回 ``(data, errors, body)``。"""
    return parse_document(read_text(path))


def serialize(data: dict[str, object]) -> str:
    """把 flat dict 序列化成 front matter 块（测试/模板生成用）。"""
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            lines.append(f"{key}: " + ", ".join(str(item) for item in value))
        elif isinstance(value, bool):
            lines.append(f"{key}: " + ("true" if value else "false"))
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"
