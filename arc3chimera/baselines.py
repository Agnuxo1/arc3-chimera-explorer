"""Random baseline equivalent to the official sample agent (no RESET except when required)."""
import random

import numpy as np


class RandomAgent:
    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)
        self.stats = {}

    def act(self, obs):
        if obs.state in ("NOT_PLAYED", "GAME_OVER"):
            return 0, {}
        a = self.rng.choice([x for x in obs.available if x != 0])
        if a == 6:
            colours = np.unique(obs.grid).tolist()
            c = self.rng.choice(colours)
            ys, xs = np.where(obs.grid == c)
            i = self.rng.randrange(len(xs))
            return 6, {"x": int(xs[i]), "y": int(ys[i])}
        return a, {}
