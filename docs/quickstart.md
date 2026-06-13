# Quickstart

Use this path to learn Temporalis without running the live Kilvin stack.

## Hosted

Open https://phi9t.github.io/temporalis/ and start in Basics. Then switch to Deep Dive for Lifecycle, Control Paths, and Kilvin Internals.

Use the [Learning Path](learning-path.md) when you want the full guided route
from Temporal vocabulary to Kilvin code and model-training operations.

For the model-training motivation, read
[Durable Model Training Systems](model-training-systems.md). It explains how the
simple Kilvin path generalizes to multi-phase training, dependency pinning,
quota, placement, materialized launch specs, and monitoring.

## Local

```bash
git clone https://github.com/phi9t/temporalis.git
cd temporalis
make quickstart
./explorer/scripts/workflow.sh install
make explorer-dev
```

`make quickstart` checks the generated explorer manifests and deterministic hack probes. It does not require docker, k3s, cloud credentials, or a live Temporal server.

## What You Learn

- how a workflow turns a training intent into durable execution;
- why Temporal history is the source of truth;
- how task queues, workers, activations, activity heartbeats, retries, replay, and sticky caches fit together;
- how the Kilvin implementation maps a 64-A100/FineWeb teaching intent onto a laptop-scale tiny CPU GPT trainer.
- why the same orchestration shape helps with modern multi-phase training programs without making the demo itself complicated.
