# Changelog

## 2.0.0 - Unreleased

- Rebuild on digest-pinned Ubuntu 26.04 with Apache, PHP 8.5 FPM and MariaDB 11.8.
- Add a protected owner dashboard, multiple websites, separate database accounts,
  PHP pools and per-site PHP limits.
- Add pinned WordPress/Joomla installers, progress reporting and retained failure
  resources. Existing destinations and allocated hostnames are never overwritten.
- Replace shared defaults with first-boot secrets and persistent hashed owner
  credentials. Keep internal tools and database ports unpublished.
- Replace the archived File Browser upstream with FileBrowser Quantum.
- Add private backups, daily retention, confirmed restore and pre-restore backups.
- Add supervised services, readiness checks, graceful shutdown and container metrics.
- Add Caddy HTTPS configuration, native architecture CI, vulnerability scanning,
  SBOMs, release-candidate gates and publication workflows.
- Refresh the logo, banner, dashboard controls and reusable documentation.

### Breaking changes

- Administration is hosted on its own configured hostname and requires sign-in.
- File Browser moves to `/filebrowser/`; `/mo` opens the protected dashboard.
- No default database password, global application grants, database port exposure,
  or separately exposed File Browser port remains.
- Four persistent volumes must be kept together. Legacy database directories are
  unsupported; migrate with logical exports into fresh volumes.
