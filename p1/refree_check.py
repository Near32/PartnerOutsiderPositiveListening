"""Exploratory robustness check (decided 26 Oct 2026 ~08:10 UTC, after the main results): is PoPLi's covert value
an artefact of the outsider being pinned to 'raise' relative to B's previous ask?
No new model calls: it re-analyses data/replies.jsonl two ways.
  1. Dollar shift: 1-Wasserstein distance between ask distributions, id vs para minus id vs id2 (and id vs pooled
     res minus a simulated 5-vs-8 floor), so no categories and no reference price.
  2. Self-referenced categories: the registered categories and tau, but relative to the median of the listener's own
     unchanged replies (id and id2) instead of B's previous ask.
Same clustered bootstrap as the registered analysis. Writes results/exploratory/ and results_exploratory.md only.
Usage: python -m p1.refree_check
"""
import json
from collections import defaultdict

import numpy as np

from p1.common import ROOT, load_config, load_prereg, read_jsonl, write_text_safe
from p1.estimate import bootstrap, per_turn
from p1.transforms import discretise, to_ask


def w1(a, b):
    """1-Wasserstein distance between two empirical distributions (any sizes)."""
    a, b = np.sort(a), np.sort(b)
    grid = np.sort(np.concatenate([a, b]))
    ca = np.searchsorted(a, grid[:-1], side="right") / len(a)
    cb = np.searchsorted(b, grid[:-1], side="right") / len(b)
    return float(np.sum(np.abs(ca - cb) * np.diff(grid)))


def main():
    cfg, pr = load_config(), load_prereg()
    D, OUT = cfg["data_dir"], cfg["results_dir"] / "exploratory"
    OUT.mkdir(parents=True, exist_ok=True)
    turns = {t["turn_id"]: t for t in read_jsonl(D / "turns.jsonl")}
    replies = read_jsonl(D / "replies.jsonl")
    rng = np.random.default_rng(pr["floor_seed"])
    res_v = [f"res{m}" for m in range(1, pr["M"] + 1)]
    asks = defaultdict(list)  # (turn, listener, version) -> numeric asks
    for r in replies:
        a = to_ask(r["ask"]) if not r["invalid"] else None
        if isinstance(a, float):
            asks[(r["turn_id"], r["listener"], r["version"])].append(a)

    # 1. dollar shift, mapped onto the estimator's row schema so the registered bootstrap applies unchanged
    dollar = {}
    for t in turns:
        row = {}
        for L in ("B", "C0"):
            g = {v: asks[(t, L, v)] for v in ["id", "id2", "para"] + res_v}
            pool_res = [x for v in res_v for x in g[v]]
            if not (g["id"] and g["id2"] and g["para"] and pool_res):
                break
            pooled = g["id"] + g["id2"]
            floor = float(np.mean([w1(rng.choice(pooled, len(g["id"])), rng.choice(pooled, len(pool_res)))
                                   for _ in range(pr["floor_simulations"])]))
            raw_pi, raw_marg = w1(g["id"], g["para"]), w1(g["id"], pool_res)
            row[L] = {"pl_pi": raw_pi - w1(g["id"], g["id2"]), "pl_pi_raw": raw_pi,
                      "pl_marg": raw_marg - floor, "pl_marg_raw": raw_marg}
        else:
            dollar[t] = row

    # 2. self-referenced categories: re-discretise against each listener's own median unchanged ask
    ref = {(t, L): float(np.median(asks[(t, L, "id")] + asks[(t, L, "id2")]))
           for t in turns for L in ("B", "C0") if asks[(t, L, "id")] + asks[(t, L, "id2")]}
    selfref = [dict(r, category=discretise(r["ask"], ref[(r["turn_id"], r["listener"])], pr["tau"]),
                    invalid=r["invalid"] or (r["turn_id"], r["listener"]) not in ref
                    or discretise(r["ask"], ref[(r["turn_id"], r["listener"])], pr["tau"]) is None)
               if (r["turn_id"], r["listener"]) in ref else dict(r, invalid=True) for r in replies]

    out, lines = {}, []
    for c in ("covert", "honest"):
        sess = {t: turns[t]["session_id"] for t in turns}
        d = {t: v for t, v in dollar.items() if turns[t]["condition"] == c}
        bd = bootstrap(d, sess, pr["bootstrap"]["replicates"], pr["bootstrap"]["seed"])
        pt, excl = per_turn([r for r in selfref if turns[r["turn_id"]]["condition"] == c], ["B", "C0"], pr["M"],
                            pr["floor_simulations"], rng)
        bs = bootstrap(pt, sess, pr["bootstrap"]["replicates"], pr["bootstrap"]["seed"])
        out[c] = {"dollar_shift": bd, "self_referenced_categories": bs, "excluded_selfref": excl}
        f = lambda b, k: f"{b['point'][k]:.3f} [{b['ci'][k][0]:.3f}, {b['ci'][k][1]:.3f}]"
        for name, b, unit in (("dollar shift", bd, " ($)"), ("self-referenced categories", bs, " (TV)")):
            for k in ("pl_pi(B)", "pl_pi(C0)", "delta_pl", "pl_marg(B)", "pl_marg(C0)"):
                lines.append(f"| {c} | {name}{unit} | {k} | {f(b, k)} | T = {b['T']}, {b['n_sessions']} sessions |")
    write_text_safe(OUT / "refree_check.json", json.dumps(out, indent=2))
    md = ("# Exploratory results (not pre-registered)\n\n"
          "## Reference-free robustness check (post hoc, decided 26 Oct 2026 ~08:10 UTC; not pre-registered)\n\n"
          "Same replies, same clustered bootstrap (2,000 replicates, seed 7, 95% percentile) as the registered analysis.\n"
          "Dollar shift: 1-Wasserstein distance between ask distributions, noise-floor corrected. Self-referenced categories:\n"
          "registered categories and tau = 0.01, relative to the median of the listener's own unchanged replies.\n\n"
          "| condition | measure | quantity | value [95% CI] | n |\n|---|---|---|---|---|\n" + "\n".join(lines) + "\n\n"
          "Source: results/exploratory/refree_check.json; code: p1/refree_check.py.\n")
    write_text_safe(ROOT / "results_exploratory.md", md)
    print(md)


if __name__ == "__main__":
    main()
