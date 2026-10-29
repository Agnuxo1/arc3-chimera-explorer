import sys, logging, collections
import numpy as np
logging.disable(logging.CRITICAL)
import arc_agi
from arcengine import GameAction, GameState
from arc3chimera.explorer import Obs, GraphExplorer
from arc3chimera.perception import last_grid
env_dir, game, steps = sys.argv[1], sys.argv[2], int(sys.argv[3])
arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=env_dir)
env = arcade.make(game, seed=0)
p = GraphExplorer(seed=0)
r = env.observation_space
changes = collections.Counter(); states = []
for i in range(steps):
    g = last_grid(r.frame)
    obs = Obs(grid=g, state=r.state.name, levels=r.levels_completed, available=list(r.available_actions))
    aid, data = p.act(obs)
    r2 = env.step(GameAction.from_id(aid), data)
    g2 = last_grid(r2.frame)
    d = int((g != g2).sum())
    changes[(aid, d > 0)] += 1
    if i < 40 or i % 200 == 0:
        print(i, aid, data, "diff", d, "state", r2.state.name, "lvl", r2.levels_completed, "nodes", len(p.nodes), "mask", int(p.vol.mask.sum()), "nframes", len(r2.frame))
    r = r2
    if r.state == GameState.WIN: break
print(changes)
print("nodes", len(p.nodes), "stats", p.stats)
