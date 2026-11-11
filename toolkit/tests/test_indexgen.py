"""indexgen 测试：临时仓库生成 agent-manifest、计数、阅读顺序、缺失目录容错。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from toolkit.repurpose.indexgen import (
    CONTENT_GROUPS,
    build_manifest,
    default_manifest_path,
    format_index_summary,
    write_manifest,
)
from toolkit.repurpose.util import SCHEMA_MANIFEST, parse_iso
from toolkit.tests.fixtures.repo_builder import build_sample_repo, write_doc


class IndexSampleRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_manifest_schema_and_required_fields(self) -> None:
        manifest = build_manifest(self.root)
        self.assertEqual(manifest["schema"], SCHEMA_MANIFEST)
        self.assertIsNotNone(parse_iso(manifest["generated_at"]))
        self.assertEqual(manifest["repo"]["root"], ".")
        self.assertNotIn(str(self.root), json.dumps(manifest, ensure_ascii=False))
        for key in (
            "entrypoints",
            "reading_order",
            "content",
            "tools",
            "invariants",
            "commands",
            "counts",
            "warnings",
            "errors",
        ):
            self.assertIn(key, manifest)

    def test_counts_match_content(self) -> None:
        manifest = build_manifest(self.root)
        counts = manifest["counts"]
        self.assertEqual(counts["methodology"], 2)
        self.assertEqual(counts["pitfalls"], 2)
        self.assertEqual(counts["guardrails"], 2)
        self.assertEqual(counts["case_studies"], 2)
        self.assertEqual(counts["tools"], 5)  # repurpose CLI + ps1 + 3 termux 脚本
        self.assertGreaterEqual(counts["reading_order"], 8)

    def test_entrypoints_include_indexes_and_tool_readme(self) -> None:
        manifest = build_manifest(self.root)
        ids = [entry["id"] for entry in manifest["entrypoints"]]
        self.assertIn("MTH-000", ids)
        self.assertIn("TOOL-000", ids)
        self.assertIn("PIT-000", ids)
        self.assertIn("GRD-000", ids)
        self.assertIn("CASE-000", ids)

    def test_reading_order_groups_methodology_before_guardrails(self) -> None:
        manifest = build_manifest(self.root)
        paths = [step["path"] for step in manifest["reading_order"]]
        mth_index = paths.index("methodology/README.md")
        tool_index = paths.index("toolkit/README.md")
        guardrails = paths.index("guardrails/README.md")
        pitfalls = paths.index("pitfalls/README.md")
        self.assertLess(mth_index, tool_index)
        self.assertLess(tool_index, guardrails)
        self.assertLess(guardrails, pitfalls)
        for step in manifest["reading_order"]:
            self.assertTrue(step["reason"])
            self.assertGreater(step["step"], 0)

    def test_severity_domain_scope_carried_into_entries(self) -> None:
        manifest = build_manifest(self.root)
        pitfall = next(entry for entry in manifest["content"]["pitfalls"] if entry["id"] == "PIT-001")
        self.assertEqual(pitfall["severity"], "S2")
        self.assertEqual(pitfall["domain"], "server")
        guardrail = next(
            entry for entry in manifest["content"]["guardrails"] if entry["id"] == "GRD-001"
        )
        self.assertEqual(guardrail["severity"], "blocker")
        self.assertEqual(guardrail["scope"], "device")

    def test_entries_have_no_absolute_paths(self) -> None:
        manifest = build_manifest(self.root)
        for group in CONTENT_GROUPS:
            for entry in manifest["content"][group]:
                self.assertFalse(entry["path"].startswith("/"))
                self.assertFalse(":" in entry["path"] and entry["path"][1:2] == "\\")

    def test_toolkit_readme_indexed_as_tool_entry(self) -> None:
        manifest = build_manifest(self.root)
        tool_entries = [
            entry
            for step in manifest["reading_order"]
            if step["path"] == "toolkit/README.md"
            for entry in [step]
        ]
        self.assertEqual(tool_entries[0]["id"], "TOOL-000")
        self.assertTrue(any(tool["name"] == "repurpose" for tool in manifest["tools"]))

    def test_write_manifest_default_and_custom_out(self) -> None:
        target, manifest = write_manifest(self.root)
        self.assertEqual(target, default_manifest_path(self.root))
        self.assertTrue(target.is_file())
        parsed = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(parsed["schema"], SCHEMA_MANIFEST)
        custom = Path(self._tmp.name) / "custom-manifest.json"
        target2, _manifest2 = write_manifest(self.root, custom)
        self.assertEqual(target2, custom)
        self.assertTrue(custom.is_file())

    def test_format_summary(self) -> None:
        manifest = build_manifest(self.root)
        text = format_index_summary(manifest, default_manifest_path(self.root))
        self.assertIn("agent-manifest", text)
        self.assertIn("计数", text)


class IndexMissingDirectoryTests(unittest.TestCase):
    def test_empty_root_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            manifest = build_manifest(root)
            self.assertEqual(manifest["counts"]["methodology"], 0)
            self.assertFalse(manifest["errors"])
            self.assertTrue(manifest["warnings"])
            self.assertGreaterEqual(len(manifest["warnings"]), 5)

    def test_missing_single_directory_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "partial"
            build_sample_repo(root)
            for path in (root / "cases").rglob("*.md"):
                path.unlink()
            manifest = build_manifest(root)
            self.assertEqual(manifest["counts"]["case_studies"], 0)
            self.assertTrue(any("cases" in warning for warning in manifest["warnings"]))
            self.assertFalse(manifest["errors"])

    def test_malformed_frontmatter_is_warning_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bad"
            build_sample_repo(root)
            (root / "pitfalls" / "PIT-099-bad.md").write_text(
                "---\nid: PIT-099\ntitle: 坏行\n这不是 key value\n---\n",
                encoding="utf-8",
            )
            manifest = build_manifest(root)
            self.assertTrue(manifest["warnings"])
            self.assertFalse(manifest["errors"])
            ids = [entry["id"] for entry in manifest["content"]["pitfalls"]]
            self.assertIn("PIT-099", ids)

    def test_doc_without_frontmatter_not_indexed_but_warned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nofm"
            build_sample_repo(root)
            (root / "cases" / "demo" / "notes.md").write_text("# 无 front matter\n", encoding="utf-8")
            manifest = build_manifest(root)
            self.assertTrue(any("notes.md" in warning for warning in manifest["warnings"]))
            self.assertEqual(manifest["counts"]["case_studies"], 2)


class IndexRenderingTests(unittest.TestCase):
    def test_summary_with_warnings_lists_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty2"
            root.mkdir()
            manifest = build_manifest(root)
            text = format_index_summary(manifest)
            self.assertIn("warnings", text)
            self.assertNotIn("无 warnings/errors", text)


if __name__ == "__main__":
    unittest.main()
