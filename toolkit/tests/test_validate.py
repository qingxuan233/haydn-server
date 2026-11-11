"""validate 测试：front matter/ID/断链/JSON/manifest/严格模式。"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from toolkit.repurpose.indexgen import write_manifest
from toolkit.repurpose.util import SCHEMA_VALIDATION
from toolkit.repurpose.validate import format_validation_human, validate_repo
from toolkit.tests.fixtures.repo_builder import add_valid_json, build_sample_repo, write_doc


def _codes(report: dict) -> list[str]:
    return [issue["code"] for issue in report["issues"]]


class ValidRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)
        write_manifest(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_valid_repo_passes(self) -> None:
        report = validate_repo(self.root)
        self.assertEqual(report["schema"], SCHEMA_VALIDATION)
        self.assertTrue(report["ok"])
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 0)
        self.assertEqual(report["checked"]["markdown_files"], 9)
        self.assertTrue(report["checked"]["manifest"])

    def test_strict_also_passes_when_no_warnings(self) -> None:
        report = validate_repo(self.root, strict=True)
        self.assertTrue(report["ok"])

    def test_human_summary(self) -> None:
        text = format_validation_human(validate_repo(self.root))
        self.assertIn("validate 结果：OK", text)
        self.assertIn("strict=False", text)


class BrokenContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_duplicate_id(self) -> None:
        write_doc(
            self.root,
            "methodology/10-duplicate.md",
            entry_id="MTH-001",
            title="重复 ID",
            doc_type="methodology",
            body="# 重复\n",
        )
        report = validate_repo(self.root)
        self.assertIn("ID_DUPLICATE", _codes(report))
        self.assertFalse(report["ok"])

    def test_broken_relative_link(self) -> None:
        write_doc(
            self.root,
            "methodology/11-broken-link.md",
            entry_id="MTH-002",
            title="断链",
            doc_type="methodology",
            body="# 断链\n\n见 [不存在的文档](missing-file.md)。\n",
        )
        report = validate_repo(self.root)
        self.assertIn("LINK_BROKEN", _codes(report))
        self.assertFalse(report["ok"])

    def test_link_target_exists_ignores_anchor(self) -> None:
        write_doc(
            self.root,
            "methodology/12-anchor.md",
            entry_id="MTH-003",
            title="anchor",
            doc_type="methodology",
            body="# anchor\n\n见 [有效链接带 anchor](00-foundations.md#section)。\n",
        )
        report = validate_repo(self.root)
        self.assertNotIn("LINK_BROKEN", _codes(report))
        self.assertIn("LINK_ANCHOR", _codes(report))

    def test_absolute_link_warning(self) -> None:
        write_doc(
            self.root,
            "cases/demo/abs.md",
            entry_id="CASE-002",
            title="绝对路径",
            doc_type="case-study",
            body="# 绝对路径\n\n见 [绝对路径](/etc/passwd)。\n",
        )
        report = validate_repo(self.root)
        self.assertIn("LINK_ABSOLUTE", _codes(report))
        self.assertTrue(report["ok"])  # 默认 warning 不算失败

    def test_missing_required_frontmatter_key(self) -> None:
        path = self.root / "guardrails" / "GRD-002-bad.md"
        path.write_text(
            "---\nid: GRD-002\ntitle: 缺键\n---\n\n# 缺键\n",
            encoding="utf-8",
        )
        report = validate_repo(self.root)
        self.assertIn("FM_MISSING_KEY", _codes(report))
        self.assertFalse(report["ok"])

    def test_guardrail_convention_warnings(self) -> None:
        write_doc(
            self.root,
            "guardrails/GRD-003-convention.md",
            entry_id="GRD-003",
            title="约定",
            doc_type="guardrail",
            severity="high",
            scope="galaxy",
            body="# 约定\n\n正文\n",
        )
        report = validate_repo(self.root)
        self.assertIn("GRD_SEVERITY", _codes(report))
        self.assertIn("GRD_SCOPE", _codes(report))
        # warning 默认不失败，但 --strict 视为失败
        self.assertTrue(report["ok"])
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])

    def test_pitfall_convention_warnings(self) -> None:
        write_doc(
            self.root,
            "pitfalls/PIT-002-convention.md",
            entry_id="PIT-002",
            title="约定",
            doc_type="pitfall",
            severity="medium",
            domain="unknown",
            body="# 约定\n\n正文\n",
        )
        report = validate_repo(self.root)
        self.assertIn("PIT_SEVERITY", _codes(report))
        self.assertIn("PIT_DOMAIN", _codes(report))

    def test_invalid_json_detected(self) -> None:
        add_valid_json(self.root, "cases/demo/broken.json", "{not-json")
        report = validate_repo(self.root)
        self.assertIn("JSON_PARSE", _codes(report))
        self.assertFalse(report["ok"])

    def test_valid_json_accepted(self) -> None:
        add_valid_json(self.root, "cases/demo/profile.json", json.dumps({"schema": "x"}))
        report = validate_repo(self.root)
        self.assertNotIn("JSON_PARSE", _codes(report))
        self.assertTrue(report["ok"])

    def test_manifest_missing_is_warning_not_error(self) -> None:
        report = validate_repo(self.root)
        self.assertIn("MANIFEST_MISSING", _codes(report))
        self.assertTrue(report["ok"])
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])

    def test_missing_frontmatter_entirely(self) -> None:
        (self.root / "methodology" / "no-front.md").write_text("# 无 front matter\n", encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("FM_MISSING", _codes(report))
        self.assertFalse(report["ok"])

    def test_id_format_warning(self) -> None:
        write_doc(
            self.root,
            "cases/demo/badid.md",
            entry_id="case-1",
            title="坏 ID",
            doc_type="case-study",
            override={"id": "case-1"},
            body="# 坏 ID\n",
        )
        report = validate_repo(self.root)
        self.assertIn("ID_FORMAT", _codes(report))
        self.assertTrue(report["ok"])


class ManifestFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_manifest_stale_warning(self) -> None:
        manifest = write_manifest(self.root, generated_at="2026-01-01T00:00:00Z")[0]
        # 让内容文件 mtime 明显新于 manifest.generated_at
        future = time.time() + 3600
        for path in self.root.rglob("*.md"):
            os.utime(path, (future, future))
        report = validate_repo(self.root)
        self.assertIn("MANIFEST_STALE", _codes(report))
        self.assertTrue(report["ok"])
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])
        self.assertTrue(manifest.name == "agent-manifest.json")

    def test_manifest_counts_mismatch_warning(self) -> None:
        write_manifest(self.root)
        write_doc(
            self.root,
            "pitfalls/PIT-003-new.md",
            entry_id="PIT-003",
            title="新增",
            doc_type="pitfall",
            severity="S3",
            domain="docs",
            body="# 新增\n",
        )
        report = validate_repo(self.root)
        self.assertIn("MANIFEST_COUNTS", _codes(report))

    def test_manifest_schema_error(self) -> None:
        add_valid_json(self.root, "agent-manifest.json", json.dumps({"schema": "wrong"}))
        report = validate_repo(self.root)
        self.assertIn("JSON_SCHEMA", _codes(report))
        self.assertFalse(report["ok"])


if __name__ == "__main__":
    unittest.main()
