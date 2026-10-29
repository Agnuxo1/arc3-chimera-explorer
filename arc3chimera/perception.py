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
                 border_ratio: float = 0.2, lines: bool = True, min_line: int = 3):
        self.min_transitions = min_transitions
        self.ratio = ratio
        self.border = border
        self.border_ratio = border_ratio
        # progress bars grow one pixel per action: each pixel changes once, but the
        # border line holding the bar changes on almost every transition
        self.lines = lines
        self.min_line = min_line
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
        self.row_counts = np.zeros(GRID, dtype=np.int32)
        self.col_counts = np.zeros(GRID, dtype=np.int32)

    def _line_mask(self) -> np.ndarray | None:
        b, m = self.border, np.zeros((GRID, GRID), dtype=bool)
        edge = np.r_[0:b, GRID - b:GRID]
        for i in edge:
            if self.row_counts[i] >= self.ratio * self.n:
                m[i, :] = True
            if self.col_counts[i] >= self.ratio * self.n:
                m[:, i] = True
        return m

    def update(self, before: np.ndarray, after: np.ndarray) -> bool:
        diff = before != after
        if not diff.any():
            return False
        self.counts += diff
        self.n += 1
        if self.lines:
            small = diff.sum() <= 2 * GRID       # a bar step, not a full-screen redraw
            if small:
                self.row_counts += diff.any(axis=1)
                self.col_counts += diff.any(axis=0)
            if self.n >= self.min_line:
                lm = self._line_mask() & ~self.mask
                if lm.any() and (self.mask | lm).mean() <= 0.33:
                    self.mask = self.mask | lm
                    self.version += 1
                    return True
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
    """4-connected same-colour components, background (largest) removed.

    Components are labelled with scipy.ndimage per colour and returned in
    raster order of their first pixel.
    """
    try:
        from scipy import ndimage
    except ImportError:          # pure-python fallback, same output order
        return _segments_py(g, ignore, max_segments)
    h, w = g.shape
    valid = np.ones((h, w), dtype=bool) if ignore is None else ~ignore
    found = []
    for c in np.unique(g[valid]):
        lab, n = ndimage.label((g == c) & valid, structure=_FOUR)
        if n == 0:
            continue
        flat = lab.ravel()
        order = np.argsort(flat, kind="stable")
        counts = np.bincount(flat, minlength=n + 1)
        bounds = np.cumsum(counts)
        for i in range(1, n + 1):
            idx = order[bounds[i - 1]:bounds[i]]
            found.append((int(idx[0]), int(c), idx))
    found.sort(key=lambda t: t[0])
    return _build_segments(found, h, w, max_segments)


def _build_segments(found, h, w, max_segments):
    out: list[Segment] = []
    for _, c, arr in found[:max_segments]:
        ys, xs = arr // w, arr % w
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        my, mx = ys.mean(), xs.mean()
        k = int(np.argmin((ys - my) ** 2 + (xs - mx) ** 2))
        local = np.zeros((y1 - y0 + 1, x1 - x0 + 1), dtype=np.uint8)
        local[ys - y0, xs - x0] = 1
        shape_key = hashlib.blake2b(np.packbits(local).tobytes() + bytes(local.shape), digest_size=8).digest()
        out.append(Segment(c, len(arr), int(ys[k]), int(xs[k]), int(y0), int(x0), int(y1), int(x1),
                           bool(y0 == 0 or x0 == 0 or y1 == h - 1 or x1 == w - 1), shape_key))
    if out:
        big = max(out, key=lambda s: s.size)
        out = [s for s in out if s is not big]
    return out


def _segments_py(g, ignore, max_segments):
    h, w = g.shape
    seen = np.zeros((h, w), dtype=bool) if ignore is None else ignore.copy()
    flat = g.ravel()
    found = []
    for start in range(h * w):
        if seen.flat[start]:
            continue
        c = flat[start]
        stack, pix = [start], []
        seen.flat[start] = True
        while stack:
            p = stack.pop()
            pix.append(p)
            y, x = divmod(p, w)
            for q, ok in ((p - w, y > 0), (p + w, y < h - 1), (p - 1, x > 0), (p + 1, x < w - 1)):
                if ok and not seen.flat[q] and flat[q] == c:
                    seen.flat[q] = True
                    stack.append(q)
        found.append((start, int(c), np.sort(np.array(pix))))
    return _build_segments(found, h, w, max_segments)


_FOUR = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])


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
