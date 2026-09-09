"""Test the Caddy proxy boundary with a private CA, without disabling TLS checks."""
import json
from pathlib import Path
import re
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
configuration.write_text("localhost, site.localhost {\n tls internal\n reverse_proxy lampplus-https:80\n}\n")


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
        healthy = docker("exec", "lampplus-https", "python3", "/opt/lampplus/health.py", check=False)
        if copied.returncode == 0 and healthy.returncode == 0:
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
    session = requests.Session()
    session.verify = str(certificate)
    page = session.get("https://localhost:8443/login", timeout=10)
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text)[1]
    page = session.post("https://localhost:8443/login", data={"csrf": csrf, "username": "admin", "password": secret_file.read_text()}, timeout=10)
    login_errors = re.findall(r'role="alert">([^<]+)', page.text)
    assert page.status_code == 200 and "New website" in page.text, (
        f"HTTPS sign-in returned HTTP {page.status_code}; alerts: {login_errors}"
    )
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', page.text)[1]
    tool = session.get("https://localhost:8443/phpmyadmin/", timeout=20)
    assert tool.status_code == 200 and 'name="pma_username"' in tool.text
    job = session.post("https://localhost:8443/api/actions/site.create", json={"hostname": "site.localhost", "cms": "empty"},
                       headers={"X-CSRF-Token": csrf}, timeout=20).json()["job"]
    for _ in range(60):
        jobs = session.get("https://localhost:8443/api/overview", timeout=10).json()["jobs"]
        operation = next(entry for entry in jobs if entry["id"] == job)
        if operation["status"] == "failed":
            raise AssertionError(operation["message"])
        if operation["status"] == "complete":
            break
        time.sleep(1)
    else:
        raise AssertionError("HTTPS site provisioning timed out")
    site = operation["result"]["site"]
    probe = f"/srv/sites/{site}/public/scheme.php"
    docker("exec", "lampplus-https", "python3", "-c", f"from pathlib import Path;p=Path({probe!r});p.write_text(\"<?php echo json_encode($_SERVER['HTTPS'] ?? null);\");p.chmod(0o644)")
    secure = subprocess.run(["curl", "--noproxy", "*", "--cacert", str(certificate), "--resolve", "site.localhost:8443:127.0.0.1",
                             "--silent", "--show-error", "--fail", "https://site.localhost:8443/scheme.php"], capture_output=True, text=True, timeout=20, check=True)
    assert json.loads(secure.stdout) == "on", "PHP did not receive the trusted HTTPS scheme"
    forged = docker("exec", "lampplus-https", "curl", "--silent", "--fail", "-H", "Host: site.localhost", "-H", "X-Forwarded-Proto: https", "http://127.0.0.1/scheme.php")
    assert json.loads(forged.stdout) is None, "Untrusted website headers changed PHP's HTTPS state"
    print("Verified HTTPS, redirect, secure cookies and proxy-spoofing checks passed")
finally:
    secret_file.unlink(missing_ok=True)
    docker("rm", "-f", "lampplus-caddy", "lampplus-https", check=False)
    docker("network", "rm", "lampplus-https-test", check=False)
