# LAMP+

<img src="https://raw.githubusercontent.com/ahmed-sami94/LAMP-/release/2.0.0/assets/logo.png" alt="LAMP+ logo" width="112">

![LAMP+ banner](https://raw.githubusercontent.com/ahmed-sami94/LAMP-/release/2.0.0/assets/banner.png)

**One container for your PHP workspace.** LAMP+ combines Ubuntu, Apache, PHP-FPM
and MariaDB with a protected owner dashboard, phpMyAdmin and FileBrowser Quantum.

**v2 image publication is pending.** The source is available for review and local
builds. Do not assume that `2.0.0` or `latest` exists until the release is announced.

## Included In v2

- Multiple websites with separate databases, generated credentials and PHP-FPM pools.
- WordPress and Joomla setup using pinned, checksum-verified packages.
- Per-site PHP limits, Composer and WP-CLI access.
- Manual and daily backups, retention and confirmed restoration.
- Supervised services, persistent state, health checks and container metrics.
- Protected database and file tools; only Apache is exposed by default.
- A Caddy HTTPS example with persistent certificates and mounted secrets.

This is a workspace for one trusted owner, not isolated hosting for unrelated
tenants. Uploaded PHP shares the container. Use trusted code and keep off-host backups.

## Screenshots

![Websites dashboard](https://raw.githubusercontent.com/ahmed-sami94/LAMP-/release/2.0.0/docs/screenshots/dashboard-desktop.png)

![Services page](https://raw.githubusercontent.com/ahmed-sami94/LAMP-/release/2.0.0/docs/screenshots/services-desktop.png)

![WordPress setup](https://raw.githubusercontent.com/ahmed-sami94/LAMP-/release/2.0.0/docs/screenshots/website-setup-desktop.png)

[Full page gallery and mobile captures](https://github.com/ahmed-sami94/LAMP-/blob/release/2.0.0/docs/PROJECT.md)

Screenshots come from a running, disposable CI container with synthetic websites
and no visible credentials. Resource measurements vary between runs.

## Build And Configure

Follow the [README quick start](https://github.com/ahmed-sami94/LAMP-/blob/release/2.0.0/README.md#local-development).
It requires Docker with Compose v2 and Linux containers. Configure a unique
administrator password before the first boot; there are no shared default passwords.

Preserve all four volumes: website content, MariaDB data, private application
state and backups. A restart does not reset credentials. Legacy installations
must migrate through file transfer and logical SQL export/import into fresh volumes.

## Documentation

- [Configuration, tools and backups](https://github.com/ahmed-sami94/LAMP-/blob/release/2.0.0/README.md)
- [HTTPS and domains](https://github.com/ahmed-sami94/LAMP-/blob/release/2.0.0/docs/HOSTING.md)
- [Verification and release status](https://github.com/ahmed-sami94/LAMP-/blob/release/2.0.0/docs/STATUS.md)
- [Security reporting](https://github.com/ahmed-sami94/LAMP-/blob/release/2.0.0/SECURITY.md)
- [Contributing](https://github.com/ahmed-sami94/LAMP-/blob/release/2.0.0/CONTRIBUTING.md)

Copyright (c) 2026 **Ahmed Sami**. Developed and maintained by Ahmed Sami.
[i@ahmed-sami.me](mailto:i@ahmed-sami.me) | [ahmed-sami.me](https://ahmed-sami.me/).

LAMP+ is GPLv3; bundled components retain their own licenses.
[Source and license notices](https://github.com/ahmed-sami94/LAMP-/tree/release/2.0.0)
