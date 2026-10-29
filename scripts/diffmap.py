import sys, logging
import numpy as np
logging.disable(logging.CRITICAL)
import arc_agi
from arcengine import GameAction
from arc3chimera.perception import last_grid
env_dir, game = sys.argv[1], sys.argv[2]
seq = [int(x) for x in sys.argv[3].split(",")]
arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=env_dir)
env = arcade.make(game, seed=0)
r = env.observation_space
g0 = last_grid(r.frame)
print("\n".join("".join("%x" % v for v in row) for row in g0))
for a in seq:
    g = last_grid(r.frame)
    r = env.step(GameAction.from_id(a), {"x": 32, "y": 32})
    g2 = last_grid(r.frame)
    ys, xs = np.where(g != g2)
    regions = {}
    for y, x in zip(ys, xs):
        regions.setdefault((y // 8, x // 8), 0); regions[(y // 8, x // 8)] += 1
    print(a, "diff", len(ys), "rows", (ys.min(), ys.max()) if len(ys) else None, "cols", (xs.min(), xs.max()) if len(xs) else None, sorted(regions.items()))
