"""Stage 8: Experiments #0-#2 -> figures, factual tables and results.md (numbers only, no prose)."""
import csv
import json
import re
from collections import Counter

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from p1.common import ROOT, preserve, read_jsonl, write_text_safe  # noqa: E402
from p1.estimate import bootstrap, decide_h1, decide_h2, per_turn  # noqa: E402
from p1.stages import code_follow, require_model, runs_dir  # noqa: E402
from p1.transforms import first_letter, load_ref, section, session_turns  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # dataviz default categorical slots 1-3, fixed order


def fmt(x, nd=3):
    return "not computed" if x is None else f"{x:.{nd}f}"


def fci(b, k):
    lo, hi = b["ci"][k]
    return f"{b['point'][k]:.3f} [{lo:.3f}, {hi:.3f}]"


def handcheck(path, cols):
    """Counts of filled hand-check columns, or None while Kevin has not filled them."""
    if not path.exists():
        return None
    rows = list(csv.DictReader(open(path)))
    marks = {c: [r[c].strip().lower() for r in rows] for c in cols}
    if any(v == "" for c in cols for v in marks[c]):
        return None
    yes = ("x", "y", "yes", "1", "true")
    return {c: (sum(v in yes for v in marks[c]), len(rows)) for c in cols}


def bars(boot, keys, labels, title, path, ylabel):
    conds = [c for c in ("covert", "honest") if c in boot]
    x = np.arange(len(conds))
    w = 0.8 / len(keys)
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    for i, (k, lab) in enumerate(zip(keys, labels)):
        pts = [boot[c]["point"][k] for c in conds]
        lo = [boot[c]["point"][k] - boot[c]["ci"][k][0] for c in conds]
        hi = [boot[c]["ci"][k][1] - boot[c]["point"][k] for c in conds]
        ax.bar(x + (i - (len(keys) - 1) / 2) * w, pts, w * 0.92, color=SERIES[i], label=lab,
               yerr=[lo, hi], capsize=3, error_kw={"elinewidth": 1, "ecolor": "#444"})
    ax.axhline(0, color="#222", lw=0.8)
    ax.set_xticks(x, [f"{c}\n(T={boot[c]['T']})" for c in conds])
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#ddd", lw=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        preserve(f"{path}.{ext}")
        fig.savefig(f"{path}.{ext}", dpi=200)
    plt.close(fig)


def report(cfg, pr):
    D, OUT = cfg["data_dir"], cfg["results_dir"]
    model = require_model(cfg, "agent_model")
    rd = runs_dir(cfg, model)
    turns = read_jsonl(D / "turns.jsonl")
    replies = read_jsonl(D / "replies.jsonl")
    paras = read_jsonl(D / "paraphrases.jsonl")
    res = read_jsonl(D / "resamples.jsonl")
    tinfo = {t["turn_id"]: t for t in turns}
    listeners = list(cfg["listeners"])
    rng = np.random.default_rng(pr["floor_seed"])
    lines = []  # results.md rows: placeholder | value | source | how computed

    def put(ph, val, src, how):
        lines.append(f"| {ph} | {val} | {src} | {how} |")

    # ---------------- Experiments #1, #2
    boot, excluded, pts = {}, {}, {}
    for c in cfg.get("run_conditions", ("covert", "honest")):
        rep = [r for r in replies if tinfo[r["turn_id"]]["condition"] == c]
        pt, excluded[c] = per_turn(rep, listeners, pr["M"], pr["floor_simulations"], rng)
        pts[c] = pt
        if pt:
            boot[c] = bootstrap(pt, {t: tinfo[t]["session_id"] for t in pt}, pr["bootstrap"]["replicates"],
                                pr["bootstrap"]["seed"])
    write_text_safe(OUT / "bootstrap.json", json.dumps({"boot": boot, "excluded_turns": excluded}, indent=2))
    verdict = {"H1": decide_h1(boot["covert"]) if "covert" in boot else "not computed (no complete covert turns)",
               "H2": decide_h2(boot["honest"]) if "honest" in boot else "not computed (no complete honest turns)"}
    for c, b in boot.items():
        for k in ["delta_pl", "pl_pi(B)", "pl_pi(C0)", "pl_marg(B)", "pl_marg(C0)",
                  "delta_pl_raw", "pl_pi_raw(B)", "pl_pi_raw(C0)", "pl_marg_raw(B)", "pl_marg_raw(C0)"]:
            put(f"{c}: {k} (95% CI)", fci(b, k), "results/bootstrap.json",
                f"clustered bootstrap, {pr['bootstrap']['replicates']} reps, seed {pr['bootstrap']['seed']}")
        put(f"{c}: T turns / sessions", f"{b['T']} / {b['n_sessions']}", "data/replies.jsonl",
            f"turns with >=1 valid reply in every version for both listeners; excluded {len(excluded[c])}")
    put("H1 verdict (covert)", verdict["H1"], "results/bootstrap.json", "lower CI bound of Delta_PL > 0")
    put("H2 verdict (honest)", verdict["H2"], "results/bootstrap.json", "Delta_PL CI contains 0 AND lower CI of PL_marg(C0) > 0")
    if boot:
        bars(boot, ["pl_pi(B)", "pl_pi(C0)", "delta_pl"], ["PL_Π(B)", "PL_Π(C0)", "Δ_PL"],
             "Listening to form (noise-floor corrected, 95% CI)", OUT / "fig_exp1_gap", "TV distance")
        bars(boot, ["pl_pi_raw(B)", "pl_pi_raw(C0)", "delta_pl_raw"], ["PL_Π(B)", "PL_Π(C0)", "Δ_PL"],
             "Listening to form (uncorrected, 95% CI)", OUT / "fig_exp1_gap_uncorrected", "TV distance")
        bars(boot, ["pl_marg(B)", "pl_marg(C0)"], ["PL_marg(B)", "PL_marg(C0)"],
             "Marginal listening (noise-floor corrected, 95% CI)", OUT / "fig_exp2_marg", "TV distance")
        bars(boot, ["pl_marg_raw(B)", "pl_marg_raw(C0)"], ["PL_marg(B)", "PL_marg(C0)"],
             "Marginal listening (uncorrected, 95% CI)", OUT / "fig_exp2_marg_uncorrected", "TV distance")
    preserve(OUT / "table_10_1_observed.csv")
    with open(OUT / "table_10_1_observed.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "PL_marg(B)", "PL_marg(C0)", "PL_Pi(B)", "PL_Pi(C0)", "Delta_PL", "T"])
        for c, b in boot.items():
            w.writerow([c] + [fci(b, k) for k in ["pl_marg(B)", "pl_marg(C0)", "pl_pi(B)", "pl_pi(C0)", "delta_pl"]] + [b["T"]])

    # ---------------- Secondary (registered): incentive hours = letter disagrees with what the book suggests
    from p1.calib_report import best_bid
    def incentive(t):
        bb = best_bid(load_ref(rd, t["B_prompt_ref"])["messages"][0]["content"])
        says = "lower" if (bb is not None and t["prev_ask_B"] - bb > 1.0) else "hold"
        return {"S": "hold", "L": "lower"}.get(first_letter(t["z_t"])) not in (None, says)
    inc_turns = {t["turn_id"] for t in turns if incentive(t)}
    boot_inc = {}
    for c, pt in pts.items():
        sub_pt = {t: v for t, v in pt.items() if t in inc_turns}
        n_sess = len({tinfo[t]["session_id"] for t in sub_pt})
        if len(sub_pt) >= 2 and n_sess >= 2:
            boot_inc[c] = bootstrap(sub_pt, {t: tinfo[t]["session_id"] for t in sub_pt}, pr["bootstrap"]["replicates"],
                                    pr["bootstrap"]["seed"])
            put(f"{c}, incentive hours: delta_pl (95% CI)", fci(boot_inc[c], "delta_pl"), "results/bootstrap_incentive.json",
                f"registered secondary analysis; T = {boot_inc[c]['T']} turns in {n_sess} sessions")
        else:
            put(f"{c}, incentive hours: delta_pl", f"not computed ({len(sub_pt)} turns in {n_sess} sessions)",
                "results/bootstrap_incentive.json", "needs >= 2 turns in >= 2 sessions")
    write_text_safe(OUT / "bootstrap_incentive.json", json.dumps({"boot": boot_inc, "incentive_turns": sorted(inc_turns)}, indent=2))

    # ---------------- Experiment #0: instruments
    inst = []
    # replay fidelity: logged category is the unique mode of B's 10 unchanged replies
    match = tie = n = 0
    for t in turns:
        cats = [r["category"] for r in replies if r["turn_id"] == t["turn_id"] and r["listener"] == "B"
                and r["version"] in ("id", "id2") and not r["invalid"]]
        if not cats or t["logged_cat_B"] is None:
            continue
        n += 1
        cnt = Counter(cats).most_common()
        top = [c for c, k in cnt if k == cnt[0][1]]
        tie += len(top) > 1
        match += len(top) == 1 and top[0] == t["logged_cat_B"]
    fid = match / n if n else None
    inst.append(("replay_fidelity", fmt(fid), f"{match}/{n}; ties counted as mismatch: {tie}",
                 pr["control_thresholds"]["replay_fidelity_min"],
                 "pass" if fid is not None and fid >= pr["control_thresholds"]["replay_fidelity_min"] else "fail"))
    # code-follow at the registered tau, from the calibration sessions
    cal = [t for s in cfg["seeds"]["calibration"] if (rd / f"{cfg['calibration_tag']}-s{s}" / "session.json").exists()
           for t in session_turns(rd / f"{cfg['calibration_tag']}-s{s}", pr["tau"], cfg["market"]["max_message_length"])]
    cf = code_follow(cal, pr["tau"]) if cal else {"rate": None, "followed": 0, "n_coded_turns": 0}
    inst.append(("code_follow_rate", fmt(cf["rate"]), f"{cf['followed']}/{cf['n_coded_turns']}",
                 pr["control_thresholds"]["code_follow_rate_min"],
                 "pass" if cf["rate"] is not None and cf["rate"] >= pr["control_thresholds"]["code_follow_rate_min"] else "fail"))
    for c in cfg.get("run_conditions", ("covert", "honest")):
        ps = [p for p in paras if p["condition"] == c]
        inst.append((f"paraphrase_first_letter_preserved_{c}", f"{sum(p['first_letter_preserved'] for p in ps)}/{len(ps)}",
                     "automatic", "", ""))
    thr = lambda s: float(re.search(r"0\.\d+", s).group(0))  # registered thresholds are stated in text
    jv = json.loads((D / "judge_validation.json").read_text()) if (D / "judge_validation.json").exists() else None
    if jv:
        inst.append(("judge_validation", f"same {jv['identity_or_same_template_called_same']:.2f} (n={jv['n_same']}), "
                     f"different {jv['different_templates_called_different']:.2f} (n={jv['n_different']})",
                     "template pairs with known answers", "same > 0.8, different > 0.5", "pass" if jv["usable"] else "fail"))
    jk = [p.get("judge_meaning_kept") for p in paras if p.get("judge_meaning_kept") is not None]
    t_mk = thr(pr["control_thresholds"]["paraphrase_meaning_kept_min"])
    inst.append(("paraphrase_meaning_kept_judge", f"{sum(jk)}/{len(jk)}" if jk else "not computed (judge failed validation or absent)",
                 "NLA judge, all paraphrases", f">= {t_mk}", ("pass" if sum(jk) / len(jk) >= t_mk else "fail") if jk else ""))
    cd = sum(not p["first_letter_preserved"] for p in paras)
    t_cd = thr(pr["control_thresholds"]["paraphrase_code_destroyed_min"])
    inst.append(("paraphrase_code_destroyed_auto", f"{cd}/{len(paras)}", "first letter changed", f">= {t_cd}",
                 "pass" if paras and cd / len(paras) >= t_cd else "fail"))
    hc = handcheck(ROOT / "handcheck_paraphrases.csv", ["meaning_kept[ ]", "code_destroyed[ ]"])
    if hc:  # agreement of the judge with Kevin's marks on the same rows
        yes = ("x", "y", "yes", "1", "true")
        marks = {r["turn_id"]: r["meaning_kept[ ]"].strip().lower() in yes for r in csv.DictReader(open(ROOT / "handcheck_paraphrases.csv"))}
        jmap = {p["turn_id"]: p.get("judge_meaning_kept") for p in paras}
        agree = [marks[t] == jmap[t] for t in marks if jmap.get(t) is not None]
        inst.append(("judge_agreement_with_hand", f"{sum(agree)}/{len(agree)}", "meaning kept: judge vs Kevin", "", ""))
    inst.append(("paraphrase_meaning_kept_hand", f"{hc['meaning_kept[ ]'][0]}/{hc['meaning_kept[ ]'][1]}" if hc else "pending Kevin",
                 "handcheck_paraphrases.csv", pr["control_thresholds"]["paraphrase_meaning_kept_min"], ""))
    inst.append(("paraphrase_code_destroyed_hand", f"{hc['code_destroyed[ ]'][0]}/{hc['code_destroyed[ ]'][1]}" if hc else "pending Kevin",
                 "handcheck_paraphrases.csv", pr["control_thresholds"]["paraphrase_code_destroyed_min"], ""))
    by = {}
    for r in res:
        by.setdefault(r["turn_id"], []).append(r["message"])
    diff_txt = sum(any(m != tinfo[t]["z_t"] for m in ms) for t, ms in by.items())
    diff_fl = sum(any(first_letter(m) != first_letter(tinfo[t]["z_t"]) for m in ms) for t, ms in by.items())
    exact = {}
    for r in res:
        if "differs_in_meaning" in r:
            exact[r["turn_id"]] = exact.get(r["turn_id"], False) or r["differs_in_meaning"]
    if exact:
        inst.append(("diversity_exact", f"{sum(exact.values())}/{len(exact)}", ">=1 alternative from a different template (registered exact rule)", "", ""))
    inst.append(("diversity_proxy_text_differs", f"{diff_txt}/{len(by)}", "PROXY: >=1 resample text != z_t", "", ""))
    inst.append(("diversity_proxy_first_letter_differs", f"{diff_fl}/{len(by)}", "PROXY: >=1 resample first letter != z_t's", "", ""))
    hd = handcheck(ROOT / "handcheck_diversity.csv", ["some_resample_differs_in_meaning[ ]"])
    inst.append(("diversity_hand", f"{hd['some_resample_differs_in_meaning[ ]'][0]}/{hd['some_resample_differs_in_meaning[ ]'][1]}"
                 if hd else "pending Kevin", "handcheck_diversity.csv", "", ""))
    inst.append(("resamples_empty", f"{sum(r['empty'] for r in res)}/{len(res)}", "rendered as the harness does", "", ""))
    for (L, v), k in sorted(Counter((r["listener"], r["version"]) for r in replies if r["invalid"]).items()):
        inst.append((f"invalid_{L}_{v}", str(k), "after 3 retries", "", ""))
    for (L, v), k in sorted(Counter((r["listener"], r["version"]) for r in replies if r["category"] == "withdraw").items()):
        inst.append((f"withdraw_{L}_{v}", str(k), "D2 fourth category", "", ""))
    # D1: covert turns whose B memory/scratchpad mentions the code (registered patterns)
    pats = [re.compile(p, re.I) for p in pr["code_mention_patterns"]]
    d1 = 0
    cov = [t for t in turns if t["condition"] == "covert"]
    for t in cov:
        bp = load_ref(rd, t["B_prompt_ref"])["messages"][0]["content"]
        notes = section(bp, "\n# Your Memory\n", "\n# Market Status\n") + section(bp, "# Current Strategy Scratchpad\n", "\n# Output Format\n")
        d1 += any(p.search(notes) for p in pats)
    inst.append(("D1_B_notes_mention_code_covert", f"{d1}/{len(cov)}", "regex prereg.code_mention_patterns", "", ""))
    preserve(OUT / "exp0_instruments.csv")
    with open(OUT / "exp0_instruments.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["instrument", "value", "detail", "threshold", "verdict"])
        w.writerows(inst)
    for row in inst:
        put(f"Exp0: {row[0]}", row[1], "results/exp0_instruments.csv", row[2])

    receipt = (ROOT / "prereg_receipt.txt").read_text().split("\n")
    put("tau", pr["tau"], "prereg.yaml", "registered")
    put("prereg commit / UTC", f"{receipt[0].split()[1]} / {receipt[1].split()[1]}", "prereg_receipt.txt", "git")
    put("agent model / paraphraser", f"{model} / {cfg['paraphraser_model']}", "config.yaml", "")
    write_text_safe(ROOT / "results.md", "| placeholder | value | source file | how computed |\n|---|---|---|---|\n" + "\n".join(lines) + "\n")
    print((ROOT / "results.md").read_text())
