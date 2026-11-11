"""assess 离线评估测试：四条路线、门禁规则、未知降置信度、软门禁风险。"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from toolkit.repurpose.assess import (
    ROUTE_LABELS,
    assess_profile,
    evaluate_gates,
    format_assessment_human,
    select_route,
)
from toolkit.repurpose.profile import CAPABILITY_IDS
from toolkit.repurpose.util import SCHEMA_ASSESSMENT

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LOCKED_PROFILE = FIXTURES / "profile-haydn-locked.json"


def _locked() -> dict:
    return json.loads(LOCKED_PROFILE.read_text(encoding="utf-8"))


def _unlocked(**overrides) -> dict:
    profile = _locked()
    profile["boot"]["bootloader_unlocked"] = True
    profile["boot"]["oem_unlock_policy"] = "open"
    profile["boot"]["oem_unlock_evidence"] = None
    profile["root"]["state"] = "none"
    profile["root"]["su_available"] = False
    profile["features"]["user_ns"] = False
    profile["features"]["pid_ns"] = False
    profile["features"]["cgroup_v2_delegation"] = False
    profile["features"]["native_linux_port"] = False
    profile["features"]["custom_kernel"] = False
    profile.update(overrides)
    return profile


def _gate_map(assessment: dict) -> dict[str, dict]:
    return {gate["id"]: gate for gate in assessment["gates"]}


class RouteATests(unittest.TestCase):
    def test_locked_device_recommends_route_a(self) -> None:
        assessment = assess_profile(_locked())
        self.assertEqual(assessment["schema"], SCHEMA_ASSESSMENT)
        self.assertEqual(assessment["route"], "A")
        self.assertEqual(assessment["route_hint"], "A")
        self.assertEqual(assessment["route_label"], ROUTE_LABELS["A"])
        self.assertGreaterEqual(assessment["confidence"], 0.5)
        self.assertLessEqual(assessment["confidence"], 0.95)

    def test_gate_b0_fails_and_bcd_blocked(self) -> None:
        assessment = assess_profile(_locked())
        gates = _gate_map(assessment)
        self.assertEqual(gates["G-B0"]["status"], "fail")
        self.assertIn("解锁", gates["G-B0"]["reason"])
        joined = "\n".join(assessment["blocked"])
        self.assertIn("B/C/D", joined)
        self.assertIn("容器", joined)

    def test_containers_require_user_pid_ns_and_cgroup_delegation(self) -> None:
        assessment = assess_profile(_locked())
        self.assertEqual(_gate_map(assessment)["G-B2"]["status"], "fail")
        reason = _gate_map(assessment)["G-B2"]["reason"]
        self.assertIn("user_ns", reason)
        self.assertIn("pid_ns", reason)

        profile = _locked()
        profile["features"]["user_ns"] = True
        profile["features"]["pid_ns"] = True
        profile["features"]["cgroup_v2_delegation"] = None
        self.assertEqual(_gate_map(assess_profile(profile))["G-B2"]["status"], "unknown")

    def test_seven_gates_with_valid_status(self) -> None:
        assessment = assess_profile(_locked())
        ids = [gate["id"] for gate in assessment["gates"]]
        self.assertEqual(
            ids,
            ["G-A", "G-B0", "G-B1", "G-B2", "G-C", "G-D", "G-RISK"],
        )
        for gate in assessment["gates"]:
            self.assertIn(gate["status"], ("pass", "fail", "unknown"))
            self.assertTrue(gate["name"])
            self.assertTrue(gate["reason"])

    def test_output_sections_are_non_empty_lists(self) -> None:
        assessment = assess_profile(_locked())
        for section in (
            "blocked",
            "alternatives",
            "risks",
            "next_steps",
            "assumptions",
            "unknowns",
        ):
            self.assertIsInstance(assessment[section], list)
            self.assertTrue(assessment[section], msg=f"{section} 不应为空")
        self.assertEqual(assessment["profile"]["source_mode"], "documented")

    def test_risks_cover_no_root_and_battery(self) -> None:
        assessment = assess_profile(_locked())
        joined = "\n".join(assessment["risks"])
        self.assertIn("插电", joined)
        self.assertIn("无 Root", joined)


class RouteBTests(unittest.TestCase):
    def test_unlocked_roote_device_recommends_route_b(self) -> None:
        profile = _unlocked()
        profile["root"]["state"] = "magisk"
        profile["root"]["su_available"] = True
        profile["features"]["user_ns"] = True
        profile["features"]["pid_ns"] = True
        profile["features"]["cgroup_v2_delegation"] = True
        assessment = assess_profile(profile)
        self.assertEqual(assessment["route"], "B")
        gates = _gate_map(assessment)
        self.assertEqual(gates["G-B0"]["status"], "pass")
        self.assertEqual(gates["G-B1"]["status"], "pass")
        self.assertEqual(gates["G-B2"]["status"], "pass")
        self.assertFalse(any("容器运行时" in item for item in assessment["blocked"]))
        self.assertTrue(any(item.startswith("A") for item in assessment["alternatives"]))

    def test_open_policy_but_locked_blocks_bcd(self) -> None:
        profile = _unlocked()
        profile["boot"]["bootloader_unlocked"] = False
        profile["boot"]["oem_unlock_policy"] = "open"
        self.assertEqual(_gate_map(assess_profile(profile))["G-B0"]["status"], "fail")

    def test_oem_policy_closed_blocks_even_if_unlocked(self) -> None:
        profile = _unlocked()
        profile["boot"]["oem_unlock_policy"] = "closed"
        self.assertEqual(_gate_map(assess_profile(profile))["G-B0"]["status"], "fail")
        self.assertEqual(assess_profile(profile)["route"], "A")


class RouteCTests(unittest.TestCase):
    def test_unlocked_no_root_with_custom_kernel_recommends_route_c(self) -> None:
        profile = _unlocked()
        profile["features"]["custom_kernel"] = True
        assessment = assess_profile(profile)
        self.assertEqual(assessment["route"], "C")
        gates = _gate_map(assessment)
        self.assertEqual(gates["G-C"]["status"], "pass")
        self.assertEqual(gates["G-B0"]["status"], "pass")
        self.assertTrue(any("变砖" in risk for risk in assessment["risks"]))

    def test_custom_kernel_false_excludes_c(self) -> None:
        profile = _unlocked()
        profile["features"]["custom_kernel"] = False
        self.assertEqual(_gate_map(assess_profile(profile))["G-C"]["status"], "fail")


class RouteDTests(unittest.TestCase):
    def test_native_linux_port_recommends_route_d(self) -> None:
        profile = _unlocked()
        profile["features"]["native_linux_port"] = True
        assessment = assess_profile(profile)
        self.assertEqual(assessment["route"], "D")
        self.assertEqual(_gate_map(assessment)["G-D"]["status"], "pass")
        self.assertTrue(any(item.startswith("B") for item in assessment["alternatives"]))

    def test_no_native_port_excludes_d(self) -> None:
        profile = _unlocked()
        profile["features"]["native_linux_port"] = False
        self.assertEqual(_gate_map(assess_profile(profile))["G-D"]["status"], "fail")


class UnknownAndRiskTests(unittest.TestCase):
    def _empty_profile(self) -> dict:
        profile = _locked()
        for key in ("identity", "boot", "root", "kernel", "hardware", "storage", "crypto"):
            for field in list(profile[key]):
                profile[key][field] = None
        for key in profile["features"]:
            profile["features"][key] = None
        profile["unknowns"] = []
        profile["evidence_refs"] = []
        return profile

    def test_unknown_fields_lower_confidence_and_add_assumptions(self) -> None:
        empty_assessment = assess_profile(self._empty_profile())
        known_assessment = assess_profile(_locked())
        self.assertEqual(empty_assessment["route"], "A")
        self.assertEqual(_gate_map(empty_assessment)["G-B0"]["status"], "unknown")
        self.assertLess(empty_assessment["confidence"], known_assessment["confidence"])
        self.assertTrue(any("未证实" in item for item in empty_assessment["assumptions"]))
        self.assertTrue(empty_assessment["unknowns"])

    def test_play_integrity_requirement_raises_risk(self) -> None:
        profile = _unlocked()
        profile["root"]["state"] = "magisk"
        profile["root"]["su_available"] = True
        profile["crypto"]["play_integrity_required"] = True
        assessment = assess_profile(profile)
        self.assertIn("Play Integrity", "\n".join(assessment["risks"]))
        self.assertEqual(_gate_map(assessment)["G-RISK"]["status"], "unknown")

    def test_play_integrity_false_does_not_raise_risk(self) -> None:
        profile = _locked()
        profile["crypto"]["play_integrity_required"] = False
        assessment = assess_profile(profile)
        self.assertNotIn("Play Integrity", "\n".join(assessment["risks"]))
        self.assertEqual(_gate_map(assessment)["G-RISK"]["status"], "pass")

    def test_human_summary_contains_route_and_sections(self) -> None:
        text = format_assessment_human(assess_profile(_locked()))
        self.assertIn("路线：A", text)
        self.assertIn("门禁", text)
        self.assertIn("下一步", text)
        self.assertNotIn("serial", text.lower())


class HelperTests(unittest.TestCase):
    def test_select_route_is_deterministic_for_unknown_unlock(self) -> None:
        profile = _locked()
        profile["boot"]["bootloader_unlocked"] = None
        profile["boot"]["oem_unlock_policy"] = "unknown"
        gates, status_map = evaluate_gates(profile)
        self.assertEqual(select_route(profile, status_map), "A")

    def test_route_labels_cover_all_ids(self) -> None:
        self.assertEqual(set(ROUTE_LABELS), {"A", "B", "C", "D"})

    def test_capabilities_present_does_not_change_locked_route(self) -> None:
        profile = _locked()
        profile["capabilities"] = {
            capability: {"status": "unknown", "evidence": "fixture"} for capability in CAPABILITY_IDS
        }
        assessment = assess_profile(profile)
        self.assertEqual(assessment["route"], "A")
        self.assertEqual(assessment["profile"]["capabilities_present"], len(CAPABILITY_IDS))


if __name__ == "__main__":
    unittest.main()
