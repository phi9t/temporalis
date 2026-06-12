# Runtime Proof

The runtime proof is the optional Tier 2 path. It runs the Kilvin workflow locally with real side effects: Temporal, a Python worker, uv+docker image materialization, an allocator ledger, a local registry, k3s Job submission, monitoring, and artifacts.

Start with the doctor. After it passes, start the local Kilvin infrastructure and run the proof:

```bash
make kilvin-doctor
kilvin-py/infra/up.sh
make runtime-proof
```

Use `docs/kilvin/real-local-runbook.md` when you want to run each component manually. Use `docs/kilvin/proof-checklist.md` to confirm a completed run has real evidence: image digest, quota decision, materialized env vars, k3s Job completion, trainer logs, allocator release, and Temporal workflow completion.

This is a laptop-scale proof. The story begins with a production-shaped 64-A100/FineWeb request, but the local proof uses a tiny CPU GPT trainer and local k3s.
