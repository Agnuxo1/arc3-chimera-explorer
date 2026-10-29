"""Build the Kaggle submission notebook with the arc3chimera package inlined.

usage: python scripts/build_notebook.py <policy> <kw-json> <out_dir>
The notebook plays every game of the Arcade (25 public offline, 110 hidden via
the gateway on rerun) with one agent per game, games in a thread pool.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
policy, kw, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src}


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src}


cells = [md(f"# ARC-AGI-3 — graph explorer + CHIMERA world model (Agnuxo1)\n\n"
            f"Policy `{policy}`, options `{kw}`. Non-LLM agent: state-graph exploration; CHIMERA "
            f"(holographic phase memory + local cellular-automaton rules, numpy port of "
            f"github.com/Agnuxo1/ARC2_CHIMERA) re-ranks untried actions. Apache-2.0.\n"),
         code("import time\nT_KERNEL = time.time()   # global clock starts with the kernel\n"
              "!pip install --no-index --find-links /kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels arc-agi==0.9.8 python-dotenv\n"),
         code("import os\nos.makedirs('/kaggle/working/arc3chimera', exist_ok=True)\n")]
for f in ["__init__.py", "perception.py", "explorer.py", "chimera.py", "baselines.py"]:
    cells.append(code(f"%%writefile /kaggle/working/arc3chimera/{f}\n" + (ROOT / "arc3chimera" / f).read_text(encoding="utf-8")))

cells.append(code(r'''import os, sys, time, json, logging, threading
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/kaggle/working')
import pandas as pd

import subprocess
RERUN = os.getenv('KAGGLE_IS_COMPETITION_RERUN', '').strip().lower() not in ('', '0', 'false', 'no')
if RERUN:
    # wait for the competition gateway (fixed command, no user input)
    rc = subprocess.run(['curl', '--fail', '--silent', '--retry', '999', '--retry-all-errors', '--retry-delay', '5',
                         '--retry-max-time', '900', '-o', '/dev/null', 'http://gateway:8001/api/games']).returncode
    print('gateway wait, curl rc =', rc, flush=True)
    if rc != 0:
        print('WARNING: gateway did not answer /api/games; the game list below is retried before failing', flush=True)
mode, envdir = ('online', '') if RERUN else ('offline', '/kaggle/input/competitions/arc-prize-2026-arc-agi-3/environment_files/')
with open('/kaggle/working/.env', 'w') as f:
    f.write(f"""SCHEME=http
HOST=gateway
PORT=8001
ARC_API_KEY=test-key-123
ARC_BASE_URL=http://gateway:8001/
OPERATION_MODE={mode}
ENVIRONMENTS_DIR={envdir}
{'RECORDINGS_DIR=/kaggle/working/server_recording' if RERUN else ''}
""")
import dotenv
dotenv.load_dotenv(dotenv_path='/kaggle/working/.env', override=True)
import arc_agi
from arcengine import GameAction, GameState
from arc3chimera.explorer import Obs
from arc3chimera.perception import last_grid
from arc3chimera.runner import make_policy
logging.disable(logging.INFO)

POLICY, KW = ''' + repr(policy) + ", " + kw.replace("true", "True").replace("false", "False") + r'''
MAX_ACTIONS = 30000 if RERUN else 2000
T_START = T_KERNEL
TOTAL_BUDGET = 7.5 * 3600          # whole notebook must finish in 9 h: margin for setup and teardown
WORKERS = 8
arcade = arc_agi.Arcade()
games = [e.game_id for e in arcade.available_environments]
for _ in range(10):                # the gateway may still be warming up
    if games or not RERUN:
        break
    time.sleep(30)
    arcade = arc_agi.Arcade()
    games = [e.game_id for e in arcade.available_environments]
if not games:
    raise RuntimeError(f'no games available from the Arcade (rerun={RERUN}); refusing to finish silently')
PER_GAME = max(120.0, (TOTAL_BUDGET - (time.time() - T_START)) * WORKERS / max(1, len(games)))
print(len(games), 'games; per-game budget s =', PER_GAME, flush=True)

def play(game_id):
    t0 = time.time()
    n, lv, nones = 0, 0, 0
    try:
        env = arcade.make(game_id)
        r = env.observation_space
        if r is None:
            r = env.step(GameAction.RESET, {})
        pol = make_policy(POLICY, 0, **KW)
        while r is not None and r.state != GameState.WIN and n < MAX_ACTIONS:
            if time.time() - t0 > PER_GAME or time.time() - T_START > TOTAL_BUDGET:
                break
            obs = Obs(grid=last_grid(r.frame), state=r.state.name, levels=r.levels_completed,
                      available=list(r.available_actions))
            aid, data = pol.act(obs)
            nxt = env.step(GameAction.from_id(aid), data)
            n += 1
            if nxt is None and nones < 3:    # transient failure: resync with a RESET, at most 3 times
                nones += 1
                nxt = env.step(GameAction.RESET, {})
                pol.prev_obs, pol.prev_action, pol.plan = None, None, []
            r = nxt
            if r is not None:
                lv = r.levels_completed
    except Exception as e:
        return 'error', f'{game_id}: ERROR {e!r} after {n} actions'
    status = 'ok' if r is not None else 'none'
    return status, f'{game_id}: {status} {n} actions, levels={lv}, none_resets={nones}, {time.time()-t0:.0f}s'

counts = {'ok': 0, 'none': 0, 'error': 0}
with ThreadPoolExecutor(WORKERS) as ex:
    for status, line in ex.map(play, games):
        counts[status] += 1
        print(line, flush=True)
print(f'games={len(games)} ok={counts["ok"]} ended_on_none={counts["none"]} errors={counts["error"]} '
      f'elapsed={time.time() - T_START:.0f}s since kernel start', flush=True)

if not RERUN:
    sc = arcade.get_scorecard()
    print('Score', sc.score, 'levels', sc.total_levels_completed, '/', sc.total_levels, 'actions', sc.total_actions)
    for e in sc.environments:
        print(e.id, round(e.score, 3), e.levels_completed, e.actions)
    pd.DataFrame(data=[['1_0', '1', True, 1]], columns=['row_id', 'game_id', 'end_of_game', 'score']).to_parquet('/kaggle/working/submission.parquet', index=False)
'''))
# runner.py is needed for make_policy
cells.insert(3, code("%%writefile /kaggle/working/arc3chimera/runner.py\n" + (ROOT / "arc3chimera" / "runner.py").read_text(encoding="utf-8")))
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                    "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
(out / "arc3-chimera.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
print("wrote", out / "arc3-chimera.ipynb")
