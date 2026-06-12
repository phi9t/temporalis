# Source Grounding

Temporalis generated explorer data cites upstream source code so the diagrams remain inspectable.

The generator reads `.monorepo/current.lock.json` and emits refs for:

- `temporal`: server frontend, history, matching, retry, timer, cancellation, and heartbeat paths;
- `sdk-core`: polling, activations, completions, replay mediation, sticky cache, and heartbeats;
- `sdk-python`: Python worker loops, asyncio workflow activation, activity execution, and bridge boundaries;
- `ui`: operator inspection surfaces such as workflow event-history fetching;
- `kilvin`: local workflow, activities, and artifacts.

Maintainers refresh the generated data with:

```bash
make explorer-gen-data
PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py
```

Public quickstart uses the checked-in generated data, so a fresh clone does not need to clone upstream Temporal repositories.
