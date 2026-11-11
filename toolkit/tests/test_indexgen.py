"""indexgen 测试：根摘要（≤160 行）+ 四层分片、限额、旧分片清理、缺失目录容错。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from toolkit.repurpose.docpolicy import load_policy, manifest_limits
from toolkit.repurpose.indexgen import (
    CONTENT_GROUPS,
    SHARD_DIR,
    SHARD_FILENAMES,
    SCHEMA_SHARD,
    build_bundle,
    build_manifest,
    cleanup_stale_shards,
    default_manifest_path,
    default_shard_dir,
    format_index_summary,
    render_root_manifest,
    render_shard,
    scan_group,
    shard_relative_path,
    write_bundle,
    write_manifest,
)
from toolkit.repurpose.util import SCHEMA_MANIFEST, parse_iso
from toolkit.tests.fixtures.repo_builder import build_sample_repo, write_doc


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _add_many_pitfalls(root: Path, count: int) -> None:
    for index in range(1, count + 1):
        write_doc(
            root,
            f"pitfalls/PIT-{900 + index:03d}.md",
            entry_id=f"PIT-{900 + index:03d}",
            title=f"批量踩坑 {index}",
            doc_type="pitfall",
            severity="S3",
            domain="docs",
            body=f"# 批量踩坑 {index}\n\n正文。\n",
        )


class IndexBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_root_manifest_is_compact_summary(self) -> None:
        manifest = build_manifest(self.root)
        self.assertEqual(manifest["schema"], SCHEMA_MANIFEST)
        self.assertIsNotNone(parse_iso(manifest["generated_at"]))
        self.assertNotIn("content", manifest)
        text = render_root_manifest(manifest)
        self.assertLessEqual(len(text.splitlines()), 160)
        self.assertLessEqual(len(text.encode("utf-8")), 16384)
        # JSON 合法且无绝对路径
        parsed = json.loads(text)
        self.assertNotIn(str(self.root), text)
        self.assertEqual(parsed["repo"]["root"], ".")

    def test_root_required_keys(self) -> None:
        manifest = build_manifest(self.root)
        for key in (
            "schema",
            "generated_at",
            "repo",
            "entrypoints",
            "reading_order",
            "counts",
            "shards",
            "tools",
            "invariants",
            "commands",
            "warnings",
            "errors",
        ):
            self.assertIn(key, manifest)

    def test_counts_match_content_and_shards(self) -> None:
        bundle = build_bundle(self.root)
        manifest = bundle["root"]
        counts = manifest["counts"]
        self.assertEqual(counts["methodology"], 2)
        self.assertEqual(counts["pitfalls"], 2)
        self.assertEqual(counts["guardrails"], 2)
        self.assertEqual(counts["case_studies"], 2)
        self.assertEqual(counts["tools"], 5)
        self.assertEqual(counts["total_entry_docs"], 8)
        for layer in CONTENT_GROUPS:
            shard = bundle["shards"][layer]["data"]
            self.assertEqual(counts[layer], len(shard["entries"]))
            self.assertEqual(manifest["shards"][layer]["count"], len(shard["entries"]))

    def test_entrypoints_and_reading_order_groups(self) -> None:
        manifest = build_manifest(self.root)
        ids = [entry["id"] for entry in manifest["entrypoints"]]
        self.assertIn("MTH-000", ids)
        self.assertIn("TOOL-000", ids)
        self.assertIn("PIT-000", ids)
        self.assertIn("GRD-000", ids)
        self.assertIn("CASE-000", ids)
        layers = [group["layer"] for group in manifest["reading_order"]]
        self.assertEqual(layers, ["methodology", "tools", "case_studies", "guardrails", "pitfalls"])
        case_group = next(group for group in manifest["reading_order"] if group["layer"] == "case_studies")
        self.assertEqual(case_group["ids"], ["CASE-000", "CASE-001"])
        for group in manifest["reading_order"]:
            self.assertEqual(group["count"], len(group["ids"]))
            self.assertIn("reason", group)
        self.assertEqual(
            manifest["counts"]["reading_order"],
            sum(group["count"] for group in manifest["reading_order"]),
        )

    def test_shards_four_layers_and_fields(self) -> None:
        bundle = build_bundle(self.root)
        limits = manifest_limits(load_policy()[0])
        expected_files = {
            layer: shard_relative_path(layer) for layer in CONTENT_GROUPS
        }
        self.assertEqual(set(bundle["shards"]), set(CONTENT_GROUPS))
        for layer, shard_info in bundle["shards"].items():
            shard = shard_info["data"]
            self.assertEqual(shard["schema"], SCHEMA_SHARD)
            self.assertEqual(shard["layer"], layer)
            self.assertIsNotNone(parse_iso(shard["generated_at"]))
            self.assertEqual(shard["count"], len(shard["entries"]))
            self.assertLessEqual(len(shard_info["text"].splitlines()), limits["shard_max_lines"])
            self.assertLessEqual(shard_info["bytes"], limits["shard_max_bytes"])
            self.assertLessEqual(len(shard["entries"]), limits["shard_max_entries"])
            self.assertEqual(shard_info["path"], expected_files[layer])
            self.assertTrue(shard_info["path"].startswith("agent-manifest.d/"))
            for entry in shard["entries"]:
                for key in ("id", "title", "path", "type", "status", "tags", "agent_hint"):
                    self.assertIn(key, entry)
                self.assertFalse(entry["path"].startswith("/"))
            json.loads(shard_info["text"])  # 合法 JSON

    def test_shards_carry_severity_domain_scope(self) -> None:
        bundle = build_bundle(self.root)
        pitfall = next(
            entry
            for entry in bundle["shards"]["pitfalls"]["data"]["entries"]
            if entry["id"] == "PIT-001"
        )
        self.assertEqual(pitfall["severity"], "S2")
        self.assertEqual(pitfall["domain"], "server")
        guardrail = next(
            entry
            for entry in bundle["shards"]["guardrails"]["data"]["entries"]
            if entry["id"] == "GRD-001"
        )
        self.assertEqual(guardrail["severity"], "blocker")
        self.assertEqual(guardrail["scope"], "device")

    def test_write_bundle_writes_root_and_shards(self) -> None:
        info = write_bundle(self.root)
        root_path = Path(info["root_path"])
        self.assertEqual(root_path, default_manifest_path(self.root))
        self.assertTrue(root_path.is_file())
        manifest = _read_json(root_path)
        self.assertNotIn("content", manifest)
        self.assertEqual(set(manifest["shards"]), set(CONTENT_GROUPS))
        shard_dir = default_shard_dir(self.root)
        self.assertTrue(shard_dir.is_dir())
        self.assertEqual(
            sorted(path.name for path in shard_dir.glob("*.json")),
            sorted(SHARD_FILENAMES.values()),
        )
        self.assertEqual(info["root"]["lines"], len(root_path.read_text(encoding="utf-8").splitlines()))
        self.assertEqual(set(info["shards"]), set(CONTENT_GROUPS))
        self.assertEqual(info["errors"], [])
        self.assertLessEqual(info["root"]["lines"], 160)

    def test_write_manifest_compatibility(self) -> None:
        target, manifest = write_manifest(self.root)
        self.assertEqual(target, default_manifest_path(self.root))
        self.assertEqual(manifest["schema"], SCHEMA_MANIFEST)
        self.assertTrue(default_shard_dir(self.root).is_dir())

    def test_write_bundle_custom_out(self) -> None:
        custom = Path(self._tmp.name) / "custom-manifest.json"
        info = write_bundle(self.root, out=custom)
        self.assertEqual(Path(info["root_path"]), custom)
        self.assertTrue(custom.is_file())
        self.assertEqual(info["root"]["path"], "custom-manifest.json")

    def test_stale_shard_cleanup_only_own_schema(self) -> None:
        shard_dir = default_shard_dir(self.root)
        shard_dir.mkdir(parents=True, exist_ok=True)
        stale = shard_dir / "case_studies.json"
        stale.write_text(
            json.dumps({"schema": SCHEMA_SHARD, "layer": "case_studies", "entries": []}),
            encoding="utf-8",
        )
        foreign = shard_dir / "foreign.json"
        foreign.write_text(json.dumps({"note": "not generated by toolkit"}), encoding="utf-8")
        broken = shard_dir / "broken.json"
        broken.write_text("{not-json", encoding="utf-8")
        removed, warnings = cleanup_stale_shards(self.root)
        self.assertIn("agent-manifest.d/case_studies.json", removed)
        self.assertFalse(stale.exists())
        self.assertTrue(foreign.exists())
        self.assertTrue(broken.exists())
        self.assertTrue(any("foreign.json" in warning for warning in warnings))
        self.assertTrue(any("broken.json" in warning for warning in warnings))

        another = shard_dir / "guardrails_old.json"
        another.write_text(
            json.dumps({"schema": SCHEMA_SHARD, "layer": "guardrails", "entries": []}),
            encoding="utf-8",
        )
        info = write_bundle(self.root)
        self.assertIn("agent-manifest.d/guardrails_old.json", info["removed_shards"])
        self.assertTrue(any("foreign.json" in warning for warning in info["warnings"]))

    def test_shard_over_limit_reports_error(self) -> None:
        _add_many_pitfalls(self.root, 45)
        bundle = build_bundle(self.root)
        self.assertEqual(len(bundle["shards"]["pitfalls"]["data"]["entries"]), 47)
        joined = "\n".join(bundle["root"]["errors"])
        self.assertIn("分片超限", joined)
        self.assertIn("pitfalls", joined)

    def test_policy_limits_follow_doc_policy_file(self) -> None:
        policy, warnings = load_policy()
        self.assertEqual(warnings, [])
        limits = manifest_limits(policy)
        self.assertEqual(limits["root_max_lines"], 160)
        self.assertEqual(limits["shard_max_entries"], 40)

    def test_format_summary_mentions_root_and_shards(self) -> None:
        text = format_index_summary(write_bundle(self.root))
        self.assertIn("根摘要", text)
        self.assertIn("分片", text)
        self.assertIn("计数", text)


class IndexMissingDirectoryTests(unittest.TestCase):
    def test_empty_root_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            info = write_bundle(root)
            manifest = info["manifest"]
            self.assertEqual(manifest["counts"]["methodology"], 0)
            self.assertEqual(manifest["errors"], [])
            self.assertGreaterEqual(len(manifest["warnings"]), 5)
            self.assertEqual(set(manifest["shards"]), set(CONTENT_GROUPS))
            for layer in CONTENT_GROUPS:
                self.assertEqual(manifest["shards"][layer]["count"], 0)

    def test_missing_single_directory_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "partial"
            build_sample_repo(root)
            for path in (root / "cases").rglob("*.md"):
                path.unlink()
            manifest = build_manifest(root)
            self.assertEqual(manifest["counts"]["case_studies"], 0)
            self.assertTrue(any("cases" in warning for warning in manifest["warnings"]))
            self.assertEqual(manifest["errors"], [])

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
            self.assertEqual(manifest["errors"], [])
            self.assertIn("PIT-099", manifest["reading_order"][-1]["ids"])

    def test_doc_without_frontmatter_not_indexed_but_warned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nofm"
            build_sample_repo(root)
            (root / "cases" / "demo" / "notes.md").write_text("# 无 front matter\n", encoding="utf-8")
            manifest = build_manifest(root)
            self.assertTrue(any("notes.md" in warning for warning in manifest["warnings"]))
            self.assertEqual(manifest["counts"]["case_studies"], 2)


class ScanGroupTests(unittest.TestCase):
    def test_scan_group_returns_sorted_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "scan"
            build_sample_repo(root)
            entries, warnings, errors = scan_group(root, "methodology")
            self.assertEqual(errors, [])
            self.assertEqual([entry["id"] for entry in entries], ["MTH-000", "MTH-001"])
            self.assertTrue(entries[0]["path"].endswith("README.md"))
            self.assertFalse(warnings)

    def test_render_shard_has_one_line_per_entry(self) -> None:
        shard = {
            "schema": SCHEMA_SHARD,
            "layer": "pitfalls",
            "generated_at": "2026-11-11T00:00:00Z",
            "count": 2,
            "entries": [
                {
                    "id": "PIT-001",
                    "title": "a",
                    "path": "pitfalls/PIT-001.md",
                    "type": "pitfall",
                    "status": "current",
                    "tags": ["a"],
                    "agent_hint": "hint",
                    "severity": "S2",
                    "domain": "server",
                },
                {
                    "id": "PIT-002",
                    "title": "b",
                    "path": "pitfalls/PIT-002.md",
                    "type": "pitfall",
                    "status": "current",
                    "tags": ["b"],
                    "agent_hint": "hint",
                },
            ],
        }
        text = render_shard(shard)
        lines = text.splitlines()
        self.assertLessEqual(len(lines), 12)
        self.assertEqual(sum(1 for line in lines if '"id"' in line), 2)  # 每个条目录一行
        json.loads(text)


if __name__ == "__main__":
    unittest.main()
