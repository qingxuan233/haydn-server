"""profile 结构校验、模板生成、模板/schema 一致性测试（BL-009 最小版）。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from toolkit.repurpose.frontmatter import parse_file
MARKER_PLACEHOLDER = "TO" + "DO"  # 避免源码出现待办标记字面量
from toolkit.repurpose.profile import (
    CAPABILITY_IDS,
    PROFILE_TOP_KEYS,
    build_new_profile,
    load_and_validate,
    load_profile,
    load_template_profile,
    validate_profile,
)
from toolkit.repurpose.util import (
    SCHEMA_PROFILE,
    TEMPLATES_DIR,
    SCHEMA_DIR,
    UsageError,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LOCKED_PROFILE = FIXTURES / "profile-haydn-locked.json"


def _locked() -> dict:
    return json.loads(LOCKED_PROFILE.read_text(encoding="utf-8"))


class FixtureProfileTests(unittest.TestCase):
    def test_fixture_profile_validates(self) -> None:
        profile = _locked()
        self.assertEqual(validate_profile(profile), [])
        self.assertEqual(profile["schema"], SCHEMA_PROFILE)
        self.assertIsNone(profile["identity"]["serial"])
        self.assertTrue(profile["identity"]["serial_redacted"])

    def test_load_and_validate_returns_dict(self) -> None:
        profile = load_and_validate(str(LOCKED_PROFILE))
        self.assertEqual(profile["identity"]["codename"], "haydn")

    def test_load_profile_rejects_broken_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(UsageError):
                load_profile(path)

    def test_template_profile_validates(self) -> None:
        template = load_template_profile()
        self.assertEqual(validate_profile(template), [])


class ValidationErrorTests(unittest.TestCase):
    def test_wrong_schema(self) -> None:
        profile = _locked()
        profile["schema"] = "other.schema"
        errors = validate_profile(profile)
        self.assertTrue(any("schema" in error for error in errors))

    def test_missing_top_level_key(self) -> None:
        profile = _locked()
        del profile["features"]
        errors = validate_profile(profile)
        self.assertTrue(any("features" in error for error in errors))

    def test_top_keys_constant_matches_profile(self) -> None:
        profile = _locked()
        for key in PROFILE_TOP_KEYS:
            self.assertIn(key, profile)

    def test_wrong_feature_type(self) -> None:
        profile = _locked()
        profile["features"]["user_ns"] = "false"
        errors = validate_profile(profile)
        self.assertTrue(any("features.user_ns" in error for error in errors))

    def test_bad_source_mode(self) -> None:
        profile = _locked()
        profile["source"]["mode"] = "imaginary"
        errors = validate_profile(profile)
        self.assertTrue(any("source.mode" in error for error in errors))

    def test_bad_generated_at(self) -> None:
        profile = _locked()
        profile["generated_at"] = "昨天"
        errors = validate_profile(profile)
        self.assertTrue(any("generated_at" in error for error in errors))

    def test_bad_boot_policy(self) -> None:
        profile = _locked()
        profile["boot"]["oem_unlock_policy"] = "maybe"
        self.assertTrue(any("oem_unlock_policy" in error for error in validate_profile(profile)))

    def test_bad_root_state(self) -> None:
        profile = _locked()
        profile["root"]["state"] = "rooted-please"
        self.assertTrue(any("root.state" in error for error in validate_profile(profile)))

    def test_capabilities_structure(self) -> None:
        profile = _locked()
        profile["capabilities"] = {"proot": {"status": "pass", "evidence": "ok"}}
        self.assertEqual(validate_profile(profile), [])
        profile["capabilities"] = {"proot": {"status": "maybe", "evidence": "x"}}
        self.assertTrue(any("status" in error for error in validate_profile(profile)))
        profile["capabilities"] = {"not-a-capability": {"status": "pass", "evidence": "x"}}
        self.assertTrue(any("未定义的项" in error for error in validate_profile(profile)))

    def test_capability_ids_are_twelve(self) -> None:
        self.assertEqual(len(CAPABILITY_IDS), 12)
        self.assertEqual(len(set(CAPABILITY_IDS)), 12)


class NewProfileTests(unittest.TestCase):
    def test_build_new_profile_is_editable_skeleton(self) -> None:
        profile = build_new_profile("demo-device")
        self.assertEqual(validate_profile(profile), [])
        self.assertEqual(profile["identity"]["codename"], "demo-device")
        self.assertEqual(profile["source"]["mode"], "manual")
        self.assertIsNone(profile["identity"]["serial"])
        self.assertTrue(profile["unknowns"])
        self.assertTrue(profile["warnings"])
        self.assertEqual(profile["boot"]["bootloader_unlocked"], None)
        self.assertEqual(profile["boot"]["oem_unlock_policy"], "unknown")
        self.assertEqual(profile["root"]["state"], "unknown")
        self.assertEqual(len(profile["capabilities"]), 12)
        for capability in profile["capabilities"].values():
            self.assertEqual(capability["status"], "unknown")

    def test_new_profile_requires_codename(self) -> None:
        with self.assertRaises(UsageError):
            build_new_profile("   ")

    def test_new_profile_written_to_file(self) -> None:
        profile = build_new_profile("demo")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
            loaded = load_and_validate(str(path))
            self.assertEqual(loaded["identity"]["codename"], "demo")


class TemplateSchemaConsistencyTests(unittest.TestCase):
    """模板与 schema 一致性（BL-009 最小版）：防止模板/字段漂移。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_schema = json.loads(
            (SCHEMA_DIR / "device-profile.schema.json").read_text(encoding="utf-8")
        )
        cls.manifest_schema = json.loads(
            (SCHEMA_DIR / "agent-manifest.schema.json").read_text(encoding="utf-8")
        )
        cls.frontmatter_schema = json.loads(
            (SCHEMA_DIR / "frontmatter.schema.json").read_text(encoding="utf-8")
        )

    def test_schema_files_are_valid_json_objects(self) -> None:
        for schema in (self.profile_schema, self.manifest_schema, self.frontmatter_schema):
            self.assertIsInstance(schema, dict)
            self.assertIn("$schema", schema)

    def test_frontmatter_schema_required_matches_contract(self) -> None:
        expected = ["id", "title", "type", "status", "audience", "tags", "updated", "agent_hint"]
        self.assertEqual(self.frontmatter_schema["required"], expected)

    def test_device_profile_template_conforms_to_schema_keys(self) -> None:
        template = load_template_profile()
        schema_props = self.profile_schema["properties"]
        for key in PROFILE_TOP_KEYS:
            self.assertIn(key, template)
            self.assertIn(key, schema_props, msg=f"schema 缺少顶层属性 {key}")

    def test_manifest_schema_entry_has_retrieval_fields(self) -> None:
        entry_props = self.manifest_schema["definitions"]["entry"]["properties"]
        for key in ("id", "title", "type", "status", "tags", "path", "severity", "domain"):
            self.assertIn(key, entry_props)

    def test_markdown_templates_use_valid_frontmatter_values(self) -> None:
        type_enum = self.frontmatter_schema["properties"]["type"]["enum"]
        severity_pattern = self.frontmatter_schema["properties"]["severity"]["pattern"]
        for template in sorted(TEMPLATES_DIR.glob("*.md")):
            with self.subTest(template=template.name):
                data, errors, _body = parse_file(template)
                self.assertEqual(errors, [])
                self.assertIn(data["type"], type_enum)
                if "severity" in data:
                    import re

                    self.assertRegex(str(data["severity"]), severity_pattern)
                if data["type"] == "guardrail":
                    self.assertIn(data["severity"], ("blocker", "warning"))
                    self.assertIn(data["scope"], ("device", "server", "agent", "repo"))
                if data["type"] == "pitfall":
                    self.assertIn(data["severity"], ("S1", "S2", "S3", "S4"))
                    self.assertIn(
                        data["domain"],
                        ("device", "boot", "server", "bridge", "security", "ops", "docs"),
                    )

    def test_templates_have_no_todo_or_placeholder_links(self) -> None:
        for template in sorted(TEMPLATES_DIR.glob("*.md")):
            text = template.read_text(encoding="utf-8")
            self.assertNotIn(MARKER_PLACEHOLDER, text, msg=f"{template.name} 不应包含待办占位")
            # 模板不允许出现真实 Markdown 链接（避免路径断链）；路径只应出现在代码块/纯文本。
            self.assertNotIn("](", text, msg=f"{template.name} 不应包含 Markdown 链接")


if __name__ == "__main__":
    unittest.main()
