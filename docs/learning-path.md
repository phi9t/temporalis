# Learning Path

Temporalis is easiest to read as one story with three layers:

1. the training request: **train model X on FineWeb with 64 A100 GPUs**;
2. the Temporal machinery that makes the request durable;
3. the small Kilvin implementation that proves the shape locally.

Use this path when you want to understand both Temporal internals and modern
model-training orchestration without losing the thread.

## 1. Start With The Explorer

Open <https://phi9t.github.io/temporalis/> and read **Basics** first.

Basics teaches the vocabulary:

- workflow: the durable decision process;
- activity: retryable side effects such as dependency builds, quota calls, and
  Kubernetes submission;
- worker: the process that polls for workflow and activity tasks;
- task queue: the routing layer between Temporal and workers;
- history: the durable source of truth;
- replay: how Temporal reconstructs state after worker restarts.

Pause at the section titled **Why the small demo has a production-shaped
request**. That is the bridge from Kilvin's small local proof to real training
systems: multi-phase runs, token budgets, CUDA/NCCL/Torch compatibility, GPU
quota, materialized launch specs, and operator controls.

## 2. Follow The Temporal Internals

Switch to **Deep Dive / Lifecycle**.

Read it as the path of one workflow task:

- the client starts the workflow;
- the server records history;
- matching routes tasks to workers;
- SDK Core polls and builds activations;
- SDK Python runs workflow and activity code;
- completions and new commands go back to the server;
- UI/operator views read recorded history.

Then switch to **Deep Dive / Control Paths**.

Control paths explain why Temporal is useful for training systems:

- retries re-run failed activities without replaying completed decisions;
- cancellation records operator intent instead of relying on process death;
- heartbeats let long monitors resume from known progress;
- pause/resume and targeted replay become explicit events in history;
- sticky replay keeps common workflow turns fast while preserving correctness.

Every Lifecycle call and Control Path step includes source refs. Treat those
links as the ground truth when the prose is too high level.

## 3. Map The Story To Kilvin Code

Switch to **Deep Dive / Kilvin Internals**, then inspect these files:

| Concept | File | What to notice |
| --- | --- | --- |
| Workflow orchestration | `kilvin-py/kilvin_py/workflows.py` | One `KilvinTrainingWorkflow` coordinates the run and records signal/query control state. |
| Activity side effects | `kilvin-py/kilvin_py/activities.py` | Dependency concretization, resource allocation, bundle materialization, k8s submission, and monitoring are activities. |
| Typed intent and results | `kilvin-py/kilvin_py/models.py` | The run moves through typed contracts instead of loose JSON blobs. |
| Artifacts | `kilvin-py/kilvin_py/artifacts.py` | Each step writes inspectable YAML evidence. |
| Worker registration | `kilvin-py/worker.py` | The worker binds activities and workflow code to the task queue. |
| Start request | `kilvin-py/start_workflow.py` | The production-shaped intent enters the local proof. |

The key teaching point: Kilvin is small, but it has the same control-plane
shape a larger training system needs.

## 4. Learn The Training-System Concerns

Read [Durable Model Training Systems](model-training-systems.md) after the
Basics page. Keep these correspondences in mind:

| Training concern | Kilvin foundation | Temporal concept |
| --- | --- | --- |
| Dependency builds and image pinning | `concretize_dependencies` | retryable activity with durable output |
| Research intent to launch plan | `interpret_training_intent` | workflow-owned decision state |
| Scarce quota and placement | `allocate_resources` | activity retries plus recorded reservation state |
| Concrete Kubernetes launch | `materialize_training_bundle` and `submit_k8s_job` | materialized commands in history plus side-effect boundaries |
| Long-running monitoring | `monitor_training` | activity heartbeats and retry recovery |
| Operator changes | `pause`, `resume`, `cancel`, `replay_step` | signals recorded as history events |
| Debugging and inspection | YAML artifacts plus Temporal UI/history | durable evidence instead of implicit process memory |

## 5. Run The Proofs

For a fresh clone or quick teaching session:

```bash
make quickstart
make explorer-dev
```

For the optional real local workflow:

```bash
make kilvin-doctor
kilvin-py/infra/up.sh
make runtime-proof
```

The first path proves the learning materials and generated source-grounded data.
The second path proves the local Temporal workflow, allocator, registry, k3s
Job, monitor, and artifacts.

## 6. What You Should Be Able To Explain

After walking this path, you should be able to answer:

- Why should workflow code own decisions while activities own side effects?
- Why does history matter more than process memory?
- Why can retries be safe for dependency builds, quota calls, and monitoring?
- How do activity heartbeats help long-running training monitors recover?
- Why does materializing a launch spec make debugging easier?
- How can a small local Kilvin workflow teach the shape of a larger
  foundation-model training platform?

If those questions feel clear, the repo has done its job: Temporal internals and
training-system operations are part of the same durable execution story.
