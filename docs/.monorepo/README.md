# Monorepo Control

This workspace root is a small control repo for the Temporal multi-repo workspace that lives beside the managed subrepos.

## Canonical files

- `.monorepo/repos.yaml` is the curated source of truth for which repos belong to this workspace.
- `.monorepo/current.lock.json` is the latest captured machine-readable snapshot.
- `docs/.monorepo/snapshots/` stores timestamped Markdown reports for human review.

## Commands

- `make monorepo-init` runs `./.monorepo/monoctl init` to clone missing managed repos and fast-forward pull existing clean repos.
- `make monorepo-list` runs `./.monorepo/monoctl list` and prints the curated membership and role metadata.
- `make monorepo-status` runs `./.monorepo/monoctl status` and prints current branch, HEAD, and dirty state for each managed repo.
- `make monorepo-doctor` runs `./.monorepo/monoctl doctor` to validate paths, git repo presence, expected remote URLs, expected default branches, and dirty worktrees.
- `make monorepo-snapshot` runs `./.monorepo/monoctl snapshot` and writes the lockfile and a timestamped Markdown snapshot.

## Operating rules

- Update `.monorepo/repos.yaml` when adding or removing managed repos or when upstream defaults change.
- Run `monorepo-init` from the control repo after cloning `temporalis`, or after adding a managed repo.
- `monorepo-init` fails without mutating if an existing managed repo is dirty, detached, on the wrong branch, or configured with an unexpected remote.
- Treat `monorepo-doctor` as the preflight check before coordinated multi-repo work.
- The control repo never rewrites managed repos; initialization only clones missing paths or fast-forward pulls clean repos on the expected branch.
