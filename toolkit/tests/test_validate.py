"""validate 测试：内容层 + doc-policy 体积/归档窗口 + manifest 根/分片一致性。"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from toolkit.repurpose.docpolicy import DEFAULT_POLICY, load_policy
from toolkit.repurpose.indexgen import (
    SCHEMA_SHARD,
    default_shard_dir,
    write_bundle,
    write_manifest,
)
from toolkit.repurpose.util import SCHEMA_VALIDATION
from toolkit.repurpose.validate import format_validation_human, validate_repo
from toolkit.tests.fixtures.repo_builder import (
    build_sample_repo,
    write_changelog_archive,
    write_changelog_with_archive,
    write_doc,
)


def _codes(report: dict) -> list[str]:
    return [issue["code"] for issue in report["issues"]]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_long_doc(root: Path, relative: str, *, entry_id: str, title: str, body_lines: int) -> Path:
    body = "# 长文\n\n" + "".join(f"行 {index}：说明文字。\n" for index in range(1, body_lines + 1))
    return write_doc(
        root, relative, entry_id=entry_id, title=title, doc_type="methodology", body=body
    )


def _write_changelog(root: Path, rows: int, *, width: int = 10) -> Path:
    lines = ["# 变更记录（CHANGELOG）", "", "## 3. 当前窗口", "", "| 日期 | 版本 | 变更 |", "|---|---|---|"]
    for index in range(rows):
        lines.append(f"| 2026-11-{index + 1:02d} | v1.{index} | 变更条目 {index} |")
    lines.append("")
    path = root / "CHANGELOG.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class ValidRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)
        write_bundle(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_valid_repo_passes(self) -> None:
        report = validate_repo(self.root)
        self.assertEqual(report["schema"], SCHEMA_VALIDATION)
        self.assertTrue(report["ok"])
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 0)
        self.assertEqual(report["checked"]["markdown_files"], 11)
        self.assertTrue(report["checked"]["manifest"])
        self.assertEqual(report["checked"]["shards"], 4)
        self.assertGreater(report["checked"]["policy_files"], 0)
        # 治理检查计数（新增：协议/命名/PIT/ADR/backlog/归档/回归）
        self.assertTrue(report["checked"]["protocol"])
        self.assertEqual(report["checked"]["protocol_tier"], "healthy")
        self.assertEqual(report["checked"]["pitfall_files"], 1)
        self.assertEqual(report["checked"]["adr_files"], 1)
        self.assertEqual(report["checked"]["backlog_items"], 2)
        self.assertGreater(report["checked"]["agent_regression_checks"], 0)

    def test_strict_also_passes_when_no_warnings(self) -> None:
        report = validate_repo(self.root, strict=True)
        self.assertTrue(report["ok"])

    def test_human_summary(self) -> None:
        text = format_validation_human(validate_repo(self.root))
        self.assertIn("validate 结果：OK", text)
        self.assertIn("分片 4", text)
        self.assertIn("strict=False", text)

    def test_root_manifest_within_limits(self) -> None:
        manifest_path = self.root / "agent-manifest.json"
        text = manifest_path.read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 160)
        self.assertLessEqual(len(text.encode("utf-8")), 16384)
        self.assertNotIn("content", _read_json(manifest_path))


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
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])

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
        (self.root / "cases" / "demo" / "broken.json").write_text("{not-json", encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("JSON_PARSE", _codes(report))
        self.assertFalse(report["ok"])

    def test_valid_json_accepted(self) -> None:
        (self.root / "cases" / "demo" / "profile.json").write_text(
            json.dumps({"schema": "x"}), encoding="utf-8"
        )
        report = validate_repo(self.root)
        self.assertNotIn("JSON_PARSE", _codes(report))

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


class ManifestLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_manifest_missing_is_warning_not_error(self) -> None:
        report = validate_repo(self.root)
        self.assertIn("MANIFEST_MISSING", _codes(report))
        self.assertTrue(report["ok"])
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])

    def test_manifest_stale_is_opt_in_via_mtime_check(self) -> None:
        """MANIFEST_STALE 默认关闭（CI/新 checkout 的 mtime 必然比 generated_at 新）。"""
        write_manifest(self.root, generated_at="2026-01-01T00:00:00Z")
        future = time.time() + 3600
        for path in self.root.rglob("*.md"):
            os.utime(path, (future, future))
        report = validate_repo(self.root)
        self.assertNotIn("MANIFEST_STALE", _codes(report))
        self.assertTrue(report["ok"])
        self.assertTrue(validate_repo(self.root, strict=True)["ok"])
        # 显式 --mtime-check（本地调试）才报告 stale
        checked = validate_repo(self.root, mtime_check=True)
        self.assertIn("MANIFEST_STALE", _codes(checked))
        self.assertTrue(checked["ok"])  # warning 非 strict 不失败
        self.assertFalse(validate_repo(self.root, strict=True, mtime_check=True)["ok"])

    def test_manifest_counts_mismatch_after_content_change(self) -> None:
        write_bundle(self.root)
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

    def test_legacy_root_with_content_flags_migration(self) -> None:
        legacy = _read_json(self.root / "agent-manifest.json") if (self.root / "agent-manifest.json").is_file() else {}
        write_bundle(self.root)
        legacy = _read_json(self.root / "agent-manifest.json")
        legacy["content"] = {"methodology": [], "pitfalls": [], "guardrails": [], "case_studies": []}
        (self.root / "agent-manifest.json").write_text(
            json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report = validate_repo(self.root)
        self.assertIn("MANIFEST_LEGACY_CONTENT", _codes(report))
        self.assertTrue(report["ok"])

    def test_root_manifest_too_large(self) -> None:
        write_bundle(self.root)
        manifest = _read_json(self.root / "agent-manifest.json")
        # 人为塞入大量字段把根摘要撑到 >160 行
        for index in range(200):
            manifest[f"extra_{index}"] = index
        (self.root / "agent-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report = validate_repo(self.root)
        self.assertIn("MANIFEST_SIZE", _codes(report))
        self.assertTrue(report["ok"])
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])

    def test_shard_missing(self) -> None:
        write_bundle(self.root)
        (default_shard_dir(self.root) / "pitfalls.json").unlink()
        report = validate_repo(self.root)
        self.assertIn("SHARD_MISSING", _codes(report))
        self.assertTrue(report["ok"])

    def test_shard_entries_over_limit(self) -> None:
        write_bundle(self.root)
        shard_path = default_shard_dir(self.root) / "pitfalls.json"
        shard = _read_json(shard_path)
        base_entry = shard["entries"][0]
        entries = []
        for index in range(45):
            entry = dict(base_entry)
            entry["id"] = f"PIT-{900 + index:03d}"
            entries.append(entry)
        shard["entries"] = entries
        shard["count"] = len(entries)
        shard_path.write_text(json.dumps(shard, ensure_ascii=False, indent=2), encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("SHARD_ENTRIES", _codes(report))
        self.assertIn("SHARD_SIZE", _codes(report))
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])

    def test_shard_duplicate_id_and_absolute_path(self) -> None:
        write_bundle(self.root)
        shard_path = default_shard_dir(self.root) / "pitfalls.json"
        shard = _read_json(shard_path)
        first, second = shard["entries"][0], shard["entries"][1]
        duplicated = dict(first)
        duplicated["path"] = "C:/absolute/PIT-001.md"
        shard["entries"].append(duplicated)
        shard["count"] = len(shard["entries"])
        shard_path.write_text(json.dumps(shard, ensure_ascii=False, indent=2), encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("SHARD_ID_DUPLICATE", _codes(report))
        self.assertIn("SHARD_ABSOLUTE_PATH", _codes(report))
        self.assertIn(second["id"], [entry["id"] for entry in shard["entries"]])

    def test_shard_content_frontmatter_mismatch(self) -> None:
        write_bundle(self.root)
        shard_path = default_shard_dir(self.root) / "methodology.json"
        shard = _read_json(shard_path)
        shard["entries"][1]["title"] = "被手改的标题"
        shard_path.write_text(json.dumps(shard, ensure_ascii=False, indent=2), encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("SHARD_CONTENT", _codes(report))

    def test_shard_split_over_40_is_valid(self) -> None:
        for index in range(2, 41):  # 2 + 39 = 41 > 40（PIT 有 40 条上限，故用 methodology）
            write_doc(
                self.root,
                f"methodology/{index:02d}-batch-{index}.md",
                entry_id=f"MTH-{index:03d}",
                title=f"批量方法 {index}",
                doc_type="methodology",
                body=f"# 批量方法 {index}\n\n正文。\n",
            )
        write_bundle(self.root)
        shard_dir = default_shard_dir(self.root)
        self.assertTrue((shard_dir / "methodology-p01.json").is_file())
        self.assertTrue((shard_dir / "methodology-p02.json").is_file())
        self.assertFalse((shard_dir / "methodology.json").exists())
        report = validate_repo(self.root, strict=True)
        self.assertTrue(report["ok"], _codes(report))
        self.assertEqual(report["checked"]["shards"], 5)  # 四层 4 片 + methodology 拆 2 片
        self.assertNotIn("SHARD_SPLIT", _codes(report))

    def test_shard_split_contract_violations_detected(self) -> None:
        for index in range(2, 41):
            write_doc(
                self.root,
                f"methodology/{index:02d}-batch-{index}.md",
                entry_id=f"MTH-{index:03d}",
                title=f"批量方法 {index}",
                doc_type="methodology",
                body=f"# 批量方法 {index}\n\n正文。\n",
            )
        write_bundle(self.root)
        shard_dir = default_shard_dir(self.root)
        manifest_path = self.root / "agent-manifest.json"
        manifest_text = manifest_path.read_text(encoding="utf-8").replace(
            "agent-manifest.d/methodology-p02.json", "agent-manifest.d/methodology-2.json"
        )
        manifest_path.write_text(manifest_text, encoding="utf-8")
        (shard_dir / "methodology-p02.json").rename(shard_dir / "methodology-2.json")
        report = validate_repo(self.root)
        self.assertIn("SHARD_NAMING", _codes(report))
        self.assertNotIn("SHARD_MISSING", _codes(report))
        report = validate_repo(self.root, strict=True)
        self.assertFalse(report["ok"])

    def test_manifest_schema_error_reported_by_json_check(self) -> None:
        (self.root / "agent-manifest.json").write_text(
            json.dumps({"schema": "wrong"}), encoding="utf-8"
        )
        report = validate_repo(self.root)
        self.assertIn("JSON_SCHEMA", _codes(report))
        self.assertFalse(report["ok"])


class DocPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)
        write_bundle(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_doc_line_limit_warning_then_strict_error(self) -> None:
        _write_long_doc(
            self.root, "methodology/20-long.md", entry_id="MTH-020", title="长文", body_lines=310
        )
        report = validate_repo(self.root)
        self.assertIn("DOC_LINES", _codes(report))
        self.assertTrue(report["ok"])
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])

    def test_changelog_window_limit(self) -> None:
        _write_changelog(self.root, 9)
        report = validate_repo(self.root)
        self.assertIn("CHANGELOG_WINDOW", _codes(report))
        self.assertTrue(report["ok"])
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])
        _write_changelog(self.root, 8)
        self.assertNotIn("CHANGELOG_WINDOW", _codes(validate_repo(self.root)))

    def test_changelog_archive_index_row_not_counted(self) -> None:
        """§4 归档索引行（| 2026-11 | 44 条… |）不是窗口数据行，不得计入 ≤8 上限。"""
        path = _write_changelog(self.root, 8)
        write_changelog_archive(self.root, month="2026-11", rows=44)
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n## 4. 归档索引\n\n")
            handle.write("| 月份 | 条数 | 文件 |\n|---|---|---|\n")
            handle.write("| 2026-11 | 44 条 | [changelog/2026-11.md](changelog/2026-11.md) |\n")
        report = validate_repo(self.root)
        self.assertNotIn("CHANGELOG_WINDOW", _codes(report))
        self.assertNotIn("CHANGELOG_ARCHIVE", _codes(report))
        self.assertTrue(report["ok"])

    def test_changelog_archive_consistent_passes(self) -> None:
        write_changelog_with_archive(self.root, month="2026-10", rows=5)
        report = validate_repo(self.root)
        self.assertNotIn("CHANGELOG_ARCHIVE", _codes(report))
        self.assertTrue(report["ok"])
        self.assertEqual(report["checked"]["changelog_archive_rows"], 1)

    def test_changelog_archive_byte_limit(self) -> None:
        archive = self.root / "changelog" / "2026-01.md"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text("# 归档\n\n" + ("x" * (262144 + 100)), encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("CHANGELOG_ARCHIVE_BYTES", _codes(report))

    def test_status_section_limit(self) -> None:
        readme = self.root / "README.md"
        body = "# 仓库入口\n\n## 10. 当前状态\n\n" + "".join(
            f"行 {index}\n" for index in range(1, 12)
        )
        readme.write_text(body, encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("STATUS_SECTION", _codes(report))
        self.assertTrue(report["ok"])
        self.assertFalse(validate_repo(self.root, strict=True)["ok"])

    def test_policy_missing_falls_back_to_defaults(self) -> None:
        missing = Path(self._tmp.name) / "missing-policy.json"
        report = validate_repo(self.root, policy_path=missing)
        self.assertIn("POLICY_MISSING", _codes(report))
        self.assertTrue(report["ok"])
        self.assertFalse(report["issues"][0]["level"] == "error")
        # 默认策略仍执行：9 条窗口仍可被识别
        _write_changelog(self.root, 9)
        self.assertIn("CHANGELOG_WINDOW", _codes(validate_repo(self.root, policy_path=missing)))

    def test_policy_invalid_falls_back_to_defaults(self) -> None:
        bad = Path(self._tmp.name) / "bad-policy.json"
        bad.write_text("{not-json", encoding="utf-8")
        report = validate_repo(self.root, policy_path=bad)
        self.assertIn("POLICY_INVALID", _codes(report))
        self.assertTrue(report["ok"])

    def test_policy_limits_match_doc_policy_file(self) -> None:
        policy, warnings = load_policy()
        self.assertEqual(warnings, [])
        self.assertEqual(policy["archival"]["max_current_entries"], 8)
        self.assertEqual(policy["manifest"]["root_max_lines"], 160)
        self.assertEqual(policy["line_limits"]["pitfalls/PIT-*.md"], 90)
        self.assertEqual(policy["line_limits"]["pitfalls/README.md"], 150)
        self.assertEqual(policy["line_limits"]["guardrails/GRD-*.md"], 90)
        self.assertEqual(policy["line_limits"]["guardrails/README.md"], 130)
        self.assertEqual(policy["line_limits"]["adr/*.md"], 120)
        self.assertEqual(policy["line_limits"]["adr/README.md"], 90)
        self.assertEqual(policy["line_limits"]["AGENTS.md"], 320)
        self.assertEqual(policy["line_limits"]["toolkit/README.md"], 440)
        self.assertEqual(policy["line_limits"]["toolkit/templates/*.md"], 130)
        self.assertEqual(policy["line_limits"]["backlog.json"], 600)
        self.assertEqual(policy["manifest"]["shard_max_entries"], 40)
        self.assertEqual(policy["archival"]["current_file"], DEFAULT_POLICY["archival"]["current_file"])
        self.assertEqual(
            policy["archival"]["window_row_pattern"],
            DEFAULT_POLICY["archival"]["window_row_pattern"],
        )
        # 新增策略段：protocol / naming / governance / backlog（与 DEFAULT_POLICY 同步）
        for section in ("protocol", "naming", "governance", "backlog"):
            self.assertEqual(policy[section], DEFAULT_POLICY[section])
        self.assertEqual(policy["protocol"]["recommended_max_lines"], 200)
        self.assertEqual(policy["protocol"]["hard_max_lines"], 320)
        self.assertEqual(policy["protocol"]["sentinel"], "<!-- END-OF-PROTOCOL -->")
        self.assertEqual(policy["governance"]["pitfall_max_entries"], 40)
        self.assertEqual(policy["backlog"]["schema_file"], "toolkit/schema/backlog.schema.json")
        self.assertEqual(
            policy["backlog"]["archive_schema_file"],
            "toolkit/schema/backlog-archive.schema.json",
        )
        self.assertEqual(policy["backlog"]["archive_file"], "backlog-archive.json")
        self.assertEqual(policy["backlog"]["max_active_done"], 5)
        self.assertEqual(policy["line_limit_margin"], DEFAULT_POLICY["line_limit_margin"])
        self.assertEqual(policy["line_limit_margin"]["warning_within"], 15)

    def test_doc_lines_margin_advisory_does_not_fail_strict(self) -> None:
        """距上限 <15 行报 advisory；strict 仍 ok，余量恢复后预警消失。"""
        path = _write_long_doc(
            self.root, "methodology/17-margin.md", entry_id="MTH-017", title="余量", body_lines=10
        )
        text = path.read_text(encoding="utf-8").rstrip("\n")

        def _pad_to(target_lines: int) -> None:
            missing = target_lines - len(text.splitlines())
            self.assertGreater(missing, 0)
            path.write_text(
                text + "\n" + "\n".join("补充行" for _ in range(missing)) + "\n",
                encoding="utf-8",
            )

        _pad_to(300 - 5)
        write_bundle(self.root)
        report = validate_repo(self.root, strict=True)
        self.assertIn("DOC_LINES_MARGIN", _codes(report))
        self.assertGreaterEqual(report["advisory_count"], 1)
        self.assertEqual(report["warning_count"], 0)
        self.assertTrue(report["ok"])

        _pad_to(300 - 20)
        report = validate_repo(self.root, strict=True)
        self.assertNotIn("DOC_LINES_MARGIN", _codes(report))
        self.assertEqual(report["advisory_count"], 0)
        self.assertTrue(report["ok"])


if __name__ == "__main__":
    unittest.main()
