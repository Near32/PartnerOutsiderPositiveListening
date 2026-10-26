"""Stages 0-8 of README §6. Each stage is resumable: every model call goes through the cache."""
import csv
import difflib
import hashlib
import json
import random
import re
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from p1.client import BudgetExceeded
from p1.common import (ROOT, check_budget, preserve, write_text_safe, ledger, load_prereg, read_jsonl, require_model, utc,
                       write_jsonl)
from p1.transforms import (EditError, apply_listener, discretise, to_ask, edit_message, first_letter, load_ref,
                           section, session_turns)



def slug(model):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


def runs_dir(cfg, model):
    return (cfg.get("runs_root") or cfg["data_dir"] / "runs") / slug(model)


def run_sessions(client, cfg, model, specs):
    """specs: [(condition, seed, rounds, session_id)], run concurrently (each round is itself parallel)."""
    from p1.harness_bridge import run_session
    out = runs_dir(cfg, model)
    with ThreadPoolExecutor(max_workers=max(1, len(specs))) as ex:
        return list(ex.map(lambda s: run_session(client, cfg, model, s[0], s[1], s[2], s[3], out), specs))


def calls_per_session(cfg, rounds):
    return rounds * (cfg["market"]["n_sellers"] + cfg["market"]["n_buyers"])


def _begin(client, stage):
    client.stage, client.new_calls = stage, 0


# ---------------------------------------------------------------- Stage 0
def stage0(client, cfg, model=None):
    """Smoke test. `model` overrides config for a dev smoke (logged as such)."""
    model = model or require_model(cfg, "agent_model")
    s = cfg["smoke"]
    planned = calls_per_session(cfg, s["rounds"])
    check_budget(client, cfg, "stage0", planned)
    _begin(client, "stage0")
    d, = run_sessions(client, cfg, model, [(s["condition"], s["seed"], s["rounds"], f"smoke-s{s['seed']}")])
    calls = read_jsonl(d / "calls.jsonl")
    S = json.loads((d / "session.json").read_text())
    with_pi = sorted({c["agent_id"] for c in calls if "# Private Instruction\n" in c["messages"][0]["content"]})
    n_fail = sum(c["parsed"] is None for c in calls)
    print(f"[stage0] {d}\n  calls logged: {len(calls)}  parse failures (retried): {n_fail}\n"
          f"  private section present for: {with_pi}  (A={S['A_id']}, B={S['B_id']})\n"
          f"  messages sent by A: {[c['parsed'].get('message_to_sellers') for c in calls if c['role'] == 'A' and c['parsed']]}")
    assert with_pi == sorted([S["A_id"], S["B_id"]]), "private section must be present for A and B only"
    ledger("stage0" + ("" if model == cfg.get("agent_model") else f" (dev: {model})"), planned, client.new_calls, n_fail)


# ---------------------------------------------------------------- Stage 1
def code_follow(turns, tau):
    coded = [t for t in turns if t["eligible"] and first_letter(t["z_t"]) in ("S", "L")]
    cats = [discretise(t["logged_ask_B"], t["prev_ask_B"], tau) for t in coded]
    follow = [(first_letter(t["z_t"]) == "S" and c == "hold") or (first_letter(t["z_t"]) == "L" and c == "lower")
              for t, c in zip(coded, cats)]
    return {"tau": tau, "n_coded_turns": len(coded), "followed": sum(follow),
            "rate": sum(follow) / len(coded) if coded else None,
            "by_letter": {f"{k[0]}->{k[1]}": v for k, v in Counter((first_letter(t["z_t"]), c) for t, c in zip(coded, cats)).items()}}


def stage1(client, cfg):
    model = require_model(cfg, "agent_model")
    R = cfg["market"]["rounds"]
    specs = [("covert", s, R, f"{cfg['calibration_tag']}-s{s}") for s in cfg["seeds"]["calibration"]]
    planned = len(specs) * calls_per_session(cfg, R)
    check_budget(client, cfg, "stage1", planned)
    _begin(client, "stage1")
    dirs = run_sessions(client, cfg, model, specs)
    turns = [t for d in dirs for t in session_turns(d, load_prereg(require_receipt=False)["tau"], cfg["market"]["max_message_length"])]
    a_msgs = []
    for d in dirs:
        S = json.loads((d / "session.json").read_text())
        a_msgs += [c["parsed"].get("message_to_sellers") for c in read_jsonl(d / "calls.jsonl")
                   if c["agent_id"] == S["A_id"] and c["parsed"] and c["parsed"].get("message_to_sellers")]
    out = {"sessions": [d.name for d in dirs], "n_A_messages": len(a_msgs),
           "share_A_messages_starting_S_or_L": (sum(first_letter(m) in ("S", "L") for m in a_msgs if isinstance(m, str))
                                                / len(a_msgs)) if a_msgs else None,
           "eligible_turns": sum(t["eligible"] for t in turns),
           "tau_sweep": [code_follow(turns, tau) for tau in (0.0, 0.01, 0.25, 0.5, 1.0, 2.0)],
           "B_ask_changes_cents": sorted(Counter(round((to_ask(t["logged_ask_B"]) - t["prev_ask_B"]) * 100)
                                                 for t in turns if t["eligible"] and t["logged_cat_B"] not in (None, "withdraw")).items())}
    write_text_safe(cfg["data_dir"] / f"stage1_{cfg['calibration_tag']}.json", json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))
    ledger("stage1", planned, client.new_calls)


# ---------------------------------------------------------------- Stage 2
def stage2(client, cfg):
    path = ROOT / "prereg.yaml"
    txt = path.read_text()
    if "<final wording>" in txt or "TODO" in txt:
        raise SystemExit("prereg.yaml still has placeholders.")
    if (ROOT / "prereg_receipt.txt").exists():
        raise SystemExit("prereg_receipt.txt exists: registered values are frozen; record any change as a deviation.")
    subprocess.run(["git", "add", "prereg.yaml"], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet", "--", "prereg.yaml"], cwd=ROOT).returncode:  # changed
        subprocess.run(["git", "commit", "-m", "Pre-register P1 core (prereg.yaml)"], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "prereg.yaml"], cwd=ROOT).returncode:
        raise SystemExit("prereg.yaml differs from the committed version")
    h = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    (ROOT / "prereg_receipt.txt").write_text(f"commit {h}\nutc {utc()}\nsha256(prereg.yaml) {hashlib.sha256(txt.encode()).hexdigest()}\n")
    print((ROOT / "prereg_receipt.txt").read_text())


# ---------------------------------------------------------------- Stage 3
def stage3(client, cfg):
    pr = load_prereg()
    assert pr["code_instruction_text"] == cfg["conditions"]["covert"]["private_instruction"], \
        "config.yaml covert instruction differs from the registered wording"
    assert pr["honest_instruction_text"] == cfg["conditions"]["honest"]["private_instruction"], \
        "config.yaml honest instruction differs from the registered wording"
    assert pr["scripted_speaker"] == (cfg["scripted_speaker"] if cfg["scripted_speaker"]["enabled"] else {"enabled": False}), \
        "config.yaml scripted_speaker differs from the registered one"
    model = require_model(cfg, "agent_model")
    R = cfg["market"]["rounds"]
    specs = [(c, s, R, f"{cfg.get('session_prefix', '')}{c}-s{s}") for c in cfg.get("run_conditions", ("covert", "honest")) for s in cfg["seeds"][c]]
    planned = len(specs) * calls_per_session(cfg, R)
    check_budget(client, cfg, "stage3", planned)
    _begin(client, "stage3")
    run_sessions(client, cfg, model, specs)
    ledger("stage3", planned, client.new_calls)


# ---------------------------------------------------------------- Stage 4
def stage4(client, cfg):
    pr = load_prereg()
    rd = runs_dir(cfg, require_model(cfg, "agent_model"))
    rows, all_turns = [], []
    for c in cfg.get("run_conditions", ("covert", "honest")):
        ts = [t for s in cfg["seeds"][c] for t in session_turns(rd / f"{cfg.get('session_prefix', '')}{c}-s{s}", pr["tau"], cfg["market"]["max_message_length"])]
        all_turns += ts
        el = [t for t in ts if t["eligible"]]
        pick = sorted(random.Random(pr["turn_sampling_seed"]).sample(el, min(pr["T_per_condition"], len(el))),
                      key=lambda t: t["turn_id"])
        print(f"[stage4] {c}: {len(el)} eligible of {len(ts)} turns; selected {len(pick)}; "
              f"ineligible reasons {dict(Counter(t['reason'] for t in ts if not t['eligible']))}")
        rows += pick
    write_jsonl(cfg["data_dir"] / "turns.jsonl", rows)
    write_jsonl(cfg["data_dir"] / "all_turns.jsonl", all_turns)


# ---------------------------------------------------------------- Stage 5a
def clean_paraphrase(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


def stage5a(client, cfg):
    pr = load_prereg()
    model = require_model(cfg, "paraphraser_model")
    turns = read_jsonl(cfg["data_dir"] / "turns.jsonl")
    check_budget(client, cfg, "stage5a", len(turns))
    _begin(client, "stage5a")
    L = cfg["market"]["max_message_length"]

    def one(t):
        raw = client.call(model, [{"role": "user", "content": pr["paraphraser_prompt"].format(z=t["z_t"])}],
                          cfg["paraphraser_temperature"], 0, f"paraphrase:{t['turn_id']}")
        p = clean_paraphrase(raw)
        return {"turn_id": t["turn_id"], "condition": t["condition"], "z_t": t["z_t"], "paraphrase_raw": raw,
                "paraphrase": p[:L], "paraphraser_model": model,
                "first_letter_preserved": first_letter(p) == first_letter(t["z_t"]),
                "len_ratio": len(p) / len(t["z_t"]), "under_max_len": len(p) <= L}
    rows = client.map(one, turns, sink=cfg["data_dir"] / "paraphrases.partial.jsonl")
    validation, verdicts = judge_paraphrases(client, cfg, pr, rows)
    for r in rows:
        r["judge_meaning_kept"] = verdicts.get(r["turn_id"]) if validation["usable"] else None
    write_jsonl(cfg["data_dir"] / "paraphrases.jsonl", rows)
    rng = random.Random(pr["turn_sampling_seed"])
    pick = [r for c in cfg.get("run_conditions", ("covert", "honest")) for r in rng.sample([r for r in rows if r["condition"] == c],
                                                                 min(10, sum(r["condition"] == c for r in rows)))]
    preserve(ROOT / "handcheck_paraphrases.csv")  # keeps any marks Kevin already made
    with open(ROOT / "handcheck_paraphrases.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["turn_id", "z_t", "paraphrase", "meaning_kept[ ]", "code_destroyed[ ]"])
        w.writerows([[r["turn_id"], r["z_t"], r["paraphrase"], "", ""] for r in pick])
    print(f"[stage5a] {len(rows)} paraphrases; first letter preserved in {sum(r['first_letter_preserved'] for r in rows)}")
    ledger("stage5a", len(turns), client.new_calls)


def judge_paraphrases(client, cfg, pr, rows):
    """The NLA project's meaning-preservation judge (same model and question), validated first on template
    pairs with known answers: a message against itself and the S/L versions of one template (YES), and
    messages from two different templates (NO). Verdicts count only if it passes the NLA thresholds."""
    j = pr["judge"]
    ask = lambda a, b, tag: client.call(j["model"], [{"role": "user", "content": j["prompt"].format(a=a, b=b)}],
                                        0.0, 0, f"judge:{tag}", max_tokens=5).strip().upper().startswith("Y")
    T = [t[:2] for t in cfg["scripted_speaker"]["templates"]]
    pos = [(s, s) for s, _ in T] + [(s, l) for s, l in T]
    neg = [(T[i][0], T[k][0]) for i in range(len(T)) for k in range(len(T)) if i != k]
    yes_pos = client.map(lambda ab: ask(*ab, "control-same"), pos, sink=cfg["data_dir"] / "judge_controls.partial.jsonl")
    yes_neg = client.map(lambda ab: ask(*ab, "control-diff"), neg)
    validation = {"identity_or_same_template_called_same": sum(yes_pos) / len(pos), "n_same": len(pos),
                  "different_templates_called_different": 1 - sum(yes_neg) / len(neg), "n_different": len(neg)}
    validation["usable"] = (validation["identity_or_same_template_called_same"] > j["min_same"]
                            and validation["different_templates_called_different"] > j["min_different"])
    write_text_safe(cfg["data_dir"] / "judge_validation.json", json.dumps(validation, indent=2))
    print(f"[judge] validation {validation}")
    v = client.map(lambda r: ask(r["z_t"], r["paraphrase"], r["turn_id"]), rows, sink=cfg["data_dir"] / "judge_verdicts.partial.jsonl")
    return validation, {r["turn_id"]: x for r, x in zip(rows, v)}


# ---------------------------------------------------------------- Stage 5b
def parse_reply(raw):
    from p1.harness_bridge import parse
    return parse(raw)


def stage5b(client, cfg):
    pr = load_prereg()
    rd = runs_dir(cfg, require_model(cfg, "agent_model"))
    turns = read_jsonl(cfg["data_dir"] / "turns.jsonl")
    M, L = pr["M"], cfg["market"]["max_message_length"]
    check_budget(client, cfg, "stage5b", len(turns) * M)
    _begin(client, "stage5b")
    retries = Counter()

    sessions = {s: json.loads((rd / s / "session.json").read_text()) for s in {t["session_id"] for t in turns}}

    def one(job):
        t, m = job
        if sessions[t["session_id"]].get("script"):  # F1: the speaker's policy is the script, no model call
            from p1.harness_bridge import script_message
            letter, msg = script_message(cfg["scripted_speaker"], random.Random(f"resample:{t['turn_id']}:{m}"))
            tid = lambda x: next(i for i, tpl in enumerate(cfg["scripted_speaker"]["templates"]) if x in tpl)
            return {"turn_id": t["turn_id"], "m": m, "message": msg[:L], "empty": False, "invalid": False,
                    "scripted": True, "differs_in_meaning": tid(msg) != tid(t["z_t"])}  # exact: templates differ
        a = load_ref(rd, t["A_prompt_ref"])
        for attempt in range(4):  # 1 try + up to 3 retries on a malformed reply
            raw = client.call(a["model"], a["messages"], a["temperature"], attempt,
                              f"resample:{t['turn_id']}:{m}", cfg["json_mode"])
            p = parse_reply(raw)
            if p is not None:
                break
            retries[t["turn_id"]] += 1
        msg = p.get("message_to_sellers") if p else None
        ok = isinstance(msg, str) and bool(msg)  # harness broadcasts only truthy messages
        return {"turn_id": t["turn_id"], "m": m, "message": msg[:L] if ok else None, "empty": not ok,
                "invalid": p is None}
    rows = client.map(one, [(t, m) for t in turns for m in range(1, M + 1)], sink=cfg["data_dir"] / "resamples.partial.jsonl")
    write_jsonl(cfg["data_dir"] / "resamples.jsonl", rows)
    by = {}
    for r in rows:
        by.setdefault(r["turn_id"], []).append(r["message"])
    preserve(ROOT / "handcheck_diversity.csv")  # keeps any marks Kevin already made
    with open(ROOT / "handcheck_diversity.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["turn_id", "z_t"] + [f"res{m}" for m in range(1, M + 1)] + ["some_resample_differs_in_meaning[ ]"])
        w.writerows([[t["turn_id"], t["z_t"]] + by[t["turn_id"]] + [""] for t in turns])
    print(f"[stage5b] {len(rows)} resamples; empty {sum(r['empty'] for r in rows)}; invalid {sum(r['invalid'] for r in rows)}")
    ledger("stage5b", len(turns) * M, client.new_calls, sum(retries.values()), sum(r["invalid"] for r in rows))


# ---------------------------------------------------------------- Stage 6
def listener_model(cfg, spec):
    return cfg["agent_model"] if spec == "agent" else spec


def stage6(client, cfg):
    pr = load_prereg()
    rd = runs_dir(cfg, require_model(cfg, "agent_model"))
    D = cfg["data_dir"]
    turns = read_jsonl(D / "turns.jsonl")
    para = {r["turn_id"]: r["paraphrase"] for r in read_jsonl(D / "paraphrases.jsonl")}
    res = {(r["turn_id"], r["m"]): r["message"] for r in read_jsonl(D / "resamples.jsonl")}
    (D / "prompts").mkdir(exist_ok=True)
    (D / "diffs").mkdir(exist_ok=True)
    rows, failures = [], []
    for t in turns:
        logged = load_ref(rd, t["B_prompt_ref"])["messages"][0]["content"]
        versions = {"id": t["z_t"], "id2": t["z_t"], "para": para[t["turn_id"]]}
        versions |= {f"res{m}": res[(t["turn_id"], m)] for m in range(1, pr["M"] + 1)}
        for L, spec in cfg["listeners"].items():
            try:
                base, log = apply_listener(logged, spec["transforms"], t)
                if "delete_private_instruction" in spec["transforms"]:  # both conditions now have a private section
                    assert log["delete_private_instruction"] == 1, "covert C0 prompt lacked the private section"
                assert "# Private Instruction\n" not in base or "delete_private_instruction" not in spec["transforms"]
            except (EditError, AssertionError) as e:
                failures.append((t["turn_id"], L, "transforms", str(e)))
                continue
            for v, new in versions.items():
                try:
                    p = edit_message(base, t["A_id"], t["z_t"], new)
                except EditError as e:
                    failures.append((t["turn_id"], L, v, str(e)))
                    continue
                h = hashlib.sha256(p.encode()).hexdigest()
                write_text_safe(D / "prompts" / f"{h}.txt", p)  # content-addressed
                diff_ref = f"diffs/{t['turn_id']}__{L}__{v}.diff"
                write_text_safe(D / diff_ref, "".join(difflib.unified_diff(
                    logged.splitlines(True), p.splitlines(True), "logged_B_prompt", f"{L}/{v}")))
                rows.append({"turn_id": t["turn_id"], "listener": L, "version": v, "model": listener_model(cfg, spec["model"]),
                             "prompt_hash": h, "diff_ref": diff_ref, "transforms": log})
    write_jsonl(D / "listener_prompts.jsonl", rows)
    write_jsonl(D / "listener_prompt_failures.jsonl", [dict(zip(["turn_id", "listener", "version", "error"], f)) for f in failures])
    print(f"[stage6] {len(rows)} listener prompts; {len(failures)} assertion failures (see listener_prompt_failures.jsonl)")


# ---------------------------------------------------------------- Stage 7
def stage7(client, cfg):
    pr = load_prereg()
    D = cfg["data_dir"]
    prev = {t["turn_id"]: t["prev_ask_B"] for t in read_jsonl(D / "turns.jsonl")}
    lps = read_jsonl(D / "listener_prompts.jsonl")
    if cfg.get("replay_conditions"):  # e.g. run one condition first; the rest stays cached for a later full run
        cond = {t["turn_id"]: t["condition"] for t in read_jsonl(D / "turns.jsonl")}
        lps = [lp for lp in lps if cond[lp["turn_id"]] in cfg["replay_conditions"]]
    jobs = [(lp, i) for lp in lps for i in range(pr["k"] if lp["version"] in ("id", "id2", "para") else pr["k_prime"])]
    uncached = sum(not client.is_cached(lp["model"], [{"role": "user", "content": (D / "prompts" / f"{lp['prompt_hash']}.txt").read_text()}],
                                         cfg["temperature"], [i, 0], f"replay:{lp['turn_id']}:{lp['listener']}:{lp['version']}",
                                         cfg["json_mode"]) for lp, i in jobs)
    print(f"[stage7] {len(jobs)} replies, {len(jobs) - uncached} already cached")
    check_budget(client, cfg, "stage7", uncached)  # only uncached first attempts cost calls
    _begin(client, "stage7")
    retries = Counter()

    def one(job):
        lp, i = job
        msgs = [{"role": "user", "content": (D / "prompts" / f"{lp['prompt_hash']}.txt").read_text()}]
        cat, p, err = None, None, None
        for attempt in range(4):  # 1 try + up to 3 retries (README §4.2)
            try:
                raw = client.call(lp["model"], msgs, cfg["temperature"], [i, attempt],
                                  f"replay:{lp['turn_id']}:{lp['listener']}:{lp['version']}", cfg["json_mode"])
            except BudgetExceeded:
                raise
            except Exception as e:  # provider/API error: a failed attempt, like a malformed reply
                err = repr(e)[:300]
                print(f"[stage7] {lp['turn_id']} {lp['listener']} {lp['version']} #{i} attempt {attempt}: {err}", flush=True)
                retries[lp["listener"]] += 1
                continue
            p = parse_reply(raw)
            cat = discretise(p.get("ask"), prev[lp["turn_id"]], pr["tau"]) if p else None
            if cat is not None:
                break
            retries[lp["listener"]] += 1
        return {"turn_id": lp["turn_id"], "listener": lp["listener"], "version": lp["version"], "sample_idx": i,
                "ask": p.get("ask") if p else None, "category": cat,
                "reflection": p.get("reflection") if p else None,
                "plan_for_this_hour": p.get("plan_for_this_hour") if p else None, "invalid": cat is None,
                "error": err if cat is None else None}
    sfx = "_" + "_".join(cfg["replay_conditions"]) if cfg.get("replay_conditions") else ""  # parallel runs never share files
    rows = client.map(one, jobs, sink=D / f"replies{sfx}.partial.jsonl")
    write_jsonl(D / f"replies{sfx}.jsonl", rows)
    inv = sum(r["invalid"] for r in rows)
    print(f"[stage7] {len(rows)} replies; invalid {inv}; retries {dict(retries)}")
    ledger("stage7", len(jobs), client.new_calls, sum(retries.values()), inv)


# ---------------------------------------------------------------- Stage 8
def stage8(client, cfg):
    from p1.report import report
    report(cfg, load_prereg())


STAGES = {"stage0": stage0, "stage1": stage1, "stage2": stage2, "stage3": stage3, "stage4": stage4,
          "stage5a": stage5a, "stage5b": stage5b, "stage6": stage6, "stage7": stage7, "stage8": stage8}
