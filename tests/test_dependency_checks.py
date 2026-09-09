import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "tools/resolve-lock.py"
spec = importlib.util.spec_from_file_location("dependency_lock", path)
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ChecksumTests(unittest.TestCase):
    def test_matching_download_is_pinned(self):
        payload = b"Verified test artifact"
        expected = hashlib.sha256(payload).hexdigest()
        with patch.object(resolver, "read", return_value=payload):
            for supplied in (expected, "sha256:" + expected, None):
                with self.subTest(supplied=supplied):
                    self.assertEqual(resolver.artifact("https://example.test/tool", supplied)["sha256"], expected)

    def test_modified_download_is_rejected(self):
        with patch.object(resolver, "read", return_value=b"Modified artifact"):
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                resolver.artifact("https://example.test/tool", "0" * 64)

    def test_invalid_upstream_digest_is_rejected(self):
        for supplied in ("sha256:invalid", "g" * 64, "sha512:" + "0" * 64):
            with self.subTest(supplied=supplied), self.assertRaisesRegex(RuntimeError, "Invalid upstream SHA256"):
                resolver.artifact("https://example.test/tool", supplied)
