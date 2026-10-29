"""Observation-only perception for ARC-AGI-3 frames.

Everything here uses only what the public API returns (the rendered frames,
game state, level counter and available actions). No engine internals.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

GRID = 64


def last_grid(frame_list) -> np.ndarray:
    """Return the settled (last) grid of an observation as int8 64x64."""
    if frame_list is None or len(frame_list) == 0:
        return np.zeros((GRID, GRID), dtype=np.int8)
    g = np.asarray(frame_list[-1], dtype=np.int8)
    if g.shape != (GRID, GRID):
        out = np.zeros((GRID, GRID), dtype=np.int8)
        h, w = min(GRID, g.shape[0]), min(GRID, g.shape[1])
        out[:h, :w] = g[:h, :w]
        g = out
    return g


def grid_hash(g: np.ndarray, mask: np.ndarray | None = None) -> bytes:
    if mask is not None and mask.any():
        g = g.copy()
        g[mask] = -1
    return hashlib.blake2b(g.tobytes(), digest_size=12).digest()


class VolatilityTracker:
    """Detects housekeeping pixels (step counters, energy bars, timers).

    A pixel is volatile when it changes in a large share of the transitions
    in which anything changed. Those pixels are masked out of the state key so
    that a moving counter does not make every state look new.
    """

    def __init__(self, min_transitions: int = 6, ratio: float = 0.6, border: int = 4,
                 border_ratio: float = 0.2):
        self.min_transitions = min_transitions
        self.ratio = ratio
        self.border = border
        self.border_ratio = border_ratio
        self.reset()
        b = border
        self._border = np.zeros((GRID, GRID), dtype=bool)
        self._border[:b, :] = True
        self._border[-b:, :] = True
        self._border[:, :b] = True
        self._border[:, -b:] = True

    def reset(self):
        self.counts = np.zeros((GRID, GRID), dtype=np.int32)
        self.n = 0
        self.mask = np.zeros((GRID, GRID), dtype=bool)
        self.version = 0

    def update(self, before: np.ndarray, after: np.ndarray) -> bool:
        diff = before != after
        if not diff.any():
            return False
        self.counts += diff
        self.n += 1
        if self.n < self.min_transitions:
            return False
        if self.n % 3 and self.version:
            return False
        share = self.counts / self.n
        cand = (share >= self.ratio) | (self._border & (share >= self.border_ratio))
        # never mask more than a third of the screen: that would be the game itself
        if cand.mean() > 0.33:
            cand = share >= max(self.ratio, 0.9)
        new_mask = self.mask | cand          # monotonic: avoids re-keying back and forth
        if new_mask.mean() > 0.33:
            return False
        if (new_mask != self.mask).any():
            self.mask = new_mask
            self.version += 1
            return True
        return False


@dataclass
class Segment:
    color: int
    size: int
    cy: int
    cx: int
    y0: int
    x0: int
    y1: int
    x1: int
    touches_border: bool
    shape_key: bytes


def segments(g: np.ndarray, ignore: np.ndarray | None = None, max_segments: int = 400) -> list[Segment]:
    """4-connected same-colour components, background (largest) removed."""
    h, w = g.shape
    seen = np.zeros((h, w), dtype=bool)
    if ignore is not None:
        seen |= ignore
    out: list[Segment] = []
    flat = g.ravel()
    for start in range(h * w):
        if seen.flat[start]:
            continue
        c = flat[start]
        stack = [start]
        seen.flat[start] = True
        pix = []
        while stack:
            p = stack.pop()
            pix.append(p)
            y, x = divmod(p, w)
            if y > 0:
                q = p - w
                if not seen.flat[q] and flat[q] == c:
                    seen.flat[q] = True; stack.append(q)
            if y < h - 1:
                q = p + w
                if not seen.flat[q] and flat[q] == c:
                    seen.flat[q] = True; stack.append(q)
            if x > 0:
                q = p - 1
                if not seen.flat[q] and flat[q] == c:
                    seen.flat[q] = True; stack.append(q)
            if x < w - 1:
                q = p + 1
                if not seen.flat[q] and flat[q] == c:
                    seen.flat[q] = True; stack.append(q)
        arr = np.array(pix)
        ys, xs = arr // w, arr % w
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        my, mx = ys.mean(), xs.mean()
        k = int(np.argmin((ys - my) ** 2 + (xs - mx) ** 2))
        local = np.zeros((y1 - y0 + 1, x1 - x0 + 1), dtype=np.uint8)
        local[ys - y0, xs - x0] = 1
        shape_key = hashlib.blake2b(np.packbits(local).tobytes() + bytes(local.shape), digest_size=8).digest()
        out.append(Segment(int(c), len(pix), int(ys[k]), int(xs[k]), int(y0), int(x0), int(y1), int(x1),
                           bool(y0 == 0 or x0 == 0 or y1 == h - 1 or x1 == w - 1), shape_key))
        if len(out) >= max_segments:
            break
    if out:
        big = max(out, key=lambda s: s.size)
        out = [s for s in out if s is not big]
    return out


def click_candidates(g: np.ndarray, ignore: np.ndarray | None = None, limit: int = 64) -> list[tuple[int, int, Segment]]:
    """One click per salient segment, ordered by salience (small, interior, rare colour first)."""
    segs = segments(g, ignore)
    if not segs:
        return []
    colour_area = np.bincount(g.ravel().astype(np.int64) & 15, minlength=16)

    def salience(s: Segment):
        return (s.touches_border, s.size > 400, colour_area[s.color] > 1200, s.size)

    segs.sort(key=salience)
    return [(s.cx, s.cy, s) for s in segs[:limit]]
