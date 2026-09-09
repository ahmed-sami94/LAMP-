# HTTPS hosting with Caddy

This example is a release acceptance target, not yet a production recommendation.
Do not expose the development candidate until all release gates pass.

## Setup

Use a Linux Docker host. Point separate DNS records for `panel.example.com` and
`www.example.com` to it. Allow inbound TCP 80/443 and optionally UDP 443. Keep the
Docker API, databases, File Browser and control worker private.

Create `secrets/admin_password` with a unique password of at least 16 characters.
Set its Linux ownership to root and permission to `0600` before starting Compose.
Docker Compose file-based secrets preserve source permissions: do not rely on
the Compose `mode` field to hide a world-readable source file.

Set these values in the project's ignored `.env` file:

```dotenv
LAMP_ADMIN_HOST=panel.example.com
SITE_HOST=www.example.com
ACME_EMAIL=you@example.com
UBUNTU_IMAGE=<ubuntu reference from dependencies.lock.json>
CADDY_IMAGE=<caddy reference from dependencies.lock.json>
```

```sh
docker compose --env-file .env -f examples/hosting.compose.yaml up --build -d
```

Caddy obtains HTTPS certificates and redirects HTTP. Certificates persist in the
`certificates` volume. Only Caddy publishes ports; LAMP+ trusts forwarded scheme
headers solely from its fixed Caddy address. Choose a non-conflicting private
subnet and update the proxy allowlist and both addresses together when needed.

Do not place another unconfigured proxy in front of Caddy. Configure any extra
trusted proxy chain explicitly and repeat the HTTPS tests.

## Add a domain

1. Create a DNS record pointing the new hostname to the host.
2. Create the website with that exact hostname in the owner dashboard.
3. Add the hostname to the site-address list in `examples/Caddyfile`.
4. Validate and reload Caddy:

```sh
docker compose --env-file .env -f examples/hosting.compose.yaml exec caddy caddy validate --config /etc/caddy/Caddyfile
docker compose --env-file .env -f examples/hosting.compose.yaml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

The dashboard does not modify Caddy or DNS. Unknown Apache hostnames are denied.
Reserve the administration hostname exclusively for LAMP+; do not upload site
content there.

## Troubleshooting

- HTTPS fails: verify DNS, inbound ports and Caddy logs; check ACME rate limits.
- Panel rejects a request: verify the exact hostname, HTTPS scheme and configured
  proxy IP. Do not disable the proxy check to work around routing problems.
- Container unhealthy: inspect `docker compose ... ps` and service logs. Account
  bootstrap refuses missing secrets or unmanaged database volumes.
- CMS redirect loop: confirm PHP receives the trusted HTTPS scheme, then check
  the application's configured URL. Never trust forwarded headers from all peers.
- Backup or restore fails: stop file edits/background writers, check free space,
  and inspect the Activity message and retained recovery point.

Retain off-host backups and regularly test restoration on a disposable host.
