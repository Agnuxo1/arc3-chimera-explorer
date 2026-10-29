# ARC3 CHIMERA Explorer

An offline graph-exploration research prototype for [ARC-AGI-3](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3), built from our CHIMERA research direction. It perceives public frames, tracks observed states and actions, and evaluates with the official environment scorecard. It does not inspect hidden game source or solutions.

## Measured status

The stored exploratory smoke run covered five public games, seed0 and at most1500actions/game: mean score **0.0058973574**, one completed level, zero recorded exceptions. [Raw run](results/smoke_explorer.json). This is a single-seed smoke result, with no matched random-control comparison. Standard deviation0 across one seed is not an uncertainty estimate. No official submission or competitive improvement is established by this snapshot.

## Reproduce

```bash
python -m pip install -r requirements.txt
python -m arc3chimera.runner --env-dir /path/to/official/environments --policy explorer --seeds 0 --games ft09,lp85,ls20,tu93,vc33 --max-actions 1500 --workers 1 --out /tmp/explorer.json
```

Use the game IDs available in your official environment release; the IDs above reproduce the stored smoke selection and may differ in another release. `--policy random` supplies the control. Follow-up comparisons must freeze the same games and action/time budget and use at least three seeds. Only `explorer` and `random` are implemented in this snapshot; the reserved `chimera` option has no implementation and must not be used.

## Method and limits

`arc3chimera/perception.py` extracts observed frame information; `explorer.py` maintains graph exploration; `runner.py` isolates each game/seed in a process and records exceptions. `results/census_public25.jsonl` describes public observations only. No environment bundle, weights or private game data are included. Inspect exact versions of the official `arc-agi` and `arcengine` release before comparing scores. This exploratory snapshot is not a three-seed confirmation or an official result.

See [research protocol](docs/RESEARCH_PROTOCOL.md). Original project code: MIT; dependencies retain their own licences. No prize, affiliation or organiser endorsement is claimed.
