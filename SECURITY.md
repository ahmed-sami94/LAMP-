# Security policy

LAMP+ v2 is under development. Stable publication is blocked until release
acceptance and security scanning pass. Do not expose development builds publicly.

Report suspected vulnerabilities privately through the repository's GitHub
Security Advisory reporting feature when enabled, or email `i@ahmed-sami.me`.
Do not include real passwords, tokens, private keys or production database dumps.
Provide the image digest, affected version, reproduction steps and impact.

## Trust boundaries

- One trusted owner, trusted website code; not unrelated multi-tenant hosting.
- Apache is the only published service. Private worker accepts only root/panel UIDs.
- Site credentials have privileges on one application database, not global grants.
- Keep administration on its own hostname and use HTTPS for anything beyond loopback.
- Protect Docker socket/host access as root access. Do not mount it into LAMP+.
- `_FILE` secrets and backups must remain outside public website roots.
- A compromised panel account can intentionally upload executable website code.

Release scans must include source, downloaded tools, package dependencies and
final image layers. Unresolved exploitable HIGH/CRITICAL findings block stable
publication. Findings cannot be silently ignored to obtain a green build.
