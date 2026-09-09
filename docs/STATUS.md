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

[Run 34403917190](https://github.com/ahmed-sami94/LAMP-/actions/runs/34403917190)
passed on native amd64 and arm64 at commit `c281ef9`: build, 15 unit/security
checks, two-site routing, database separation, file and SQL restoration,
WordPress/Joomla setup, container recreation with persistent state, graceful
shutdown, service failures, responsive screenshots, Caddy TLS verification,
proxy-spoofing rejection, source scanning and high/critical image scanning.

Subsequent changes add explicit CMS development ports and deeper authenticated
tool tests. The baseline is evidence for that commit, not a waiver for later changes.

## Release blockers

- Both architecture builds and all runtime tests must pass.
- PHP 8.5 compatibility, especially phpMyAdmin, must be demonstrated.
- Security scans, privilege separation, failure recovery, HTTPS proxy and browser
  acceptance require completed evidence.
- Updated screenshots and final documentation must match the accepted commit.
- Docker Hub ownership is confirmed and its overview is published. Image-push
  authorization still needs secure configuration; web sign-in alone is insufficient.
- Release-candidate acceptance precedes stable GitHub/Docker publication.

This file records remaining work; it does not waive any gate in the release plan.
