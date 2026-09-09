"""Refresh phpMyAdmin's production dependency lock, retaining its upstream ranges."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "config/phpmyadmin"
DEST.mkdir(parents=True, exist_ok=True)
lock = json.loads((ROOT / "dependencies.lock.json").read_text())
version = lock["versions"]["phpmyadmin"].replace(".", "_")
with urllib.request.urlopen(f"https://raw.githubusercontent.com/phpmyadmin/phpmyadmin/RELEASE_{version}/composer.json", timeout=30) as response:
    manifest = json.load(response)
manifest.pop("require-dev", None)
manifest.pop("autoload-dev", None)
manifest.pop("scripts", None)
manifest.pop("repositories", None)
manifest["config"] = {"platform": {"php": "8.5.0"}, "allow-plugins": False, "sort-packages": True}
(DEST / "composer.json").write_text(json.dumps(manifest, indent=2) + "\n")
artifact = ROOT / "artifacts"
artifact.mkdir(exist_ok=True)
composer = artifact / "composer.phar"
with urllib.request.urlopen(lock["artifacts"]["composer"]["url"], timeout=120) as response:
    content = response.read()
if hashlib.sha256(content).hexdigest() != lock["artifacts"]["composer"]["sha256"]:
    raise ValueError("Composer checksum mismatch")
composer.write_bytes(content)
php = [sys.argv[1]]
if os.name == "nt":
    php.extend(["-d", "extension_dir=" + str(Path(sys.argv[1]).parent / "ext"), "-d", "extension=openssl"])
environment = dict(os.environ, COMPOSER_HOME=str(artifact / "composer-home"))
subprocess.run([*php, str(composer), "update", "--no-install", "--no-dev", "--no-scripts", "--no-plugins",
                "--ignore-platform-req=ext-*", "--no-interaction"], cwd=DEST, env=environment, check=True)
print("Review config/phpmyadmin/composer.lock before committing.")
