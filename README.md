<div align="center">

<img src="docs/readme/01-banner.gif" alt="ARC3 CHIMERA Explorer: a state graph discovered node by node" width="100%">

# ARC3 CHIMERA Explorer

[![Release integrity](https://github.com/Agnuxo1/arc3-chimera-explorer/actions/workflows/release.yml/badge.svg)](https://github.com/Agnuxo1/arc3-chimera-explorer/actions/workflows/release.yml) [![licence: MIT](https://img.shields.io/badge/licence-MIT-3fb950?style=flat-square)](LICENSE) ![status: exploratory snapshot](https://img.shields.io/badge/status-exploratory%20snapshot-c98500?style=flat-square) [![evaluation: local · official scorecard package](https://img.shields.io/badge/evaluation-local%20·%20official%20scorecard%20package-3987e5?style=flat-square)](docs/RESEARCH_PROTOCOL.md) [![Kaggle: ARC Prize 2026 · ARC-AGI-3](https://img.shields.io/badge/Kaggle-ARC%20Prize%202026%20·%20ARC--AGI--3-20beff?style=flat-square&logo=kaggle&logoColor=white)](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3)

[**Measured status**](#measured-status) · [**Reproduce**](#reproduce) · [**Method and limits**](#method-and-limits) · [**Raw run**](results/smoke_explorer.json) · [**Research protocol**](docs/RESEARCH_PROTOCOL.md) · [**Competition**](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3)

</div>

An offline graph-exploration research prototype for [ARC-AGI-3](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3), built from our CHIMERA research direction. It perceives public frames, tracks observed states and actions, and evaluates with the official environment scorecard. It does not inspect hidden game source or solutions.

**Contents** — [Measured status](#measured-status) · [Background](#background) · [Reproduce](#reproduce) · [Method and limits](#method-and-limits) · [Real-world applications](#real-world-applications) · [Possible improvements](#possible-improvements) · [Future work](#future-work) · [Bibliography](#bibliography)

## Measured status

<p align="center"><img src="docs/readme/02-status.gif" alt="Stat tiles and per-game rows: levels completed, actions, resets and score for five public games" width="100%"><br><sub>Fig. 1 — The stored smoke run. Data: results/smoke_explorer.json; levels per game from results/census_public25.jsonl.</sub></p>

Local evaluation on the 25 public games with the official `arc_agi` 0.9.8 scorecard (scale 0-100), 5000 actions/game, 5 seeds of the holographic projection (games and the control are deterministic), paired per-game Wilcoxon test against the control. Raw runs: [results/v2_perception](results/v2_perception); full log: [docs/EXPERIMENT_LOG.md](docs/EXPERIMENT_LOG.md).

| system | mean ± sd over seeds | levels per seed | vs control |
|---|---|---|---|
| control: graph explorer + perception v2 | 0.1465 ± 0 | 14 | — |
| CHIMERA world model | 0.3078 ± 0.1461 | 18-21 | +15/-2 games, p = 0.0008 |
| CHIMERA + keyboard local rules (kb-CA) | 0.3932 ± 0.1742 | 18-22 | +14/-3 games, p = 0.0046 |
| CHIMERA + kb-CA, alpha 4 (Kaggle submission 2) | 0.4216 ± 0.1961 | 18-21 | +14/-2 games, p = 0.0034 |

Ablations against CHIMERA + kb-CA (no click CA 0.404, no goal/death traces 0.396, no cross-level persistence 0.324, dimension 2048 0.291) are not significant; alpha 1 is worse (0.287, p = 0.037). The largest single effect is not CHIMERA: masking volatile border lines (progress bars) raised the control from 0.0013 to 0.147. A server replica on Linux reproduces these numbers exactly ([results/server_replica](results/server_replica)). These are public-game results; the 110 hidden games and the official leaderboard can differ. Kaggle submissions are listed with their ids once scored. The earlier five-game smoke run is kept in [results/smoke_explorer.json](results/smoke_explorer.json).

## Background

<p align="center"><img src="docs/readme/03-background.gif" alt="Animated timeline from A* search (1968) to ARC-AGI-3 and this repository (2026)" width="100%"><br><sub>Fig. 2 — Search, game benchmarks and exploration research behind this agent. Sources: bibliography below.</sub></p>

ARC was proposed as a measure of skill-acquisition efficiency — how quickly a system learns a new task from little
experience [[1](#ref-1)]. ARC-AGI-3 moves that idea from static grids to interactive games, in which an agent has to
discover each environment's controls, rules and goals by acting in it [[2](#ref-2), [3](#ref-3)]. Video games have served as
agent benchmarks for more than a decade: the Arcade Learning Environment and deep Q-networks learning from pixels
made them standard [[11](#ref-11), [12](#ref-12)]. The exploration problem they expose has its own literature — count-based
novelty bonuses [[4](#ref-4)], curiosity from prediction error [[5](#ref-5)], random network distillation [[6](#ref-6)] and
Go-Explore, which remembers promising states and returns to them before exploring further [[7](#ref-7)]. Classical graph
search, from breadth-first search to A* [[8](#ref-8)], supplies the deterministic backbone, and core-knowledge accounts of human cognition describe the
priors (objects, agents, number, geometry) that such tasks are designed around [[9](#ref-9), [10](#ref-10)].

This repository is a deliberately simple, learning-free control in that tradition. It hashes observed frames
(volatile cells masked) into a state graph, tries untried actions in a fixed salience order, walks the known graph by
breadth-first search to the nearest state that still has untried actions, and avoids transitions that ended in
GAME_OVER. It comes from the author's CHIMERA research direction [[13](#ref-13)]; CHIMERA (`arc3chimera/chimera.py`) is a numpy port of its two
ingredients, a complex-phase holographic memory and local cellular-automaton rules, used as a world model that re-ranks untried actions.

## Reproduce

<p align="center"><img src="docs/readme/04-reproduce.gif" alt="Terminal with the runner command and real release-check output" width="100%"><br><sub>Fig. 3 — Commands from this section; the release check is a real local run.</sub></p>

```bash
python -m pip install -r requirements.txt
python -m arc3chimera.runner --env-dir /path/to/official/environments --policy explorer --seeds 0 --games ft09,lp85,ls20,tu93,vc33 --max-actions 1500 --workers 1 --out /tmp/explorer.json
```

Use the game IDs available in your official environment release; the IDs above reproduce the stored smoke selection and may differ in another release. `--policy random` supplies the control. Follow-up comparisons must freeze the same games and action/time budget and use at least three seeds. Policies: `explorer` (control), `random`, `chimera` (options via `--kw`, e.g. `{"use_kbca": true, "alpha": 4.0}`). `scripts/stats.py` runs the paired comparison; `scripts/build_notebook.py` builds the Kaggle notebook (copies in [kaggle/](kaggle)).

## Method and limits

<p align="center"><img src="docs/readme/05-method.gif" alt="Schematic state graph explored node by node, with a dead end and a deadly transition" width="100%"><br><sub>Fig. 4 — Schematic of <code>arc3chimera/explorer.py</code>; illustrative graph, not a recorded run.</sub></p>

`arc3chimera/perception.py` extracts observed frame information; `explorer.py` maintains graph exploration; `runner.py` isolates each game/seed in a process and records exceptions. `results/census_public25.jsonl` describes public observations only. No environment bundle, weights or private game data are included. Inspect exact versions of the official `arc-agi` and `arcengine` release before comparing scores. `chimera.py` keeps three holographic traces (effect, goal, death) written by the delta rule and read by correlation; features are the action, the clicked segment and 3x3 neighbourhood, and (kb-CA) the 7x7 neighbourhood of the last region each keyboard action changed. Exploration stays complete: a predicted-useless action is postponed, never removed.

<p align="center"><img src="docs/readme/06-census.gif" alt="Bars: levels to win for each of 25 public games, coloured by input type" width="100%"><br><sub>Fig. 5 — Public observations only. Data: results/census_public25.jsonl.</sub></p>

See [research protocol](docs/RESEARCH_PROTOCOL.md). Original project code: MIT; dependencies retain their own licences. No prize, affiliation or organiser endorsement is claimed.

## Real-world applications

<p align="center"><img src="docs/readme/07-applications.gif" alt="Six application cards appearing one after another" width="100%"><br><sub>Fig. 6 — Potential uses of observation-only exploration; this snapshot demonstrates none of them.</sub></p>

- **Automated game testing.** Map the reachable states of a level and flag dead ends or crashes without access to
  the game's source code.
- **User-interface exploration.** Click and keyboard agents can enumerate the screens of an application as a state
  graph for regression testing.
- **Safe exploration.** Transitions that ended in failure are marked and avoided on later visits, a simple form of
  caution without learning.
- **State-space mapping.** Frame hashing plus breadth-first search gives a cheap map of what an unknown interactive
  system can do.
- **Benchmark baselines.** A transparent, learning-free control against which world-model agents can be compared
  under the same local scorecard.
- **Teaching exploration research.** Per-game records and exceptions make experiments easy to audit.

## Possible improvements

<p align="center"><img src="docs/readme/08-improvements.gif" alt="Limits of the smoke run on the left turning into next experiments on the right" width="100%"><br><sub>Fig. 7 — Each improvement answers a limit stated in this README.</sub></p>

- **More than one seed.** A standard deviation of 0 over one seed is not an uncertainty estimate; follow-ups need at
  least three seeds on frozen games and budgets.
- **A matched random control.** `--policy random` exists but no matched comparison has been run.
- **Learning across levels.** One level was completed across five games. The explorer already exposes
  `rank_untried` and `learn` hooks, so a learned forward model, as used for curiosity [[5](#ref-5)], could re-rank untried
  actions.
- **The CHIMERA policy.** High variance across holographic projection seeds (sd ~0.17); most of the score comes from a few games solved near human efficiency.

## Future work

<p align="center"><img src="docs/readme/09-roadmap.gif" alt="Roadmap with two completed items and four planned steps" width="100%"><br><sub>Fig. 8 — Done items are stored in results/; the rest are planned.</sub></p>

1. Run the matched random control on the same five games, action budget and time budget.
2. Confirm with at least three seeds under a frozen protocol, as the README requires.
3. Add a world model behind `rank_untried` / `learn` and compare it with both controls.
4. Reduce the seed variance of the CHIMERA world model and measure it on more games.
5. Check the exact `arc-agi` and `arcengine` versions before any comparison with official scores.

## Bibliography

1. <a id="ref-1"></a>Chollet, F. (2019). On the Measure of Intelligence. *arXiv* 1911.01547. https://arxiv.org/abs/1911.01547
2. <a id="ref-2"></a>ARC Prize Foundation. *ARC-AGI-3: interactive reasoning benchmark* (website). https://arcprize.org/arc-agi/3/
3. <a id="ref-3"></a>ARC Prize Foundation & Kaggle (2026). *ARC Prize 2026: ARC-AGI-3* (competition). https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3
4. <a id="ref-4"></a>Bellemare, M. G., Srinivasan, S., Ostrovski, G., et al. (2016). Unifying Count-Based Exploration and Intrinsic Motivation. *arXiv* 1606.01868. https://arxiv.org/abs/1606.01868
5. <a id="ref-5"></a>Pathak, D., Agrawal, P., Efros, A. A., & Darrell, T. (2017). Curiosity-driven Exploration by Self-supervised Prediction. *arXiv* 1705.05363. https://arxiv.org/abs/1705.05363
6. <a id="ref-6"></a>Burda, Y., Edwards, H., Storkey, A., & Klimov, O. (2018). Exploration by Random Network Distillation. *arXiv* 1810.12894. https://arxiv.org/abs/1810.12894
7. <a id="ref-7"></a>Ecoffet, A., Huizinga, J., Lehman, J., Stanley, K. O., & Clune, J. (2021). First return, then explore. *Nature*, 590(7847), 580–586. https://doi.org/10.1038/s41586-020-03157-9
8. <a id="ref-8"></a>Hart, P., Nilsson, N., & Raphael, B. (1968). A Formal Basis for the Heuristic Determination of Minimum Cost Paths. *IEEE Transactions on Systems Science and Cybernetics*, 4(2), 100–107. https://doi.org/10.1109/TSSC.1968.300136
9. <a id="ref-9"></a>Spelke, E. S., & Kinzler, K. D. (2006). Core knowledge. *Developmental Science*, 10(1), 89–96. https://doi.org/10.1111/j.1467-7687.2007.00569.x
10. <a id="ref-10"></a>Lake, B. M., Ullman, T. D., Tenenbaum, J. B., & Gershman, S. J. (2016). Building machines that learn and think like people. *Behavioral and Brain Sciences*, 40. https://doi.org/10.1017/S0140525X16001837
11. <a id="ref-11"></a>Bellemare, M. G., Naddaf, Y., Veness, J., & Bowling, M. (2013). The Arcade Learning Environment: An Evaluation Platform for General Agents. *Journal of Artificial Intelligence Research*, 47, 253–279. https://doi.org/10.1613/jair.3912
12. <a id="ref-12"></a>Mnih, V., Kavukcuoglu, K., Silver, D., et al. (2015). Human-level control through deep reinforcement learning. *Nature*, 518(7540), 529–533. https://doi.org/10.1038/nature14236
13. <a id="ref-13"></a>Angulo de Lafuente, F. *ARC2_CHIMERA: research proof-of-concept for ARC-AGI* (software). https://github.com/Agnuxo1/ARC2_CHIMERA

---

<div align="center">
<sub>Built by <a href="https://github.com/Agnuxo1">Francisco Angulo de Lafuente</a> · every figure is an animated
rendering of the published file named in its footer · <a href="#arc3-chimera-explorer">back to top ↑</a></sub>
</div>
