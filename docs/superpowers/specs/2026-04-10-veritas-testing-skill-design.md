# Veritas Testing Skill Design

## Goal

Create a global Codex skill for any software repository that:

- inspects the repo and infers the current testing model
- interviews the human only where ambiguity remains
- designs a comprehensive test architecture across unit, integration, smoke, and live layers using best judgment
- writes the result as a stable, progressive-disclosure repository contract under `docs/veritas/`
- leaves behind a lightweight progress reflection showing how much current work follows the Veritas contract

## Scope

This design covers:

- a personal global Codex skill under `<codex-home>/skills`
- behavior across arbitrary code repositories
- a repository-facing artifact layout under `docs/veritas/`
- a light adherence/progress mechanism

This design does not cover:

- project-specific implementation details for any one repository
- a formal compliance scoring engine
- automatic enforcement via CI or linters in v1

## Core Role

The skill is not just a “testing advice” skill. It is a reusable test-architecture and compliance skill.

Its responsibilities are:

1. Discover the repository’s current testing reality
2. Infer a reasonable target test architecture using model judgment
3. Interview the user only where ambiguity or tradeoffs remain
4. Write the result as a stable repository contract under `docs/veritas/`
5. Initialize or refresh a lightweight progress reflection showing how well current work follows the contract

## Naming Recommendation

Recommended skill name:

- `veritas-testing`

This name is short, memorable, and aligned with the repository contract directory name `docs/veritas/`.

## Triggering Conditions

The skill should trigger when the user:

- asks for a comprehensive testing strategy
- asks how tests should be structured in a repository
- asks for unit/integration/smoke/live coverage design
- asks to rationalize or improve testing architecture
- wants a persistent testing doctrine for a repo
- wants agents to reflect adherence to a testing policy

The description should focus on when to use it, not how it works.

## Operating Model

### Repo Inspection First

The skill must inspect the repository before asking substantive questions.

It should gather evidence from:

- test directories and file naming conventions
- package manifests and build files
- CI config
- container/dev environment config
- developer docs
- fixture directories
- smoke/e2e/live markers
- recent testing conventions visible in the repo

The user should not be asked questions the repository can already answer.

### Interview Only On Ambiguity

After inspection, the skill asks one question at a time only for unresolved tradeoffs.

Likely interview topics:

- release and risk profile
- what “live” should mean in the repo
- test pain points
- expensive or controversial layers
- constraints on environment access or secrets
- whether certain layers are intentionally absent

### Best-Judgment Layering

The skill should treat `unit`, `integration`, `smoke`, and `live` as candidate layers, not mandatory labels in every repo.

However:

- if `smoke` is omitted or minimized, the skill must require explicit justification
- if `live` is omitted or minimized, the skill must require explicit justification
- in both cases, the human user must make the final verdict

This keeps the skill opinionated without being mechanically rigid.

## Repository Artifacts

The repository contract should live under:

- `docs/veritas/`

Recommended structure:

- `docs/veritas/README.md`
  - canonical root contract
  - first file agents should read
  - concise, stable, operational
- `docs/veritas/layers.md`
  - on-demand definitions of unit/integration/smoke/live in this repo
  - examples and boundary rules
- `docs/veritas/tooling.md`
  - framework, runner, fixture, and environment details
- `docs/veritas/progress.md`
  - light progress reflection
- optional companion docs when justified:
  - `fixtures.md`
  - `ci.md`
  - `live-tests.md`
  - `safety.md`

## Stability Model

`docs/veritas/README.md` should be reasonably stable.

The skill should prefer:

- keeping root doctrine concise
- pushing detail into companion docs
- revising the root only when the actual doctrine changes

The skill should still actively challenge weak, stale, or under-specified doctrine. Stability is not an excuse to preserve bad policy.

## Progressive Disclosure

The skill must enforce progressive disclosure in the repository artifacts:

1. Root contract in `README.md`
2. Layer definitions in `layers.md`
3. Tooling/environment details in `tooling.md`
4. Optional focused docs only when the repo needs them

Agents should be able to get the repo’s testing contract quickly from the root document, and load further detail only on demand.

## Progress Reflection

V1 should use a lightweight progress mechanism, not a formal scorecard.

Recommended `docs/veritas/progress.md` structure:

- `Following`
- `Partially following`
- `Not yet addressed`
- `Human decision required`

Each entry should reference:

- the current work item or area
- the relevant Veritas rule or section
- what is missing, deferred, or explicitly waived

This gives the agentic system a concrete way to reflect adherence without turning the process into bureaucracy.

## Skill Workflow

The skill’s required sequence should be:

1. Inspect the repository
2. Summarize current test reality
3. Ask one question at a time on remaining ambiguity
4. Propose the layered test architecture
5. Require explicit human justification for omitted/minimized smoke or live layers
6. Write or update `docs/veritas/`
7. Initialize or refresh `docs/veritas/progress.md`
8. Present the resulting doctrine and ask for approval before proceeding to implementation-oriented planning

## Required Outputs

Every invocation should aim to produce:

1. `repo assessment`
2. `proposed test architecture`
3. `human decisions needed`
4. `docs/veritas/` written or updated
5. `progress reflection` initialized or refreshed

## Sub-Skill Position

V1 should be a single orchestrator skill rather than several mandatory sub-skills.

This avoids over-modularization and keeps triggering simple.

However, the design should leave room for future specialized helpers, such as:

- fixture strategy support
- live-test safety support
- CI matrix support

Those can be added later if repeated patterns justify them.

## Internal Rules For The Skill

The skill should explicitly instruct the agent to:

- inspect first, ask later
- prefer inference over user burden
- ask one question at a time
- write the contract in a clear, operational style
- keep the root Veritas doc concise
- require explicit human verdicts for missing or minimized smoke/live coverage
- keep a lightweight progress reflection current
- seek opportunities to challenge and improve the test doctrine over time

## Suggested Skill Description

Suggested draft:

`Use when designing, revising, or rationalizing a repository’s testing strategy, especially when you need a durable contract across unit, integration, smoke, and live layers plus a lightweight way to track adherence.`

## Acceptance Criteria

The skill is successful when:

- it works across arbitrary software repositories
- it inspects the repo before interviewing
- it converges on a reasonable layered test strategy using best judgment
- it writes a stable `docs/veritas/` contract with progressive disclosure
- it leaves a lightweight adherence/progress trail
- it escalates smoke/live omissions to explicit human decisions

## Recommended Next Step

Create the global skill at `<codex-home>/skills/veritas-testing/` with:

- `SKILL.md`
- optional supporting references only if needed after drafting

Keep the first version compact and strong. Do not prematurely split it into many helper skills.
