# Release procedure

Stable publication is blocked until the candidate acceptance evidence passes.
The publication destination is `ahmedsamigmail/lampplus`; the GitHub release
destination is this repository. Publishing from the Docker Hub website alone
does not upload an image: the image must be pushed by an authenticated client.

## Authorization

Set `DOCKERHUB_TOKEN` in this repository's encrypted GitHub Actions secrets.
Prefer a token restricted to this repository with read/write access. If the
account only offers account-wide personal tokens, use a short expiration, omit
Delete permission, obtain the owner's approval for the broader scope, and revoke
the token after publication. Never commit or paste tokens into issues or chat.

The Docker Hub repository must exist, be public, and belong to the authenticated
publisher. Public pull verification deliberately does not use a publishing token.

## Candidate

1. Review the upgrade pull request, current verification run, and dependency lock.
2. Merge only after acceptance is complete. The publication workflow must be on
   the default branch before it can be dispatched from GitHub Actions.
3. Run **Publish LAMP+**, phase `candidate`.
4. Each native architecture builds, runs the runtime/browser/HTTPS suite, scans
   source and image, emits an SBOM, and pushes its tested architecture image.
5. The workflow assembles `2.0.0-rc.1`, verifies its public multi-platform manifest,
   pulls the immutable digest on both architectures, and repeats runtime tests.
6. The candidate GitHub release includes source identity, verification evidence,
   package manifests and SBOMs. Build provenance is attested through GitHub.

Do not reuse a candidate version after accepting it. A changed source commit
requires a new candidate version and complete verification, not an overwrite of
an accepted release. The current workflow targets the first v2 candidate.

## Stable

Review the candidate evidence and remaining items in [STATUS.md](STATUS.md).
Run **Publish LAMP+**, phase `stable`, with the acceptance checkbox selected,
from the exact source commit recorded in the candidate metadata.

The workflow promotes the accepted image digest to `2.0.0`, `2.0`, `2`, and
`latest`, then creates GitHub release `v2.0.0`. No rebuild is performed during
promotion. Verify public pulls after publication and retain the candidate's
evidence and immutable digest for rollback.

## Rollback and legacy migration

Keep the previously deployed image digest and an off-host copy of all four
volumes. An image rollback is not a database downgrade. When the database format
or application schema has changed, restore a compatible recovery point into
fresh volumes and test it before switching traffic.

Legacy data is migrated by file transfer and logical SQL export/import. Never
attach an unknown MariaDB data directory and attempt an in-place upgrade.
