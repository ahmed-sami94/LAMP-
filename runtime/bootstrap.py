"""Initialize only empty managed volumes; reconstruct ephemeral service config."""
import ipaddress
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess
import sys
from werkzeug.security import generate_password_hash
from common import STATE, SITES, BACKUPS, atomic_json, hostname, identifier, secret
from configuration import admin_config, site_config


def user(site):
    try:
        existing = pwd.getpwnam(site["id"])
        if existing.pw_uid != site["uid"]:
            raise ValueError("Site UID collision.")
    except KeyError:
        subprocess.run(["groupadd", "-g", str(site["uid"]), site["id"]], check=True)
        subprocess.run(["useradd", "-u", str(site["uid"]), "-g", str(site["uid"]), "-M", "-s", "/usr/sbin/nologin", site["id"]], check=True)


def main():
    host = hostname(os.environ.get("LAMP_ADMIN_HOST", "localhost"))
    mode = os.environ.get("LAMP_MODE", "development")
    if mode not in ("development", "hosting"):
        raise ValueError("LAMP_MODE must be development or hosting.")
    public_port = int(os.environ.get("LAMP_PUBLIC_PORT", "443" if mode == "hosting" else "80"))
    if not 1 <= public_port <= 65535:
        raise ValueError("LAMP_PUBLIC_PORT must be between 1 and 65535.")
    proxies = [str(ipaddress.ip_network(x.strip())) for x in os.environ.get("LAMP_TRUSTED_PROXIES", "").split(",") if x.strip()]
    if mode == "hosting" and not proxies:
        raise ValueError("Hosting requires explicit LAMP_TRUSTED_PROXIES and HTTPS.")
    for directory in (STATE, SITES, BACKUPS, Path("/run/lampplus"), Path("/run/php"), Path("/run/apache2"), Path("/var/lock/apache2")):
        directory.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o711)
    os.chmod(BACKUPS, 0o700)
    os.chmod(SITES, 0o755)
    account_file = STATE / "account.json"
    if not account_file.exists():
        password_file = os.environ.get("LAMP_ADMIN_PASSWORD_FILE")
        if password_file and Path(password_file).stat().st_mode & 0o077:
            raise ValueError("Administrator secret file must not be readable by group or others (use mode 0600).")
        password = secret("LAMP_ADMIN_PASSWORD")
        if not password or len(password) < 16:
            raise ValueError("First boot requires a unique LAMP_ADMIN_PASSWORD or _FILE secret of at least 16 characters.")
        if (Path("/var/lib/mysql/mysql")).exists():
            raise ValueError("Refusing an unrecognized database volume. Export/import legacy databases into fresh volumes.")
        atomic_json(account_file, {"user": os.environ.get("LAMP_ADMIN_USER", "admin"), "hash": generate_password_hash(password)})
    config_path = STATE / "panel.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {"key": secrets.token_hex(32), "filebrowser_key": secrets.token_hex(32)}
    config.update(host=host, mode=mode, proxies=proxies, public_port=public_port)
    atomic_json(config_path, config, 0o640, 1500)
    fbdir = STATE / "filebrowser"
    fbdir.mkdir(exist_ok=True)
    os.chown(fbdir, 1600, 1600)
    os.chmod(fbdir, 0o700)
    config_directory = STATE / "filebrowser-config"
    config_directory.mkdir(exist_ok=True)
    os.chown(config_directory, 0, 1600)
    os.chmod(config_directory, 0o750)
    fb_config = config_directory / "config.yaml"
    if not fb_config.exists():
        import yaml
        fb = {"server": {"listen": "127.0.0.1", "port": 8081, "baseURL": "/filebrowser", "database": str(fbdir / "database.db"), "cacheDir": str(fbdir / "cache"), "disableUpdateCheck": True, "disablePreviews": True, "disableWebDAV": True, "sources": [{"path": str(SITES), "name": "Websites", "config": {"private": True, "defaultEnabled": True, "rules": [{"ignoreSymlinks": True}]}}]},
              "auth": {"adminUsername": "lamp-owner", "adminPassword": secrets.token_urlsafe(40), "key": secrets.token_hex(32), "methods": {"password": {"enabled": False, "signup": False}, "jwt": {"enabled": True, "header": "X-Lamp-Assertion", "secret": config["filebrowser_key"], "algorithm": "HS256", "userIdentifier": "sub"}}},
              "userDefaults": {"account": {"permissions": {"modify": True, "create": True, "delete": True, "download": True, "share": False, "api": False}}}}
        fb_config.write_text(yaml.safe_dump(fb))
        os.chown(fb_config, 0, 1600)
        os.chmod(fb_config, 0o640)
    Path("/run/mysqld").mkdir(exist_ok=True)
    mysql = pwd.getpwnam("mysql")
    os.chown("/run/mysqld", mysql.pw_uid, mysql.pw_gid)
    if not Path("/var/lib/mysql/mysql").exists():
        subprocess.run(["mariadb-install-db", "--user=mysql", "--datadir=/var/lib/mysql", "--auth-root-authentication-method=socket", "--skip-test-db"], check=True, stdout=subprocess.DEVNULL)
        atomic_json(STATE / "database-managed.json", {"major": "11.8"})
    elif not (STATE / "database-managed.json").exists():
        raise ValueError("Database initialization interrupted or volume not managed by LAMP+.")
    admin_config(config)
    pma = Path("/opt/lampplus/phpmyadmin/config.inc.php")
    # This key is a cookie encryption secret, never a database credential.
    pma.write_text("<?php\n$cfg['blowfish_secret'] = '" + config["key"][:32] + "';\n" + """$cfg['Servers'][1]['auth_type'] = 'cookie';
$cfg['Servers'][1]['host'] = 'localhost';
$cfg['Servers'][1]['AllowNoPassword'] = false;
$cfg['Servers'][1]['AllowRoot'] = false;
$cfg['AllowArbitraryServer'] = false;
$cfg['VersionCheck'] = false;
$cfg['TempDir'] = '/var/lib/php/sessions';
""")
    os.chown(pma, 0, pwd.getpwnam("www-data").pw_gid)
    os.chmod(pma, 0o640)
    sites_file = STATE / "sites.json"
    if not sites_file.exists():
        atomic_json(sites_file, [])
    records = json.loads(sites_file.read_text())
    # Rebuild from committed ready records; an interrupted wizard must stay unpublished.
    for pattern in ("/etc/apache2/sites-enabled", "/etc/php/8.5/fpm/pool.d"):
        for generated in Path(pattern).glob("s*.conf"):
            try:
                identifier(generated.stem)
            except ValueError:
                continue
            generated.unlink()
    for site in records:
        if site["status"] == "creating":
            site.update(status="failed", remaining=[str(SITES / site["id"]), "Inspect database/account " + site["id"]])
        user(site)
        if site["status"] == "ready":
            site_config(site)
    atomic_json(sites_file, records)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"LAMP+ startup refused: {error}", file=sys.stderr)
        sys.exit(1)
