---
name: kilvin-real-runtime
description: Use when running, debugging, or proving Temporalis Kilvin real-runtime work, including local Temporal, allocator, docker image builds, registry, k3s jobs, Colima setup, workflow smoke tests, or live training artifacts.
---

# Kilvin Real Runtime

Use this repo-local skill before touching or validating the real Kilvin runtime.

## Start Here

Run the preflight first:

```bash
make kilvin-doctor
```

If the doctor fails, read:

```text
docs/kilvin/troubleshooting-colima.md
```

Then run the canonical proof:

```bash
make kilvin-real-smoke
```

## Operator Path

1. Read `docs/kilvin/real-local-runbook.md`.
2. Run `make kilvin-doctor`.
3. Start infra only if needed:

   ```bash
   cd kilvin-py
   ./infra/up.sh
   ```

4. Run `make kilvin-real-smoke`.
5. Check the proof against `docs/kilvin/proof-checklist.md`.

## What Counts As Real Proof

The smoke proof is not just "tests passed." It must show:

- Temporal workflow completed.
- Six Kilvin steps succeeded.
- `concretize_dependencies` wrote a digest-pinned image.
- allocator granted quota and released it.
- k3s Job completed.
- trainer logs include `TRAINING_DONE`.
- `.kilvin-artifacts/<run-id>/...` contains the step artifacts.

## Common Mistakes

- Starting with UI/docs changes before `make kilvin-doctor`.
- Treating Colima, DNS, proxy, or k3s registry failures as incidental.
- Running a workflow but not proving allocator release or trainer logs.
- Leaving proof scripts in `.agent/` instead of making them repo tools.

## Related Commands

```bash
make kilvin-doctor
make kilvin-real-smoke
make kilvin-pages-check
```
