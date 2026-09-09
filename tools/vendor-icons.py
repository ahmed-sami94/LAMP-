"""Vendor only the dashboard's icons from the verified official Lucide package."""
import base64
import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request

VERSION = "1.43.0"
INTEGRITY = "w7vdVFqh4vv7RxWHN4sSeylA0s3GHV5vpyGqZI0q22MINKJyhMNWSMd90RyTUYWBRNYqdZVZzrMmijVxU3Cl9A=="
ROOT = Path(__file__).resolve().parents[1]
with urllib.request.urlopen(f"https://registry.npmjs.org/lucide-static/-/lucide-static-{VERSION}.tgz", timeout=120) as response:
    package = response.read()
if base64.b64encode(hashlib.sha512(package).digest()).decode() != INTEGRITY:
    raise SystemExit("Lucide package integrity mismatch")
destination = ROOT / "panel/static/icons"
destination.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(package)) as archive:
    for name in ("globe", "activity", "archive", "history", "plus", "x", "settings", "external-link", "log-out"):
        (destination / (name + ".svg")).write_bytes(archive.extractfile("package/icons/" + name + ".svg").read())
    (destination / "LICENSE").write_bytes(archive.extractfile("package/LICENSE").read())
print("Vendored Lucide", VERSION)
