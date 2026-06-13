# Temporalis Docs

This directory is the learning map for Temporalis. Start with the hosted
explorer when you want the visual path; use these docs when you want a guided
reading order, quick reference, hands-on labs, or runtime proof.

## Start Here

- [Quickstart](quickstart.md): hosted and lightweight local path.
- [Learning Path](learning-path.md): the guided route through Temporal concepts,
  model-training operations, Deep Dive internals, and Kilvin code.
- [Concept Map](concept-map.md): short reference from term to training role to
  source location.

## Model Training Systems

- [Durable Model Training Systems](model-training-systems.md): why the small
  Kilvin workflow is shaped like a real foundation-model training control plane.
- [Reading Kilvin Artifacts](artifacts.md): how to inspect intent,
  dependencies, quota, materialized launch specs, and monitoring evidence from
  `.kilvin-artifacts/`.
- Together, these docs make intent, dependencies, quota, materialized launch specs, and monitoring inspectable instead of implicit.
- [Exercises](exercises.md): lightweight labs with the checked-in hack scripts
  plus optional live-runtime labs.

## Temporal Internals

- [Temporal Internals](temporal-internals.md): a plain-English pass through
  Frontend, History, Matching, SDK Core, SDK Python, Temporal UI, and how those
  pieces execute the training request.
- [Source Grounding](source-grounding.md): how generated explorer data cites
  pinned Temporal server, SDK Core, SDK Python, Temporal UI, and Kilvin source
  refs.
- Deep Dive in the explorer: Lifecycle, Control Paths, and Kilvin Internals.

## Runtime And Release

- [Runtime Proof](runtime-proof.md): optional live Kilvin path using Temporal,
  allocator, registry, k3s, worker, and trainer artifacts.
- [Kilvin runbook](kilvin/real-local-runbook.md): manual operator path for the
  real local stack.
- [Kilvin proof checklist](kilvin/proof-checklist.md): evidence required before
  claiming a real run worked.
- [Release checklist](release-checklist.md): maintainer release gates.

## What To Read For Each Question

| Question | Read |
| --- | --- |
| I want the fastest path. | [Quickstart](quickstart.md) |
| I want a full guided lesson. | [Learning Path](learning-path.md) |
| I forgot what a term means. | [Concept Map](concept-map.md) |
| I want to understand larger training systems. | [Durable Model Training Systems](model-training-systems.md) |
| I want to inspect run evidence. | [Reading Kilvin Artifacts](artifacts.md) |
| I want hands-on labs. | [Exercises](exercises.md) |
| I want source-backed Temporal internals. | [Temporal Internals](temporal-internals.md), [Source Grounding](source-grounding.md), and Deep Dive |
| I want to run the live proof. | [Runtime Proof](runtime-proof.md) |
