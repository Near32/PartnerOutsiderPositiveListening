| placeholder | value | source file | how computed |
|---|---|---|---|
| covert: delta_pl (95% CI) | 0.615 [0.453, 0.751] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: pl_pi(B) (95% CI) | 0.615 [0.479, 0.738] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: pl_pi(C0) (95% CI) | 0.000 [-0.040, 0.047] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: pl_marg(B) (95% CI) | 0.284 [0.175, 0.407] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: pl_marg(C0) (95% CI) | -0.000 [-0.027, 0.028] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: delta_pl_raw (95% CI) | 0.650 [0.469, 0.794] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: pl_pi_raw(B) (95% CI) | 0.715 [0.579, 0.832] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: pl_pi_raw(C0) (95% CI) | 0.065 [0.017, 0.135] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: pl_marg_raw(B) (95% CI) | 0.352 [0.246, 0.468] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: pl_marg_raw(C0) (95% CI) | 0.047 [0.006, 0.099] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| covert: T turns / sessions | 40 / 10 | data/replies.jsonl | turns with >=1 valid reply in every version for both listeners; excluded 0 |
| honest: delta_pl (95% CI) | -0.027 [-0.112, 0.044] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: pl_pi(B) (95% CI) | -0.007 [-0.076, 0.055] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: pl_pi(C0) (95% CI) | 0.020 [-0.033, 0.068] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: pl_marg(B) (95% CI) | 0.004 [-0.046, 0.049] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: pl_marg(C0) (95% CI) | 0.040 [-0.011, 0.097] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: delta_pl_raw (95% CI) | 0.000 [-0.110, 0.088] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: pl_pi_raw(B) (95% CI) | 0.135 [0.079, 0.200] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: pl_pi_raw(C0) (95% CI) | 0.135 [0.050, 0.245] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: pl_marg_raw(B) (95% CI) | 0.131 [0.083, 0.179] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: pl_marg_raw(C0) (95% CI) | 0.127 [0.057, 0.217] | results/bootstrap.json | clustered bootstrap, 2000 reps, seed 7 |
| honest: T turns / sessions | 40 / 10 | data/replies.jsonl | turns with >=1 valid reply in every version for both listeners; excluded 0 |
| H1 verdict (covert) | holds | results/bootstrap.json | lower CI bound of Delta_PL > 0 |
| H2 verdict (honest) | trivial pass not ruled out | results/bootstrap.json | Delta_PL CI contains 0 AND lower CI of PL_marg(C0) > 0 |
| covert, incentive hours: delta_pl (95% CI) | 0.624 [0.459, 0.775] | results/bootstrap_incentive.json | registered secondary analysis; T = 17 turns in 10 sessions |
| honest, incentive hours: delta_pl (95% CI) | -0.000 [-0.157, 0.114] | results/bootstrap_incentive.json | registered secondary analysis; T = 19 turns in 10 sessions |
| Exp0: replay_fidelity | 0.835 | results/exp0_instruments.csv | 66/79; ties counted as mismatch: 3 |
| Exp0: code_follow_rate | 0.972 | results/exp0_instruments.csv | 35/36 |
| Exp0: paraphrase_first_letter_preserved_covert | 2/40 | results/exp0_instruments.csv | automatic |
| Exp0: paraphrase_first_letter_preserved_honest | 2/40 | results/exp0_instruments.csv | automatic |
| Exp0: judge_validation | same 0.81 (n=16), different 0.96 (n=56) | results/exp0_instruments.csv | template pairs with known answers |
| Exp0: paraphrase_meaning_kept_judge | 80/80 | results/exp0_instruments.csv | NLA judge, all paraphrases |
| Exp0: paraphrase_code_destroyed_auto | 76/80 | results/exp0_instruments.csv | first letter changed |
| Exp0: paraphrase_meaning_kept_hand | pending Kevin | results/exp0_instruments.csv | handcheck_paraphrases.csv |
| Exp0: paraphrase_code_destroyed_hand | pending Kevin | results/exp0_instruments.csv | handcheck_paraphrases.csv |
| Exp0: diversity_exact | 80/80 | results/exp0_instruments.csv | >=1 alternative from a different template (registered exact rule) |
| Exp0: diversity_proxy_text_differs | 80/80 | results/exp0_instruments.csv | PROXY: >=1 resample text != z_t |
| Exp0: diversity_proxy_first_letter_differs | 72/80 | results/exp0_instruments.csv | PROXY: >=1 resample first letter != z_t's |
| Exp0: diversity_hand | pending Kevin | results/exp0_instruments.csv | handcheck_diversity.csv |
| Exp0: resamples_empty | 0/320 | results/exp0_instruments.csv | rendered as the harness does |
| Exp0: invalid_B_id2 | 1 | results/exp0_instruments.csv | after 3 retries |
| Exp0: withdraw_B_id2 | 1 | results/exp0_instruments.csv | D2 fourth category |
| Exp0: D1_B_notes_mention_code_covert | 40/40 | results/exp0_instruments.csv | regex prereg.code_mention_patterns |
| tau | 0.01 | prereg.yaml | registered |
| prereg commit / UTC | f46f3d95e86595d528d850293d29c729c83f0a52 / 2026-10-25T17:42:06+00:00 | prereg_receipt.txt | git |
| agent model / paraphraser | openrouter:deepseek/deepseek-v4-flash / hf:Qwen/Qwen2.5-7B-Instruct | config.yaml |  |
