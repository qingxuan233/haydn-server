"""CLI 契约测试：--help/退出码、fixture 离线跑通、子命令输出、probe 能力契约。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from toolkit.repurpose import cli
from toolkit.repurpose.adb import FixtureTransport
from toolkit.repurpose.indexgen import write_manifest, write_bundle
from toolkit.repurpose.probe import probe_profile
from toolkit.repurpose.profile import CAPABILITY_IDS, validate_profile
from toolkit.repurpose.util import REPO_ROOT, SCHEMA_PROFILE
from toolkit.tests.fixtures.repo_builder import build_sample_repo, write_doc

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ADB_FIXTURE = FIXTURES / "adb-haydn.json"
LOCKED_PROFILE = FIXTURES / "profile-haydn-locked.json"
ROOT_READY_PROFILE = FIXTURES / "profile-root-lab-ready.json"
ROOT_RESEARCH_PROFILE = REPO_ROOT / "cases" / "ace-pro-pgp110" / "profile.json"


def _run(args: list[str], cwd: Path = REPO_ROOT, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "toolkit.repurpose", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )


def _run_raw(args: list[str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[bytes]:
    """模拟普通用户环境：移除 UTF-8 相关环境变量，按 Windows 默认编码捕获字节。

    这是编码回归测试的关键：CLI 必须自己把 stdout 切成 UTF-8，不能依赖调用方设置
    PYTHONIOENCODING/PYTHONUTF8，否则中文 JSON 在 cp936 管道下不是合法 UTF-8。
    """
    env = dict(os.environ)
    for key in ("PYTHONIOENCODING", "PYTHONUTF8", "PYTHONLEGACYWINDOWSSTDIO"):
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, "-m", "toolkit.repurpose", *args],
        cwd=str(cwd),
        capture_output=True,
        env=env,
        timeout=120,
    )


MARKER_PLACEHOLDER = "TO" + "DO"  # 避免源码出现待办标记字面量


class _NoDeviceTransport:
    """模拟 adb 存在但没有在线设备。"""

    name = "adb"

    def devices(self) -> list[dict[str, str]]:
        return []

    def shell(self, command: str, serial: str | None = None) -> str:
        return ""


class HelpAndUsageTests(unittest.TestCase):
    def test_help_exits_zero_and_lists_commands(self) -> None:
        result = _run(["--help"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        for command in (
            "detect",
            "probe",
            "assess",
            "plan",
            "rootcheck",
            "rescue-kit",
            "new-profile",
            "index",
            "validate",
            "preflight",
        ):
            self.assertIn(command, result.stdout)
        self.assertIn("退出码", result.stdout)
        self.assertIn("python -m toolkit.repurpose", result.stdout)
        self.assertNotIn(MARKER_PLACEHOLDER, result.stdout)

    def test_subcommand_help_exits_zero(self) -> None:
        for command in (
            "detect",
            "probe",
            "assess",
            "plan",
            "rootcheck",
            "rescue-kit",
            "new-profile",
            "index",
            "validate",
            "preflight",
        ):
            with self.subTest(command=command):
                result = _run([command, "--help"])
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_no_subcommand_shows_help_and_returns_2(self) -> None:
        result = _run([])
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stdout + result.stderr)

    def test_assess_requires_profile(self) -> None:
        result = _run(["assess", "--json"])
        self.assertEqual(result.returncode, 2)

    def test_verbose_global_flag(self) -> None:
        result = _run(["--verbose", "assess", "--profile", str(LOCKED_PROFILE), "--json"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("[verbose]", result.stderr)


class DetectTests(unittest.TestCase):
    def test_detect_with_fixture_outputs_valid_profile(self) -> None:
        result = _run(["detect", "--adb-fixture", str(ADB_FIXTURE)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        profile = json.loads(result.stdout)
        self.assertEqual(profile["schema"], SCHEMA_PROFILE)
        self.assertEqual(profile["source"]["mode"], "fixture")
        self.assertEqual(profile["identity"]["codename"], "haydn")
        self.assertIsNone(profile["identity"]["serial"])
        self.assertTrue(profile["identity"]["serial_redacted"])
        self.assertFalse(profile["boot"]["bootloader_unlocked"])
        self.assertEqual(profile["root"]["state"], "none")
        self.assertFalse(profile["features"]["user_ns"])
        self.assertFalse(profile["features"]["pid_ns"])
        self.assertEqual(validate_profile(profile), [])
        for key in (
            "identity",
            "boot",
            "root",
            "kernel",
            "hardware",
            "storage",
            "crypto",
            "features",
            "constraints",
            "unknowns",
            "evidence_refs",
            "warnings",
        ):
            self.assertIn(key, profile)

    def test_detect_include_serial(self) -> None:
        result = _run(["detect", "--adb-fixture", str(ADB_FIXTURE), "--include-serial"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        profile = json.loads(result.stdout)
        self.assertEqual(profile["identity"]["serial"], "TEST00000001")
        self.assertFalse(profile["identity"]["serial_redacted"])

    def test_detect_out_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "detected.json"
            result = _run(["detect", "--adb-fixture", str(ADB_FIXTURE), "--out", str(out)])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(out.is_file())
            self.assertIn("已写入", result.stdout)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["schema"], SCHEMA_PROFILE)

    def test_detect_without_device_returns_3(self) -> None:
        rc = cli.main(["detect"], transport=_NoDeviceTransport())
        self.assertEqual(rc, 3)

    def test_detect_bad_fixture_returns_3(self) -> None:
        result = _run(["detect", "--adb-fixture", "toolkit/tests/fixtures/does-not-exist.json"])
        self.assertEqual(result.returncode, 3)
        self.assertIn("fixture", result.stderr.lower())


class ProbeTests(unittest.TestCase):
    def test_probe_with_fixture_adds_twelve_capabilities(self) -> None:
        result = _run(
            [
                "probe",
                "--base",
                str(LOCKED_PROFILE),
                "--adb-fixture",
                str(ADB_FIXTURE),
                "--json",
            ]
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        profile = json.loads(result.stdout)
        self.assertEqual(profile["probe"]["mode"], "fixture")
        self.assertEqual(set(profile["capabilities"]), set(CAPABILITY_IDS))
        for capability_id, item in profile["capabilities"].items():
            self.assertIn(item["status"], ("pass", "fail", "unknown"))
            self.assertTrue(item["evidence"])
        verdicts = profile["verdicts"]["summary"]
        self.assertEqual(verdicts["pass"] + verdicts["fail"] + verdicts["unknown"], 12)
        self.assertEqual(profile["verdicts"]["route_hint"], "A")
        self.assertEqual(profile["capabilities"]["containers"]["status"], "fail")
        self.assertEqual(profile["capabilities"]["native_linux"]["status"], "fail")
        self.assertEqual(validate_profile(profile), [])

    def test_probe_offline_mode_with_base_only(self) -> None:
        fixture_transport = FixtureTransport(ADB_FIXTURE)
        locked = json.loads(LOCKED_PROFILE.read_text(encoding="utf-8"))
        probed, mode = probe_profile(locked, None)
        self.assertEqual(mode, "offline")
        self.assertIn("离线模式", " ".join(probed["warnings"]))
        self.assertEqual(set(probed["capabilities"]), set(CAPABILITY_IDS))
        self.assertGreaterEqual(len(locked["unknowns"]), 1)
        self.assertEqual(probed["capabilities"]["containers"]["status"], "fail")
        # 用 fixture 跑一次，确保同一 profile 在线/离线都不崩
        probed_online, mode_online = probe_profile(locked, fixture_transport)
        self.assertEqual(mode_online, "fixture")

    def test_probe_requires_base_or_device(self) -> None:
        # 用空 PATH 模拟“没有 adb 的机器”，否则本机装了 platform-tools 且连着设备时该用例不成立
        result = _run(["probe", "--json"], env_extra={"PATH": "", "ADB_PATH": ""})
        self.assertEqual(result.returncode, 3)


class AssessPlanTests(unittest.TestCase):
    def test_assess_locked_profile_route_a(self) -> None:
        result = _run(["assess", "--profile", str(LOCKED_PROFILE), "--json"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        assessment = json.loads(result.stdout)
        self.assertEqual(assessment["schema"], "repurpose.assessment.v1")
        self.assertEqual(assessment["route"], "A")
        self.assertIn("gates", assessment)
        gate_status = {gate["id"]: gate["status"] for gate in assessment["gates"]}
        self.assertEqual(gate_status["G-B0"], "fail")
        self.assertNotIn("TEST00000001", result.stdout)

    def test_assess_human_output(self) -> None:
        result = _run(["assess", "--profile", str(LOCKED_PROFILE)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("路线：A", result.stdout)
        self.assertIn("下一步", result.stdout)

    def test_plan_default_markdown(self) -> None:
        result = _run(["plan", "--profile", str(LOCKED_PROFILE)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("## P0", result.stdout)
        self.assertIn("## P6", result.stdout)
        self.assertIn("改造计划", result.stdout)

    def test_plan_json_format(self) -> None:
        result = _run(["plan", "--profile", str(LOCKED_PROFILE), "--format", "json"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["schema"], "repurpose.plan.v1")
        self.assertEqual([stage["id"] for stage in plan["stages"]], [f"P{i}" for i in range(7)])
        self.assertEqual(plan["route"], "A")

    def test_plan_route_choice_validation(self) -> None:
        result = _run(["plan", "--profile", str(LOCKED_PROFILE), "--route", "Z"])
        self.assertEqual(result.returncode, 2)


class RootcheckTests(unittest.TestCase):
    def test_rootcheck_ready_profile_json(self) -> None:
        result = _run(["rootcheck", "--profile", str(ROOT_READY_PROFILE), "--json"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "repurpose.rootcheck.v1")
        self.assertEqual(report["verdict"], "tech-ready")
        self.assertTrue(report["tech_ready"])

    def test_rootcheck_strict_ready_returns_0(self) -> None:
        result = _run(["rootcheck", "--profile", str(ROOT_READY_PROFILE), "--strict"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_rootcheck_strict_research_returns_4(self) -> None:
        result = _run(["rootcheck", "--profile", str(ROOT_RESEARCH_PROFILE), "--strict", "--json"])
        self.assertEqual(result.returncode, 4, msg=result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "blocked")

    def test_rootcheck_human_output(self) -> None:
        result = _run(["rootcheck", "--profile", str(ROOT_RESEARCH_PROFILE)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Root 实验姿态", result.stdout)
        self.assertIn("人工确认", result.stdout)

    def test_rootcheck_requires_profile(self) -> None:
        result = _run(["rootcheck", "--json"])
        self.assertEqual(result.returncode, 2)

    def test_assess_route_unchanged_for_research_and_ready_profiles(self) -> None:
        research = _run(["assess", "--profile", str(ROOT_RESEARCH_PROFILE), "--json"])
        self.assertEqual(research.returncode, 0, msg=research.stderr)
        research_report = json.loads(research.stdout)
        self.assertEqual(research_report["route"], "A")
        gate_status = {gate["id"]: gate["status"] for gate in research_report["gates"]}
        self.assertEqual(gate_status["G-B0"], "unknown")

        ready = _run(["assess", "--profile", str(ROOT_READY_PROFILE), "--json"])
        self.assertEqual(ready.returncode, 0, msg=ready.stderr)
        ready_report = json.loads(ready.stdout)
        self.assertEqual(ready_report["route"], "B")
        gate_status = {gate["id"]: gate["status"] for gate in ready_report["gates"]}
        self.assertEqual(gate_status["G-B0"], "pass")
        self.assertEqual(gate_status["G-B1"], "pass")


class NewProfileTests(unittest.TestCase):
    def test_new_profile_stdout(self) -> None:
        result = _run(["new-profile", "--codename", "demo-device"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        profile = json.loads(result.stdout)
        self.assertEqual(profile["identity"]["codename"], "demo-device")
        self.assertEqual(validate_profile(profile), [])

    def test_new_profile_out_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "new-profile.json"
            result = _run(["new-profile", "--codename", "demo", "--out", str(out)])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(out.is_file())
            self.assertIn("已写入", result.stdout)


class IndexValidateTests(unittest.TestCase):
    def test_index_generates_manifest_at_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            build_sample_repo(root)
            result = _run(["index", "--root", str(root), "--json"])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["schema"], "repurpose.agent-manifest.v1")
            self.assertEqual(summary["counts"]["methodology"], 2)
            self.assertEqual(summary["counts"]["pitfalls"], 2)
            self.assertEqual(summary["output"], "agent-manifest.json")
            self.assertLessEqual(summary["root"]["lines"], 160)
            self.assertLessEqual(summary["root"]["bytes"], 16384)
            self.assertEqual(set(summary["shards"]), {"methodology", "pitfalls", "guardrails", "case_studies"})
            manifest_path = root / "agent-manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("reading_order", manifest)
            self.assertIn("shards", manifest)
            self.assertNotIn("content", manifest)
            shard_dir = root / "agent-manifest.d"
            self.assertEqual(
                sorted(path.name for path in shard_dir.glob("*.json")),
                ["case-studies.json", "guardrails.json", "methodology.json", "pitfalls.json"],
            )
            shard = json.loads((shard_dir / "pitfalls.json").read_text(encoding="utf-8"))
            self.assertEqual(shard["schema"], "repurpose.manifest-shard.v1")
            self.assertEqual(shard["layer"], "pitfalls")
            self.assertEqual(shard["count"], len(shard["entries"]))

    def test_index_cleans_stale_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo-clean"
            build_sample_repo(root)
            shard_dir = root / "agent-manifest.d"
            shard_dir.mkdir(parents=True, exist_ok=True)
            stale = shard_dir / "case_studies.json"
            stale.write_text(
                json.dumps(
                    {
                        "schema": "repurpose.manifest-shard.v1",
                        "layer": "case_studies",
                        "generated_at": "2026-11-11T00:00:00Z",
                        "count": 0,
                        "entries": [],
                    }
                ),
                encoding="utf-8",
            )
            result = _run(["index", "--root", str(root), "--json"])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            summary = json.loads(result.stdout)
            self.assertIn("agent-manifest.d/case_studies.json", summary["removed_shards"])
            self.assertFalse(stale.exists())

    def test_index_missing_toolkit_readme_warns_but_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo2"
            build_sample_repo(root, with_toolkit_readme=False)
            result = _run(["index", "--root", str(root), "--json"])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            summary = json.loads(result.stdout)
            self.assertTrue(any("toolkit/README.md" in warning for warning in summary["warnings"]))

    def test_validate_valid_repo_returns_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo3"
            build_sample_repo(root)
            write_manifest(root)
            result = _run(["validate", "--root", str(root)])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("validate 结果：OK", result.stdout)

    def test_validate_broken_repo_returns_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo4"
            build_sample_repo(root)
            write_manifest(root)
            write_doc(
                root,
                "methodology/99-broken.md",
                entry_id="MTH-099",
                title="断链",
                doc_type="methodology",
                body="# 断链\n\n[不存在](missing.md)\n",
            )
            result = _run(["validate", "--root", str(root), "--json"])
            self.assertEqual(result.returncode, 4)
            report = json.loads(result.stdout)
            self.assertFalse(report["ok"])
            self.assertIn("LINK_BROKEN", [issue["code"] for issue in report["issues"]])
            self.assertIn("root", report)

    def test_validate_strict_turns_warning_into_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo5"
            build_sample_repo(root)
            write_manifest(root)
            write_doc(
                root,
                "guardrails/GRD-002-warn.md",
                entry_id="GRD-002",
                title="警告",
                doc_type="guardrail",
                severity="warning",
                scope="repo",
                body="# 警告\n\n[绝对路径](/etc/hosts)\n",
            )
            result = _run(["validate", "--root", str(root), "--strict"])
            self.assertEqual(result.returncode, 4)
            self.assertIn("warning", result.stdout.lower())


class IndexCheckTests(unittest.TestCase):
    """``index --check``：只读比较生成物与内容，一致 exit 0 / 不一致 exit 4。"""

    def _repo(self, tmp: str) -> Path:
        root = Path(tmp) / "repo-check"
        build_sample_repo(root)
        write_bundle(root)
        return root

    def test_consistent_returns_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            result = _run(["index", "--check", "--root", str(root), "--json"])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["schema"], "repurpose.index-check.v1")
            self.assertTrue(report["ok"])
            self.assertEqual(report["diffs"], [])
            self.assertTrue(report["checked"]["root"]["ok"])
            self.assertEqual(len(report["checked"]["shards"]), 4)
            self.assertTrue(all(shard["ok"] for shard in report["checked"]["shards"]))

    def test_generated_at_only_difference_returns_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo-check"
            build_sample_repo(root)
            write_bundle(root, generated_at="2026-01-01T00:00:00Z")
            result = _run(["index", "--check", "--root", str(root)])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("index 一致", result.stdout)
            self.assertFalse((root / "agent-manifest.json").read_text(encoding="utf-8").count("1970-01-01"))

    def test_tampered_shard_returns_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            shard_path = root / "agent-manifest.d" / "pitfalls.json"
            shard = json.loads(shard_path.read_text(encoding="utf-8"))
            shard["entries"][0]["title"] = "被手改的标题"
            shard_path.write_text(json.dumps(shard, ensure_ascii=False, indent=2), encoding="utf-8")
            result = _run(["index", "--check", "--root", str(root), "--json"])
            self.assertEqual(result.returncode, 4)
            report = json.loads(result.stdout)
            self.assertFalse(report["ok"])
            self.assertIn(
                "agent-manifest.d/pitfalls.json",
                [diff["path"] for diff in report["diffs"]],
            )

    def test_tampered_root_manifest_returns_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            manifest_path = root / "agent-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["counts"]["pitfalls"] = 99
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            result = _run(["index", "--check", "--root", str(root)])
            self.assertEqual(result.returncode, 4)
            self.assertIn("index 不一致", result.stdout)
            self.assertIn("agent-manifest.json", result.stdout)

    def test_missing_manifest_returns_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo-check"
            build_sample_repo(root)
            result = _run(["index", "--check", "--root", str(root), "--json"])
            self.assertEqual(result.returncode, 4)
            report = json.loads(result.stdout)
            self.assertEqual(report["diffs"][0]["reason"], "missing")

    def test_index_no_rewrite_when_content_unchanged(self) -> None:
        """默认路径 + 无显式 generated_at：内容未变化时第二次 index 保留原 generated_at。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo-noop"
            build_sample_repo(root)
            first = _run(["index", "--root", str(root), "--json"])
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            first_report = json.loads(first.stdout)
            self.assertTrue(first_report["written"])
            generated_at = first_report["generated_at"]

            second = _run(["index", "--root", str(root), "--json"])
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            second_report = json.loads(second.stdout)
            self.assertFalse(second_report["written"])
            self.assertEqual(second_report["generated_at"], generated_at)

            human = _run(["index", "--root", str(root)])
            self.assertEqual(human.returncode, 0, msg=human.stderr)
            self.assertIn("未重写", human.stdout)
            self.assertIn(generated_at, human.stdout)


class EncodingRegressionTests(unittest.TestCase):
    """回归：Windows cp936 管道下，CLI 必须自己输出合法 UTF-8。

    这些用例故意不设置 PYTHONIOENCODING/PYTHONUTF8，直接捕获字节后 decode("utf-8")，
    以此证明编码由 CLI 入口统一处理，而不是依赖调用方环境。
    """

    def _decode(self, result: subprocess.CompletedProcess[bytes]) -> str:
        self.assertEqual(result.returncode, 0, msg=result.stderr.decode("utf-8", "replace"))
        raw = result.stdout
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "stdout 不应带 UTF-8 BOM")
        return raw.decode("utf-8")  # 非法 UTF-8 会抛 UnicodeDecodeError

    def test_assess_json_stdout_is_utf8_and_parseable(self) -> None:
        result = _run_raw(["assess", "--profile", str(LOCKED_PROFILE), "--json"])
        text = self._decode(result)
        data = json.loads(text)
        self.assertEqual(data["schema"], "repurpose.assessment.v1")
        self.assertEqual(data["route"], "A")
        self.assertIn("门禁", text)  # 中文 JSON 值应保留为 UTF-8 文本

    def test_assess_human_stdout_is_utf8(self) -> None:
        result = _run_raw(["assess", "--profile", str(LOCKED_PROFILE)])
        text = self._decode(result)
        self.assertIn("路线：A", text)
        self.assertIn("下一步", text)

    def test_detect_json_stdout_is_utf8_and_parseable(self) -> None:
        result = _run_raw(["detect", "--adb-fixture", str(ADB_FIXTURE)])
        text = self._decode(result)
        data = json.loads(text)
        self.assertEqual(data["schema"], SCHEMA_PROFILE)
        self.assertFalse(data["identity"]["serial_redacted"] is False)

    def test_plan_json_stdout_is_utf8_and_parseable(self) -> None:
        result = _run_raw(["plan", "--profile", str(LOCKED_PROFILE), "--format", "json"])
        text = self._decode(result)
        data = json.loads(text)
        self.assertEqual(data["schema"], "repurpose.plan.v1")
        self.assertEqual(data["stages"][0]["id"], "P0")

    def test_index_json_stdout_is_utf8_and_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo-encoding"
            build_sample_repo(root)
            result = _run_raw(["index", "--root", str(root), "--json"])
            text = self._decode(result)
            data = json.loads(text)
            self.assertEqual(data["schema"], "repurpose.agent-manifest.v1")
            self.assertIn("counts", data)

    def test_validate_json_stdout_is_utf8_and_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo-encoding-validate"
            build_sample_repo(root)
            write_manifest(root)
            write_doc(
                root,
                "methodology/99-broken.md",
                entry_id="MTH-099",
                title="断链",
                doc_type="methodology",
                body="# 断链\n\n[不存在](missing.md)\n",
            )
            result = _run_raw(["validate", "--root", str(root), "--json"])
            self.assertEqual(result.returncode, 4)
            raw = result.stdout
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            text = raw.decode("utf-8")  # 校验失败时也必须输出合法 UTF-8 JSON
            data = json.loads(text)
            self.assertIn("LINK_BROKEN", [issue["code"] for issue in data["issues"]])
            self.assertIn("链接目标不存在", text)  # 中文错误信息也必须是合法 UTF-8

    def test_profile_out_file_is_utf8_without_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "profile.json"
            result = _run_raw(
                ["detect", "--adb-fixture", str(ADB_FIXTURE), "--out", str(out)]
            )
            self._decode(result)
            raw = out.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "profile 文件不应带 UTF-8 BOM")
            payload = json.loads(raw.decode("utf-8"))
            self.assertEqual(payload["schema"], SCHEMA_PROFILE)
            self.assertTrue(raw.decode("utf-8").endswith("\n"))

    def test_manifest_file_is_utf8_without_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo-encoding-manifest"
            build_sample_repo(root)
            result = _run_raw(["index", "--root", str(root)])
            self._decode(result)
            manifest_path = root / "agent-manifest.json"
            raw = manifest_path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "agent-manifest.json 不应带 BOM")
            manifest = json.loads(raw.decode("utf-8"))
            self.assertEqual(manifest["schema"], "repurpose.agent-manifest.v1")
            # 中文 title 应以 UTF-8 原样写入，而不是 \uXXXX 转义或乱码
            self.assertIn("方法论索引", raw.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
