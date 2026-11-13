"""preflight 三态退出码 / 步骤表 / --json 字段测试（临时仓库，不触碰真实仓库）。

三态契约：
- 0 全绿（index/validate/unittest/check-links 全部 OK）；
- 3 存在 SKIPPED（--skip-tests / --skip-links / --no-index / check-links 脚本缺失）；
- 4 任一步 FAILED（index errors / validate 非绿 / unittest 失败 / check-links 失败）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from toolkit.repurpose.util import REPO_ROOT
from toolkit.tests.fixtures.repo_builder import (
    build_sample_repo,
    make_backlog_item,
    write_backlog,
    write_preflight_harness,
)


def _run(args: list[str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
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
        timeout=300,
    )


def _statuses(report: dict) -> dict[str, str]:
    return {step["name"]: step["status"] for step in report["steps"]}


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        build_sample_repo(self.root)
        write_preflight_harness(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _preflight(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return _run(["preflight", "--root", str(self.root), *extra])

    def test_full_green_returns_0_and_json_contract(self) -> None:
        result = self._preflight("--json")
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "repurpose.preflight.v1")
        self.assertTrue(report["ok"])
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["skipped"], 0)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(
            [step["name"] for step in report["steps"]],
            ["index", "validate", "unittest", "check-links"],
        )
        self.assertEqual(_statuses(report), {name: "OK" for name in ("index", "validate", "unittest", "check-links")})
        for step in report["steps"]:
            self.assertIsInstance(step["duration_ms"], int)
            self.assertGreaterEqual(step["duration_ms"], 0)
            self.assertTrue(step["summary"])

    def test_human_output_is_step_table(self) -> None:
        result = self._preflight()
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        self.assertIn("preflight 结果：OK", result.stdout)
        for name in ("index", "validate", "unittest", "check-links"):
            self.assertIn(name, result.stdout)
        self.assertIn("skipped=0 failed=0 exit=0", result.stdout)

    def test_skip_tests_and_links_returns_3(self) -> None:
        result = self._preflight("--skip-tests", "--skip-links", "--json")
        self.assertEqual(result.returncode, 3, msg=result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["skipped"], 2)
        self.assertEqual(report["failed"], 0)
        statuses = _statuses(report)
        self.assertEqual(statuses["unittest"], "SKIPPED")
        self.assertEqual(statuses["check-links"], "SKIPPED")
        self.assertEqual(statuses["validate"], "OK")

    def test_no_index_returns_3_but_validate_still_runs(self) -> None:
        # --no-index 要求仓库已有提交版 manifest（CI 场景）；先 index 一次模拟已提交生成物
        result = self._preflight("--json")  # 生成 manifest（可能全绿或失败，只借写盘能力）
        self.assertIn(result.returncode, (0, 3, 4))
        result = self._preflight("--no-index", "--skip-tests", "--json")
        self.assertEqual(result.returncode, 3, msg=result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(_statuses(report)["index"], "SKIPPED")
        self.assertEqual(_statuses(report)["validate"], "OK")
        self.assertEqual(report["skipped"], 2)  # index + unittest

    def test_validate_failure_returns_4(self) -> None:
        write_backlog(self.root, [make_backlog_item("BL-001", priority="P9")])
        result = self._preflight("--skip-tests", "--skip-links", "--json")
        self.assertEqual(result.returncode, 4, msg=result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["failed"], 1)
        self.assertEqual(_statuses(report)["validate"], "FAILED")
        self.assertFalse(report["ok"])
        self.assertIn("BACKLOG_SCHEMA", _statuses(report) and json.dumps(report, ensure_ascii=False))

    def test_unittest_failure_returns_4(self) -> None:
        write_preflight_harness(self.root, tests_pass=False)
        result = self._preflight("--skip-links", "--json")
        self.assertEqual(result.returncode, 4, msg=result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(_statuses(report)["unittest"], "FAILED")
        self.assertGreaterEqual(report["failed"], 1)

    def test_check_links_failure_returns_4(self) -> None:
        write_preflight_harness(self.root, links_ok=False)
        result = self._preflight("--skip-tests", "--json")
        self.assertEqual(result.returncode, 4, msg=result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(_statuses(report)["check-links"], "FAILED")

    def test_missing_check_links_script_is_skipped(self) -> None:
        write_preflight_harness(self.root, with_check_links=False)
        script = self.root / "scripts" / "dev" / "check-links.py"
        if script.exists():
            script.unlink()
        result = self._preflight("--skip-tests", "--json")
        self.assertEqual(result.returncode, 3, msg=result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(_statuses(report)["check-links"], "SKIPPED")
        self.assertGreaterEqual(report["skipped"], 2)

    def test_preflight_help_lists_flags(self) -> None:
        result = _run(["preflight", "--help"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        for flag in ("--root", "--json", "--skip-tests", "--skip-links", "--no-index"):
            self.assertIn(flag, result.stdout)


if __name__ == "__main__":
    unittest.main()
