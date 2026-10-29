"""Paired comparison of runner outputs: per-game score averaged over seeds, Wilcoxon signed-rank.

usage: python scripts/stats.py <reference.json> <candidate.json> [...]
"""
import json
import sys

import numpy as np
from scipy.stats import wilcoxon


def per_game(path):
    d = json.load(open(path, encoding="utf-8"))
    acc = {}
    for r in d["results"]:
        acc.setdefault(r["game"], []).append((r["score"], r["levels"]))
    return {g: (np.mean([s for s, _ in v]), np.mean([l for _, l in v])) for g, v in acc.items()}, d["summary"]


ref, rs = per_game(sys.argv[1])
for cand in sys.argv[2:]:
    c, cs = per_game(cand)
    games = sorted(set(ref) & set(c))
    ds = np.array([c[g][0] - ref[g][0] for g in games])
    dl = np.array([c[g][1] - ref[g][1] for g in games])
    nz = ds[ds != 0]
    p = wilcoxon(nz).pvalue if len(nz) >= 5 else float("nan")
    sm = list(cs["seed_means"].values())
    print(f"{cand.split('/')[-1]:32s} mean={cs['mean_score']:.4f} sd_seeds={np.std(sm):.4f} "
          f"d_score={ds.mean():+.4f} games+={int((ds > 0).sum())} games-={int((ds < 0).sum())} "
          f"d_levels/game={dl.mean():+.2f} wilcoxon_p={p:.4f}")
