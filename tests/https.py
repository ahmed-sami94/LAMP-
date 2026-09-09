"""Test the Caddy proxy boundary with a private CA, without disabling TLS checks."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "artifacts/https"
WORK.mkdir(parents=True, exist_ok=True)
secret_file = WORK / "admin-password"
secret_file.write_text(secrets.token_urlsafe(32))
secret_file.chmod(0o600)
configuration = WORK / "Caddyfile"
configuration.write_text("localhost {\n tls internal\n reverse_proxy lampplus-https:80\n}\n")


def docker(*args, check=True):
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check, timeout=120)


try:
    docker("network", "create", "--subnet", "172.30.50.0/24", "lampplus-https-test")
    docker("run", "-d", "--name", "lampplus-https", "--network", "lampplus-https-test", "--ip", "172.30.50.3",
           "-e", "LAMP_ADMIN_HOST=localhost", "-e", "LAMP_MODE=hosting", "-e", "LAMP_TRUSTED_PROXIES=172.30.50.2/32",
           "-e", "LAMP_ADMIN_PASSWORD_FILE=/run/secrets/admin-password",
           "-v", str(secret_file) + ":/run/secrets/admin-password:ro", "lampplus:test")
    caddy = json.loads((ROOT / "dependencies.lock.json").read_text())["caddy"]
    docker("run", "-d", "--name", "lampplus-caddy", "--network", "lampplus-https-test", "--ip", "172.30.50.2",
           "-p", "127.0.0.1:8443:443", "-p", "127.0.0.1:8082:80", "-v", str(configuration) + ":/etc/caddy/Caddyfile:ro", caddy)
    certificate = WORK / "root.crt"
    for _ in range(60):
        copied = docker("cp", "lampplus-caddy:/data/caddy/pki/authorities/local/root.crt", str(certificate), check=False)
        if copied.returncode == 0:
            try:
                response = requests.get("https://localhost:8443/login", verify=str(certificate), timeout=5)
                if response.status_code == 200:
                    break
            except requests.RequestException:
                pass
        time.sleep(2)
    else:
        raise AssertionError("Verified HTTPS did not become ready")
    assert "Secure" in response.headers["Set-Cookie"]
    assert "max-age=" in response.headers["Strict-Transport-Security"]
    redirect = requests.get("http://localhost:8082/login", allow_redirects=False, timeout=10)
    assert redirect.status_code == 308 and redirect.headers["Location"].startswith("https://localhost/")
    direct = docker("exec", "lampplus-https", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    "-H", "Host: localhost", "-H", "X-Forwarded-Proto: https", "-H", "X-Lamp-Client: 172.30.50.2", "http://127.0.0.1/login")
    assert direct.stdout == "400", "Untrusted direct access must not become trusted through forged headers"
    print("Verified HTTPS, redirect, secure cookies and proxy-spoofing checks passed")
finally:
    secret_file.unlink(missing_ok=True)
    docker("rm", "-f", "lampplus-caddy", "lampplus-https", check=False)
    docker("network", "rm", "lampplus-https-test", check=False)
