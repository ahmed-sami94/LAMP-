import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

EXTRACT = Path(__file__).resolve().parents[1] / "runtime/extract.py"


class ArchiveTests(unittest.TestCase):
    def extract(self, members, occupied=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "public"
            destination.mkdir()
            if occupied:
                (destination / "index.php").write_text("Existing")
            archive = root / "package.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                for name, kind, content in members:
                    item = tarfile.TarInfo(name)
                    item.type = kind
                    item.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
                    item.size = len(content)
                    if kind == tarfile.SYMTYPE:
                        item.linkname = "../outside"
                    stream.addfile(item, io.BytesIO(content))
            result = subprocess.run([sys.executable, str(EXTRACT), str(archive), str(destination), "wordpress"],
                                    capture_output=True, timeout=20)
            files = {str(p.relative_to(destination)): p.read_text() for p in destination.rglob("*") if p.is_file()}
            self.assertFalse((root / "outside").exists())
            return result.returncode, files

    def test_wordpress_top_directory_without_trailing_slash(self):
        code, files = self.extract([("wordpress", tarfile.DIRTYPE, b""),
                                    ("wordpress/index.php", tarfile.REGTYPE, b"Ready")])
        self.assertEqual(code, 0)
        self.assertEqual(files, {"index.php": "Ready"})

    def test_existing_destination_is_preserved(self):
        code, files = self.extract([("wordpress/index.php", tarfile.REGTYPE, b"New")], occupied=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(files, {"index.php": "Existing"})

    def test_traversal_is_refused(self):
        code, _ = self.extract([("wordpress/../outside", tarfile.REGTYPE, b"Invalid")])
        self.assertNotEqual(code, 0)

    def test_symlink_is_refused(self):
        code, _ = self.extract([("wordpress/link", tarfile.SYMTYPE, b"")])
        self.assertNotEqual(code, 0)
