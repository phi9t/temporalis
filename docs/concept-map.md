# Concept Map

Use this as the short desk reference while reading the explorer or the Kilvin
code. It ties each idea to the training-run story, the Temporal concept, and the
place to inspect it.

For a field-by-field guide to the YAML evidence produced by a live run, see
[Reading Kilvin Artifacts](artifacts.md).

## Temporal Concepts

| Concept | Plain meaning | Training-run role | Where to inspect |
| --- | --- | --- | --- |
| Workflow | Durable decision process | Owns the materialization path from request to monitored job | `kilvin-py/kilvin_py/workflows.py`, Deep Dive / Lifecycle |
| Activity | Retryable side effect | Builds images, talks to the allocator, writes specs, submits jobs, polls logs | `kilvin-py/kilvin_py/activities.py`, Deep Dive / Lifecycle |
| Worker | Process that executes code after polling Temporal | Runs workflow turns and activities with the needed local tools and credentials | `kilvin-py/worker.py`, Deep Dive / Lifecycle |
| Task queue | Routing inbox for work | Keeps build, launch, and monitor work attached to workers that can perform it | `kilvin-py/worker.py`, Temporal Matching refs in Deep Dive |
| History | Durable event log | Records accepted intent, activity results, signals, retries, and monitor progress | Deep Dive / Lifecycle and Control Paths |
| Replay | Reconstruct workflow state from history | Lets a run recover without resubmitting completed work or forgetting decisions | Deep Dive / Control Paths |
| Signal | Durable external command | Pause, resume, cancel, or replay part of a run while recording operator intent | `KilvinTrainingWorkflow.pause`, `resume`, `cancel`, `replay_step` |
| Query | Read-only workflow inspection | Reads status, step trace, run plan, and artifacts without mutating the run | `run_status`, `run_step_trace`, `run_plan`, `run_artifacts` |
| Heartbeat | Progress marker from a long activity | Makes monitoring recoverable when a worker dies mid-poll | `monitor_training`, Deep Dive / Control Paths |

## Training-System Operations

| Operation | Why it is hard at scale | Kilvin foundation | Temporal fit |
| --- | --- | --- | --- |
| Intent interpretation | A small research request expands into model, dataset, runtime, and policy decisions | `interpret_training_intent` | Workflow-owned decision state with typed activity output |
| Dependency concretization | CUDA, driver, NCCL, Torch, kernels, package indexes, and image registries can disagree | `concretize_dependencies` | Retryable activity that records image digest and dependency evidence |
| Quota and allocation | Scarce GPUs, rack health, fabric constraints, and reservation queues change over time | `allocate_resources` | Activity retries plus durable reservation result |
| Launch-spec materialization | Env vars, mounts, trainer command, namespace, image digest, and retry policy must match exactly | `materialize_training_bundle` | Concrete spec becomes inspectable evidence before submission |
| Kubernetes submission | The external scheduler can accept, reject, or partially materialize work | `submit_k8s_job` | Side effect isolated in an activity, with result recorded in history |
| Monitoring | Training can run longer than any worker process and fail after launch | `monitor_training` | Heartbeating activity with retry recovery and log artifacts |
| Operator control | Real runs need pause, resume, cancel, and targeted replay without losing auditability | workflow signals | Signals become explicit history events |
| Debugging | Operators need to know what was intended, what launched, and what actually happened | YAML artifacts and source-grounded explorer refs | History plus artifacts replace implicit process memory |

## Self-Check

After using this map, you should be able to point to a file or explorer panel
for each answer:

- Where does Kilvin decide what should happen next?
- Which code is allowed to talk to Docker, the allocator, and Kubernetes?
- What evidence proves which image digest and env vars launched?
- Why can a failed allocator call be retried without forgetting the intent?
- How does a monitor recover after a worker restart?
- Where would an operator pause or replay part of a run?
