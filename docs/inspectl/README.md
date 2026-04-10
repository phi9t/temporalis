# Inspectl
`inspectl` keeps pipeline business logic prominent while using Temporal underneath for retries, durability, and pause/resume. `run(...)` boots or connects to a local Temporal dev server when needed.

## Quickstart

```python
from dataclasses import dataclass

from inspectl import PipelineState, pipeline, run, step


@dataclass
class CounterState(PipelineState):
    run_id: str
    value: int = 0


@step()
def add_one(state: CounterState) -> CounterState:
    state.value += 1
    return state


@pipeline(name="count-three")
async def count_three(state: CounterState) -> CounterState:
    state = await add_one(state)
    state = await add_one(state)
    state = await add_one(state)
    return state


if __name__ == "__main__":
    final_state = run(count_three, CounterState(run_id="run-001"))
    print(final_state.value)
```

The example keeps state explicit, step transitions readable, and the entrypoint small enough to run locally or under Temporal-backed execution without changing the pipeline body.

## Operator Commands

- `inspectl list`
- `inspectl inspect <run_id>`
- `inspectl logs <run_id>`
- `inspectl resume <run_id>`

`inspectl list` shows runs available in the local runtime, `inspectl inspect` examines a run snapshot, `inspectl logs` streams the append-only run log, and `inspectl resume` continues a paused run.

## Runtime Layout

- `.inspectl/runtime/temporal.sqlite` - local Temporal persistence
- `.inspectl/runtime/server.json` - local dev-server metadata
- `runs/<run_id>/session.jsonl` - append-only run log
- `runs/<run_id>/state_snapshots/*.json` - per-step snapshots

The runtime directory is intentionally file-based so the local execution model is easy to inspect, copy, and reset without external services.
