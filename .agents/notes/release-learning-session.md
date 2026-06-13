# Release Learning Session

This note preserves durable agent-facing context harvested from earlier local `.agent/` scratch work. It is not the public quickstart; public instructions live in `README.md`, `docs/quickstart.md`, and `docs/runtime-proof.md`.

## Task

Unify the teaching story across `kilvin-py/` and `explorer/`: one researcher intent
(`train model X on FineWeb with 64 A100 GPUs`) becomes one Temporal workflow that
materializes dependencies, placement, launch spec, Kubernetes submission, and monitoring.
The explorer should introduce the story, then use the same story to enter Temporal internals.

## Findings

- The explorer has already converged on one Basics -> Deep Dive -> Hacker's Guide path.
- `DeepDiveExplorer` uses a shared swimlane for lifecycle and control overlays; Lifecycle keeps the source/detail drawer, while Control Paths should stay swimlane-first.
- `kilvin-py` now models one pretrain stage and persists hood-open artifacts: `quota_decision`, `env_vars`, and `logs`.
- Remaining drift found in the earlier pass: `kilvin-py/README.md` used workflow id examples that did not match `start_workflow.py`.
- Remaining drift found in the current pass: Control Paths still rendered the source/detail drawer, and workflow skip/replay fallback values used a less specific model-X checkpoint/profile than the normal activity path.
- Old CMD outer-loop references are absent from app/demo code; remaining `cmd` references are historical design docs.

## Task Spec

1. Preserve the simple story as the public frame: no CMD outer-loop language in app/demo surfaces.
2. Make `kilvin-py` executable docs and code agree on workflow id, task queue, activity names, and artifact names.
3. Add tests that prove the runnable demo stays aligned with the explorer claims.
4. Keep Deep Dive as the internals bridge: lifecycle and control overlays share the same swimlane vocabulary; Lifecycle keeps detailed source evidence, Control Paths stays focused on the overlay swimlane.
5. Do an aesthetic assessment in-browser against the current UI, not just unit tests.

## Aesthetic Assessment Rubric

- First screen should read as one clear training-run story, not a generic Temporal marketing page.
- Timeline cards should scan before reading: cue badges, subprocess cards, and trace buttons must be visible without visual clutter.
- Deep Dive should look like a technical instrument: full-width swimlane, clear User app / Worker / Temporal server lanes, and no clipping.
- Control-path overlays should feel related to the happy path, not like a separate diagram language, and should not be visually competed with by the old right-side drawer.
- Text should not overlap, overflow buttons, or create nested-card clutter at desktop and a narrower viewport.

## Validation Plan

- Focused Python tests for the Kilvin story invariants and artifact names.
- `PATH=/Users/bytedance/.nvm/versions/node/v24.13.0/bin:$PATH npm test` from `explorer`.
- `PATH=/Users/bytedance/.nvm/versions/node/v24.13.0/bin:$PATH npm run build` from `explorer`.
- Focused lifecycle-data tests when source anchors or generated data are touched.
- Browser checks for Basics and Deep Dive at desktop and narrower widths.

## Validation Results

- Direct Kilvin invariant execution through `.venv/bin/python`: passed `tests/test_kilvin_training_story.py` test functions manually because local pytest is not installed.
- `.venv/bin/python -m compileall -q kilvin-py tests/test_kilvin_training_story.py`: passed.
- `PATH=/Users/bytedance/.nvm/versions/node/v24.13.0/bin:$PATH npm test` from `explorer`: 6 files passed, 25 tests passed. jsdom printed its known `window.scrollTo()` warning.
- `.venv/bin/python explorer/scripts/build_lifecycle_data.py --repo-root .`: passed and refreshed source-ref line numbers.
- `PATH=/Users/bytedance/.nvm/versions/node/v24.13.0/bin:$PATH npm run build` from `explorer`: passed after data regeneration.
- Browser aesthetic pass on `http://127.0.0.1:5173/`:
  - Desktop Basics: story, cue legend, trace buttons, Kilvin panel present; no sampled control/card overflow.
  - Desktop Deep Dive lifecycle/control: swimlane, lanes, legend, detail panel, and overlay framing present; no sampled overflow.
  - Narrow 390px Basics: no page-wide overflow.
  - Narrow 390px Deep Dive: no page-wide overflow; swimlane uses internal horizontal scroll.
- Text audit excluding build output: no old CMD framing in app/demo/guide surfaces; only test helper variable names and negative assertions remain.
- Added a red/green regression test proving Control Paths renders the swimlane and overlay framing without `Read / Run / Inspect` drawer chrome.
- Added a red/green Kilvin consistency check proving workflow skip paths use the same model-X base checkpoint, model, dataset root, and dependency fallback as the normal activity path.

## Remaining Risk

- Local `.venv` lacks pytest, so focused Python tests were executed directly but not through pytest collection in this environment.

---

## 2026-06-13 Teaching Bridge Update

## Task

Improve Temporalis as public learning material for both Temporal internals and
modern model training, using the captured Fable planning transcripts to motivate
the complex training regime while keeping Kilvin simple.

## Decision

Keep `kilvin-py/` as the smallest real slice of the control plane: one workflow,
six activities, one local allocator, one k3s Job, and inspectable YAML artifacts.
Use docs and explorer copy to explain how that slice grows into multi-phase
training programs with dependency pinning, scarce GPU quota, placement, launch
spec materialization, long-running monitoring, pause/resume, and targeted replay.

## Files Updated

- `docs/model-training-systems.md`: public bridge from the laptop-scale Kilvin
  proof to real foundation-model training systems.
- `README.md`: links the bridge from the top-level teaching story.
- `docs/quickstart.md`: tells hosted and local learners when to read the bridge.
- `kilvin-py/README.md`: clarifies that Kilvin is intentionally not a full
  foundation-model platform.
- `tests/test_public_release_readiness.py`: regression coverage for the public
  teaching bridge.

---

## 2026-06-12 Real-Infra Execution Update

## Task

Execute `fable-kilvin-real-implementation.txt`, whose actionable plan is
`docs/superpowers/plans/2026-06-12-kilvin-real-infra.md`: make `kilvin-py`
real at laptop scale while preserving the production-shaped teaching story.

## Repo Findings And Files Inspected

- The transcript file is a captured Claude session; the canonical plan is
  `docs/superpowers/plans/2026-06-12-kilvin-real-infra.md`.
- The branch is `phi9t-mainline`, currently ahead of `origin/phi9t-mainline`.
- The implementation spans:
  - `kilvin-py/trainer/` for the tiny CPU GPT trainer and image build target.
  - `kilvin-py/infra/allocator/` for the finite resource ledger service.
  - `kilvin-py/infra/docker-compose.yml`, `up.sh`, `down.sh`, and k3s registry config.
  - `kilvin-py/kilvin_py/{activities,models,workflows,config,proc,allocator_client,k8s_manifest,k8s_jobs}.py`.
  - `tests/infra/test_allocator.py`, `tests/test_kilvin_helpers.py`, `tests/test_kilvin_training_story.py`.
  - `explorer/scripts/build_lifecycle_data.py`, generated explorer data, Basics, guide, and READMEs.

## Current Understanding

- The workflow still starts from the production-shaped request: train model X on
  FineWeb with 64 A100 GPUs.
- `interpret_training_intent` maps that intent to a laptop-scale trainer config:
  tiny CPU GPT-2, 2 CPUs, 4GB, local image tag, and env-var contract.
- `concretize_dependencies` is intentionally real-only: `uv lock --check`,
  `docker build`, `docker push`, and `docker inspect` for a digest.
- `allocate_resources` talks to the allocator HTTP service. HTTP 409 becomes a
  retryable Temporal activity error; unavailable allocator is non-retryable with
  the `kilvin-py/infra/up.sh` hint.
- `materialize_training_bundle` renders the Kubernetes Job as the literal launch
  spec with `backoffLimit: 0`, because Temporal owns activity retries.
- `submit_k8s_job` and `monitor_training` use the lazy Kubernetes wrapper so
  normal unit tests do not require the package or cluster.

## Design Decisions

- Checked in trainer and allocator `uv.lock` with `git add -f` because root
  `.gitignore` ignores `uv.lock`.
- Kept Docker/k3s/Temporal as prereqs instead of stubbing the live gate; the plan
  explicitly wants a real Tier 2 run.
- Committed the CSS mobile-overflow fix separately because it was discovered by
  the aesthetic pass, not by the authored story update.

## Validation Commands And Results

- Trainer smoke:
  `UV_CACHE_DIR=/private/tmp/temporalis-uv-cache MAX_STEPS=5 N_LAYER=2 N_EMBD=64 BLOCK_SIZE=64 OUT_DIR=/private/tmp/kilvin-trainer-out .venv/bin/uv run python trainer.py`
  - Produced `TRAINING_DONE run_id=local final_loss=4.1412`.
  - Metrics: `{"steps": 5, "first_loss": 4.1843, "final_loss": 4.1412, ...}`.
- Python:
  `UV_CACHE_DIR=/private/tmp/temporalis-uv-cache .venv/bin/uv run --with pytest --with pytest-asyncio --with httpx --with fastapi python -m pytest tests/ -q`
  - Needed sandbox escalation for Temporal ephemeral server processes.
  - Result: `99 passed, 1 warning`.
  - Warning: FastAPI/Starlette `httpx` deprecation from `TestClient`.
- Explorer:
  `PATH=/Users/bytedance/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/vitest run --environment jsdom`
  - Result: 6 files, 28 tests passed; jsdom printed known `window.scrollTo()` warnings.
  `PATH=/Users/bytedance/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/tsc -b && .../vite build`
  - Result: passed.
- Browser visual:
  - Preview ran on `http://localhost:4173/`.
  - Desktop Basics: new laptop-scale copy visible, no horizontal overflow.
  - Mobile 390x844 Kilvin Internals: allocate step copy visible and `document.documentElement.scrollWidth === 390`.
  - Screenshots saved to `/private/tmp/temporalis-basics-desktop.png` and `/private/tmp/temporalis-kilvin-mobile.png`.
- Terminology:
  `rg -n -i "primus|ream" kilvin-py explorer/src explorer/scripts HACKERS_GUIDE.md --glob '*.py' --glob '*.tsx' --glob '*.md' --glob '!**/.venv/**' --glob '!**/__pycache__/**'`
  - Only substring hits remain inside words such as `workflow_stream`, `downstream`, and `streaming`.

## Missing Evidence / Blockers

- Live validation completed after bringing Colima up with Homebrew on PATH and
  routing Python package downloads through a local CONNECT proxy/tunnel.
- Main run:
  - Workflow `kilvin-training-run-191a558d` completed with
    `KILVIN_TRAINING_COMPLETED:run-191a558d`.
  - k3s Job `kilvin-pretrain-7c4965` completed `1/1`.
  - `concretize_dependencies/out.yaml` includes
    `image_digest: sha256:1d32bbeba3ef5b2822fe8b7d5f8885b80911b6eac63e48ffc8246974e8b267b6`.
  - `quota_decision.yaml` shows 2 CPUs / 4GB granted from 8 CPUs / 16GB free.
  - Trainer logs include `step=200 loss=2.4917` and
    `TRAINING_DONE run_id=run-191a558d final_loss=2.4917`.
  - Allocator `/v1/allocations` returned `{"allocations":[]}` after release.
- Control-path proof:
  - Started `kilvin-training-control-b745c494` with no worker polling, signaled
    pause, then started the worker.
  - Query returned `status=PAUSED paused=True current_step=None`.
  - Resume completed with `KILVIN_TRAINING_COMPLETED:control-b745c494`.
- Quota-contention proof:
  - Reserved all allocator capacity with blocker `alloc-eb22815152`.
  - `kilvin-training-quota-4ca1335f` reached pending `allocate_resources`
    `Attempt 4` with `QuotaExhausted: requested 2 cpus, 0 free`.
  - Releasing the blocker let the retry complete:
    `KILVIN_TRAINING_COMPLETED:quota-4ca1335f`.
- Updated the global `macos-colima-container-builder` skill with the proven
  Colima setup lessons: Homebrew PATH, health checks, proxy tunnel,
  explicit Docker/Compose build args, and localhost `NO_PROXY`.
- Push and Pages deploy verification are still pending.

## Final Teach-Back Questions

- Why does the Kubernetes Job use `backoffLimit: 0` when Temporal already has an
  activity retry policy?
- Which parts of the real-infra run are workflow state, and which are activity
  side effects that replay must not re-execute?
