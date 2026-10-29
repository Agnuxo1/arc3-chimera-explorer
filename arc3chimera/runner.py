"""Local evaluation with the official arc_agi scorecard (offline environment files).

Each (game, seed) runs in its own process with its own Arcade, so the
scorecard of that process holds exactly one play of one game. The agent only
sees the public observation (frames, state, level counter, available actions).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

logging.disable(logging.INFO)


def make_policy(name: str, seed: int, **kw):
    if name == "explorer":
        from .explorer import GraphExplorer
        return GraphExplorer(seed=seed)
    if name == "chimera":
        from .chimera import ChimeraAgent
        return ChimeraAgent(seed=seed, **kw)
    if name == "random":
        from .baselines import RandomAgent
        return RandomAgent(seed=seed)
    raise ValueError(name)


def play_one(env_dir: str, game_id: str, policy_name: str, seed: int, max_actions: int,
             max_seconds: float, kw: dict | None = None) -> dict:
    import arc_agi
    from arcengine import GameAction, GameState

    from .explorer import Obs
    from .perception import last_grid

    logging.disable(logging.CRITICAL)
    arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=env_dir)
    env = arcade.make(game_id, seed=seed)
    policy = make_policy(policy_name, seed, **(kw or {}))
    r = env.observation_space
    t0 = time.time()
    n = 0
    level_actions = []
    last_levels = 0
    plays = 1
    while r is not None and r.state != GameState.WIN and n < max_actions and time.time() - t0 < max_seconds:
        obs = Obs(grid=last_grid(r.frame), state=r.state.name, levels=r.levels_completed,
                  available=list(r.available_actions))
        aid, data = policy.act(obs)
        r = env.step(GameAction.from_id(aid), data)
        n += 1
        if r is not None and r.levels_completed != last_levels:
            level_actions.append(n)
            last_levels = r.levels_completed
    sc = arcade.get_scorecard()
    env_scores = [e for e in sc.environments]
    rec = env_scores[0] if env_scores else None
    run_list = rec.runs if rec is not None and hasattr(rec, "runs") else []
    out = {
        "game": game_id, "policy": policy_name, "seed": seed,
        "score": float(rec.score) if rec is not None else 0.0,
        "levels": int(rec.levels_completed) if rec is not None else 0,
        "actions": n, "plays": len(run_list) if run_list else plays,
        "level_actions": level_actions,
        "level_scores": list(run_list[0].level_scores) if run_list and run_list[0].level_scores else [],
        "baseline": list(run_list[0].level_baseline_actions) if run_list and run_list[0].level_baseline_actions else [],
        "seconds": round(time.time() - t0, 2),
        "stats": getattr(policy, "stats", {}),
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-dir", required=True)
    ap.add_argument("--policy", default="explorer")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--games", default="")
    ap.add_argument("--max-actions", type=int, default=3000)
    ap.add_argument("--max-seconds", type=float, default=600)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    ap.add_argument("--kw", default="{}")
    a = ap.parse_args()
    import arc_agi
    logging.disable(logging.CRITICAL)
    arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=a.env_dir)
    games = [e.game_id for e in arcade.available_environments]
    if a.games:
        sel = a.games.split(",")
        games = [g for g in games if g.split("-")[0] in sel]
    seeds = [int(s) for s in a.seeds.split(",")]
    kw = json.loads(a.kw)
    jobs = [(g, s) for s in seeds for g in games]
    results = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(play_one, a.env_dir, g, a.policy, s, a.max_actions, a.max_seconds, kw): (g, s) for g, s in jobs}
        for f in as_completed(futs):
            g, s = futs[f]
            try:
                res = f.result()
            except Exception as e:  # keep the benchmark alive, record the failure
                res = {"game": g, "policy": a.policy, "seed": s, "score": 0.0, "levels": 0, "error": repr(e)}
            results.append(res)
            print(json.dumps({k: res.get(k) for k in ("game", "seed", "score", "levels", "actions", "plays", "seconds", "error")}), flush=True)
    per_seed = {}
    for r in results:
        per_seed.setdefault(r["seed"], []).append(r["score"])
    seed_means = {s: float(np.mean(v)) for s, v in per_seed.items()}
    summary = {
        "policy": a.policy, "kw": kw, "max_actions": a.max_actions, "games": len(games), "seeds": seeds,
        "mean_score": float(np.mean(list(seed_means.values()))),
        "std_score_over_seeds": float(np.std(list(seed_means.values()))),
        "seed_means": seed_means,
        "levels_total_per_seed": {s: int(sum(r["levels"] for r in results if r["seed"] == s)) for s in seeds},
        "errors": sum(1 for r in results if "error" in r),
        "extra_plays": sum(1 for r in results if r.get("plays", 1) > 1),
        "wall_seconds": round(time.time() - t0, 1),
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": sorted(results, key=lambda r: (r["seed"], r["game"]))}, f, indent=1)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
