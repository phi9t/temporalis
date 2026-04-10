# Veritas Testing Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a global Codex skill named `veritas-testing` that inspects arbitrary software repositories, interviews the user on testing ambiguities, writes `docs/veritas/` as a progressive-disclosure testing contract, and leaves a lightweight adherence/progress artifact.

**Architecture:** Install a new personal skill at `<codex-home>/skills/veritas-testing/` with a compact `SKILL.md` that encodes the orchestrator workflow and references optional detail files only when needed. Validate it by checking trigger metadata, reviewing the workflow against the approved spec, and pressure-testing it with realistic prompts to ensure it inspects first, escalates smoke/live omissions, and writes `docs/veritas/` plus `progress.md`.

**Tech Stack:** Markdown skill authoring, Codex global skill layout, progressive disclosure references, shell-based validation, prompt-driven manual verification.

---

### Task 1: Create The Global Skill Skeleton

**Files:**
- Create: `<codex-home>/skills/veritas-testing/SKILL.md`
- Create: `<codex-home>/skills/veritas-testing/references/artifact-layout.md`
- Create: `<codex-home>/skills/veritas-testing/references/interview-topics.md`
- Create: `<codex-home>/skills/veritas-testing/references/progress-template.md`

- [ ] **Step 1: Create the skill directory structure**

Run:

```bash
mkdir -p "$CODEX_HOME/skills/veritas-testing/references"
```

Expected: the `veritas-testing` skill directory and `references/` subdirectory exist.

- [ ] **Step 2: Write the initial `SKILL.md` frontmatter and overview**

Create `<codex-home>/skills/veritas-testing/SKILL.md` with this header:

```md
---
name: veritas-testing
description: Use when designing, revising, or rationalizing a repository's testing strategy, especially when you need a durable contract across unit, integration, smoke, and live layers plus a lightweight way to track adherence.
---

# Veritas Testing

## Overview

Design a repository-specific testing doctrine by inspecting the repo first, interviewing the human only on ambiguity, writing the resulting contract under `docs/veritas/`, and initializing a lightweight progress reflection.
```

- [ ] **Step 3: Add the artifact layout reference**

Create `<codex-home>/skills/veritas-testing/references/artifact-layout.md` with:

```md
# Artifact Layout

Canonical structure:

- `docs/veritas/README.md`
- `docs/veritas/layers.md`
- `docs/veritas/tooling.md`
- `docs/veritas/progress.md`

Optional companion docs:

- `docs/veritas/fixtures.md`
- `docs/veritas/ci.md`
- `docs/veritas/live-tests.md`
- `docs/veritas/safety.md`

The root README stays concise and stable. Push detail into companion docs when possible.
```

- [ ] **Step 4: Add the interview topics reference**

Create `<codex-home>/skills/veritas-testing/references/interview-topics.md` with:

```md
# Interview Topics

Ask only after repo inspection and only one question at a time.

Likely ambiguity topics:

- release and risk profile
- what “live” means in this repo
- current test pain
- environment and secret constraints
- whether smoke or live are intentionally absent
- cost or fragility of higher-order test layers
```

- [ ] **Step 5: Add the progress template reference**

Create `<codex-home>/skills/veritas-testing/references/progress-template.md` with:

```md
# Progress Template

Use this structure in `docs/veritas/progress.md`:

- `Following`
- `Partially following`
- `Not yet addressed`
- `Human decision required`

Each entry should mention:

- work item or area
- relevant Veritas rule or section
- current status or explicit waiver
```

- [ ] **Step 6: Verify the skeleton exists**

Run:

```bash
find "$CODEX_HOME/skills/veritas-testing" -maxdepth 2 -type f | sort
```

Expected: `SKILL.md` and the three reference files are present.

- [ ] **Step 7: Commit**

```bash
ls -la "$CODEX_HOME/skills/veritas-testing" "$CODEX_HOME/skills/veritas-testing/references"
```

Expected: the new skill files are visible and readable.

### Task 2: Encode The Orchestrator Workflow In `SKILL.md`

**Files:**
- Modify: `<codex-home>/skills/veritas-testing/SKILL.md`

- [ ] **Step 1: Add the mandatory operating sequence**

Extend `SKILL.md` with this section:

```md
## Required Sequence

1. Inspect the repository before asking substantive questions.
2. Summarize the current test reality.
3. Ask one question at a time only where ambiguity remains.
4. Propose a layered strategy using best judgment.
5. Require explicit human justification for omitted or minimized smoke/live layers.
6. Write or update `docs/veritas/`.
7. Initialize or refresh `docs/veritas/progress.md`.
8. Present the resulting doctrine and ask for approval before implementation-oriented planning.
```

- [ ] **Step 2: Add repo-inspection rules**

Append:

```md
## Repository Inspection

Inspect before interviewing. Gather evidence from:

- test directories and naming
- package manifests and build files
- CI config
- container/dev environment config
- developer docs
- fixture directories
- smoke/e2e/live markers
- recent testing conventions visible in the repo

Do not ask the human questions the repository already answers.
```

- [ ] **Step 3: Add smoke/live escalation rules**

Append:

```md
## Layering Rules

Treat `unit`, `integration`, `smoke`, and `live` as candidate layers, not mandatory labels in every repo.

However:

- If `smoke` is omitted or minimized, require explicit justification and ask the human for the final verdict.
- If `live` is omitted or minimized, require explicit justification and ask the human for the final verdict.
```

- [ ] **Step 4: Add progressive disclosure instructions**

Append:

```md
## Repository Artifacts

Always write or update `docs/veritas/`.

Use progressive disclosure:

- Keep `docs/veritas/README.md` concise and stable.
- Read `references/artifact-layout.md` when creating or revising the artifact structure.
- Push detail into companion docs when the root contract would otherwise become bloated.
```

- [ ] **Step 5: Add progress reflection instructions**

Append:

```md
## Progress Reflection

Always initialize or refresh `docs/veritas/progress.md`.

Read `references/progress-template.md` when writing the file.

Use a lightweight reflection rather than a formal scorecard.
```

- [ ] **Step 6: Run a content review on `SKILL.md`**

Run:

```bash
sed -n '1,260p' "$CODEX_HOME/skills/veritas-testing/SKILL.md"
```

Expected: the workflow is complete, concise, and aligned with the spec.

- [ ] **Step 7: Commit**

```bash
wc -l "$CODEX_HOME/skills/veritas-testing/SKILL.md"
```

Expected: `SKILL.md` stays comfortably compact and does not balloon into a reference dump.

### Task 3: Add Trigger Guidance, Outputs, And Guardrails

**Files:**
- Modify: `<codex-home>/skills/veritas-testing/SKILL.md`

- [ ] **Step 1: Add trigger examples**

Append:

```md
## When to Use

Use this skill when the user:

- asks for a comprehensive testing strategy
- asks how tests should be structured in a repo
- asks for unit/integration/smoke/live coverage design
- asks to rationalize or improve testing architecture
- wants a persistent testing doctrine for a repo
- wants agents to reflect adherence to testing policy
```

- [ ] **Step 2: Add required outputs**

Append:

```md
## Required Outputs

Every invocation should aim to produce:

1. repo assessment
2. proposed test architecture
3. human decisions needed
4. `docs/veritas/` written or updated
5. `docs/veritas/progress.md` initialized or refreshed
```

- [ ] **Step 3: Add internal guardrails**

Append:

```md
## Guardrails

- Inspect first, ask later.
- Prefer inference over user burden.
- Ask one question at a time.
- Keep the root Veritas doc concise.
- Challenge stale or weak doctrine.
- Do not silently waive smoke/live layers.
- Keep progress reflection current.
```

- [ ] **Step 4: Add on-demand references guidance**

Append:

```md
## On-Demand Detail

- Read `references/interview-topics.md` when repo inspection leaves real ambiguity.
- Read `references/artifact-layout.md` when writing or revising `docs/veritas/`.
- Read `references/progress-template.md` when updating `docs/veritas/progress.md`.
```

- [ ] **Step 5: Verify the final skill text**

Run:

```bash
sed -n '1,320p' "$CODEX_HOME/skills/veritas-testing/SKILL.md"
```

Expected: the skill is complete, coherent, and uses progressive disclosure correctly.

- [ ] **Step 6: Commit**

```bash
grep -n "smoke\\|live\\|docs/veritas\\|progress.md" "$CODEX_HOME/skills/veritas-testing/SKILL.md"
```

Expected: the critical rules are explicitly present.

### Task 4: Validate The Skill Against Pressure Scenarios

**Files:**
- Create: `<codex-home>/skills/veritas-testing/references/validation-scenarios.md`

- [ ] **Step 1: Add validation scenarios**

Create `<codex-home>/skills/veritas-testing/references/validation-scenarios.md` with:

```md
# Validation Scenarios

Pressure scenarios:

1. Repo with only unit tests and no smoke/live coverage
   - Expected: infer current state, propose higher layers, require explicit human verdict if omitted

2. Repo with heavy end-to-end tests but weak unit layering
   - Expected: rebalance toward cheaper lower layers where appropriate

3. Repo with CI but no local testing docs
   - Expected: capture local-vs-CI execution guidance in `docs/veritas/tooling.md`

4. Repo with sensitive prod dependencies
   - Expected: define what “live” means safely and restrict default automation
```

- [ ] **Step 2: Run a static validation pass**

Run:

```bash
find "$CODEX_HOME/skills/veritas-testing" -maxdepth 2 -type f | sort | xargs -I{} sh -c 'echo "==== {}"; sed -n "1,220p" "{}"'
```

Expected: files are coherent, references are named correctly, and no paths are broken.

- [ ] **Step 3: Perform a manual pressure-test review**

Use these prompts manually against the skill:

```text
Design a comprehensive test strategy for this repo across unit/integration/smoke/live.
We only have unit tests today. Smoke and live are probably too expensive.
```

Expected behavior:

- inspect-first posture
- one-question-at-a-time ambiguity handling
- explicit challenge on skipping smoke/live
- `docs/veritas/` artifact orientation
- progress reflection orientation

- [ ] **Step 4: Tighten any loopholes found during review**

If the skill text implies that smoke/live can be skipped casually, or fails to push toward `docs/veritas/`, update `SKILL.md` immediately and re-run Step 2.

- [ ] **Step 5: Commit**

```bash
grep -R "docs/veritas\|progress.md\|human verdict\|explicit justification" "$CODEX_HOME/skills/veritas-testing"
```

Expected: the validation scenarios and skill text both reinforce the core contract.

### Task 5: Final Verification And Availability Check

**Files:**
- Modify: `<codex-home>/skills/veritas-testing/SKILL.md`
- Modify: `<codex-home>/skills/veritas-testing/references/*.md`

- [ ] **Step 1: Verify the skill is in the personal global skills path**

Run:

```bash
find "$CODEX_HOME/skills/veritas-testing" -maxdepth 2 -type f | sort
```

Expected: the skill is installed at the correct global Codex location.

- [ ] **Step 2: Verify the superpowers symlink state remains healthy**

Run:

```bash
readlink -f "$HOME/.agents/skills/superpowers"
```

Expected: still points to `<codex-home>/superpowers/skills`.

- [ ] **Step 3: Perform a final spec-to-skill audit**

Checklist:

- repo inspection first
- one-question-at-a-time interview
- best-judgment layering
- explicit smoke/live escalation
- stable `docs/veritas/`
- progressive disclosure
- lightweight progress reflection

If any item is weak or ambiguous in the actual skill text, patch it before completion.

- [ ] **Step 4: Record the handoff note**

Prepare a short handoff summary noting:

- skill path
- core trigger conditions
- expected repo artifacts
- the fact that smoke/live omissions require explicit human verdicts

- [ ] **Step 5: Commit**

```bash
ls -la "$CODEX_HOME/skills/veritas-testing" "$CODEX_HOME/skills/veritas-testing/references"
```

Expected: final skill files are present and ready for use.
