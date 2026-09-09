"""Live container tests. Secrets are generated in memory and never printed."""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import requests

IMAGE = os.environ.get("TEST_IMAGE", "lampplus:test")
NAME = "lampplus-test"
PASSWORD = secrets.token_urlsafe(30)
BASE = "http://localhost:8080"


class BoundedSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", 20)
        return super().request(*args, **kwargs)


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, check=check, timeout=180)
    return result.stdout + (result.stderr if args[0] == "logs" else "")


def ready():
    for _ in range(150):
        state = json.loads(docker("inspect", NAME))[0]
        if state["State"].get("Health", {}).get("Status") == "healthy":
            return
        if not state["State"]["Running"]:
            raise AssertionError("Container stopped before readiness")
        if _ > 15:
            services = docker("exec", NAME, "supervisorctl", "status", check=False)
            if "FATAL" in services:
                raise AssertionError("Service failed startup: " + services)
        time.sleep(2)
    raise AssertionError("Health check did not pass in five minutes")


def login():
    session = BoundedSession()
    page = session.get(BASE + "/login")
    assert page.status_code == 200
    token = re.search(r'name="csrf" value="([^"]+)"', page.text)[1]
    response = session.post(BASE + "/login", data={"csrf": token, "username": "admin", "password": PASSWORD})
    assert response.status_code == 200 and "New website" in response.text
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', response.text)[1]
    return session, csrf


def perform(session, csrf, action, data, expect="complete"):
    print("Testing operation:", action, data.get("hostname", data.get("site", "")), flush=True)
    response = session.post(BASE + "/api/actions/" + action, json=data, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 202, response.status_code
    key = response.json()["job"]
    for _ in range(180):
        info = session.get(BASE + "/api/overview").json()
        job = next(x for x in info["jobs"] if x["id"] == key)
        if job["status"] in ("complete", "failed"):
            assert job["status"] == expect, job["message"]
            return job.get("result", {})
        time.sleep(2)
    raise AssertionError("Provisioning timed out")


def main():
    result = subprocess.run(["docker", "run", "--rm", IMAGE], capture_output=True, timeout=30)
    assert result.returncode != 0, "Missing secrets must fail"
    environment = dict(os.environ, LAMP_ADMIN_PASSWORD=PASSWORD)
    subprocess.run(["docker", "run", "-d", "--name", NAME, "-e", "LAMP_ADMIN_PASSWORD", "-p", "127.0.0.1:8080:80",
                    "-v", "lampplus-test-sites:/srv/sites", "-v", "lampplus-test-db:/var/lib/mysql", "-v", "lampplus-test-state:/var/lib/lampplus",
                    "-v", "lampplus-test-backups:/var/backups/lampplus", IMAGE], env=environment, check=True, capture_output=True)
    ready()
    assert requests.get(BASE + "/api/overview", timeout=20).status_code == 401
    assert requests.get(BASE + "/", headers={"Host": "unknown.localhost"}, timeout=20).status_code == 403
    session, csrf = login()
    assert session.post(BASE + "/api/actions/site.create", json={}).status_code == 403
    first = perform(session, csrf, "site.create", {"hostname": "studio.localhost", "title": "Studio", "cms": "empty"})["site"]
    second = perform(session, csrf, "site.create", {"hostname": "journal.localhost", "title": "Journal", "cms": "empty"})["site"]
    for host in ("studio.localhost", "journal.localhost"):
        response = requests.get(BASE, headers={"Host": host}, timeout=20)
        assert response.status_code == 200 and "Website ready" in response.text
    perform(session, csrf, "site.create", {"hostname": "studio.localhost"}, expect="failed")
    perform(session, csrf, "site.create", {"hostname": "../bad"}, expect="failed")
    perform(session, csrf, "php.update", {"site": first, "memory": 320, "upload": 24, "timeout": 60})
    docker("cp", "tests/container_security.py", NAME + ":/run/container_security.py")
    docker("exec", NAME, "python3", "/run/container_security.py")
    snapshot = perform(session, csrf, "backup.create", {"site": first})["backup"]
    assert snapshot
    docker("exec", NAME, "python3", "-c", f"from pathlib import Path; Path('/srv/sites/{first}/public/index.html').write_text('Changed')")
    perform(session, csrf, "backup.restore", {"site": first, "backup": snapshot, "confirm": "wrong.localhost"}, expect="failed")
    perform(session, csrf, "backup.restore", {"site": first, "backup": snapshot, "confirm": "studio.localhost"})
    assert "Website ready" in requests.get(BASE, headers={"Host": "studio.localhost"}, timeout=20).text
    docker("restart", NAME)
    ready()
    session, csrf = login()
    info = session.get(BASE + "/api/overview").json()
    assert len(info["sites"]) == 2
    assert next(s for s in info["sites"] if s["id"] == first)["php"]["memory"] == 320
    assert len(info["backups"]) == 2
    for tool in ("/phpmyadmin/", "/filebrowser/"):
        response = session.get(BASE + tool)
        assert response.status_code == 200, (tool, response.status_code)
        assert requests.get(BASE + tool, allow_redirects=False, timeout=20).status_code == 302
    for host in ("studio.localhost", "journal.localhost"):
        assert requests.get(BASE + "/.env", headers={"Host": host}, timeout=20).status_code == 403
    # Install pinned CMS packages, with distinct administrator credentials.
    for cms in ("wordpress", "joomla"):
        perform(session, csrf, "site.create", {"hostname": cms + ".localhost", "title": cms.title(), "cms": cms,
            "username": "site-owner", "email": "owner@example.test", "password": secrets.token_urlsafe(30)})
    docker("exec", NAME, "python3", "-c", "import pathlib; print(pathlib.Path('/opt/lampplus/packages.txt').read_text())")
    Path("artifacts").mkdir(exist_ok=True)
    docker("cp", NAME + ":/opt/lampplus/packages.txt", "artifacts/packages.txt")
    # Screenshots can authenticate with a private temporary file, removed by CI.
    Path("artifacts/browser-secret").write_text(PASSWORD)
    os.chmod("artifacts/browser-secret", 0o600)
    print("Live startup, routing, persistence, security and CMS checks passed")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        Path("artifacts").mkdir(exist_ok=True)
        # Service diagnostics only. Avoid environment inspection or credential files.
        Path("artifacts/container.log").write_text(docker("logs", NAME, check=False))
        raise
