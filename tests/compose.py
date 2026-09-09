"""Validate the distributed Compose examples without printing expanded secrets."""
import json
import os
from pathlib import Path
import secrets
import subprocess

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / "dependencies.lock.json").read_text())
environment = dict(os.environ, LAMP_ADMIN_HOST="panel.example.test", SITE_HOST="site.example.test",
                   ACME_EMAIL="ci@example.test", LAMP_ADMIN_PASSWORD=secrets.token_urlsafe(30),
                   UBUNTU_IMAGE=lock["ubuntu"], CADDY_IMAGE=lock["caddy"])
for example in ("compose.yaml", "examples/hosting.compose.yaml"):
    subprocess.run(["docker", "compose", "-f", example, "config", "--quiet"], cwd=root,
                   env=environment, check=True, timeout=30)
print("Development and hosting Compose configurations validated")
