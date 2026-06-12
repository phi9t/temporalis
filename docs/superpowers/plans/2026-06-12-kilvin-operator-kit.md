# Kilvin Operator Kit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repo-contained skills, docs, scripts, and Make targets that make the real Kilvin local runtime and GitHub Pages release proof repeatable.

**Architecture:** Shared agent guidance lives under `.agents/skills/`. Human-facing runbooks live under `docs/kilvin/`. Python scripts under `scripts/` provide the executable checks, and root Make targets expose stable command names.

**Tech Stack:** Python standard library, existing Kilvin scripts, Make, Docker/Colima, Temporal CLI when available, kubectl when available, GitHub Pages over HTTP.

---

### Task 1: Repo-local shared skills

**Files:**
- Create: `.agents/skills/kilvin-real-runtime/SKILL.md`
- Create: `.agents/skills/github-pages-release-verification/SKILL.md`

- [ ] Create the `kilvin-real-runtime` skill with triggers for running, debugging, or proving the real Kilvin stack.
- [ ] Create the `github-pages-release-verification` skill with triggers for verifying hosted Pages content after pushing generated explorer data.
- [ ] Keep both skills repo-specific and command-first: prefer Make targets, then docs, then manual diagnostics.

### Task 2: Operator docs

**Files:**
- Create: `docs/kilvin/real-local-runbook.md`
- Create: `docs/kilvin/proof-checklist.md`
- Create: `docs/kilvin/troubleshooting-colima.md`

- [ ] Write the real local runbook: doctor, infra up, worker, workflow, smoke proof, inspection commands, teardown.
- [ ] Write the proof checklist: digest, quota decision, step trace, k3s Job, trainer logs, allocator release, hosted Pages content.
- [ ] Write the Colima troubleshooting guide: PATH, context, amd64, Docker socket, DNS/PyPI, proxy/tunnel, compose build args, registry/k3s mirror.

### Task 3: Kilvin doctor script

**Files:**
- Create: `scripts/kilvin_doctor.py`
- Test: `tests/test_kilvin_operator_scripts.py`

- [ ] Add pure helpers for command lookup, TCP probes, HTTP probes, and PASS/WARN/FAIL result formatting.
- [ ] Add tests for result exit-code classification and expected string matching.
- [ ] Implement required checks for tools, Docker daemon/context, amd64 container execution, compose status, allocator health, Temporal port, kubeconfig, namespace, and registry port.
- [ ] Exit non-zero when required checks fail; print actionable remediation messages.

### Task 4: Real smoke script

**Files:**
- Create: `scripts/kilvin_real_smoke.py`
- Test: `tests/test_kilvin_operator_scripts.py`

- [ ] Add pure helpers for extracting `run_id` from `KILVIN_TRAINING_COMPLETED:<run_id>`.
- [ ] Add pure helpers for verifying artifact paths and required file contents.
- [ ] Implement live orchestration: optional infra start, child worker process, workflow start, artifact proof, optional Temporal/kubectl proof, allocator release proof, worker cleanup.
- [ ] Keep optional tools as WARN and required proof as FAIL.

### Task 5: GitHub Pages verifier

**Files:**
- Create: `scripts/kilvin_pages_check.py`
- Test: `tests/test_kilvin_operator_scripts.py`

- [ ] Add pure helper `missing_expected_strings(body, expected)` and test it.
- [ ] Implement polling with cache-busting query params.
- [ ] Distinguish HTTP failure from content-not-yet-updated.
- [ ] Default to the current public `kilvin/internals.json` URL.

### Task 6: Make targets and validation

**Files:**
- Modify: `Makefile`

- [ ] Add `kilvin-doctor`, `kilvin-real-smoke`, and `kilvin-pages-check`.
- [ ] Run focused tests for script helpers.
- [ ] Run broad Python tests if dependencies are available.
- [ ] Run `make kilvin-pages-check` against the already-deployed Pages URL.
- [ ] Run `make kilvin-doctor` if Docker/Colima is reachable in this session.
- [ ] Run `make kilvin-real-smoke` if the live stack remains available and network/proxy state is healthy.
