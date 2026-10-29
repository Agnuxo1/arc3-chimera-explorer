"""Control agent: graph exploration with novelty detection.

State graph over (masked) frame hashes. In every state the untried actions are
tried in priority order; when the current state is exhausted the agent walks
the known graph (BFS) to the nearest state that still has untried actions.
Transitions that ended in GAME_OVER are marked deadly and avoided.

The class is written so that a world model can re-rank untried actions
(``rank_untried``) and learn from every transition (``learn``); the plain
control uses a fixed salience order and learns nothing across levels.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from .perception import VolatilityTracker, click_candidates, grid_hash, last_grid

NOT_PLAYED, NOT_FINISHED, WIN, GAME_OVER = "NOT_PLAYED", "NOT_FINISHED", "WIN", "GAME_OVER"


@dataclass
class Obs:
    grid: np.ndarray
    state: str
    levels: int
    available: list[int]


@dataclass
class Node:
    grid: np.ndarray
    actions: list = field(default_factory=list)     # action keys in try order
    tier: dict = field(default_factory=dict)        # action key -> priority tier
    meta: dict = field(default_factory=dict)        # action key -> segment (for clicks)
    tried: set = field(default_factory=set)
    edges: dict = field(default_factory=dict)       # action key -> canonical successor
    deadly: set = field(default_factory=set)


def akey_to_call(ak):
    """Action key -> (action id, data dict) for the API."""
    if isinstance(ak, tuple):
        return 6, {"x": int(ak[1]), "y": int(ak[2])}
    return int(ak), {}


class GraphExplorer:
    name = "graph_explorer"

    def __init__(self, seed: int = 0, click_limit: int = 48):
        self.rng = random.Random(seed)
        self.click_limit = click_limit
        self.prev_obs: Obs | None = None
        self.prev_key = None
        self.prev_action = None
        self.plan: list = []
        self.level = -1
        self.stats = {"actions": 0, "resets": 0, "levels": [], "nodes_per_level": []}
        self._new_level()

    # ----- level bookkeeping -------------------------------------------------
    def _new_level(self):
        self.vol = VolatilityTracker()
        self.raw_grids: dict = {}      # raw hash -> grid
        self.log: list = []            # (raw_from, akey, raw_to, outcome)
        self.nodes: dict = {}          # canonical key -> Node
        self.canon_cache: dict = {}
        self.plan = []

    def canon(self, raw):
        k = self.canon_cache.get(raw)
        if k is None:
            k = grid_hash(self.raw_grids[raw], self.vol.mask)
            self.canon_cache[raw] = k
        return k

    def _rebuild(self):
        """Mask changed: re-key every stored grid and replay the transition log."""
        self.canon_cache = {}
        old = self.nodes
        self.nodes = {}
        for raw in self.raw_grids:
            self._ensure_node(self.canon(raw), self.raw_grids[raw], old_hint=None)
        for raw_from, ak, raw_to, outcome in self.log:
            self._record_edge(self.canon(raw_from), ak, None if raw_to is None else self.canon(raw_to), outcome)
        self.plan = []

    # ----- action generation -------------------------------------------------
    def candidate_actions(self, grid: np.ndarray, available: list[int]):
        acts, tiers, meta = [], {}, {}
        for a in available:
            if a in (1, 2, 3, 4, 5, 7):
                acts.append(a)
                tiers[a] = 0
        if 6 in available:
            for i, (x, y, seg) in enumerate(click_candidates(grid, self.vol.mask, self.click_limit)):
                ak = (6, x, y)
                acts.append(ak)
                tiers[ak] = 0 if i < 8 else (1 if i < 24 else 2)
                meta[ak] = seg
        return acts, tiers, meta

    def _ensure_node(self, key, grid, old_hint=None):
        n = self.nodes.get(key)
        if n is None:
            acts, tiers, meta = self.candidate_actions(grid, self._available)
            n = Node(grid=grid, actions=acts, tier=tiers, meta=meta)
            self.nodes[key] = n
        return n

    def _record_edge(self, key_from, ak, key_to, outcome):
        n = self.nodes.get(key_from)
        if n is None:
            return
        n.tried.add(ak)
        if outcome == "deadly":
            n.deadly.add(ak)
            n.edges.pop(ak, None)
        elif key_to is not None and key_to != key_from:
            n.edges[ak] = key_to

    # ----- hooks for world models ------------------------------------------
    def rank_untried(self, key, node: Node, untried: list) -> list:
        return sorted(untried, key=lambda a: (node.tier.get(a, 0), node.actions.index(a)))

    def state_value(self, key, node: Node, untried: list) -> float:
        """Lower is better: priority of visiting this frontier state."""
        return min(node.tier.get(a, 0) for a in untried)

    def learn(self, prev: Obs, ak, obs: Obs, outcome: str, key_from, key_to):
        pass

    def on_level_up(self, levels: int):
        pass

    # ----- main step ---------------------------------------------------------
    def untried(self, node: Node):
        return [a for a in node.actions if a not in node.tried]

    def act(self, obs: Obs):
        self._available = [a for a in obs.available if a != 0]
        # learn from the previous transition
        if self.prev_obs is not None and self.prev_action is not None:
            self._observe_transition(obs)
        if obs.levels != self.level:
            if self.level >= 0:
                self.stats["levels"].append(self.stats["actions"])
                self.stats["nodes_per_level"].append(len(self.nodes))
                self.on_level_up(obs.levels)
            self.level = obs.levels
            self._new_level()
        if obs.state in (NOT_PLAYED, GAME_OVER):
            self.prev_obs, self.prev_action = None, None
            self.plan = []
            self.stats["resets"] += 1
            return 0, {}
        raw = grid_hash(obs.grid)
        self.raw_grids.setdefault(raw, obs.grid)
        key = self.canon(raw)
        node = self._ensure_node(key, obs.grid)
        ak = self._choose(key, node)
        self.prev_obs, self.prev_key, self.prev_raw, self.prev_action = obs, key, raw, ak
        self.stats["actions"] += 1
        return akey_to_call(ak)

    def _observe_transition(self, obs: Obs):
        prev, ak = self.prev_obs, self.prev_action
        if obs.levels != prev.levels:
            outcome = "level_up"
        elif obs.state == GAME_OVER:
            outcome = "deadly"
        else:
            outcome = "step"
        raw_to = None
        if outcome == "step":
            raw_to = grid_hash(obs.grid)
            self.raw_grids.setdefault(raw_to, obs.grid)
            changed_mask = self.vol.update(prev.grid, obs.grid)
        else:
            changed_mask = False
        self.log.append((self.prev_raw, ak, raw_to, outcome))
        if changed_mask:
            self._rebuild()
        key_from = self.canon(self.prev_raw)
        key_to = None if raw_to is None else self.canon(raw_to)
        if key_to is not None:
            self._ensure_node(key_to, obs.grid)
        self._record_edge(key_from, ak, key_to, outcome)
        self.learn(prev, ak, obs, outcome, key_from, key_to)

    def _choose(self, key, node: Node):
        # follow an existing plan if it is still consistent
        if self.plan:
            nxt_key, ak = self.plan[0]
            if nxt_key == key:
                self.plan.pop(0)
                return ak
            self.plan = []
        u = self.untried(node)
        if u:
            return self.rank_untried(key, node, u)[0]
        path = self._path_to_frontier(key)
        if path:
            self.plan = path[1:]
            return path[0][1]
        safe = [a for a in node.actions if a not in node.deadly] or node.actions or [1]
        return self.rng.choice(safe)

    def _path_to_frontier(self, start):
        """BFS over known edges; returns [(state, action), ...] to the best frontier."""
        prev = {start: None}
        q = deque([start])
        best, best_score = None, None
        depth = {start: 0}
        while q:
            s = q.popleft()
            n = self.nodes.get(s)
            if n is None:
                continue
            if s != start:
                u = self.untried(n)
                if u:
                    score = (self.state_value(s, n, u), depth[s])
                    if best_score is None or score < best_score:
                        best, best_score = s, score
            if best_score is not None and depth[s] > best_score[1] + 6:
                break
            for ak, t in n.edges.items():
                if ak in n.deadly or t in prev:
                    continue
                prev[t] = (s, ak)
                depth[t] = depth[s] + 1
                q.append(t)
        if best is None:
            return None
        steps = []
        cur = best
        while prev[cur] is not None:
            s, ak = prev[cur]
            steps.append((s, ak))
            cur = s
        steps.reverse()
        return steps
