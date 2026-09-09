"""Shared validation, private state IO, and local worker protocol."""
import json
import os
import re
import socket
from pathlib import Path

STATE = Path(os.environ.get("LAMP_STATE", "/var/lib/lampplus"))
SITES = Path("/srv/sites")
BACKUPS = Path("/var/backups/lampplus")
SOCKET = "/run/lampplus/worker.sock"


def hostname(value):
    if not isinstance(value, str) or len(value) > 253 or value != value.lower():
        raise ValueError("Use a lowercase DNS hostname without a port or URL.")
    labels = value.split(".")
    if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in labels):
        raise ValueError("Invalid hostname.")
    if all(x.isdigit() for x in labels):
        raise ValueError("Use a hostname, not an IP address.")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"s[a-f0-9]{12}", value):
        raise ValueError("Invalid site identifier.")
    return value


def php_limits(data):
    result = {}
    for key, default, minimum, maximum in (
        ("memory", 256, 64, 1024), ("upload", 32, 2, 128), ("timeout", 120, 10, 300)
    ):
        value = data.get(key, default)
        if isinstance(value, bool) or str(value) != str(int(value)) or not minimum <= int(value) <= maximum:
            raise ValueError(f"{key} must be between {minimum} and {maximum}.")
        result[key] = int(value)
    return result


def secret(name):
    value, filename = os.environ.get(name), os.environ.get(name + "_FILE")
    if value and filename:
        raise ValueError(f"Set {name} or {name}_FILE, not both.")
    return Path(filename).read_text().rstrip("\r\n") if filename else value


def atomic_json(path, value, mode=0o600, gid=0):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, mode)
    os.chown(temporary, 0, gid)
    temporary.replace(path)


def rpc(action, **data):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(15)
        connection.connect(SOCKET)
        connection.sendall(json.dumps({"action": action, "data": data}).encode() + b"\n")
        response = json.loads(connection.makefile("rb").readline(2_000_000))
    if "error" in response:
        raise ValueError(response["error"])
    return response["result"]
