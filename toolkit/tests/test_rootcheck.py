"""rootcheck 契约测试：技术姿态判定、人工项、边界与不伪造结论。"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from toolkit.repurpose.profile import load_profile, validate_profile
from toolkit.repurpose.rootcheck import (
    MANUAL_CHECKS,
    SCHEMA_ROOTCHECK,
    _arb_suffix,
    build_rootcheck,
    format_rootcheck_human,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
READY_PROFILE = FIXTURES / "profile-root-lab-ready.json"
RESEARCH_PROFILE = (
    Path(__file__).resolve().parents[2] / "cases" / "ace-pro-pgp110" / "profile.json"
)


def _load(path: Path) -> dict:
    return load_profile(path)


class ReadyPostureTests(unittest.TestCase):
    def test_fixture_is_structurally_valid(self) -> None:
        self.assertEqual(validate_profile(_load(READY_PROFILE)), [])

    def test_ready_report_is_tech_ready(self) -> None:
        report = build_rootcheck(_load(READY_PROFILE))
        self.assertEqual(report["schema"], SCHEMA_ROOTCHECK)
        self.assertEqual(report["verdict"], "tech-ready")
        self.assertTrue(report["tech_ready"])
        self.assertEqual(report["blocking_failures"], [])
        self.assertEqual(report["blocking_unknowns"], [])
        self.assertEqual(report["summary"]["pass"], report["summary"]["total"])
        for check in report["checks"]:
            self.assertEqual(check["status"], "pass", msg=check)

    def test_manual_checks_are_required_and_explicit(self) -> None:
        report = build_rootcheck(_load(READY_PROFILE))
        self.assertTrue(report["manual_review_required"])
        self.assertEqual(len(report["manual_checks"]), len(MANUAL_CHECKS))
        self.assertTrue(all(item["required"] is True for item in report["manual_checks"]))
        self.assertIn("RC-M01", [item["id"] for item in report["manual_checks"]])
        self.assertIn("RC-M05", [item["id"] for item in report["manual_checks"]])

    def test_human_output_marks_manual_review(self) -> None:
        text = format_rootcheck_human(build_rootcheck(_load(READY_PROFILE)))
        self.assertIn("tech-ready", text)
        self.assertIn("人工确认", text)
        self.assertIn("RC-M01", text)


class ResearchPostureTests(unittest.TestCase):
    def test_preresearch_profile_is_not_ready(self) -> None:
        profile = _load(RESEARCH_PROFILE)
        self.assertEqual(validate_profile(profile), [])
        report = build_rootcheck(profile)
        self.assertEqual(report["verdict"], "blocked")
        self.assertFalse(report["tech_ready"])
        self.assertIn("RC-T01", report["blocking_unknowns"])
        self.assertIn("RC-T05", report["blocking_failures"])

    def test_human_output_blocks(self) -> None:
        text = format_rootcheck_human(build_rootcheck(_load(RESEARCH_PROFILE)))
        self.assertIn("blocked", text)
        self.assertIn("技术检查", text)


class BoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = _load(READY_PROFILE)

    def test_verified_boot_green_with_unlocked_fails(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["boot"]["verified_boot_state"] = "green"
        report = build_rootcheck(profile)
        self.assertEqual(report["verdict"], "blocked")
        check = next(item for item in report["checks"] if item["id"] == "RC-T02")
        self.assertEqual(check["status"], "fail")

    def test_disabled_verity_and_permissive_selinux_fail(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["boot"]["dm_verity_mode"] = "disabled"
        profile["boot"]["selinux"] = "Permissive"
        report = build_rootcheck(profile)
        self.assertEqual(report["verdict"], "blocked")
        for check_id in ("RC-T03", "RC-T04"):
            check = next(item for item in report["checks"] if item["id"] == check_id)
            self.assertEqual(check["status"], "fail", msg=check)

    def test_multiple_managers_fail(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["root"]["root_manager_packages"] = ["me.weishu.kernelsu", "com.topjohnwu.magisk"]
        report = build_rootcheck(profile)
        check = next(item for item in report["checks"] if item["id"] == "RC-T06")
        self.assertEqual(check["status"], "fail")

    def test_kernelsu_on_gki1_fails(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["kernel"]["gki_generation"] = "gki-1.x"
        report = build_rootcheck(profile)
        check = next(item for item in report["checks"] if item["id"] == "RC-T07")
        self.assertEqual(check["status"], "fail")

    def test_apatch_without_kallsyms_fails(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["root"]["state"] = "apatch"
        profile["features"]["kallsyms"] = False
        report = build_rootcheck(profile)
        check = next(item for item in report["checks"] if item["id"] == "RC-T07")
        self.assertEqual(check["status"], "fail")

    def test_unknown_partition_layout_blocks(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["boot"]["partition_style"] = None
        profile["boot"]["has_init_boot"] = None
        report = build_rootcheck(profile)
        self.assertEqual(report["verdict"], "insufficient-evidence")
        check = next(item for item in report["checks"] if item["id"] == "RC-T08")
        self.assertEqual(check["status"], "unknown")
        self.assertFalse(report["tech_ready"])

    def test_arb_suffix_heuristic(self) -> None:
        self.assertEqual(_arb_suffix({"identity": {"build_id": "ColorOS 16.0.3.500"}}), ".500")
        self.assertEqual(_arb_suffix({"identity": {"build_id": "PGP110_15.0.0.1900"}}), "")
        self.assertIsNone(_arb_suffix({"identity": {"build_id": None}}))
        self.assertEqual(
            _arb_suffix(
                {
                    "identity": {
                        "build_id": None,
                        "fingerprint": "OnePlus/PGP110/ovaltine:16/AP3A/V16.0.3.501:user",
                    }
                }
            ),
            ".501",
        )

    def test_arb_hit_fails(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["identity"]["build_id"] = "ColorOS 16.0.3.503"
        report = build_rootcheck(profile)
        check = next(item for item in report["checks"] if item["id"] == "RC-T09")
        self.assertEqual(check["status"], "fail")
        self.assertEqual(report["verdict"], "blocked")

    def test_output_is_json_serializable_and_has_no_serial(self) -> None:
        report = build_rootcheck(self.profile)
        text = json.dumps(report, ensure_ascii=False)
        self.assertIn("repurpose.rootcheck.v1", text)
        self.assertNotIn('"serial"', text)


if __name__ == "__main__":
    unittest.main()
