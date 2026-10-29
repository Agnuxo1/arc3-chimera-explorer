"""Census of the public games: actions, levels, baselines, frame shapes (observations only)."""
import json, sys, time
from pathlib import Path
import numpy as np
import arc_agi
from arcengine import GameAction, GameState

ENV_DIR = sys.argv[1]
arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_DIR)
rows = []
for info in arcade.available_environments:
    env = arcade.make(info.game_id)
    r = env.observation_space
    fr = np.array(r.frame[-1]) if r.frame else None
    t = time.time(); n = 0
    for _ in range(50):
        r = env.step(GameAction.ACTION1 if 1 in r.available_actions else GameAction.from_id(r.available_actions[0]), {"x": 32, "y": 32})
        n += 1
        if r is None or r.state != GameState.NOT_FINISHED: break
    dt = (time.time() - t) / max(n, 1)
    rows.append(dict(game=info.game_id, tags=info.tags, actions=r.available_actions if r else None,
                     win_levels=r.win_levels if r else None, baseline=info.baseline_actions,
                     shape=None if fr is None else list(fr.shape), nframes=len(r.frame) if r else None,
                     ms_per_step=round(dt * 1000, 2)))
    print(json.dumps(rows[-1]))
