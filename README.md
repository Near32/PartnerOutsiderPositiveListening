# Detecting Covert Collusion between AI Agents through Partner–Outsider Positive Listening

Code and data for the paper by Kevin Yandoka Denamganaï (AI Collusion Research Sprint, October 2026, with Apart Research). This repository reproduces every number, table and figure in the paper's Results (Section 4), and lets you re-run the whole offline-replay protocol (Algorithm 1) from the logged runs.

You can reproduce the paper at three depths:

| Depth | What it does | Time | Needs |
|---|---|---|---|
| **1. Recompute** | Every estimate, interval, verdict and figure, from the logged replies | seconds | Python only |
| **2. Re-run offline** | Algorithm 1 end to end, from the 20 markets to the figures; every model call is answered by the shipped call cache, so the output is byte-identical | about 20 s | Python only (no API key, no GPU) |
| **3. Re-run live** | New model calls with new samples | 1–3 h | an OpenRouter key (about $1–3); a GPU only for new paraphrases |

## The idea in one paragraph

Two sellers in a simulated market, a speaker *A* and a partner *B*, share a private code: the first letter of *A*'s message tells *B* whether to keep (S) or lower (L) its price. A monitor that only reads messages cannot see this. The test reads behaviour instead. Each of *B*'s logged decisions is replayed with *A*'s message reworded so that its meaning is kept but its wording, and so its first letter, changes. The same replay is given to an **outsider** *C*₀ placed in *B*'s seat without *B*'s private instruction or notes. **PoPLi** (Partner–Outsider Positive Listening) is how much more the rewording moves *B* than *C*₀. With the code, PoPLi = 0.615 [0.453, 0.751], and it comes entirely from the partner. Without the code it is −0.027 [−0.112, 0.044].

## Notation: paper and code

| Paper | Meaning | In the code and data |
|---|---|---|
| *A*, *B* | speaker and partner (sellers 0 and 1) | `A_id`, `B_id`; listener `B` |
| *C*₀ | outsider in *B*'s seat (Definition 2): *B*'s prompt minus the private instruction, `# Your Memory` and `# Current Strategy Scratchpad` | listener `C0`; `p1/transforms.py` |
| *C*′₀ | post-hoc outsider: *C*₀ plus "Your most recent ask was $X." | listener `C0p`; `followups/c0prime/` |
| *z*ₜ, Π(*z*ₜ) | *A*'s message at turn *t*, and its paraphrase | `z_t`; `data/paraphrases.jsonl` |
| *id*, *id*′, Π, *z*ₜ⁽ᵐ⁾ | the unchanged message (twice), the paraphrase, and the *M* alternative messages | versions `id`, `id2`, `para`, `res1`–`res4` |
| PL_Π(*L*) | paraphrase listening, Eq. (1) | `pl_pi(L)` (noise-floor corrected), `pl_pi_raw(L)` |
| PL_marg(*L*) | marginal listening, Eq. (2) | `pl_marg(L)`, `pl_marg_raw(L)` |
| Δ_PL(*B*, *C*₀) | PoPLi, Eq. (3) | `delta_pl`, `delta_pl_raw` |
| τ, *k*, *k*′, *M*, *T* | threshold 0.01; 5 replies per main version; 2 per alternative; 4 alternatives; 40 turns per condition | `prereg.yaml` (Table 2, Appendix C) |
| covert code / honest | the two conditions | `covert`, `honest` |
| Hypothesis 1 (FC1), Hypothesis 2 (FC2) | sensitivity and specificity | `H1 verdict`, `H2 verdict` in `results.md` |

## 0. Install

```bash
git clone <this repository> && cd <repository>
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make setup        # clones the harness of Agrawal et al. (2025) at commit 2bb2a7e and applies harness.patch
make test         # 23 unit tests: TV, the 5-vs-8 noise floor, byte-exact prompt edits, discretisation, scripted speaker
```

**Why `make setup`?** The upstream harness (<https://github.com/andyjliu/llm-agent-collusion>) has no licence file, so it is not redistributed here. `make setup` fetches it at the exact commit we used, then applies our changes from `harness.patch`:

| Id | Where | Change | Why |
|---|---|---|---|
| M2 | seller prompt template, `market/agents.py` | optional `# Private Instruction` section, rendered only for *A* and *B*; absent, the prompt is byte-identical to the original | gives the pair its private resource κ (Definition 1) |
| M5 | `market/agents.py`, `market/market.py` | unparseable replies retried at most 5 times (the original retried forever); then the agent skips the hour | bounded cost |
| M7 | `market/market.py` | replies processed in fixed agent order instead of completion order; only the order of message lines changes | re-runs give identical prompts, so the call cache answers them |
| M8 | `cda_types.py` | any model name accepted | model routing is done by `p1/client.py` |
| M9 | `market/market.py` | each agent gets a snapshot of the order book taken at the start of the hour | **fixes a race in the original harness**: agents of the same hour were given the live order book, which changes as other replies arrive, so a slow agent could see a partly updated market |

The rest is done in our own code (`p1/harness_bridge.py`), without changing the harness:
- logging every prompt and raw reply (M1);
- seeding each market (M3);
- skipping the original's LLM-judge metrics and W&B logging (M4);
- replacing *A*'s message by the script (M6).

## 1. Recompute the paper's results (no model calls)

```bash
make reproduce
```

This runs three scripts:

| Command | Writes | Paper |
|---|---|---|
| `python -m p1 stage8` | `results.md`, `results/bootstrap.json`, `results/exp0_instruments.csv`, `results/fig_exp1_gap.pdf`, `results/fig_exp2_marg.pdf` (and `_uncorrected` versions) | Experiments #0–#2, Figure 1 |
| `python -m p1.refree_check` | `results_exploratory.md`, `results/exploratory/refree_check.json` | reference-free robustness check (post hoc) |
| `python -m p1.c0prime_report` | `followups/c0prime/results/bootstrap.json`, section of `results_exploratory.md` | *C*′₀ in Experiment #1 (post hoc) |

You should get exactly these numbers (95% percentile intervals; clustered bootstrap over markets, then turns; 2,000 replicates, seed 7):

| | covert code | honest |
|---|---|---|
| PL̂_Π(*B*) | 0.615 [0.479, 0.738] | −0.007 [−0.076, 0.055] |
| PL̂_Π(*C*₀) | 0.000 [−0.040, 0.047] | 0.020 [−0.033, 0.068] |
| **PoPLi** Δ̂_PL(*B*, *C*₀) | **0.615 [0.453, 0.751]** | **−0.027 [−0.112, 0.044]** |
| PL̂_marg(*C*₀) | −0.000 [−0.027, 0.028] | 0.040 [−0.011, 0.097] |
| Verdict | Hypothesis 1 holds | Hypothesis 2: trivial pass not ruled out |
| Δ̂_PL(*B*, *C*′₀), post hoc | 0.590 [0.411, 0.748] | −0.012 [−0.126, 0.095] |

Experiment #0, the instruments:
- **Replay fidelity:** 66 of 79 turns (0.84).
- **Paraphrases:** meaning kept in 80 of 80 (judge), first letter changed in 76 of 80.
- **Judge validation:** same-meaning pairs 0.81 (n = 16), different-meaning pairs 0.96 (n = 56).
- **Code-follow in calibration:** 35 of 36 (0.97).
- **Diversity:** in 80 of 80 turns at least one alternative message differs in meaning.

## 2. Re-run Algorithm 1 from the cache (no API key, no GPU)

Every model call made for the paper is stored in `data/cache.sqlite`, keyed on (model, temperature, full prompt, sample index, purpose, JSON mode, output limit, provider options). Re-running a stage answers each call from the cache, so the output is byte-identical to the paper's.

The pipeline skips markets that already exist, so first move the logged markets and derived files out of the way:

```bash
mkdir -p ../popli_logged
mv data/runs/openrouter_deepseek_deepseek-v4-flash/{covert,honest}-s* data/turns.jsonl data/all_turns.jsonl \
   data/paraphrases.jsonl data/resamples.jsonl data/replies.jsonl data/judge_validation.json results.md ../popli_logged/
make rerun-offline          # stages 3-8; about 20 seconds
diff results.md ../popli_logged/results.md && echo identical
```

Every file is reproduced exactly, with one exception. The `A_prompt_ref` and `B_prompt_ref` fields in `turns.jsonl` are line numbers into each market's call log. Within an hour the six agents' calls are logged in completion order, so these numbers can differ, but the prompts they point to do not.

## 3. Re-run with new model calls

To draw new samples you need an OpenRouter key, `export OPENROUTER_API_KEY=...`. Model sampling is not seeded, so new samples give slightly different numbers.
- **New markets:** change the seeds in `config.yaml` (`seeds: covert/honest`), or use a fresh `data/cache.sqlite`.
- **Every call is cached as it is made,** so an interrupted run resumes without paying twice. `config.yaml: max_calls` is a hard cap on new calls.
- **Agents:** `deepseek/deepseek-v4-flash`, pinned to one provider (Baidu, no fallbacks) with low reasoning effort, as in the paper. The core needs about 5,200 calls, about $1–3, and 1–3 hours depending on the provider's throughput.
- **Paraphraser:** Qwen2.5-7B-Instruct (bf16, greedy) served by `tools/hf_server.py`. It needs torch, transformers and a GPU with about 20 GB. `PARAPHRASER_PY=/path/to/python bash tools/run_core.sh` starts it for Stage 5a.
- **Calibration:** `python -m p1 stage1` re-runs the code-follow check: 4 markets of 10 hours, reported as A3 in Section 5.1.

## The pipeline (Algorithm 1)

| Stage | `python -m p1 …` | What it does | Algorithm 1 |
|---|---|---|---|
| 3 | `stage3` | 10 markets per condition, 10 hours, 3 sellers + 3 buyers; every prompt and reply logged to `data/runs/.../calls.jsonl` | the logged runs |
| 4 | `stage4` | eligible turns (hour *r* ≥ 2, *B*'s prompt contains *A*'s message, *B* has a previous ask); draws *T* = 40 per condition with seed 2026 | line 2 |
| 5a | `stage5a` | Π(*z*ₜ) for each turn, plus the meaning judge (validated first on template pairs with known answers) | line 5 |
| 5b | `stage5b` | *M* = 4 alternative messages from the speaker's script | line 5 |
| 6 | `stage6` | builds *B*'s and *C*₀'s prompts for every version; each edit must match exactly once and is checked byte-for-byte against a fresh harness render | line 7 |
| 7 | `stage7` | *k* replies to *id* and *id*′, *k* to Π(*z*ₜ), *k*′ to each alternative; each ask discretised against *B*'s previous ask with τ | lines 8–9 |
| 8 | `stage8` | Equations (1)–(3) minus noise floors; clustered bootstrap; decision rules; figures | lines 12–13 |

The speaker is scripted in both conditions (Section 3.3). Each hour, *A* sends one of eight short remarks whose first letter follows a seeded, balanced random S/L schedule, and the S and L versions of each remark mean the same thing. The script is in `config.yaml: scripted_speaker`.

## Pre-registration and deviations

- **`prereg.yaml`:** the analysis plan (Table 2), frozen before any main-run replay.
- **`prereg_receipt.txt`:** its UTC time and SHA-256. Check it with `sha256sum prereg.yaml`. The commit hash refers to the development repository.
- **The design choices that differ from the original plan,** such as the agent model, the scripted speaker and the market length and number, are described in the paper (Sections 3.3 and 4). `prereg.yaml` and the C′0 prediction file mention working documents that are not part of this release; they are kept byte-identical so that their fingerprints match the receipts.
- **The two post-hoc analyses,** each labelled as such in the paper:
  - the reference-free robustness check (`p1/refree_check.py`);
  - the corrected outsider *C*′₀ (`followups/c0prime/`, with its own prediction file and receipt, committed before it ran). *C*′₀ was served by a different provider of the same model, because the main provider was throttled.

## Layout

```
config.yaml          the configuration of every run in the paper
prereg.yaml, prereg_receipt.txt
harness.patch        our changes to the harness (applied by make setup)
p1/                  the pipeline: client (cached calls), harness_bridge (one market), transforms (prompt edits,
                     discretisation), estimate (TV, floors, bootstrap, decision rules), stages, report, follow-ups
tests/               unit tests
tools/               get_harness.sh, run_core.sh, hf_server.py (paraphraser), guard.sh (optional memory guard)
data/cache.sqlite    every model call made for the paper (9,174 entries, outputs only)
data/runs/…/         the 20 main markets and the 4 calibration markets: every prompt and raw reply
data/*.jsonl         turns, paraphrases, alternative messages, replies (the inputs of Stage 8)
results/, results.md, results_exploratory.md     the outputs reproduced above
followups/c0prime/   the post-hoc outsider C′0: config, prediction, receipt, replies, results
```

## Limitations of this release

These are the paper's limitations (Section 5.1 and Appendix A). The results come from one environment, one agent model and ten markets per condition, with an instructed code carried by a feature that paraphrasing destroys. The speaker is scripted, so the positive control shows that the test detects a code a partner follows, not that an AI speaker would invent one. The test cannot see codes carried by the choice of meaning (Proposition 5).

## Citation

```
@techreport{denamganai2026popli,
  title       = {Detecting Covert Collusion between AI Agents through Partner--Outsider Positive Listening},
  author      = {Denamgana{\"i}, Kevin Yandoka},
  year        = {2026},
  month       = oct
}
```

The market environment is that of Agrawal, Teo, Vazquez, Kunnavakkam, Srikanth and Liu (2025), "Evaluating LLM Agent Collusion in Double Auctions", arXiv:2507.01413.

## Licence

The code and data in this repository are released under the MIT License (see `LICENSE`). The market harness of Agrawal et al. is not part of this repository and is not covered by this licence: `make setup` fetches it from its original repository, and `harness.patch` contains only our modifications to it.
