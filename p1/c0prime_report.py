"""Report for the post-hoc follow-up C0' (paper, Experiment #1). Pairs B's registered replies
(data/replies.jsonl) with C0''s replies (followups/c0prime/data/replies.jsonl), applies the registered estimator
and bootstrap, checks the prediction committed in followups/c0prime/prereg.yaml, and writes
followups/c0prime/results/bootstrap.json (schema of results/bootstrap.json) plus a section in results_exploratory.md.
Usage: python -m p1.c0prime_report
"""
import json
from collections import Counter

import numpy as np
import yaml

from p1.common import CODE, read_jsonl, write_text_safe
from p1.estimate import bootstrap, per_turn

F = CODE / "followups" / "c0prime"


def main():
    pr = yaml.safe_load(open(F / "prereg.yaml"))
    turns = {t["turn_id"]: t for t in read_jsonl(F / "data" / "turns.jsonl")}
    b = [r for r in read_jsonl(CODE / "data" / "replies.jsonl") if r["listener"] == "B"]
    c = read_jsonl(F / "data" / "replies.jsonl")
    rng = np.random.default_rng(pr["floor_seed"])
    boot, excl, shares, counts = {}, {}, {}, {}
    conds = [x for x in ("covert", "honest") if any(turns[r["turn_id"]]["condition"] == x for r in c)]
    for cond in conds:
        rows = [r for r in b + c if turns[r["turn_id"]]["condition"] == cond]
        pt, excl[cond] = per_turn(rows, ["B", "C0p"], pr["M"], pr["floor_simulations"], rng)
        boot[cond] = bootstrap(pt, {t: turns[t]["session_id"] for t in pt}, pr["bootstrap"]["replicates"], pr["bootstrap"]["seed"])
        un = [r for r in c if turns[r["turn_id"]]["condition"] == cond and r["version"] in ("id", "id2") and not r["invalid"]]
        n = len(un)
        shares[cond] = {k: round(v / n, 3) for k, v in sorted(Counter(r["category"] for r in un).items())}
        cc = [r for r in c if turns[r["turn_id"]]["condition"] == cond]
        counts[cond] = {"invalid": sum(r["invalid"] for r in cc), "withdraw": sum(r["category"] == "withdraw" for r in cc), "n": len(cc)}
    ci = lambda cond, k: boot[cond]["ci"][k]
    verdict = {}
    if "covert" in boot:
        verdict["covert"] = "holds" if ci("covert", "pl_pi(C0p)")[0] <= 0 <= ci("covert", "pl_pi(C0p)")[1] and ci("covert", "delta_pl")[0] > 0 else "does not hold"
    if "honest" in boot:
        verdict["honest"] = "holds" if ci("honest", "delta_pl")[0] <= 0 <= ci("honest", "delta_pl")[1] else "does not hold"
    write_text_safe(F / "results" / "bootstrap.json", json.dumps({"boot": boot, "excluded_turns": excl, "category_shares_unchanged": shares,
                                                                   "counts": counts, "prediction": pr["followup"]["prediction"], "verdict": verdict}, indent=2))
    f = lambda cond, k: f"{boot[cond]['point'][k]:.3f} [{ci(cond, k)[0]:.3f}, {ci(cond, k)[1]:.3f}]"
    lines = []
    for cond in conds:
        for k in ("pl_pi(C0p)", "pl_pi_raw(C0p)", "pl_marg(C0p)", "pl_marg_raw(C0p)", "delta_pl", "delta_pl_raw", "pl_pi(B)"):
            lines.append(f"| {cond} | {k} | {f(cond, k)} | T = {boot[cond]['T']}, {boot[cond]['n_sessions']} sessions |")
        lines.append(f"| {cond} | C0' categories (unchanged message) | {shares[cond]} | invalid {counts[cond]['invalid']}, withdraw {counts[cond]['withdraw']} of {counts[cond]['n']} |")
        lines.append(f"| {cond} | committed prediction | {pr['followup']['prediction'][cond]} | **{verdict[cond]}** |")
    section = ("\n## Post-hoc corrected outsider C0′ (post hoc; prediction committed 2026-10-26 08:24:58 UTC; paper, Experiment #1)\n\n"
               "C0′ = C0 plus the line \"Your most recent ask was $X.\" (B's registered previous ask). B's registered replies reused; "
               "registered estimator and bootstrap (2,000 replicates, seed 7, 95% percentile); Δ = PL_Π(B) − PL_Π(C0′). "
               "Listener key in the JSON: `C0p`.\n\n| condition | quantity | value [95% CI] | n |\n|---|---|---|---|\n" + "\n".join(lines) +
               "\n\nSource: followups/c0prime/results/bootstrap.json; code: p1/c0prime_report.py; prediction: followups/c0prime/prereg.yaml.\n")
    md_path = CODE / "results_exploratory.md"
    md = md_path.read_text()
    marker = "\n## Post-hoc corrected outsider C0′"
    md = (md[:md.index(marker)] if marker in md else md.rstrip("\n") + "\n") + section
    write_text_safe(md_path, md)
    print(section)


if __name__ == "__main__":
    main()
