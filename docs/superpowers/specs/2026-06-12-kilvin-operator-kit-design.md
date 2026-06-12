# Kilvin Operator Kit Design

Status: approved 2026-06-12 by user direction in this thread. This spec follows the retrospective on the real Kilvin implementation and turns the hard parts into repo-contained skills, docs, scripts, and Make targets.

## Goal

Make the real Kilvin implementation easy for future agents and humans to operate, verify, and publish without reconstructing the command sequence from memory.

The operator kit must:

- Keep shared skills inside this repository under `.agents/skills/` so all agents working on Temporalis can use them.
- Provide a one-command environment preflight before live Kilvin work.
- Provide a one-command real smoke proof for the Temporal -> allocator -> docker image -> k3s Job path.
- Provide a one-command GitHub Pages content verifier after publishing explorer data.
- Document the happy path, proof checklist, and Colima troubleshooting in repo docs.

## Non-Goals

- Do not edit personal/global skills under `/Users/bytedance/.codex/skills`.
- Do not make live Kilvin checks part of the default `make test` target.
- Do not push or publish automatically.
- Do not replace the existing `kilvin-py/infra/up.sh` and `down.sh` control-plane scripts.

## Architecture

The operator kit has three layers:

1. **Skills** under `.agents/skills/`.
   These are short, repo-local entrypoints that tell agents which Make targets and docs to use before falling back to manual diagnostics.
2. **Docs** under `docs/kilvin/`.
   These explain the happy path, what counts as proof, and how to debug common macOS/Colima failures.
3. **Scripts and Make targets**.
   Scripts perform the repeatable checks; Make targets expose stable names that humans and agents can remember.

The Make targets are the public interface:

```text
make kilvin-doctor
make kilvin-real-smoke
make kilvin-pages-check PAGES_URL=https://phi9t.github.io/temporalis/data/kilvin/internals.json
```

## Components

### Repo-local skills

Create:

- `.agents/skills/kilvin-real-runtime/SKILL.md`
- `.agents/skills/github-pages-release-verification/SKILL.md`

`kilvin-real-runtime` applies when an agent needs to run, debug, or prove the real Kilvin local stack. It points first to `make kilvin-doctor`, `make kilvin-real-smoke`, and the docs under `docs/kilvin/`.

`github-pages-release-verification` applies when a branch has been pushed and success depends on hosted GitHub Pages content changing. It points first to `make kilvin-pages-check`.

### Docs

Create:

- `docs/kilvin/real-local-runbook.md`
- `docs/kilvin/proof-checklist.md`
- `docs/kilvin/troubleshooting-colima.md`

The docs should stay concrete and command-oriented. They should not duplicate every line of the scripts, but they should explain what each proof means and what to do when it fails.

### Scripts

Create:

- `scripts/kilvin_doctor.py`
- `scripts/kilvin_real_smoke.py`
- `scripts/kilvin_pages_check.py`

`kilvin_doctor.py` checks:

- required tools: `docker`, `uv`, `python`, `curl`
- Docker context and daemon reachability
- Docker architecture and ability to run a `linux/amd64` container
- compose service status for `kilvin-py/infra/docker-compose.yml`
- allocator health endpoint
- Temporal TCP port
- k3s kubeconfig presence
- k3s namespace presence when `kubectl` is available
- local registry TCP port

The doctor should report PASS/WARN/FAIL rows and exit non-zero if required checks fail.

`kilvin_real_smoke.py` runs the live proof:

- optionally starts infra by invoking `kilvin-py/infra/up.sh`
- starts `kilvin-py/worker.py` as a child process
- starts `kilvin-py/start_workflow.py`
- extracts the completed run id
- verifies Temporal step trace contains the six expected successful steps when the Temporal CLI is available
- verifies `.kilvin-artifacts/<run-id>/...` contains the digest, quota decision, env vars, and logs
- verifies logs contain `TRAINING_DONE`
- verifies allocator allocations are empty after completion
- exits non-zero on missing proof

The script should keep the workflow path explicit and legible rather than hiding everything behind a framework. It may skip optional CLI checks with WARN when a tool is missing, but artifact and allocator-release checks are required.

`kilvin_pages_check.py` polls a URL until expected strings appear:

- `laptop scale`
- `uv lock --check`
- `local allocator`
- `k3s`

The default URL is the existing GitHub Pages `kilvin/internals.json`; callers can override with `--url`.

## Error Handling

- Missing local tools should produce actionable messages, not stack traces.
- Docker socket permission failures should say that Docker/Colima must be reachable from the current shell.
- Colima DNS or package-resolution failures are documented in `troubleshooting-colima.md`; the doctor can point there.
- Smoke-run worker processes must be terminated on script exit.
- Pages polling should distinguish HTTP failure from content-not-yet-updated.

## Testing and Verification

Add focused tests only for pure helper behavior where it is practical:

- command result classification
- artifact path verification
- Pages expected-string matching

Manual/live validation for this implementation:

- `PYTHONPATH=. pytest -q`
- `make kilvin-doctor`
- `make kilvin-pages-check` against the already-deployed Pages URL
- `make kilvin-real-smoke` if the local Colima/Temporal/k3s stack is available

## Acceptance Criteria

- Future agents can discover the repo-local skills in `.agents/skills/`.
- A human can run the local happy path from `docs/kilvin/real-local-runbook.md`.
- `make kilvin-doctor` gives a clear preflight report.
- `make kilvin-real-smoke` either proves the real Temporal/k3s training path or fails with a concrete missing proof.
- `make kilvin-pages-check` proves the public explorer data has deployed.
- No personal/global skill files are modified.
