"""Private Unix-socket worker with a bounded, serialized provisioning queue."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import socketserver
import sqlite3
import struct
import threading
import time
from werkzeug.security import check_password_hash

from common import STATE, SOCKET, atomic_json
from operations import ACTIONS, backup, backup_list, sites, sql

LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1)
JOBS = {}


def persist_jobs():
    atomic_json(STATE / "jobs.json", JOBS)


def execute(key, action, data):
    def progress(message):
        with LOCK:
            JOBS[key].update(status="running", message=message)
            persist_jobs()
    try:
        result = ACTIONS[action](data, progress)
        with LOCK:
            JOBS[key].update(status="complete", message="Completed", result=result)
    except (ValueError, RuntimeError) as error:
        with LOCK:
            JOBS[key].update(status="failed", message=str(error))
    except Exception:
        with LOCK:
            JOBS[key].update(status="failed", message="Operation failed. Inspect container service health; no credentials are logged.")
    finally:
        data.clear()
        with LOCK:
            persist_jobs()


def login(data):
    user, password = data.get("username", ""), data.get("password", "")
    if not isinstance(user, str) or not isinstance(password, str) or len(password) > 1024:
        return False
    account = json.loads((STATE / "account.json").read_text())
    # Persistent global throttling cannot be bypassed by spoofing a forwarded IP.
    with LOCK, sqlite3.connect(STATE / "auth.sqlite") as db:
        db.execute("CREATE TABLE IF NOT EXISTS attempts (created REAL)")
        db.execute("DELETE FROM attempts WHERE created < ?", (time.time() - 300,))
        if db.execute("SELECT count(*) FROM attempts").fetchone()[0] >= 5:
            raise ValueError("Login temporarily limited. Try again in five minutes.")
        valid = check_password_hash(account["hash"], password) and secrets.compare_digest(user, account["user"])
        if not valid:
            db.execute("INSERT INTO attempts VALUES (?)", (time.time(),))
        else:
            db.execute("DELETE FROM attempts")
        return valid


def metrics():
    services = {}
    for name, port in (("Apache", 80), ("MariaDB", 3306), ("File Browser", 8081), ("Panel", 9000)):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                services[name] = True
        except OSError:
            services[name] = False
    services["PHP-FPM"] = Path("/run/php/tools.sock").exists()
    used = None
    limit = None
    cgroup = Path("/sys/fs/cgroup")
    try:
        used = int((cgroup / "memory.current").read_text())
        raw = (cgroup / "memory.max").read_text().strip()
        limit = None if raw == "max" else int(raw)
    except (OSError, ValueError):
        pass
    disk = shutil.disk_usage("/srv/sites")
    return {"services": services, "memory_bytes": used, "memory_limit": limit,
            "storage_free": disk.free, "storage_total": disk.total,
            "scope": "Container cgroup memory; website-volume filesystem capacity", "measured_at": int(time.time())}


def dispatch(action, data):
    if action == "login":
        return login(data)
    if action == "health":
        sql("SELECT 1;")
        return metrics()
    if action == "overview":
        with LOCK:
            return {"sites": sites(), "jobs": list(JOBS.values())[-30:][::-1], "backups": backup_list(), "metrics": metrics()}
    if action not in ACTIONS:
        raise ValueError("Operation is not allowed.")
    with LOCK:
        if sum(x["status"] in ("queued", "running") for x in JOBS.values()) >= 8:
            raise ValueError("Operation queue is full. Wait for current jobs.")
        key = secrets.token_hex(12)
        JOBS[key] = {"id": key, "action": action, "status": "queued", "message": "Queued", "created": int(time.time())}
        # Keep bounded history without losing active operations.
        while len(JOBS) > 100:
            oldest = next((k for k, v in JOBS.items() if v["status"] not in ("queued", "running")), None)
            if oldest is None:
                break
            del JOBS[oldest]
        persist_jobs()
        POOL.submit(execute, key, action, data)
        return {"job": key}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        credentials = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _, uid, _ = struct.unpack("3i", credentials)
        if uid not in (0, 1500):
            return
        try:
            line = self.rfile.readline(16385)
            if len(line) > 16384 or not line.endswith(b"\n"):
                raise ValueError("Request exceeds limit.")
            request = json.loads(line)
            if not isinstance(request.get("data"), dict):
                raise ValueError("Invalid request.")
            response = {"result": dispatch(request.get("action"), request["data"])}
        except (ValueError, TypeError):
            response = {"error": "Invalid operation or login temporarily limited. Check values and try again."}
        except Exception:
            response = {"error": "Service unavailable. Check container health."}
        self.wfile.write(json.dumps(response).encode() + b"\n")


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def scheduler():
    while True:
        time.sleep(60)
        for site in sites():
            if site["status"] != "ready" or not site.get("daily_backup"):
                continue
            history = [b for b in backup_list() if b["site"] == site["id"]]
            if not history or history[0]["created"] < time.time() - 86400:
                with LOCK:
                    if any(x["status"] in ("running", "queued") for x in JOBS.values()):
                        continue
                    dispatch("backup.create", {"site": site["id"]})
            for item in history[site["retention"]:]:
                from common import BACKUPS
                shutil.rmtree(BACKUPS / item["id"])


if __name__ == "__main__":
    for attempt in range(120):
        try:
            sql("SELECT 1;")
            break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit("MariaDB did not become ready.")
    if (STATE / "jobs.json").exists():
        JOBS.update(json.loads((STATE / "jobs.json").read_text()))
        for job in JOBS.values():
            if job["status"] in ("running", "queued"):
                job.update(status="failed", message="Interrupted by restart. Inspect retained resources before retrying.")
        persist_jobs()
    Path(SOCKET).unlink(missing_ok=True)
    with Server(SOCKET, Handler) as server:
        os.chown(SOCKET, 0, 1500)
        os.chmod(SOCKET, 0o660)
        threading.Thread(target=scheduler, daemon=True).start()
        server.serve_forever()
