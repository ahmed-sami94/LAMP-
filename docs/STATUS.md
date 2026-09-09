# Release readiness

This branch is a development candidate for LAMP+ 2.0.0, not a stable release.
Do not use it for public hosting until the acceptance matrix and security scans pass.

## Implemented, awaiting Linux acceptance

- Ubuntu 26.04 digest pin; verified PHP tooling and CMS package downloads.
- Supervised Apache, MariaDB, PHP-FPM, worker, panel and FileBrowser Quantum.
- First-boot secrets, persistent account state, separated admin hostname.
- Owner dashboard, site-specific databases and PHP pools, CMS jobs.
- Manual/scheduled backups, retention and confirmed restoration.
- Unit/security tests and native amd64/arm64 build/runtime workflows.

## Release blockers

- Both architecture builds and all runtime tests must pass.
- PHP 8.5 compatibility, especially phpMyAdmin, must be demonstrated.
- Security scans, privilege separation, failure recovery, HTTPS proxy and browser
  acceptance require completed evidence.
- Actual desktop/mobile screenshots, final documentation and branding are pending.
- Docker Hub authenticated ownership and repository token must be verified.
- Release-candidate acceptance precedes stable GitHub/Docker publication.

This file records remaining work; it does not waive any gate in the release plan.
