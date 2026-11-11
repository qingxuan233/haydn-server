"""plan 生成测试：P0–P6、A/B 阶段差异、auto 路线、json/md 输出。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from toolkit.repurpose.assess import assess_profile
from toolkit.repurpose.plan import STAGE_IDS, build_plan, format_plan_markdown
from toolkit.repurpose.util import SCHEMA_PLAN, UsageError
MARKER_PLACEHOLDER = "TO" + "DO"  # 避免源码出现待办标记字面量

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LOCKED_PROFILE = FIXTURES / "profile-haydn-locked.json"


def _locked() -> dict:
    return json.loads(LOCKED_PROFILE.read_text(encoding="utf-8"))


def _unlocked_rooted() -> dict:
    profile = _locked()
    profile["boot"]["bootloader_unlocked"] = True
    profile["boot"]["oem_unlock_policy"] = "open"
    profile["root"]["state"] = "magisk"
    profile["root"]["su_available"] = True
    profile["features"]["user_ns"] = True
    profile["features"]["pid_ns"] = True
    profile["features"]["cgroup_v2_delegation"] = True
    profile["features"]["native_linux_port"] = False
    profile["features"]["custom_kernel"] = False
    return profile


class PlanStructureTests(unittest.TestCase):
    def test_plan_has_p0_to_p6(self) -> None:
        plan = build_plan(_locked(), "auto")
        self.assertEqual(plan["schema"], SCHEMA_PLAN)
        self.assertEqual([stage["id"] for stage in plan["stages"]], list(STAGE_IDS))
        self.assertEqual(plan["route"], "A")
        self.assertEqual(plan["route_label"], assess_profile(_locked())["route_label"])

    def test_every_stage_has_required_fields(self) -> None:
        plan = build_plan(_locked(), "auto")
        for stage in plan["stages"]:
            for key in ("id", "title", "objective", "actions", "gate", "exit_criteria", "rollback"):
                self.assertIn(key, stage)
            self.assertTrue(stage["actions"])
            self.assertTrue(stage["deliverables"])
            self.assertTrue(stage["gate"])
            self.assertTrue(stage["exit_criteria"])
            self.assertTrue(stage["rollback"])

    def test_auto_route_uses_assess(self) -> None:
        self.assertEqual(build_plan(_locked(), "auto")["route"], "A")
        self.assertEqual(build_plan(_unlocked_rooted(), "auto")["route"], "B")

    def test_plan_profile_summary(self) -> None:
        plan = build_plan(_locked(), "auto")
        self.assertEqual(plan["profile"]["source_mode"], "documented")
        self.assertTrue(plan["profile"]["unknowns"])


class PlanRouteDifferenceTests(unittest.TestCase):
    def test_a_and_b_p2_actions_differ(self) -> None:
        plan_a = build_plan(_locked(), "A")
        plan_b = build_plan(_unlocked_rooted(), "B")
        stage_a = next(stage for stage in plan_a["stages"] if stage["id"] == "P2")
        stage_b = next(stage for stage in plan_b["stages"] if stage["id"] == "P2")
        self.assertNotEqual(stage_a["actions"], stage_b["actions"])
        self.assertIn("proot", " ".join(stage_a["actions"]).lower())
        self.assertIn("Magisk", " ".join(stage_b["actions"]))
        self.assertNotEqual(stage_a["title"], stage_b["title"])

    def test_route_c_and_d_have_distinct_stages(self) -> None:
        profile_c = _locked()
        profile_c["boot"]["bootloader_unlocked"] = True
        profile_c["boot"]["oem_unlock_policy"] = "open"
        profile_c["root"]["state"] = "none"
        profile_c["root"]["su_available"] = False
        profile_c["features"]["custom_kernel"] = True
        profile_c["features"]["native_linux_port"] = False
        plan_c = build_plan(profile_c, "C")
        self.assertEqual(plan_c["route"], "C")
        self.assertIn("内核", " ".join(
            stage["title"] + stage["objective"] for stage in plan_c["stages"] if stage["id"] == "P2"
        ))

        profile_d = dict(profile_c)
        profile_d["features"] = dict(profile_c["features"])
        profile_d["features"]["native_linux_port"] = True
        plan_d = build_plan(profile_d, "auto")
        self.assertEqual(plan_d["route"], "D")
        self.assertIn("原生", " ".join(
            stage["title"] + stage["objective"] for stage in plan_d["stages"] if stage["id"] == "P2"
        ))

    def test_explicit_route_different_from_assessment_adds_warning(self) -> None:
        plan = build_plan(_locked(), "B")
        self.assertEqual(plan["route"], "B")
        self.assertTrue(plan["warnings"])
        self.assertTrue(any("Bootloader" in warning for warning in plan["warnings"]))

    def test_invalid_route_raises_usage_error(self) -> None:
        with self.assertRaises(UsageError):
            build_plan(_locked(), "Z")


class PlanMarkdownTests(unittest.TestCase):
    def test_markdown_contains_all_stage_sections(self) -> None:
        markdown = format_plan_markdown(build_plan(_locked(), "auto"))
        self.assertIn("# 改造计划（路线 A）", markdown)
        for stage_id in STAGE_IDS:
            self.assertIn(f"## {stage_id}", markdown)
        for label in ("**目标**", "**动作**", "**交付物**", "**门禁**", "**退出标准**", "**回滚**"):
            self.assertIn(label, markdown)
        self.assertNotIn(MARKER_PLACEHOLDER, markdown)

    def test_markdown_for_b_differs_from_a(self) -> None:
        markdown_a = format_plan_markdown(build_plan(_locked(), "A"))
        markdown_b = format_plan_markdown(build_plan(_unlocked_rooted(), "B"))
        self.assertNotEqual(markdown_a, markdown_b)
        self.assertIn("解锁", markdown_b)
        self.assertIn("Termux", markdown_a)

    def test_markdown_does_not_leak_serial(self) -> None:
        markdown = format_plan_markdown(build_plan(_locked(), "auto"))
        self.assertNotIn("TEST00000001", markdown)


if __name__ == "__main__":
    unittest.main()
