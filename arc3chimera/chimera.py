"""CHIMERA world model for ARC-AGI-3 (numpy port of the CHIMERA principle).

CHIMERA (Agnuxo1/ARC2_CHIMERA) computes with cellular-automaton texture
updates and a holographic memory in OpenGL shaders. The Kaggle runtime has no
display, so the same two ingredients are ported to numpy here:

* Holographic memory: every context feature f has a fixed random phase vector
  exp(i*phi_f) of dimension D. An action context is the superposition of its
  feature vectors (one complex trace). Three traces store what happened after
  each action: EFFECT (state changed / no-op), GOAL (level completed) and
  DEADLY (game over). Writes use the delta rule, reads are the normalised real
  correlation, so similar contexts share what was learned.
* Cellular-automaton rule table: the 3x3 neighbourhood around a click and the
  action id form a local rule key; its observed outcomes are written into the
  same traces as one more feature, i.e. local rules generalise across states.

The memory persists across levels of a game (the control forgets everything at
each level). The world model only re-ranks which untried action to try next
and which frontier state to visit; exploration stays complete, so an untried
action predicted useless is postponed, never removed.
"""
from __future__ import annotations

import hashlib

import numpy as np

from .explorer import GraphExplorer, Node


def _phase_vector(feature: tuple, dim: int, salt: int = 0) -> np.ndarray:
    seed = int.from_bytes(hashlib.blake2b(repr((salt, feature)).encode(), digest_size=8).digest(), "little")
    rng = np.random.default_rng(seed)
    return np.exp(1j * rng.uniform(0, 2 * np.pi, dim)).astype(np.complex64)


def _patch(grid: np.ndarray, y: int, x: int, r: int) -> np.ndarray:
    """(2r+1)^2 neighbourhood of (y, x), -1 outside the screen: a local CA rule context."""
    p = np.full((2 * r + 1, 2 * r + 1), -1, dtype=np.int8)
    y0, y1, x0, x1 = max(0, y - r), min(grid.shape[0], y + r + 1), max(0, x - r), min(grid.shape[1], x + r + 1)
    p[y0 - y + r:y1 - y + r, x0 - x + r:x1 - x + r] = grid[y0:y1, x0:x1]
    return p


class HolographicMemory:
    """Complex phase associative memory with delta-rule writes."""

    def __init__(self, dim: int = 512, lr: float = 0.5, salt: int = 0):
        self.dim = dim
        self.salt = salt
        self.lr = lr
        self.trace = np.zeros(dim, dtype=np.complex64)
        self.cache: dict = {}
        self.writes = 0

    def key(self, feats: list) -> np.ndarray:
        k = np.zeros(self.dim, dtype=np.complex64)
        for f in feats:
            v = self.cache.get(f)
            if v is None:
                v = _phase_vector(f, self.dim, self.salt)
                self.cache[f] = v
            k += v
        return k / max(1, len(feats))

    def read(self, k: np.ndarray) -> float:
        return float(np.real(np.vdot(k, self.trace)) / self.dim)

    def write(self, k: np.ndarray, target: float):
        err = target - self.read(k)
        norm = float(np.real(np.vdot(k, k))) / self.dim or 1.0
        self.trace += (self.lr * err / norm) * k
        self.writes += 1


class ChimeraAgent(GraphExplorer):
    name = "chimera"

    def __init__(self, seed: int = 0, dim: int = 512, alpha: float = 2.0, persist: bool = True,
                 use_ca: bool = True, use_goal: bool = True, use_dead: bool = True, use_kbca: bool = False,
                 salt_seed: bool = False, **kw):
        super().__init__(seed=seed, **kw)
        self.dim, self.alpha, self.persist = dim, alpha, persist
        self.use_ca, self.use_goal, self.use_dead = use_ca, use_goal, use_dead
        self.use_kbca = use_kbca
        self.salt = seed if salt_seed else 0
        self.kb_loc: dict = {}
        self._init_memory()
        self.stats.update({"wm_reorders": 0, "wm_writes": 0})

    def _init_memory(self):
        self.effect = HolographicMemory(self.dim, salt=self.salt)
        self.goal = HolographicMemory(self.dim, salt=self.salt)
        self.dead = HolographicMemory(self.dim, salt=self.salt)
        self.fcache: dict = {}

    # ----- features ----------------------------------------------------------
    def features(self, grid: np.ndarray, ak, seg=None) -> list:
        if not isinstance(ak, tuple):
            f = [("a", ak)]
            loc = self.kb_loc.get(ak) if self.use_kbca else None
            if loc is not None:
                f.append(("kb", ak, _patch(grid, loc[0], loc[1], 3).tobytes()))
            return f
        _, x, y = ak
        f = [("click",)]
        if seg is not None:
            f += [("c", seg.color), ("cs", seg.color, seg.shape_key), ("sz", seg.color, min(seg.size, 63) // 8),
                  ("bd", seg.touches_border)]
        else:
            f.append(("c", int(grid[y, x])))
        if self.use_ca:
            y0, y1, x0, x1 = max(0, y - 1), min(64, y + 2), max(0, x - 1), min(64, x + 2)
            patch = np.full((3, 3), -1, dtype=np.int8)
            patch[y0 - y + 1:y1 - y + 1, x0 - x + 1:x1 - x + 1] = grid[y0:y1, x0:x1]
            f.append(("ca", patch.tobytes()))
        return f

    def _key(self, node_key, node: Node, ak):
        ck = (node_key, ak, self.kb_loc.get(ak) if self.use_kbca and not isinstance(ak, tuple) else None)
        k = self.fcache.get(ck)
        if k is None:
            k = self.effect.key(self.features(node.grid, ak, node.meta.get(ak)))
            self.fcache[ck] = k
        return k

    def value(self, node_key, node: Node, ak) -> float:
        k = self._key(node_key, node, ak)
        v = self.effect.read(k)
        if self.use_goal:
            v += 2.0 * max(0.0, self.goal.read(k))
        if self.use_dead:
            v -= 2.0 * max(0.0, self.dead.read(k))
        return v

    # ----- hooks -------------------------------------------------------------
    def rank_untried(self, key, node: Node, untried: list) -> list:
        base = super().rank_untried(key, node, untried)
        if self.effect.writes == 0:
            return base
        order = {a: i for i, a in enumerate(base)}
        ranked = sorted(untried, key=lambda a: (node.tier.get(a, 0) - self.alpha * self.value(key, node, a), order[a]))
        if ranked[0] != base[0]:
            self.stats["wm_reorders"] += 1
        return ranked

    def state_value(self, key, node: Node, untried: list) -> float:
        if self.effect.writes == 0:
            return super().state_value(key, node, untried)
        return min(node.tier.get(a, 0) - self.alpha * self.value(key, node, a) for a in untried)

    def learn(self, prev, ak, obs, outcome, key_from, key_to):
        node = self.nodes.get(key_from)
        if node is None:
            return
        k = self._key(key_from, node, ak)
        changed = outcome != "step" or (key_to is not None and key_to != key_from)
        if self.use_kbca and not isinstance(ak, tuple) and outcome == "step" and changed:
            d = (prev.grid != obs.grid) & ~self.vol.mask
            if d.any():
                ys, xs = np.nonzero(d)
                self.kb_loc[ak] = (int(ys.mean()), int(xs.mean()))
        self.effect.write(k, 1.0 if changed else -1.0)
        if self.use_goal:
            self.goal.write(k, 1.0 if outcome == "level_up" else 0.0)
        if self.use_dead:
            self.dead.write(k, 1.0 if outcome == "deadly" else 0.0)
        self.stats["wm_writes"] += 1

    def _rebuild(self):
        self.fcache = {}
        super()._rebuild()

    def _new_level(self):
        super()._new_level()
        self.fcache = {}
        if not getattr(self, "persist", True) and hasattr(self, "effect"):
            self._init_memory()
