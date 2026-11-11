"""frontmatter 解析测试：BOM/CRLF、flat YAML、列表、引号、注释、错误分支。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from toolkit.repurpose.frontmatter import (
    REQUIRED_KEYS,
    parse,
    parse_document,
    parse_file,
    serialize,
)


def _basic_doc(front: str) -> str:
    return "---\n" + front.strip("\n") + "\n---\n\n# 正文\n"


class ParseBasicTests(unittest.TestCase):
    def test_simple_flat_yaml(self) -> None:
        data, errors = parse(
            _basic_doc(
                "id: MTH-001\n"
                "title: 基础\n"
                "type: methodology\n"
                "status: current\n"
                "audience: human, agent\n"
                "tags: test, demo\n"
                "updated: 2026-11-11\n"
                "agent_hint: 先读这里\n"
            )
        )
        self.assertEqual(errors, [])
        self.assertEqual(data["id"], "MTH-001")
        self.assertEqual(data["title"], "基础")
        self.assertEqual(data["audience"], ["human", "agent"])
        self.assertEqual(data["tags"], ["test", "demo"])

    def test_bom_and_crlf(self) -> None:
        text = "\ufeff---\r\nid: PIT-001\r\ntitle: 带 BOM\r\n---\r\n\r\n正文\r\n"
        data, errors = parse(text)
        self.assertEqual(errors, [])
        self.assertEqual(data["id"], "PIT-001")
        self.assertEqual(data["title"], "带 BOM")

    def test_cr_only_line_endings(self) -> None:
        text = "---\rid: GRD-001\rtitle: CR only\r---\rbody"
        data, errors = parse(text)
        self.assertEqual(errors, [])
        self.assertEqual(data["id"], "GRD-001")

    def test_leading_bom_does_not_break(self) -> None:
        data, errors = parse("\ufeff---\nid: TOOL-000\n---\n")
        self.assertEqual(errors, [])
        self.assertEqual(data["id"], "TOOL-000")

    def test_bracket_list(self) -> None:
        data, _ = parse(_basic_doc("tags: [a, b, c]\naudience: [human, agent]\n"))
        self.assertEqual(data["tags"], ["a", "b", "c"])
        self.assertEqual(data["audience"], ["human", "agent"])

    def test_comma_list_without_brackets(self) -> None:
        data, _ = parse(_basic_doc("tags: a, b, c\ndepends: MTH-001, GRD-003\n"))
        self.assertEqual(data["tags"], ["a", "b", "c"])
        self.assertEqual(data["depends"], ["MTH-001", "GRD-003"])

    def test_empty_list_values(self) -> None:
        for raw in ("tags:", "tags: []", 'tags: ""'):
            data, errors = parse(_basic_doc(raw + "\n"))
            self.assertEqual(errors, [])
            self.assertEqual(data["tags"], [], msg=f"raw={raw!r}")

    def test_quotes_are_stripped(self) -> None:
        data, _ = parse(_basic_doc('title: "带 引号 的标题"\nhint: \'单引号值\'\n'))
        self.assertEqual(data["title"], "带 引号 的标题")
        self.assertEqual(data["hint"], "单引号值")

    def test_blank_and_comment_lines_ignored(self) -> None:
        data, errors = parse(
            _basic_doc(
                "# 这是注释\n\n"
                "id: PIT-002\n"
                "   # 缩进注释也忽略\n"
                "title: 正常标题\n"
            )
        )
        self.assertEqual(errors, [])
        self.assertNotIn("#", data)
        self.assertEqual(data["id"], "PIT-002")

    def test_value_containing_colon(self) -> None:
        data, _ = parse(_basic_doc("agent_hint: 步骤：先 detect，再 probe\n"))
        self.assertEqual(data["agent_hint"], "步骤：先 detect，再 probe")

    def test_body_is_returned(self) -> None:
        _data, _errors, body = parse_document(_basic_doc("id: X-001\n"))
        self.assertIn("# 正文", body)
        self.assertNotIn("id: X-001", body)


class ParseErrorTests(unittest.TestCase):
    def test_missing_front_matter(self) -> None:
        data, errors = parse("# 没有 front matter 的文档\n")
        self.assertEqual(data, {})
        self.assertTrue(any("front matter" in error for error in errors))

    def test_unterminated_front_matter(self) -> None:
        data, errors = parse("---\nid: MTH-001\n")
        self.assertEqual(data, {})
        self.assertTrue(any("未闭合" in error for error in errors))

    def test_malformed_line(self) -> None:
        data, errors = parse(_basic_doc("id: MTH-001\n这不是 key value 行\n"))
        self.assertEqual(data["id"], "MTH-001")
        self.assertTrue(any("不是合法的" in error for error in errors))

    def test_empty_key(self) -> None:
        _data, errors = parse(_basic_doc(": value\n"))
        self.assertTrue(any("键名为空" in error for error in errors))

    def test_duplicate_key(self) -> None:
        data, errors = parse(_basic_doc("id: A-001\nid: A-002\n"))
        self.assertEqual(data["id"], "A-002")
        self.assertTrue(any("重复的键" in error for error in errors))

    def test_unclosed_bracket_list(self) -> None:
        _data, errors = parse(_basic_doc("tags: [a, b\n"))
        self.assertTrue(any("]" in error for error in errors))


class RequiredKeysTests(unittest.TestCase):
    def test_required_keys_are_the_eight_contract_keys(self) -> None:
        self.assertEqual(
            REQUIRED_KEYS,
            ("id", "title", "type", "status", "audience", "tags", "updated", "agent_hint"),
        )

    def test_template_front_matter_has_required_keys(self) -> None:
        templates = sorted((Path(__file__).resolve().parents[1] / "templates").glob("*.md"))
        self.assertTrue(templates, "templates/ 下应有 Markdown 模板")
        for template in templates:
            with self.subTest(template=template.name):
                data, errors, _body = parse_file(template)
                self.assertEqual(errors, [])
                for key in REQUIRED_KEYS:
                    self.assertIn(key, data)
                    self.assertTrue(data[key], msg=f"{template.name} 的 {key} 为空")

    def test_serialize_round_trip(self) -> None:
        payload = {
            "id": "MTH-001",
            "title": "标题",
            "type": "methodology",
            "status": "current",
            "audience": ["human", "agent"],
            "tags": ["a", "b"],
            "updated": "2026-11-11",
            "agent_hint": "提示",
        }
        text = serialize(payload)
        data, errors = parse(text + "\n正文\n")
        self.assertEqual(errors, [])
        self.assertEqual(data["id"], "MTH-001")
        self.assertEqual(data["audience"], ["human", "agent"])


class ParseFileTests(unittest.TestCase):
    def test_parse_file_utf8_sig(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_text(
                "\ufeff---\r\nid: CASE-001\r\ntitle: 案例\r\n---\r\n\r\n# 正文\r\n",
                encoding="utf-8",
                newline="",
            )
            data, errors, body = parse_file(path)
            self.assertEqual(errors, [])
            self.assertEqual(data["id"], "CASE-001")
            self.assertIn("# 正文", body)


if __name__ == "__main__":
    unittest.main()
