# Durable Model Training Systems

Kilvin stays deliberately small: one Temporal workflow, one pretraining stage,
one local allocator, one Kubernetes Job, and one tiny CPU trainer. That is the
right size for learning the foundations. The reason the repo uses a
production-shaped request anyway -- train model X on FineWeb with 64 A100 GPUs
-- is that the simple slice only makes sense when you can see what it grows
into.

The project theme is **shaping the foundation model**. Kilvin's name points at
the master artificer from *The Name of the Wind*: a builder who cares about
materials, constraints, evidence, and durable craft. In this repo, the raw
material is research intent; the shaped object is an auditable training run.

## The Simple Slice

The runnable path in `kilvin-py/` teaches the invariant that matters most:
research intent should become durable, inspectable execution state.

The local implementation maps the large request onto laptop-scale work:

- `interpret_training_intent` turns the researcher request into typed run state.
- `concretize_dependencies` pins code, dependencies, and the image digest.
- `allocate_resources` reserves capacity from a finite local ledger.
- `materialize_training_bundle` writes the literal Kubernetes launch spec.
- `submit_k8s_job` creates the local k3s Job.
- `monitor_training` heartbeats while polling Job state and trainer logs.

That path is intentionally small enough to inspect from end to end. The
important part is not the tiny GPT trainer; it is the shape of the control
plane: durable decisions, retryable side effects, and artifacts that explain
what happened.

## What Changes At Real Training Scale

Modern model training usually stops being "run this script" long before the
first token is processed. A real foundation-model launch may need to coordinate:

- multiple training phases such as base pretraining, continued pretraining,
  supervised fine-tuning, preference or reinforcement-style stages, and
  quantization-aware follow-up work;
- huge token budgets, explicit data-mixture targets, modality splits, quality
  thresholds, long-context curricula, and dataset locality constraints;
- CUDA, driver, NCCL, Torch, custom kernels, tokenizer assets, checkpoint
  format, and image-registry compatibility;
- scarce GPU quota across clusters, rack placement, healthy machines,
  InfiniBand or other fabric constraints, and storage reachability;
- one or more Kubernetes jobs, distributed trainer roles, checkpoint writers,
  evaluators, data loaders, and monitoring sidecars;
- long-running monitoring, stuck-job detection, checkpoint promotion, rollback,
  pause/resume, and hotfix controls.

Qwen3 and Qwen3-VL are useful concrete examples of this shape. A Qwen3-style
text recipe moves from broad general pretraining into reasoning-heavy continued
pretraining, long-context adaptation, cold-start SFT, verifier-driven RL,
thinking/non-thinking mode fusion, general RL, and strong-to-weak distillation.
A Qwen3-VL-style recipe adds vision-language alignment, multimodal pretraining,
ultra-long document/video adaptation, multimodal SFT, visual reasoning RL, and
tool-integrated visual-agent training. The exact source-level sampler weights
are not public, but the stage graph makes the orchestration problem visible.
See [Qwen3 / Qwen3-VL Extension](qwen3-kilvin-extension.md) for the recipe-level
mapping onto Kilvin stages and Temporal controls.

The difficult part is that these concerns are coupled. A data decision can
change placement. A placement decision can change the launch spec. A dependency
pin can determine whether the trainer can use the chosen machines. Monitoring
must know which concrete spec actually launched, not merely what someone
intended to launch.

## Why Temporal Is Useful Here

Temporal is useful because it separates durable orchestration from fragile
side effects.

Workflow code owns the run's decision history: what intent was accepted, which
plan was materialized, which capacity was reserved, which launch spec was
submitted, and which control signals were recorded. Activity code owns the
outside world: dependency builds, allocator calls, Kubernetes submission,
cluster inspection, and log polling.

That split gives a training platform several practical properties:

- retries can rebuild an image, retry an allocator call, or continue monitoring
  without replaying already-recorded business decisions;
- replay can reconstruct the workflow state after a worker restart without
  resubmitting the whole job by accident;
- activity heartbeats can make long monitors recoverable and show where work
  last made progress;
- signals can pause, resume, cancel, or request a targeted replay while leaving
  an auditable event in workflow history;
- queries can expose current run state without changing the run;
- task queues can route build, quota, launch, and monitoring work to workers
  that have the right credentials and environment.

In other words, Temporal makes the orchestration state durable while allowing
the messy operational work to remain ordinary code.

## How To Read This Repo

Use the explorer in this order:

1. **Basics** teaches the vocabulary with one model-training request.
2. **Deep Dive / Lifecycle** shows how Temporal server, SDK Core, SDK Python,
   and UI paths cooperate to execute that request.
3. **Deep Dive / Control Paths** shows retries, cancellation, heartbeat
   recovery, pause/resume, and sticky replay as variations on the same run.
4. **Deep Dive / Kilvin Internals** maps the teaching story back to the
   runnable workflow, activities, signals, queries, and YAML artifacts.

Then run the local paths:

1. `make quickstart` verifies the checked-in teaching data and probes.
2. `make runtime-proof` runs the optional live Kilvin stack when Docker, k3s,
   and Temporal are available.

The repo should leave you with one mental model: complex training platforms are
not made reliable by hiding complexity. They become learnable when every
important decision is shaped into materialized, durable, source-grounded, and
inspectable evidence.
