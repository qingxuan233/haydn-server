"""rescue-kit 测试：清单生成、校验、路径脱敏与 CLI 退出码。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from toolkit.repurpose.cli import main
from toolkit.repurpose.rescuekit import (
    MANIFEST_NAME,
    build_manifest,
    verify_manifest,
    write_manifest,
)
from toolkit.repurpose.util import SCHEMA_RESCUE_KIT, SCHEMA_RESCUE_KIT_VERIFY, UsageError


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "rescue"
        self.root.mkdir()
        (self.root / "boot.img").write_bytes(b"boot-image")
        (self.root / "OFP.zip").write_bytes(b"full-package")
        (self.root / "README.txt").write_text("救援包说明", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_build_manifest_uses_relative_paths_and_sha256(self) -> None:
        manifest = build_manifest(self.root, notes="fixture")
        self.assertEqual(manifest["schema"], SCHEMA_RESCUE_KIT)
        self.assertEqual(manifest["algorithm"], "sha256")
        self.assertEqual(sorted(item["path"] for item in manifest["files"]), ["OFP.zip", "README.txt", "boot.img"])
        for item in manifest["files"]:
            self.assertFalse(Path(item["path"]).is_absolute())
            self.assertEqual(len(item["sha256"]), 64)
            self.assertGreaterEqual(item["size"], 1)

    def test_write_then_verify_ok(self) -> None:
        target, _ = write_manifest(self.root)
        self.assertEqual(target.name, MANIFEST_NAME)
        report = verify_manifest(self.root)
        self.assertEqual(report["schema"], SCHEMA_RESCUE_KIT_VERIFY)
        self.assertTrue(report["ok"])
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["extra"], [])
        self.assertEqual(report["changed"], [])

    def test_write_manifest_refuses_overwrite_without_force(self) -> None:
        write_manifest(self.root, notes="first")
        with self.assertRaises(UsageError):
            write_manifest(self.root)
        _, manifest = write_manifest(self.root, force=True, notes="second")
        self.assertEqual(manifest["notes"], "second")

    def test_verify_detects_change_and_missing(self) -> None:
        write_manifest(self.root)
        (self.root / "boot.img").write_bytes(b"modified")
        report = verify_manifest(self.root)
        self.assertFalse(report["ok"])
        self.assertEqual([item["path"] for item in report["changed"]], ["boot.img"])

        (self.root / "OFP.zip").unlink()
        report = verify_manifest(self.root)
        self.assertFalse(report["ok"])
        self.assertEqual(report["missing"], ["OFP.zip"])

    def test_verify_detects_extra_file(self) -> None:
        write_manifest(self.root)
        (self.root / "extra.img").write_bytes(b"unexpected")
        report = verify_manifest(self.root)
        self.assertFalse(report["ok"])
        self.assertEqual(report["extra"], ["extra.img"])

    def test_manifest_does_not_include_itself(self) -> None:
        write_manifest(self.root)
        manifest = build_manifest(self.root)
        self.assertNotIn(MANIFEST_NAME, [item["path"] for item in manifest["files"]])

    def test_empty_dir_is_usage_error(self) -> None:
        empty = Path(self._tmp.name) / "empty"
        empty.mkdir()
        with self.assertRaises(UsageError):
            build_manifest(empty)

    def test_verify_without_manifest_is_usage_error(self) -> None:
        with self.assertRaises(UsageError):
            verify_manifest(self.root)


class CliTests(unittest.TestCase):
    def test_cli_init_then_verify_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp) / "kit"
            kit.mkdir()
            (kit / "boot.img").write_bytes(b"boot")
            self.assertEqual(main(["rescue-kit", "--dir", str(kit), "--init", "--json"]), 0)
            self.assertTrue((kit / MANIFEST_NAME).is_file())
            report_stdout = main(["rescue-kit", "--dir", str(kit), "--verify", "--json"])
            self.assertEqual(report_stdout, 0)

    def test_cli_verify_mismatch_returns_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp) / "kit"
            kit.mkdir()
            (kit / "boot.img").write_bytes(b"boot")
            main(["rescue-kit", "--dir", str(kit), "--init", "--json"])
            (kit / "boot.img").write_bytes(b"modified")
            self.assertEqual(main(["rescue-kit", "--dir", str(kit), "--verify", "--json"]), 4)

    def test_cli_init_without_force_refuses_overwrite_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp) / "kit"
            kit.mkdir()
            (kit / "boot.img").write_bytes(b"boot")
            self.assertEqual(main(["rescue-kit", "--dir", str(kit), "--init", "--json"]), 0)
            self.assertEqual(main(["rescue-kit", "--dir", str(kit), "--init", "--json"]), 2)
            self.assertEqual(main(["rescue-kit", "--dir", str(kit), "--init", "--force", "--json"]), 0)

    def test_cli_requires_one_of_init_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["rescue-kit", "--dir", tmp]), 2)

    def test_cli_verify_missing_manifest_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["rescue-kit", "--dir", tmp, "--verify"]), 2)


if __name__ == "__main__":
    unittest.main()
