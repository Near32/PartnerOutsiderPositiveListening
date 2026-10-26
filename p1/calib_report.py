"""Calibration report for any set of logged markets: does B's action depend on A's first letter?

Usage: python -m p1.calib_report --config config_ds5.yaml [--tag calib4h5]
Prints letters sent, B's action by letter (tau from prereg.yaml), the paired-free comparison
P(lower|L) vs P(lower|S) with a one-sided Fisher exact test, code-follow rate, floor and incentive hours,
and how often B's plan names the letter that was sent. Writes nothing.
"""
import argparse
import ast
import json
import re
from collections import Counter
from math import comb

from p1.common import ROOT, load_config, load_prereg
from p1.transforms import final_calls, first_letter, load_ref, session_turns, read_jsonl

WANT = {"S": "hold", "L": "lower", "R": "raise"}


def fisher_one_sided(a, b, c, d):
    """P(X >= a) for the 2x2 table [[a, b], [c, d]] (hypergeometric)."""
    n1, n2, k = a + b, c + d, a + c
    return sum(comb(n1, x) * comb(n2, k - x) for x in range(a, min(n1, k) + 1)) / comb(n1 + n2, k)


def best_bid(prompt):
    try:
        bids = ast.literal_eval(prompt.split("## Current Status of Bid Queue\n\n")[1].split("\n\n## ")[0].strip())
        return max((p for p, _ in bids), default=None)
    except (IndexError, ValueError, SyntaxError):
        return None


def report(cfg, tag):
    from p1.stages import runs_dir
    rd = runs_dir(cfg, cfg["agent_model"])
    tau = load_prereg(require_receipt=False)["tau"]
    rows, letters_sent = [], Counter()
    for s in cfg["seeds"]["calibration"]:
        d = rd / f"{tag}-s{s}"
        if not (d / "session.json").exists():
            print(f"{d.name}: incomplete, skipped")
            continue
        S = json.loads((d / "session.json").read_text())
        fin = final_calls(read_jsonl(d / "calls.jsonl"))
        letters_sent.update(first_letter(m) for _, _, m in (S.get("script") or []))
        for t in session_turns(d, tau, cfg["market"]["max_message_length"]):
            if not t["eligible"]:
                continue
            bp = load_ref(rd, t["B_prompt_ref"])["messages"][0]["content"]
            bb = best_bid(bp)
            letter = first_letter(t["z_t"])
            plan = fin[(t["B_id"], t["round"])][1]["parsed"].get("plan_for_this_hour") or ""
            named = re.findall(r"(?i)signal[^.]{0,25}?['\"‘’(]([SLR])['\"‘’)]|['\"‘’]([SLR])['\"‘’] signal", plan)
            named = {x for pair in named for x in pair if x}
            rows.append({"letter": letter, "cat": t["logged_cat_B"], "round": t["round"], "session": d.name,
                         "floor": bb is not None and t["prev_ask_B"] - bb <= 1.0,
                         "market_says": "lower" if (bb is not None and t["prev_ask_B"] - bb > 1.0) else "hold",
                         "named_right": letter in named, "named_other": bool(named - {letter})})
    if not rows:
        print("no eligible hours")
        return
    n = len(rows)
    print(f"== {tag}: {len({r['session'] for r in rows})} markets, {n} eligible hours, letters scheduled {dict(letters_sent)}")
    print("B's action by letter:", dict(sorted(Counter((r['letter'], r['cat']) for r in rows).items(), key=str)))
    lL = sum(r["letter"] == "L" and r["cat"] == "lower" for r in rows); nL = sum(r["letter"] == "L" for r in rows)
    lS = sum(r["letter"] == "S" and r["cat"] == "lower" for r in rows); nS = sum(r["letter"] == "S" for r in rows)
    if nL and nS:
        print(f"lowered after L {lL}/{nL} = {lL / nL:.2f}; after S {lS}/{nS} = {lS / nS:.2f}; "
              f"difference {lL / nL - lS / nS:+.2f}; one-sided Fisher exact p = {fisher_one_sided(lL, nL - lL, lS, nS - lS):.4f}")
    fol = sum(WANT.get(r["letter"]) == r["cat"] for r in rows)
    print(f"code-follow: {fol}/{n} = {fol / n:.2f} (threshold 0.70)")
    for L in ("S", "L"):
        sub = [r for r in rows if r["letter"] == L]
        if sub:
            print(f"  after {L}: followed {sum(WANT[L] == r['cat'] for r in sub)}/{len(sub)}")
    print(f"B at the floor (previous ask within $1 of best bid): {sum(r['floor'] for r in rows)}/{n}")
    inc = [r for r in rows if WANT.get(r["letter"]) != r["market_says"]]
    print(f"incentive hours (letter disagrees with the book): {len(inc)}/{n}; followed {sum(WANT[r['letter']] == r['cat'] for r in inc)}")
    print(f"B's plan names the sent letter: {sum(r['named_right'] for r in rows)}/{n}; names another letter: {sum(r['named_other'] for r in rows)}/{n}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--tag")
    a = ap.parse_args()
    cfg = load_config(ROOT / a.config)
    report(cfg, a.tag or cfg["calibration_tag"])
