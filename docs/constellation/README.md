# Repo Constellation

This workspace root is a small control repo for the Temporal repo constellation that lives beside the managed subrepos.

## Canonical files

- `constellation/repos.yaml` is the curated source of truth for which repos belong to this workspace constellation.
- `constellation/current.lock.json` is the latest captured machine-readable snapshot.
- `docs/constellation/snapshots/` stores timestamped Markdown reports for human review.

## Commands

- `make constellation-list` runs `monoctl list` and prints the curated membership and role metadata.
- `make constellation-status` runs `monoctl status` and prints current branch, HEAD, and dirty state for each managed repo.
- `make constellation-doctor` runs `monoctl doctor` to validate paths, git repo presence, expected remote URLs, expected default branches, and dirty worktrees.
- `make constellation-snapshot` runs `monoctl snapshot` and writes the lockfile and a timestamped Markdown snapshot.

## Operating rules

- Update `constellation/repos.yaml` when adding or removing managed repos or when upstream defaults change.
- Treat `constellation-doctor` as the preflight check before coordinated multi-repo work.
- V1 is read-only with respect to subrepos. The control repo reports state; it does not fetch, pull, switch branches, or rewrite any managed repo.
