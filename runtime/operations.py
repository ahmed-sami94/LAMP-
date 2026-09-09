"""Serialized, allowlisted root operations. Never execute request-provided commands."""
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import stat
import subprocess
import time

from common import STATE, SITES, BACKUPS, atomic_json, hostname, identifier, php_limits
from bootstrap import user
from configuration import site_config


class CommandFailed(RuntimeError):
    def __init__(self, name, code, stderr):
        super().__init__(f"{name} failed (exit {code}).")
        self.stderr = stderr


def run(arguments, **kwargs):
    result = subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, **kwargs)
    if result.returncode:
        # CLI output may contain secrets; do not forward it to logs or clients.
        raise CommandFailed(Path(arguments[0]).name, result.returncode, result.stderr)
    return result.stdout


def sql(statement):
    return run(["mariadb", "--protocol=socket", "--batch", "--skip-column-names"], input=statement.encode())


def sites():
    return json.loads((STATE / "sites.json").read_text())


def save_site(site):
    records = sites()
    records = [x for x in records if x["id"] != site["id"]] + [site]
    atomic_json(STATE / "sites.json", records)


def get_site(key):
    identifier(key)
    for site in sites():
        if site["id"] == key and site["status"] == "ready":
            return site
    raise ValueError("Ready website not found.")


def reload_services():
    run(["apachectl", "configtest"])
    run(["php-fpm8.5", "-t"])
    pid = int(Path("/run/php/php8.5-fpm.pid").read_text())
    os.kill(pid, signal.SIGUSR2)
    run(["apachectl", "graceful"])


def as_site(site, arguments, **kwargs):
    return run(["runuser", "-u", site["id"], "--", *arguments], **kwargs)


def php_command(site, script, arguments):
    try:
        return as_site(site, ["php", "/opt/lampplus/invoke-php.php"],
                       cwd=SITES / site["id"] / "public",
                       input=json.dumps({"script": script, "arguments": arguments}).encode())
    except CommandFailed as error:
        diagnostic = error.stderr.decode(errors="replace")
        for argument in arguments:
            if "=" in argument and any(word in argument.split("=", 1)[0] for word in ("pass", "email", "user")):
                diagnostic = diagnostic.replace(argument.split("=", 1)[1], "[redacted]")
        atomic_json(STATE / "last-install-error.json", {"site": site["id"], "diagnostic": diagnostic[-8000:]})
        raise


def public_permissions(root, uid):
    # Descriptor-based changes cannot follow an uploaded symlink outside the root.
    for directory, _, files, descriptor in os.fwalk(root, follow_symlinks=False):
        os.fchown(descriptor, uid, 1600)
        os.fchmod(descriptor, 0o2770)
        for name in files:
            handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
            try:
                info = os.fstat(handle)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError("Public content must contain regular, unlinked files.")
                os.fchown(handle, uid, 1600)
                private_config = Path(directory) == root and name == "configuration.php"
                os.fchmod(handle, 0o600 if private_config else 0o660)
            finally:
                os.close(handle)


def create_site(data, progress):
    host = hostname(data.get("hostname"))
    config = json.loads((STATE / "panel.json").read_text())
    if host == config["host"] or any(s["hostname"] == host and s["status"] != "failed" for s in sites()):
        raise ValueError("Hostname is already allocated; existing data was not changed.")
    cms = data.get("cms", "empty")
    if cms not in ("empty", "wordpress", "joomla"):
        raise ValueError("Unsupported CMS.")
    limits = php_limits(data)
    if cms != "empty":
        if not isinstance(data.get("password"), str) or len(data["password"]) < 16:
            raise ValueError("CMS administrator password must contain at least 16 characters.")
        if not isinstance(data.get("username"), str) or not 1 <= len(data["username"]) <= 60:
            raise ValueError("CMS administrator username is required.")
        if not isinstance(data.get("email"), str) or "@" not in data["email"] or len(data["email"]) > 254:
            raise ValueError("A valid administrator email is required.")
    title = str(data.get("title", host))[:120]
    key = "s" + secrets.token_hex(6)
    site = {"id": key, "hostname": host, "title": title, "cms": cms, "php": limits,
            "uid": max([s["uid"] for s in sites()] + [9999]) + 1, "status": "creating",
            "created": int(time.time()), "daily_backup": False, "retention": 7}
    home = SITES / key
    # The parent is root-owned. Never reuse, adopt, or empty an existing directory.
    home.mkdir(mode=0o755)
    os.chmod(home, 0o755)
    save_site(site)
    database_created = False
    account_created = False
    try:
        progress("Creating website account")
        user(site)
        for name in ("public", "sessions", "tmp"):
            folder = home / name
            folder.mkdir(mode=0o700)
            os.chown(folder, site["uid"], 1600 if name == "public" else site["uid"])
            os.chmod(folder, 0o2770 if name == "public" else 0o700)
        password = secrets.token_hex(24)
        progress("Provisioning a dedicated database")
        sql(f"CREATE DATABASE `{key}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        database_created = True
        sql(f"CREATE USER '{key}'@'localhost' IDENTIFIED BY '{password}';")
        account_created = True
        sql(f"GRANT ALL PRIVILEGES ON `{key}`.* TO '{key}'@'localhost';")
        atomic_json(STATE / f"{key}.json", {"database": key, "username": key, "password": password})
        if cms != "empty":
            progress("Extracting verified " + cms + " package")
            try:
                as_site(site, ["python3", "/opt/lampplus/extract.py", f"/opt/lampplus/{cms}.tar.gz", str(home / "public"), cms])
            except CommandFailed as error:
                atomic_json(STATE / "last-install-error.json", {"site": key, "phase": "extraction",
                    "diagnostic": error.stderr.decode(errors="replace")[-8000:]})
                raise
            progress("Installing " + cms)
            if cms == "wordpress":
                php_command(site, "/usr/local/bin/wp", ["config", "create", "--dbname=" + key, "--dbuser=" + key,
                    "--dbpass=" + password, "--dbhost=localhost", "--skip-check"])
                php_command(site, "/usr/local/bin/wp", ["core", "install", "--url=" + ("https://" if config["mode"] == "hosting" else "http://") + host,
                    "--title=" + title, "--admin_user=" + data["username"], "--admin_password=" + data["password"], "--admin_email=" + data["email"], "--skip-email"])
                # WordPress supports its configuration one level above the web root.
                (home / "public/wp-config.php").replace(home / "wp-config.php")
                os.chmod(home / "wp-config.php", 0o600)
            else:
                php_command(site, str(home / "public/installation/joomla.php"), ["install", "--no-interaction",
                    "--site-name=" + title, "--admin-user=" + data["username"], "--admin-username=" + data["username"],
                    "--admin-password=" + data["password"], "--admin-email=" + data["email"], "--db-type=mysqli",
                    "--db-host=localhost", "--db-user=" + key, "--db-pass=" + password, "--db-name=" + key,
                    "--db-prefix=j_", "--db-encryption=0", "--public-folder="])
                os.chmod(home / "public/configuration.php", 0o600)
        else:
            # Static placeholder contains no runtime or environment information.
            (home / "public/index.html").write_text("<!doctype html><title>Website ready</title><h1>Website ready</h1>")
            os.chown(home / "public/index.html", site["uid"], 1600)
        progress("Activating Apache and PHP-FPM")
        public_permissions(home / "public", site["uid"])
        site_config(site)
        reload_services()
        site["status"] = "ready"
        save_site(site)
        return {"site": key}
    except Exception as error:
        # Leave interrupted files available for inspection, but never publish them.
        for path in (Path(f"/etc/apache2/sites-enabled/{key}.conf"), Path(f"/etc/php/8.5/fpm/pool.d/{key}.conf")):
            path.unlink(missing_ok=True)
        remaining = [str(home)]
        try:
            if account_created:
                sql(f"DROP USER '{key}'@'localhost';")
            if database_created:
                sql(f"DROP DATABASE `{key}`;")
        except RuntimeError:
            remaining.append("database/account " + key)
        site.update(status="failed", remaining=remaining)
        save_site(site)
        try:
            reload_services()
        except Exception:
            pass
        detail = str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__
        raise RuntimeError("Setup failed: " + detail + " Preserved for inspection: " + ", ".join(remaining)) from None


def update_php(data, progress):
    site = get_site(data.get("site"))
    previous = site["php"]
    site["php"] = php_limits(data)
    progress("Validating PHP configuration")
    try:
        site_config(site)
        reload_services()
    except Exception:
        site["php"] = previous
        site_config(site)
        reload_services()
        raise
    save_site(site)
    return {"site": site["id"]}


def backup(data, progress):
    site = get_site(data.get("site"))
    key = site["id"]
    backup_id = key + "-" + secrets.token_hex(8)
    destination = BACKUPS / backup_id
    destination.mkdir(mode=0o700)
    progress("Backing up website files and database")
    try:
        # Archive creation runs as the website UID: root cannot follow uploaded links.
        with (destination / "files.tar.gz").open("wb") as output:
            process = subprocess.run(["runuser", "-u", key, "--", "tar", "--one-file-system", "--exclude=./sessions", "--exclude=./tmp",
                "-czf", "-", "-C", str(SITES / key), "."], stdout=output, stderr=subprocess.DEVNULL, timeout=600)
            if process.returncode:
                raise RuntimeError("File backup failed; website may be changing.")
        with (destination / "database.sql").open("wb") as output:
            process = subprocess.run(["mariadb-dump", "--protocol=socket", "--single-transaction", "--routines", "--triggers", key],
                stdout=output, stderr=subprocess.DEVNULL, timeout=600)
            if process.returncode:
                raise RuntimeError("Database backup failed.")
        atomic_json(destination / "manifest.json", {"id": backup_id, "site": key, "hostname": site["hostname"], "created": int(time.time())})
        if data.get("scheduled") is True and site["daily_backup"]:
            # Prune on the serialized worker, never concurrently with a restore.
            history = [b for b in backup_list() if b["site"] == key and b["id"] != backup_id]
            for item in history[site["retention"] - 1:]:
                shutil.rmtree(BACKUPS / item["id"])
        return {"backup": backup_id}
    except Exception:
        shutil.rmtree(destination)
        raise


def backup_list():
    return sorted([json.loads(p.read_text()) for p in BACKUPS.glob("*/manifest.json")], key=lambda x: x["created"], reverse=True)


def schedule(data, progress):
    site = get_site(data.get("site"))
    if type(data.get("enabled")) is not bool or type(data.get("retention")) is not int or not 1 <= data["retention"] <= 30:
        raise ValueError("Schedule requires a boolean and retention between 1 and 30.")
    site.update(daily_backup=data["enabled"], retention=data["retention"])
    save_site(site)
    return {"site": site["id"]}


def restore(data, progress):
    site = get_site(data.get("site"))
    key = site["id"]
    item = next((x for x in backup_list() if x["id"] == data.get("backup") and x["site"] == key), None)
    if not item or data.get("confirm") != site["hostname"]:
        raise ValueError("Choose a backup for this site and confirm its exact hostname.")
    safety = backup({"site": key}, progress)["backup"]
    progress("Restoring; pre-restore backup: " + safety)
    stage = SITES / (".restore-" + secrets.token_hex(12))
    stage.mkdir(mode=0o700)
    os.chown(stage, site["uid"], site["uid"])
    previous = SITES / (".previous-" + secrets.token_hex(12))
    source = BACKUPS / item["id"]
    switched = False
    run(["supervisorctl", "stop", "php"])
    try:
        with (source / "files.tar.gz").open("rb") as archive:
            as_site(site, ["python3", "/opt/lampplus/restore-files.py", str(stage)], stdin=archive)
        public_permissions(stage / "public", site["uid"])
        for name in ("sessions", "tmp"):
            folder = stage / name
            folder.mkdir(mode=0o700)
            os.chown(folder, site["uid"], site["uid"])
        restore_database(site, source / "database.sql")
        os.chown(stage, 0, 0)
        os.chmod(stage, 0o755)
        (SITES / key).replace(previous)
        stage.replace(SITES / key)
        switched = True
        shutil.rmtree(previous)
        return {"site": key, "pre_restore_backup": safety}
    except Exception:
        if not switched:
            restore_database(site, BACKUPS / safety / "database.sql")
            if previous.exists() and not (SITES / key).exists():
                previous.replace(SITES / key)
        raise RuntimeError("Restore failed. Pre-restore recovery point: " + safety) from None
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        run(["supervisorctl", "start", "php"])


def restore_database(site, dump):
    key = site["id"]
    credentials = json.loads((STATE / f"{key}.json").read_text())
    auth = STATE / (key + ".cnf")
    auth.write_text(f"[client]\nuser={key}\npassword={credentials['password']}\n")
    os.chmod(auth, 0o600)
    try:
        sql(f"DROP DATABASE `{key}`; CREATE DATABASE `{key}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        with dump.open("rb") as stream:
            run(["mariadb", "--defaults-extra-file=" + str(auth), "--protocol=socket", "--binary-mode", "--local-infile=0", key], stdin=stream)
    finally:
        auth.unlink(missing_ok=True)


ACTIONS = {"site.create": create_site, "php.update": update_php, "backup.create": backup,
           "backup.schedule": schedule, "backup.restore": restore}
