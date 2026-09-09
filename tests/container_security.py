"""Runs inside the disposable container, never inside the distributed image."""
import json
import os
from pathlib import Path
import subprocess
import sys

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
