# Kilvin Proof Checklist

Use this checklist before claiming the real Kilvin path works.

## Local Runtime Proof

- `make kilvin-doctor` has no `FAIL` rows.
- `make kilvin-real-smoke` exits 0.
- Workflow result contains `KILVIN_TRAINING_COMPLETED:<run-id>`.
- Temporal trace has these six steps with `SUCCEEDED` status:
  - `interpret_intent`
  - `concretize_dependencies`
  - `allocate_resources`
  - `materialize_training_bundle`
  - `submit_k8s_job`
  - `monitor_training`
- `concretize_dependencies/out.yaml` contains a `sha256:` image digest.
- `allocate_resources/quota_decision.yaml` shows a real local allocator grant.
- `materialize_training_bundle/env_vars.yaml` matches the trainer job contract.
- k3s Job in namespace `kilvin-training` completed.
- `monitor_training/logs.yaml` contains `TRAINING_DONE`.
- `curl http://localhost:7070/v1/allocations` returns an empty allocation list after completion.

## Control-Path Proof

At least one live control-path check should be run when changing workflow signal, query, retry, or monitor behavior:

- pause before a worker polls, then resume and complete
- or force allocator quota exhaustion, observe Temporal retry, release quota, then complete

These checks belong in scripts or docs, not only in `.agent/` scratch files.

## Hosted Release Proof

After pushing explorer/generated-data changes:

```bash
make kilvin-pages-check
```

The public Pages JSON should include:

- `laptop scale`
- `uv lock --check`
- `local allocator`
- `k3s`

## Git Hygiene

- Implementation files are tracked.
- Scratch proof files remain under ignored local directories such as `.agent/`.
- Unrelated dirty files are called out instead of reverted.
- Push approval is explicit before publishing.
