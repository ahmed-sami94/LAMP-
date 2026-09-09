# Release readiness

This branch is a development candidate for LAMP+ 2.0.0, not a stable release.
Do not use it for public hosting until the acceptance matrix and security scans pass.

## Implemented

- Ubuntu 26.04 digest pin; verified PHP tooling and CMS package downloads.
- Supervised Apache, MariaDB, PHP-FPM, worker, panel and FileBrowser Quantum.
- First-boot secrets, persistent account state, separated admin hostname.
- Owner dashboard, site-specific databases and PHP pools, CMS jobs.
- Manual/scheduled backups, retention and confirmed restoration.
- Unit/security tests and native amd64/arm64 build/runtime workflows.

## Verified baseline

[Run 34408734668](https://github.com/ahmed-sami94/LAMP-/actions/runs/34408734668)
passed on native amd64 and arm64 at commit `fbe9270`: build, 19 unit/security
checks, two-site routing, database separation, file and SQL restoration,
WordPress/Joomla setup, container recreation with persistent state, graceful
shutdown, service failures, responsive screenshots, Caddy TLS verification,
proxy-spoofing rejection, authenticated phpMyAdmin/File Browser sessions, source
scanning and high/critical image scanning. Live checks also cover persistent
login throttling, actual PHP limits/environment isolation, scheduled retention,
installer failure cleanup and non-destructive retry.

This run also verified HTTPS scheme propagation to website PHP, rejected forged
scheme headers, and validated both distributed Compose examples. The baseline
is evidence for that commit, not a waiver for later changes.

## Release blockers

- Subsequent changes must retain passing architecture, runtime, security and
  browser checks; screenshots must identify their capture commit.
- Docker Hub ownership is confirmed and its overview is published. Image-push
  authorization still needs secure configuration; web sign-in alone is insufficient.
- Release-candidate acceptance precedes stable GitHub/Docker publication.

This file records remaining work; it does not waive any gate in the release plan.
