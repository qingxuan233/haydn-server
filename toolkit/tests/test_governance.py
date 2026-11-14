"""governance 治理检查测试：协议/命名/PIT/ADR/CHANGELOG 归档/backlog/AR 回归。

覆盖 frozen 契约（``inventory/agent-harness-plan.md`` §3.1–§3.7）的每个检查码，
并包含 **AR-04 反例自证**：构造违规仓库后 ``validate_repo(strict=True)`` 必须报
error，且 CLI ``validate --strict`` 必须 exit 4（证明检查真的会拦截）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from toolkit.repurpose.docpolicy import load_policy
from toolkit.repurpose.indexgen import write_bundle
from toolkit.repurpose.util import REPO_ROOT
from toolkit.repurpose.validate import validate_repo
from toolkit.tests.fixtures.repo_builder import (
    build_sample_repo,
    make_backlog_item,
    write_adr,
    write_adr_index,
    write_agents_md,
    write_backlog,
    write_backlog_archive,
    write_backlog_raw,
    write_changelog_with_archive,
    write_doc,
    write_pitfall,
    write_preflight_harness,
    write_unindexed_archive,
)


def _codes(report: dict) -> list[str]:
    return [issue["code"] for issue in report["issues"]]


def _messages(report: dict, code: str) -> list[str]:
    return [issue["message"] for issue in report["issues"] if issue["code"] == code]


def _run_cli(args: list[str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "toolkit.repurpose", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )


class _RepoTestCase(unittest.TestCase):
    """每个用例一个干净的临时仓库（结构完整，validate --strict 可全绿）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)
        write_bundle(self.root)  # 基线全绿（含 manifest，validate --strict 可过）

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def codes(self, strict: bool = False) -> list[str]:
        return _codes(validate_repo(self.root, strict=strict))


# ---------------------------------------------------------------------------
# §3.1 协议检查
# ---------------------------------------------------------------------------


class ProtocolCheckTests(_RepoTestCase):
    def test_valid_protocol_passes_and_tier_healthy(self) -> None:
        report = validate_repo(self.root, strict=True)
        self.assertTrue(report["ok"], msg=_codes(report))
        self.assertNotIn("PROTOCOL_SIZE", _codes(report))
        self.assertEqual(report["checked"]["protocol_tier"], "healthy")
        self.assertTrue(report["checked"]["protocol"])

    def test_missing_required_section(self) -> None:
        write_agents_md(self.root, omit_sections=["机器可读接口"])
        codes = self.codes(strict=True)
        self.assertIn("PROTOCOL_SECTION", codes)
        self.assertIn("机器可读接口", " ".join(_messages(validate_repo(self.root), "PROTOCOL_SECTION")))
        self.assertFalse(validate_repo(self.root)["ok"])

    def test_missing_sentinel(self) -> None:
        write_agents_md(self.root, sentinel=False)
        self.assertIn("PROTOCOL_SENTINEL", self.codes())

    def test_invalid_version_row(self) -> None:
        write_agents_md(self.root, protocol_version="1.2")
        self.assertIn("PROTOCOL_VERSION", self.codes())

    def test_missing_version_row(self) -> None:
        write_agents_md(self.root, omit_version_row=True)
        self.assertIn("PROTOCOL_VERSION", self.codes())

    def test_warning_tier_does_not_fail_even_strict(self) -> None:
        """201~320 行属警告档：只记 tier=warning，不产生 PROTOCOL_SIZE，strict 不失败。"""
        write_agents_md(self.root, padding_lines=190)
        lines = len((self.root / "AGENTS.md").read_text(encoding="utf-8").splitlines())
        self.assertGreater(lines, 200)
        self.assertLessEqual(lines, 320)
        report = validate_repo(self.root, strict=True)
        self.assertEqual(report["checked"]["protocol_tier"], "warning")
        self.assertNotIn("PROTOCOL_SIZE", _codes(report))
        self.assertTrue(report["ok"], msg=_codes(report))

    def test_over_hard_limit_is_error(self) -> None:
        write_agents_md(self.root, padding_lines=330)
        lines = len((self.root / "AGENTS.md").read_text(encoding="utf-8").splitlines())
        self.assertGreater(lines, 320)
        report = validate_repo(self.root)
        self.assertIn("PROTOCOL_SIZE", _codes(report))
        self.assertEqual(report["checked"]["protocol_tier"], "debt")
        self.assertFalse(report["ok"])

    def test_doc_policy_line_limit_matches_protocol_hard_limit(self) -> None:
        policy, _warnings = load_policy()
        self.assertEqual(policy["line_limits"]["AGENTS.md"], policy["protocol"]["hard_max_lines"])


# ---------------------------------------------------------------------------
# §3.2 命名检查
# ---------------------------------------------------------------------------


class NamingCheckTests(_RepoTestCase):
    def test_valid_repo_has_no_naming_issue(self) -> None:
        self.assertNotIn("DOC_NAMING", self.codes())

    def test_uppercase_filename(self) -> None:
        write_doc(
            self.root,
            "methodology/05-Bad-Name.md",
            entry_id="MTH-002",
            title="大写文件名",
            doc_type="methodology",
            body="# 大写\n",
        )
        self.assertIn("DOC_NAMING", self.codes())

    def test_chinese_filename(self) -> None:
        write_doc(
            self.root,
            "methodology/06-中文.md",
            entry_id="MTH-003",
            title="中文文件名",
            doc_type="methodology",
            body="# 中文\n",
        )
        self.assertIn("DOC_NAMING", self.codes())

    def test_forbidden_status_token(self) -> None:
        write_pitfall(self.root, 2, "final")
        report = validate_repo(self.root)
        self.assertIn("DOC_NAMING", _codes(report))
        self.assertIn("final", " ".join(_messages(report, "DOC_NAMING")))

    def test_pitfall_prefix_mismatch(self) -> None:
        write_doc(
            self.root,
            "pitfalls/PIT-2-bad.md",
            entry_id="PIT-002",
            title="前缀错误",
            doc_type="pitfall",
            severity="S2",
            domain="server",
            body="# 前缀\n\n## 症状\n\n## 根因\n\n## 规避与修复\n\n## 验证\n\n## 证据\n",
        )
        self.assertIn("DOC_NAMING", self.codes())

    def test_guardrail_prefix_mismatch(self) -> None:
        write_doc(
            self.root,
            "guardrails/GRD-2-bad.md",
            entry_id="GRD-002",
            title="前缀错误",
            doc_type="guardrail",
            severity="warning",
            scope="repo",
            body="# 前缀\n",
        )
        self.assertIn("DOC_NAMING", self.codes())

    def test_readme_is_exempt(self) -> None:
        # 基线仓库含 methodology/README.md 等约定入口；不应报命名问题
        self.assertNotIn("DOC_NAMING", self.codes())

    def test_template_naming_enforced(self) -> None:
        write_doc(
            self.root,
            "toolkit/templates/Bad-Template.md",
            entry_id="TOOL-001",
            title="模板命名测试",
            doc_type="tool",
            body="# 模板\n",
        )
        self.assertIn("DOC_NAMING", self.codes())


# ---------------------------------------------------------------------------
# §3.3 PIT 检查
# ---------------------------------------------------------------------------


class PitfallCheckTests(_RepoTestCase):
    def test_gap_is_error(self) -> None:
        write_pitfall(self.root, 3, "third")
        report = validate_repo(self.root)
        self.assertIn("PIT_ID_GAP", _codes(report))
        self.assertIn("PIT-002", " ".join(_messages(report, "PIT_ID_GAP")))

    def test_duplicate_number_is_error(self) -> None:
        write_pitfall(self.root, 1, "duplicate")
        report = validate_repo(self.root)
        self.assertIn("PIT_ID_GAP", _codes(report))
        self.assertIn("重复", " ".join(_messages(report, "PIT_ID_GAP")))

    def test_front_matter_id_mismatch(self) -> None:
        write_pitfall(self.root, 2, "mismatch", entry_id="PIT-009")
        self.assertIn("PIT_ID_GAP", self.codes())

    def test_missing_required_section(self) -> None:
        write_pitfall(self.root, 2, "broken", sections=["症状", "根因", "规避", "验证"])
        report = validate_repo(self.root)
        self.assertIn("PIT_SECTION", _codes(report))
        self.assertIn("证据", " ".join(_messages(report, "PIT_SECTION")))

    def test_count_limit(self) -> None:
        for number in range(2, 42):
            write_pitfall(self.root, number, f"entry{number}")
        report = validate_repo(self.root)
        self.assertIn("PIT_COUNT", _codes(report))
        self.assertEqual(report["checked"]["pitfall_files"], 41)
        self.assertFalse(report["ok"])

    def test_valid_pitfalls_pass(self) -> None:
        write_pitfall(self.root, 2, "second")
        write_bundle(self.root)  # 新增内容后重建索引，避免 MANIFEST_COUNTS 干扰
        report = validate_repo(self.root, strict=True)
        self.assertNotIn("PIT_ID_GAP", _codes(report))
        self.assertNotIn("PIT_SECTION", _codes(report))
        self.assertTrue(report["ok"], msg=_codes(report))


# ---------------------------------------------------------------------------
# §3.4 ADR 检查
# ---------------------------------------------------------------------------


class AdrCheckTests(_RepoTestCase):
    def test_valid_baseline(self) -> None:
        report = validate_repo(self.root, strict=True)
        self.assertTrue(report["ok"], msg=_codes(report))
        self.assertEqual(report["checked"]["adr_files"], 1)
        # 4 位 ADR ID / accepted 状态 / adr 类型不应触发旧枚举 warning
        for code in ("ID_FORMAT", "STATUS_VALUE", "TYPE_VALUE"):
            self.assertNotIn(code, _codes(report))

    def test_filename_violation(self) -> None:
        write_doc(
            self.root,
            "adr/0002_bad-name.md",
            entry_id="ADR-0002",
            title="坏文件名",
            doc_type="adr",
            status="accepted",
            body="# ADR-0002\n\n## 状态\n\n## 背景\n\n## 决策\n\n## 后果\n",
        )
        self.assertIn("ADR_FILENAME", self.codes())

    def test_number_gap(self) -> None:
        write_adr(self.root, 3, "gap")
        write_adr_index(self.root)
        self.assertIn("ADR_FILENAME", self.codes())

    def test_id_mismatch(self) -> None:
        write_adr(self.root, 2, "id-bad", entry_id="ADR-0003")
        write_adr_index(self.root)
        self.assertIn("ADR_ID", self.codes())

    def test_invalid_status(self) -> None:
        write_adr(self.root, 2, "status-bad", status="current")
        write_adr_index(self.root)
        report = validate_repo(self.root)
        self.assertIn("ADR_STATUS", _codes(report))
        self.assertIn("superseded", " ".join(_messages(report, "ADR_STATUS")))

    def test_missing_required_section(self) -> None:
        write_adr(self.root, 2, "section-bad", sections=("状态", "背景"))
        write_adr_index(self.root)
        self.assertIn("ADR_SECTION", self.codes())

    def test_superseded_without_link(self) -> None:
        write_adr(self.root, 2, "superseded", status="superseded")
        write_adr_index(self.root)
        self.assertIn("ADR_SUPERSEDED", self.codes())

    def test_superseded_broken_target(self) -> None:
        write_adr(self.root, 2, "superseded", status="superseded", superseded_by="ADR-0099")
        write_adr_index(self.root)
        report = validate_repo(self.root)
        self.assertIn("ADR_SUPERSEDED", _codes(report))
        self.assertIn("ADR-0099", " ".join(_messages(report, "ADR_SUPERSEDED")))

    def test_superseded_valid_target(self) -> None:
        write_adr(self.root, 2, "superseded-ok", status="superseded", superseded_by="ADR-0001")
        write_adr_index(self.root)
        self.assertNotIn("ADR_SUPERSEDED", self.codes())

    def test_index_orphan(self) -> None:
        write_adr(self.root, 2, "orphan")
        write_adr_index(self.root, filenames=["0001-demo.md"])
        self.assertIn("ADR_INDEX", self.codes())

    def test_index_missing(self) -> None:
        (self.root / "adr" / "README.md").unlink()
        report = validate_repo(self.root)
        self.assertIn("ADR_INDEX", _codes(report))

    def test_index_wrong_id(self) -> None:
        write_adr_index(self.root)
        path = self.root / "adr" / "README.md"
        text = path.read_text(encoding="utf-8").replace("id: ADR-000", "id: ADR-009")
        path.write_text(text, encoding="utf-8")
        self.assertIn("ADR_INDEX", self.codes())

    def test_adr_directory_absent_is_degraded(self) -> None:
        import shutil

        shutil.rmtree(self.root / "adr")
        report = validate_repo(self.root)
        self.assertNotIn("ADR_INDEX", _codes(report))
        self.assertNotIn("ADR_FILENAME", _codes(report))
        self.assertEqual(report["checked"]["adr_files"], 0)


# ---------------------------------------------------------------------------
# §3.5 CHANGELOG 归档索引
# ---------------------------------------------------------------------------


class ChangelogArchiveTests(_RepoTestCase):
    def test_consistent_archive_passes(self) -> None:
        write_changelog_with_archive(self.root, rows=5)
        report = validate_repo(self.root, strict=True)
        self.assertNotIn("CHANGELOG_ARCHIVE", _codes(report))
        self.assertTrue(report["ok"], msg=_codes(report))
        self.assertEqual(report["checked"]["changelog_archive_rows"], 1)

    def test_declared_count_mismatch(self) -> None:
        write_changelog_with_archive(self.root, rows=5, declared_count=4)
        report = validate_repo(self.root)
        self.assertIn("CHANGELOG_ARCHIVE", _codes(report))
        self.assertIn("4", " ".join(_messages(report, "CHANGELOG_ARCHIVE")))

    def test_archive_file_missing(self) -> None:
        write_changelog_with_archive(self.root, rows=3)
        (self.root / "changelog" / "2026-10.md").unlink()
        self.assertIn("CHANGELOG_ARCHIVE", self.codes())

    def test_declared_version_range_mismatch(self) -> None:
        write_changelog_with_archive(self.root, rows=5, declared_range=("v0.1", "v0.9"))
        report = validate_repo(self.root)
        self.assertIn("CHANGELOG_ARCHIVE", _codes(report))
        self.assertIn("v0.9", " ".join(_messages(report, "CHANGELOG_ARCHIVE")))

    def test_unindexed_archive_file(self) -> None:
        write_unindexed_archive(self.root, rows=2)
        self.assertIn("CHANGELOG_ARCHIVE", self.codes())

    def test_changelog_absent_is_degraded(self) -> None:
        (self.root / "CHANGELOG.md").unlink()
        import shutil

        for archive in (self.root / "changelog").glob("*.md"):
            archive.unlink()
        report = validate_repo(self.root)
        self.assertNotIn("CHANGELOG_ARCHIVE", _codes(report))
        self.assertEqual(report["checked"]["changelog_archive_rows"], 0)


# ---------------------------------------------------------------------------
# §3.6 backlog schema / 语义
# ---------------------------------------------------------------------------


class BacklogCheckTests(_RepoTestCase):
    def test_valid_baseline(self) -> None:
        report = validate_repo(self.root, strict=True)
        self.assertNotIn("BACKLOG_SCHEMA", _codes(report))
        self.assertNotIn("BACKLOG_SEMANTIC", _codes(report))
        self.assertEqual(report["checked"]["backlog_items"], 2)
        self.assertTrue(report["checked"]["backlog"])

    def test_missing_required_field(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-001", notes=None)])
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_SCHEMA", _codes(report))
        self.assertIn("notes", " ".join(_messages(report, "BACKLOG_SCHEMA")))

    def test_invalid_priority_enum(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-001", priority="P9")])
        self.assertIn("BACKLOG_SCHEMA", self.codes())

    def test_invalid_status_enum(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-001", status="finished")])
        self.assertIn("BACKLOG_SCHEMA", self.codes())

    def test_invalid_risk_enum(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-001", risk="X")])
        self.assertIn("BACKLOG_SCHEMA", self.codes())

    def test_missing_id_pattern(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-1")])
        self.assertIn("BACKLOG_SCHEMA", self.codes())

    def test_id_gap(self) -> None:
        write_backlog(
            self.root,
            [make_backlog_item("BL-001"), make_backlog_item("BL-003")],
        )
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_SEMANTIC", _codes(report))
        self.assertIn("BL-002", " ".join(_messages(report, "BACKLOG_SEMANTIC")))

    def test_duplicate_id(self) -> None:
        write_backlog(
            self.root,
            [make_backlog_item("BL-001"), make_backlog_item("BL-001")],
        )
        self.assertIn("BACKLOG_SEMANTIC", self.codes())

    def test_done_requires_result_and_owner(self) -> None:
        write_backlog(
            self.root,
            [
                make_backlog_item(
                    "BL-001",
                    status="done",
                    owner=None,
                    updated=None,
                    result=None,
                )
            ],
        )
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_SEMANTIC", _codes(report))
        messages = " ".join(_messages(report, "BACKLOG_SEMANTIC"))
        for key in ("owner", "updated", "result"):
            self.assertIn(key, messages)

    def test_done_bad_updated_date(self) -> None:
        write_backlog(
            self.root,
            [
                make_backlog_item(
                    "BL-001",
                    status="done",
                    owner="toolkit",
                    updated="2026/11/11",
                    result="已完成",
                )
            ],
        )
        self.assertIn("BACKLOG_SEMANTIC", self.codes())

    def test_depends_broken_link(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-001", depends=["BL-009"])])
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_SEMANTIC", _codes(report))
        self.assertIn("BL-009", " ".join(_messages(report, "BACKLOG_SEMANTIC")))

    def test_outputs_absolute_path(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-001", outputs=["C:/tmp/out.md"])])
        self.assertIn("BACKLOG_SEMANTIC", self.codes())

    def test_invalid_json(self) -> None:
        write_backlog_raw(self.root, "{not-json")
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_SCHEMA", _codes(report))
        self.assertIn("JSON_PARSE", _codes(report))

    def test_top_level_missing_items(self) -> None:
        write_backlog(self.root, omit_keys=["items"])
        self.assertIn("BACKLOG_SCHEMA", self.codes())

    def test_outputs_may_point_to_future_files(self) -> None:
        """outputs 允许指向尚未产出的文件（不因路径不存在报 error）。"""
        write_backlog(
            self.root,
            [make_backlog_item("BL-001", outputs=["future/not-yet-existing.md"])],
        )
        report = validate_repo(self.root, strict=True)
        self.assertNotIn("BACKLOG_SEMANTIC", _codes(report))
        self.assertTrue(report["ok"], msg=_codes(report))

    def test_backlog_absent_is_degraded(self) -> None:
        (self.root / "backlog.json").unlink()
        report = validate_repo(self.root)
        self.assertFalse(report["checked"]["backlog"])
        self.assertNotIn("BACKLOG_SCHEMA", _codes(report))

    # ------------------------------------------------------------------
    # 归档窗口（backlog-archive.json / BACKLOG_DONE_WINDOW / BACKLOG_ARCHIVE）
    # ------------------------------------------------------------------

    @staticmethod
    def _done(entry_id: str, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": "done",
            "owner": "toolkit",
            "updated": "2026-11-11",
            "result": "已完成：fixture",
        }
        payload.update(overrides)
        return make_backlog_item(entry_id, **payload)

    def test_archive_valid_and_depends_resolve_across_files(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-002", depends=["BL-001"])])
        write_backlog_archive(self.root, [self._done("BL-001")])
        report = validate_repo(self.root, strict=True)
        self.assertNotIn("BACKLOG_ARCHIVE", _codes(report))
        self.assertNotIn("BACKLOG_SEMANTIC", _codes(report))
        self.assertNotIn("BACKLOG_DONE_WINDOW", _codes(report))
        self.assertTrue(report["ok"], msg=_codes(report))

    def test_done_window_exceeded(self) -> None:
        write_backlog(self.root, [self._done(f"BL-{index:03d}") for index in range(1, 7)])
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_DONE_WINDOW", _codes(report))
        self.assertIn("5", " ".join(_messages(report, "BACKLOG_DONE_WINDOW")))
        self.assertFalse(report["ok"])

    def test_archive_item_must_be_done(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-002")])
        write_backlog_archive(self.root, [make_backlog_item("BL-001")])
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_ARCHIVE", _codes(report))
        self.assertIn("done", " ".join(_messages(report, "BACKLOG_ARCHIVE")))

    def test_archive_duplicate_with_active(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-001")])
        write_backlog_archive(self.root, [self._done("BL-001")])
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_ARCHIVE", _codes(report))
        self.assertIn("BL-001", " ".join(_messages(report, "BACKLOG_ARCHIVE")))

    def test_archive_union_gap(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-003")])
        write_backlog_archive(self.root, [self._done("BL-001")])
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_SEMANTIC", _codes(report))
        self.assertIn("BL-002", " ".join(_messages(report, "BACKLOG_SEMANTIC")))

    def test_archive_schema_const(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-001")])
        write_backlog_archive(self.root, [self._done("BL-002")], schema="repurpose.backlog.v1")
        self.assertIn("BACKLOG_ARCHIVE", self.codes())

    def test_archive_missing_result(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-002")])
        write_backlog_archive(self.root, [self._done("BL-001", result="")])
        report = validate_repo(self.root)
        self.assertIn("BACKLOG_ARCHIVE", _codes(report))
        self.assertIn("result", " ".join(_messages(report, "BACKLOG_ARCHIVE")))


# ---------------------------------------------------------------------------
# §3.7 Agent 回归（AR-02 / AR-03）
# ---------------------------------------------------------------------------


class AgentRegressionTests(_RepoTestCase):
    def test_ar02_redlines_require_grd_links(self) -> None:
        path = self.root / "AGENTS.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("[GRD-001](guardrails/GRD-001-demo.md)", "GRD-001 文件")
        path.write_text(text, encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("AGENT_REGRESSION", _codes(report))
        self.assertIn("GRD 链接", " ".join(_messages(report, "AGENT_REGRESSION")))

    def test_ar02_requires_at_least_nine_redlines(self) -> None:
        write_agents_md(self.root, redline_count=8)
        report = validate_repo(self.root)
        self.assertIn("AGENT_REGRESSION", _codes(report))
        self.assertIn("9", " ".join(_messages(report, "AGENT_REGRESSION")))

    def test_ar02_missing_redline_section(self) -> None:
        write_agents_md(self.root, omit_sections=["红线"])
        self.assertIn("AGENT_REGRESSION", self.codes())

    def test_ar03_empty_invariants(self) -> None:
        write_bundle(self.root)
        manifest_path = self.root / "agent-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["invariants"] = []
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("AGENT_REGRESSION", _codes(report))
        self.assertIn("invariants", " ".join(_messages(report, "AGENT_REGRESSION")))

    def test_ar03_missing_redline_keyword(self) -> None:
        write_bundle(self.root)
        manifest_path = self.root / "agent-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["invariants"] = ["测试用 invariant"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        report = validate_repo(self.root)
        self.assertIn("AGENT_REGRESSION", _codes(report))
        self.assertIn("不 Root", " ".join(_messages(report, "AGENT_REGRESSION")))

    def test_ar03_manifest_absent_is_degraded(self) -> None:
        (self.root / "agent-manifest.json").unlink()
        report = validate_repo(self.root)
        self.assertNotIn("AGENT_REGRESSION", _codes(report))
        self.assertEqual(report["checked"]["agent_regression_checks"], 1)  # 仅 AR-02


# ---------------------------------------------------------------------------
# AR-04 反例自证：违规仓库必须被拦截（validate_repo + CLI exit 4）
# ---------------------------------------------------------------------------


class Ar04CounterExampleTests(_RepoTestCase):
    def _corrupt_repo(self) -> None:
        """在同一仓库内制造 6 类违规（每类对应一个检查码）。"""
        # 1) 坏 front matter（缺必需键）
        (self.root / "methodology" / "99-broken-fm.md").write_text("# 无 front matter\n", encoding="utf-8")
        # 2) 非法 backlog 枚举
        write_backlog(self.root, [make_backlog_item("BL-001", priority="P9")])
        # 3) ADR 跳号（缺 0002，直接写 0003）
        write_adr(self.root, 3, "gap")
        write_adr_index(self.root)
        # 4) PIT 跳号（缺 002，直接写 003）
        write_pitfall(self.root, 3, "gap")
        # 5) CHANGELOG 归档条数不符
        write_changelog_with_archive(self.root, rows=5, declared_count=4)
        # 6) 非法命名（大写 + 禁止状态词）
        write_doc(
            self.root,
            "methodology/05-Final.md",
            entry_id="MTH-050",
            title="非法命名",
            doc_type="methodology",
            body="# 非法命名\n",
        )

    def test_clean_repo_passes_before_corruption(self) -> None:
        write_bundle(self.root)
        report = validate_repo(self.root, strict=True)
        self.assertTrue(report["ok"], msg=_codes(report))
        result = _run_cli(["validate", "--root", str(self.root), "--strict"])
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)

    def test_violations_are_caught_and_cli_exits_4(self) -> None:
        self._corrupt_repo()
        report = validate_repo(self.root, strict=True)
        self.assertFalse(report["ok"])
        codes = _codes(report)
        # 六类违规全部被拦（front matter / backlog / ADR / PIT / CHANGELOG / 命名）
        for code in (
            "FM_MISSING",
            "BACKLOG_SCHEMA",
            "ADR_FILENAME",
            "PIT_ID_GAP",
            "CHANGELOG_ARCHIVE",
            "DOC_NAMING",
        ):
            self.assertIn(code, codes, msg=f"反例未被拦截：{code}")
        self.assertGreaterEqual(report["error_count"], 6)
        result = _run_cli(["validate", "--root", str(self.root), "--strict", "--json"])
        self.assertEqual(result.returncode, 4, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertGreater(payload["error_count"], 0)


# ---------------------------------------------------------------------------
# 降级与聚合
# ---------------------------------------------------------------------------


class DegradationTests(unittest.TestCase):
    def test_missing_governance_files_do_not_error(self) -> None:
        """临时 fixture 仓库缺 AGENTS/backlog/CHANGELOG/adr 时，治理检查降级跳过。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            build_sample_repo(root, with_governance_files=False)
            report = validate_repo(root)
            self.assertTrue(report["ok"], msg=_codes(report))
            for code in (
                "PROTOCOL_SECTION",
                "PROTOCOL_VERSION",
                "PROTOCOL_SENTINEL",
                "BACKLOG_SCHEMA",
                "ADR_INDEX",
                "CHANGELOG_ARCHIVE",
                "AGENT_REGRESSION",
            ):
                self.assertNotIn(code, _codes(report))
            self.assertFalse(report["checked"]["protocol"])
            self.assertEqual(report["checked"]["protocol_tier"], "missing")

    def test_preflight_harness_repo_is_full_green(self) -> None:
        """带 preflight stub 的 fixture 仓库（index/validate/unittest/check-links 全 OK）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            build_sample_repo(root)
            write_preflight_harness(root)
            report = validate_repo(root)
            self.assertTrue(report["ok"], msg=_codes(report))


if __name__ == "__main__":
    unittest.main()
