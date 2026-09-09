# Contributing

Open an issue describing the bug or proposed change. Keep patches scoped and
include regression tests. Never submit private data, real credentials, `.env`,
database directories or generated backups.

Run the unit tests documented in the README. Changes to provisioning, persistence,
authentication or recovery also require the Linux runtime suite on both supported
architectures. UI changes require actual desktop and mobile browser screenshots.

Downloads must have explicit versions and SHA256 checksums in the lock file.
Do not introduce curl-to-shell installers, command-string execution from requests,
shared passwords, arbitrary file paths, or global application database grants.

Keep GPLv3 headers/notices where applicable and document third-party licenses.
Stable releases require the security and acceptance gates in `docs/STATUS.md`.
