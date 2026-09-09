"""Runs inside the disposable container, never inside the distributed image."""
import json
import os
from pathlib import Path
import subprocess
import sys
import sqlite3
import shutil
from unittest.mock import patch

sys.path.insert(0, "/opt/lampplus")
from common import STATE, rpc

records = [x for x in json.loads((STATE / "sites.json").read_text()) if x["status"] == "ready"]
first = next(site for site in records if site["hostname"] == "studio.localhost")
second = next(site for site in records if site["hostname"] == "journal.localhost")
credentials = json.loads((STATE / (first["id"] + ".json")).read_text())
auth = Path("/run/test-client.cnf")
auth.write_text(f"[client]\nuser={first['id']}\npassword={credentials['password']}\n")
auth.chmod(0o600)
try:
    def query(statement):
        return subprocess.run(["mariadb", "--defaults-extra-file=" + str(auth), "--protocol=socket", "--batch", "--skip-column-names"],
                              input=statement, capture_output=True, text=True, timeout=20)
    assert query(f"CREATE TABLE IF NOT EXISTS `{first['id']}`.acceptance (value INT); INSERT INTO `{first['id']}`.acceptance VALUES (42);").returncode == 0
    assert query(f"SELECT * FROM `{second['id']}`.acceptance;").returncode != 0
    assert query("SELECT * FROM mysql.user;").returncode != 0
    assert query("CREATE USER 'forbidden'@'localhost';").returncode != 0
    assert credentials["password"] not in json.dumps(rpc("overview"))
finally:
    auth.unlink()

for path in ("/var/lib/lampplus/panel.json", "/var/lib/lampplus/account.json", "/var/backups/lampplus"):
    result = subprocess.run(["runuser", "-u", first["id"], "--", "test", "-r", path])
    assert result.returncode != 0, "Website UID can read private state"
result = subprocess.run(["runuser", "-u", first["id"], "--", "python3", "-c",
    "import socket;s=socket.socket(socket.AF_UNIX);s.connect('/run/lampplus/worker.sock')"], capture_output=True)
assert result.returncode != 0, "Website UID can access provisioning socket"

# A symlink escape in an archive must fail without creating an outside file.
result = subprocess.run(["runuser", "-u", first["id"], "--", "python3", "-c", """
import io,tarfile,tempfile,pathlib,subprocess
with tempfile.TemporaryDirectory() as directory:
    destination=pathlib.Path(directory)/'dest'; destination.mkdir()
    archive=pathlib.Path(directory)/'bad.tar.gz'
    with tarfile.open(archive,'w:gz') as stream:
        item=tarfile.TarInfo('../outside'); item.size=4
        stream.addfile(item,io.BytesIO(b'evil'))
    with archive.open('rb') as source:
        result=subprocess.run(['python3','/opt/lampplus/restore-files.py',str(destination)],stdin=source,capture_output=True)
    assert result.returncode != 0
    assert not (pathlib.Path(directory)/'outside').exists()
"""], capture_output=True)
assert result.returncode == 0, "Traversal restore test failed"
print("Database isolation, private state and traversal checks passed")

# The real worker persists a global throttle; clear only this disposable test state.
try:
    for _ in range(5):
        assert rpc("login", username="admin", password="intentionally-incorrect") is False
    try:
        rpc("login", username="admin", password="intentionally-incorrect")
    except ValueError:
        pass
    else:
        raise AssertionError("Login throttle did not reject the sixth failed attempt")
    with sqlite3.connect(STATE / "auth.sqlite") as database:
        assert database.execute("SELECT count(*) FROM attempts").fetchone()[0] == 5
finally:
    with sqlite3.connect(STATE / "auth.sqlite") as database:
        database.execute("DELETE FROM attempts")
print("Persistent login throttling passed")

# Inject a CLI boundary failure after real database/account creation.
from common import SITES, atomic_json, identifier
from operations import CommandFailed, create_site, reload_services, sites, sql

original_records = sites()
original_ids = {site["id"] for site in original_records}
try:
    with patch("operations.as_site", side_effect=CommandFailed("installer", 1, b"Injected test failure")):
        try:
            create_site({"hostname": "retry.localhost", "cms": "wordpress", "username": "owner",
                         "email": "owner@example.test", "password": "disposable-test-password-only"}, lambda message: None)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Failed installer was incorrectly reported successful")
    failed = next(site for site in sites() if site["id"] not in original_ids)
    key = identifier(failed["id"])
    assert failed["status"] == "failed" and (SITES / key).is_dir()
    assert sql(f"SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='{key}';").strip() == b"0"
    assert sql(f"SELECT COUNT(*) FROM mysql.user WHERE User='{key}';").strip() == b"0"
    assert not Path(f"/etc/apache2/sites-enabled/{key}.conf").exists()
    sentinel = SITES / key / "public/retained.txt"
    sentinel.write_text("Retained failed attempt")
    retry = create_site({"hostname": "retry.localhost", "cms": "empty"}, lambda message: None)
    assert retry["site"] != key and sentinel.read_text() == "Retained failed attempt"
finally:
    # Remove only IDs allocated by this disposable fixture, never original sites.
    for created in sites():
        if created["id"] in original_ids:
            continue
        key = identifier(created["id"])
        Path(f"/etc/apache2/sites-enabled/{key}.conf").unlink(missing_ok=True)
        Path(f"/etc/php/8.5/fpm/pool.d/{key}.conf").unlink(missing_ok=True)
        sql(f"DROP DATABASE IF EXISTS `{key}`; DROP USER IF EXISTS '{key}'@'localhost';")
        shutil.rmtree(SITES / key)
        (STATE / f"{key}.json").unlink(missing_ok=True)
        subprocess.run(["userdel", key], check=True, capture_output=True)
        subprocess.run(["groupdel", key], check=False, capture_output=True)
    atomic_json(STATE / "sites.json", original_records)
    (STATE / "last-install-error.json").unlink(missing_ok=True)
    reload_services()
print("Failed provisioning cleanup and non-destructive retry passed")
