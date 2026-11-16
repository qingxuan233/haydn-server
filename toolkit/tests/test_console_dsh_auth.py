"""console dsh_auth 单测：DSH 上游 cookie 铸造（authority 绑定 + 签名）与密钥读取。

为何放在 `toolkit/tests`：`preflight` 的 unittest 步骤只发现本目录；而 `dsh_auth` 是
控制台实现层模块（`2026-11-14/web-console/console/`），故此处按路径加载它，保证
网关鉴权桥接的算法改动能进统一质量门，而不是靠人工设备自测。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

from toolkit.repurpose.util import REPO_ROOT

MODULE_PATH = REPO_ROOT / "2026-11-14" / "web-console" / "console" / "dsh_auth.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("console_dsh_auth", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


dsh_auth = _load_module()

SECRET_BYTES = 32
VALID_SECRET = base64.urlsafe_b64encode(bytes(range(SECRET_BYTES))).decode().rstrip("=")


def _credentials_text(secret_b64url: str = VALID_SECRET) -> str:
    return (
        "version: 1\n"
        "records:\n"
        "  client-connection/browser-session:\n"
        "    kind: grant\n"
        "    payload:\n"
        "      version: 1\n"
        f"      secret: \"{secret_b64url}\"\n"
    )


class ReadSecretTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / ".credentials.yaml"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_reads_browser_session_secret(self) -> None:
        self.path.write_text(_credentials_text(), encoding="utf-8")
        secret = dsh_auth.read_secret(str(self.path))
        self.assertEqual(len(secret), SECRET_BYTES)
        self.assertEqual(secret, bytes(range(SECRET_BYTES)))

    def test_missing_record_raises(self) -> None:
        self.path.write_text('version: 1\nrecords:\n  other/key:\n    kind: grant\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            dsh_auth.read_secret(str(self.path))

    def test_wrong_secret_length_raises(self) -> None:
        short = base64.urlsafe_b64encode(b"0123456789").decode().rstrip("=")
        self.path.write_text(_credentials_text(short), encoding="utf-8")
        with self.assertRaises(ValueError):
            dsh_auth.read_secret(str(self.path))

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(OSError):
            dsh_auth.read_secret(str(Path(self._tmp.name) / "nope.yaml"))


class CookieTests(unittest.TestCase):
    def test_cookie_name_is_authority_scoped(self) -> None:
        name = dsh_auth.cookie_name("qingxuan.bbs0.cc")
        other = dsh_auth.cookie_name("192.168.31.50:18090")
        self.assertTrue(name.startswith(dsh_auth.COOKIE_PREFIX))
        self.assertNotEqual(name, other)
        # 名字必须与 DSH 的算法一致：前缀 + b64url(sha256(authority))
        expected = dsh_auth.COOKIE_PREFIX + base64.urlsafe_b64encode(
            hashlib.sha256(b"qingxuan.bbs0.cc").digest()
        ).decode().rstrip("=")
        self.assertEqual(name, expected)

    def test_mint_structure_and_signature(self) -> None:
        secret = bytes(range(SECRET_BYTES))
        value = dsh_auth.mint(secret, "qingxuan.bbs0.cc", max_age_days=7)
        parts = value.split(".")
        self.assertEqual(len(parts), 3, value)
        self.assertEqual(parts[0], "v1")
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        self.assertEqual(payload["authority"], "qingxuan.bbs0.cc")
        self.assertEqual(payload["expiresAt"] - payload["issuedAt"], 7 * 86_400_000)
        expected_sig = hmac.new(secret, parts[1].encode("ascii"), hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
        self.assertEqual(actual_sig, expected_sig)

    def test_merge_cookie_header_drops_old_dsh_and_keeps_others(self) -> None:
        old = f"{dsh_auth.COOKIE_PREFIX}abc=stale; theme=dark"
        merged = dsh_auth.DshCookieMinter.merge_cookie_header(old, "dsh-auth-x=fresh")
        self.assertNotIn("stale", merged)
        self.assertIn("theme=dark", merged)
        self.assertTrue(merged.endswith("dsh-auth-x=fresh"))

    def test_merge_cookie_header_with_empty_existing(self) -> None:
        self.assertEqual(dsh_auth.DshCookieMinter.merge_cookie_header("", "a=b"), "a=b")


class MinterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / ".credentials.yaml"
        self.path.write_text(_credentials_text(), encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_cookie_pair_round_trip(self) -> None:
        minter = dsh_auth.DshCookieMinter(str(self.path), 30)
        pair = minter.cookie_pair("qingxuan.bbs0.cc")
        name, _, value = pair.partition("=")
        self.assertEqual(name, dsh_auth.cookie_name("qingxuan.bbs0.cc"))
        self.assertTrue(value.startswith("v1."))

    def test_missing_authority_raises(self) -> None:
        minter = dsh_auth.DshCookieMinter(str(self.path), 30)
        with self.assertRaises(ValueError):
            minter.cookie_pair("")

    def test_secret_cache_reloads_on_change(self) -> None:
        minter = dsh_auth.DshCookieMinter(str(self.path), 30)
        self.assertIsNotNone(minter.cookie_pair("a.example"))
        os.utime(self.path, (1234567890, 1234567890))
        self.path.write_text(
            _credentials_text(base64.urlsafe_b64encode(b"\x01" * SECRET_BYTES).decode().rstrip("=")),
            encoding="utf-8",
        )
        # 改动后必须重新读取密钥（否则旧 cookie 会一直有效/失效不可控）
        self.assertIsNotNone(minter.cookie_pair("a.example"))
        self.assertEqual(len(minter._load()), SECRET_BYTES)  # noqa: SLF001 - 单测直接检查缓存状态

    def test_credentials_path_reported_when_unreadable(self) -> None:
        minter = dsh_auth.DshCookieMinter(str(Path(self._tmp.name) / "missing.yaml"), 30)
        with self.assertRaises(ValueError) as ctx:
            minter.cookie_pair("a.example")
        self.assertIn("凭据", str(ctx.exception))

    def test_real_repo_credentials_have_no_secret_leak_in_repo(self) -> None:
        """仓库内不得出现 DSH 凭据文件（凭据只在设备上）。"""
        repo_credentials = list(REPO_ROOT.glob("**/.dsh/.credentials.yaml"))
        self.assertEqual(repo_credentials, [])


if __name__ == "__main__":
    unittest.main()
