"""Estimators (§4.5) and inference (§4.6). Inputs are the §7 JSONL schemas only, never harness internals."""
from collections import Counter, defaultdict

import numpy as np

from p1.transforms import CATEGORIES

IDX = {c: i for i, c in enumerate(CATEGORIES)}


def dist(cats):
    v = np.zeros(len(CATEGORIES))
    for c in cats:
        v[IDX[c]] += 1
    return v / v.sum()


def tv(p, q):
    return 0.5 * float(np.abs(np.asarray(p) - np.asarray(q)).sum())


def floor_sim(pooled, n1, n2, sims, rng):
    """E[TV] between an n1- and an n2-sample empirical distribution drawn iid from the pooled empirical."""
    p = dist(pooled)
    a = rng.multinomial(n1, p, size=sims) / n1
    b = rng.multinomial(n2, p, size=sims) / n2
    return float(0.5 * np.abs(a - b).sum(axis=1).mean())


def per_turn(replies, listeners, M, sims, rng):
    """{turn_id: {listener: {pl_pi, pl_pi_raw, pl_marg, pl_marg_raw}}} for turns where every needed
    version has >= 1 valid reply for every listener; also returns the excluded turn ids with reasons."""
    by = defaultdict(list)
    for r in replies:
        if not r["invalid"]:
            by[(r["turn_id"], r["listener"], r["version"])].append(r["category"])
    turns = sorted({r["turn_id"] for r in replies})
    res = [f"res{m}" for m in range(1, M + 1)]
    out, excluded = {}, {}
    for t in turns:
        row = {}
        for L in listeners:
            g = {v: by[(t, L, v)] for v in ["id", "id2", "para"] + res}
            missing = [v for v, c in g.items() if not c]
            if missing:
                excluded[t] = f"{L}: no valid reply for {missing}"
                break
            p_id, p_id2, p_para = dist(g["id"]), dist(g["id2"]), dist(g["para"])
            p_marg = np.mean([dist(g[v]) for v in res], axis=0)
            n_marg = sum(len(g[v]) for v in res)
            f = floor_sim(g["id"] + g["id2"], len(g["id"]), n_marg, sims, rng)
            raw_pi, raw_marg = tv(p_id, p_para), tv(p_id, p_marg)
            row[L] = {"pl_pi": raw_pi - tv(p_id, p_id2), "pl_pi_raw": raw_pi,
                      "pl_marg": raw_marg - f, "pl_marg_raw": raw_marg, "floor_pi": tv(p_id, p_id2), "floor_marg": f}
        else:
            out[t] = row
    return out, excluded


def quantities(rows):
    """Means over a list of per-turn rows (listener B and one outsider: C0 in the core, C3 in a follow-up)."""
    q = {}
    for k in ["pl_pi", "pl_pi_raw", "pl_marg", "pl_marg_raw"]:
        for L in rows[0]:
            q[f"{k}({L})"] = float(np.mean([r[L][k] for r in rows]))
    outsider = next(L for L in rows[0] if L != "B")
    for suffix in ["", "_raw"]:
        q[f"delta_pl{suffix}"] = q[f"pl_pi{suffix}(B)"] - q[f"pl_pi{suffix}({outsider})"]
    return q


def bootstrap(pt, session_of, replicates, seed, level=0.95):
    """Sessions with replacement, then turns within each drawn session with replacement; B and C0
    share the resampled turns. Returns point estimates, percentile intervals and T."""
    rng = np.random.default_rng(seed)
    by_s = defaultdict(list)
    for t in sorted(pt):
        by_s[session_of[t]].append(pt[t])
    sessions = sorted(by_s)
    point = quantities([pt[t] for t in sorted(pt)])
    draws = defaultdict(list)
    for _ in range(replicates):
        rows = []
        for s in rng.choice(sessions, size=len(sessions), replace=True):
            ts = by_s[s]
            rows += [ts[i] for i in rng.integers(0, len(ts), size=len(ts))]
        for k, v in quantities(rows).items():
            draws[k].append(v)
    a = (1 - level) / 2 * 100
    ci = {k: (float(np.percentile(v, a)), float(np.percentile(v, 100 - a))) for k, v in draws.items()}
    return {"point": point, "ci": ci, "T": len(pt), "n_sessions": len(sessions)}


def decide_h1(b):
    lo = b["ci"]["delta_pl"][0]
    return "holds" if lo > 0 else "falsified"


def decide_h2(b):
    lo, hi = b["ci"]["delta_pl"]
    if not (lo <= 0 <= hi):
        return "falsified"
    return "holds" if b["ci"]["pl_marg(C0)"][0] > 0 else "trivial pass not ruled out"


def invalid_counts(replies):
    return Counter((r["listener"], r["version"]) for r in replies if r["invalid"])
