# Temporal Internals For A Training Run

This guide explains what Temporal is doing when Temporalis asks for one
production-shaped run: **train model X on FineWeb with 64 A100 GPUs**. The
runnable Kilvin path shrinks that request to a laptop-scale tiny-GPT job, but
the Temporal shape is the same: durable decisions in workflow history,
retryable side effects in activities, workers polling task queues, and operators
inspecting the run through source-grounded state.

Use this page after Basics, then open **Deep Dive / Lifecycle** and **Deep Dive /
Control Paths** for the upstream source links. Those diagrams cite pinned
Temporal server, SDK Core, SDK Python, Temporal UI, and Kilvin source refs.

## One Run Through The System

The start request enters Temporal as a `StartWorkflowExecution` call. In the
teaching story, that request says "train model X on FineWeb with 64 A100 GPUs."
In the local proof, `kilvin-py/start_workflow.py` submits the same shaped intent
to one `KilvinTrainingWorkflow`.

Temporal then splits responsibility across services and SDK layers:

| Layer | What it owns | Training-system meaning |
| --- | --- | --- |
| Frontend | Accepts client RPCs such as workflow start, signal, query, cancellation, and history reads. | The user or operator has one durable API surface for launch and inspection. |
| History | Appends workflow events, schedules workflow tasks and activity tasks, records timers, retries, cancellations, heartbeats, and completions. | The training run has an auditable source of truth instead of relying on process memory. |
| Matching | Owns task queues and dispatches workflow task and activity task work to polling workers. | Build, quota, launch, and monitoring work can be routed to workers with the right environment. |
| SDK Core | Polls task queues, constructs workflow activations, accepts workflow completions, mediates replay, tracks activity heartbeat state, and manages sticky cache behavior. | The worker can restart or replay without accidentally rebuilding images, reserving quota twice, or resubmitting a job. |
| SDK Python | Bridges Core to Python workflow turns and activity functions. | Kilvin can teach the orchestration in ordinary Python while still using Temporal's durable machinery. |
| Temporal UI | Reads workflow details and event history for operator inspection. | A training operator can inspect the recorded run rather than guessing from scattered logs. |

## Workflow Tasks Are Durable Decisions

A workflow task is Temporal asking workflow code, "Given the recorded history,
what commands should happen next?" SDK Core turns server history into an
activation. SDK Python runs the workflow turn. The workflow emits a completion
containing commands such as "schedule the dependency concretization activity" or
"schedule the materialize job spec activity."

For Kilvin, workflow code owns decisions like:

- accept the model-X/FineWeb intent;
- move from intent materialization to dependency concretization;
- wait for quota before materializing the launch plan;
- schedule monitoring after Kubernetes submission;
- record signals that pause, resume, cancel, or request targeted replay.

That is why replay is safe. During replay, workflow code rebuilds decision state
from history. It does not repeat side effects that were already recorded as
completed activity results.

## Activity Tasks Are Side-Effect Boundaries

An activity task is Temporal asking activity code to do something outside
workflow memory. Kilvin uses activities for the pieces a real training platform
cannot treat as pure decisions:

- dependency concretization builds or selects the image, lockfile, code refs,
  and runtime environment;
- quota and allocation reserve scarce capacity;
- materialized launch spec generation writes the concrete Kubernetes request;
- Kubernetes submission creates the Job;
- monitoring polls job status, logs, checkpoints, and progress.

Activities can retry because their results are recorded in history. A failed
allocator call can be retried without replaying the whole workflow. A monitor can
recover using activity heartbeat details instead of starting blind.

## Matching And Task Queues Route Work

Matching is the service that makes task queues real. Workers poll a task queue;
Matching hands them workflow task and activity task work.

For model training, task queues are a useful control-plane boundary. Dependency
builds may need Docker and registry access. Quota calls may need allocator
credentials. Kubernetes submission may need cluster credentials. Monitoring may
need log and checkpoint access. The teaching repo keeps one small worker, but
the same queue boundary explains how a larger platform would route specialized
work safely.

## SDK Core And SDK Python Split The Worker

SDK Core handles the durable execution protocol: polling, activations,
completions, replay mediation, activity heartbeat plumbing, and sticky cache.
SDK Python presents that protocol as Python workflow and activity code.

The important split is practical:

- SDK Core preserves the Temporal invariants around history, replay, and
  completions;
- SDK Python lets Kilvin express the training orchestration in readable Python;
- sticky cache keeps common workflow turns fast, while replay remains the
  correctness fallback when cache state is unavailable.

This is also why workflow code must stay deterministic. During replay, the same
history must produce the same commands. Activity code is where nondeterministic
work belongs.

## Operator Control Is History, Not Hope

Signals, queries, cancellation, retries, timers, and heartbeats are the control
paths that make long-running training understandable.

Signals record operator intent such as pause, resume, cancel, or replay a
specific step. Queries read current workflow state without changing it.
Cancellation is delivered through Temporal history and worker protocol rather
than by hoping a process dies in the right place. Timers and retries make wait
and recovery behavior explicit. Activity heartbeat data lets long-running
monitoring report progress and resume from the last known point.

The **Deep Dive / Control Paths** view walks those cases with source refs. Read
it as a set of operator stories: "quota failed once," "the monitor lost its
worker," "an operator paused the run," or "sticky cache missed and replay
reconstructed state."

## Where Kilvin Fits

**Deep Dive / Kilvin Internals** maps the Temporal machinery back to the local
implementation:

- `workflows.py` is the durable decision layer;
- `activities.py` is the side-effect layer;
- `models.py` is the typed contract between steps;
- `artifacts.py` writes the inspectable YAML evidence;
- `worker.py` registers workflow and activities on the task queue;
- `start_workflow.py` submits the production-shaped intent.

Kilvin is intentionally small. It is not a full foundation-model platform. Its
job is to make the hard parts visible: intent materialization, dependency
concretization, quota and allocation, materialized launch spec, Kubernetes
submission, monitoring, signals, queries, retry, replay, and history.

## Reading Order

1. Read Basics for the vocabulary.
2. Read this guide for the control-plane story.
3. Open **Deep Dive / Lifecycle** and follow the source links for each call.
4. Open **Deep Dive / Control Paths** and compare retry, cancellation,
   heartbeat, pause/resume, and sticky replay.
5. Open **Deep Dive / Kilvin Internals** and connect the diagrams to
   `kilvin-py/`.
6. Run `make quickstart`, then use [Exercises](exercises.md) when you want to
   prove the path locally.
