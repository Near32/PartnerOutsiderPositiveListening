# Exploratory results (not pre-registered)

## Reference-free robustness check (post hoc, decided 26 Oct 2026 ~08:10 UTC; not pre-registered)

Same replies, same clustered bootstrap (2,000 replicates, seed 7, 95% percentile) as the registered analysis.
Dollar shift: 1-Wasserstein distance between ask distributions, noise-floor corrected. Self-referenced categories:
registered categories and tau = 0.01, relative to the median of the listener's own unchanged replies.

| condition | measure | quantity | value [95% CI] | n |
|---|---|---|---|---|
| covert | dollar shift ($) | pl_pi(B) | 1.021 [0.562, 1.596] | T = 40, 10 sessions |
| covert | dollar shift ($) | pl_pi(C0) | -0.039 [-0.136, 0.060] | T = 40, 10 sessions |
| covert | dollar shift ($) | delta_pl | 1.059 [0.569, 1.659] | T = 40, 10 sessions |
| covert | dollar shift ($) | pl_marg(B) | 0.135 [0.056, 0.249] | T = 40, 10 sessions |
| covert | dollar shift ($) | pl_marg(C0) | 0.038 [-0.039, 0.118] | T = 40, 10 sessions |
| covert | self-referenced categories (TV) | pl_pi(B) | 0.570 [0.442, 0.692] | T = 40, 10 sessions |
| covert | self-referenced categories (TV) | pl_pi(C0) | -0.065 [-0.188, 0.047] | T = 40, 10 sessions |
| covert | self-referenced categories (TV) | delta_pl | 0.635 [0.489, 0.781] | T = 40, 10 sessions |
| covert | self-referenced categories (TV) | pl_marg(B) | 0.250 [0.134, 0.373] | T = 40, 10 sessions |
| covert | self-referenced categories (TV) | pl_marg(C0) | 0.014 [-0.056, 0.088] | T = 40, 10 sessions |
| honest | dollar shift ($) | pl_pi(B) | 0.031 [-0.060, 0.149] | T = 40, 10 sessions |
| honest | dollar shift ($) | pl_pi(C0) | 0.450 [-0.043, 1.947] | T = 40, 10 sessions |
| honest | dollar shift ($) | delta_pl | -0.418 [-1.897, 0.097] | T = 40, 10 sessions |
| honest | dollar shift ($) | pl_marg(B) | 0.024 [-0.024, 0.100] | T = 40, 10 sessions |
| honest | dollar shift ($) | pl_marg(C0) | 0.033 [-0.007, 0.088] | T = 40, 10 sessions |
| honest | self-referenced categories (TV) | pl_pi(B) | 0.028 [-0.049, 0.100] | T = 40, 10 sessions |
| honest | self-referenced categories (TV) | pl_pi(C0) | -0.025 [-0.107, 0.049] | T = 40, 10 sessions |
| honest | self-referenced categories (TV) | delta_pl | 0.053 [-0.061, 0.155] | T = 40, 10 sessions |
| honest | self-referenced categories (TV) | pl_marg(B) | -0.001 [-0.048, 0.044] | T = 40, 10 sessions |
| honest | self-referenced categories (TV) | pl_marg(C0) | 0.051 [-0.025, 0.134] | T = 40, 10 sessions |

Source: results/exploratory/refree_check.json; code: p1/refree_check.py.

## Post-hoc corrected outsider C0′ (post hoc; prediction committed 2026-10-26 08:24:58 UTC; paper, Experiment #1)

C0′ = C0 plus the line "Your most recent ask was $X." (B's registered previous ask). B's registered replies reused; registered estimator and bootstrap (2,000 replicates, seed 7, 95% percentile); Δ = PL_Π(B) − PL_Π(C0′). Listener key in the JSON: `C0p`.

| condition | quantity | value [95% CI] | n |
|---|---|---|---|
| covert | pl_pi(C0p) | 0.025 [-0.050, 0.117] | T = 40, 10 sessions |
| covert | pl_pi_raw(C0p) | 0.105 [0.035, 0.200] | T = 40, 10 sessions |
| covert | pl_marg(C0p) | 0.027 [-0.017, 0.085] | T = 40, 10 sessions |
| covert | pl_marg_raw(C0p) | 0.086 [0.032, 0.160] | T = 40, 10 sessions |
| covert | delta_pl | 0.590 [0.411, 0.748] | T = 40, 10 sessions |
| covert | delta_pl_raw | 0.610 [0.416, 0.774] | T = 40, 10 sessions |
| covert | pl_pi(B) | 0.615 [0.479, 0.738] | T = 40, 10 sessions |
| covert | C0' categories (unchanged message) | {'hold': 0.052, 'lower': 0.06, 'raise': 0.887} | invalid 0, withdraw 0 of 920 |
| covert | committed prediction | PL_Pi(C0') 95% CI contains 0, and Delta_PL(B, C0') 95% CI above 0 | **holds** |
| honest | pl_pi(C0p) | 0.005 [-0.062, 0.079] | T = 40, 10 sessions |
| honest | pl_pi_raw(C0p) | 0.110 [0.050, 0.190] | T = 40, 10 sessions |
| honest | pl_marg(C0p) | 0.015 [-0.025, 0.066] | T = 40, 10 sessions |
| honest | pl_marg_raw(C0p) | 0.092 [0.047, 0.153] | T = 40, 10 sessions |
| honest | delta_pl | -0.012 [-0.126, 0.095] | T = 40, 10 sessions |
| honest | delta_pl_raw | 0.025 [-0.057, 0.097] | T = 40, 10 sessions |
| honest | pl_pi(B) | -0.007 [-0.076, 0.055] | T = 40, 10 sessions |
| honest | C0' categories (unchanged message) | {'hold': 0.13, 'lower': 0.657, 'raise': 0.212} | invalid 0, withdraw 0 of 920 |
| honest | committed prediction | Delta_PL(B, C0') 95% CI contains 0 | **holds** |

Source: followups/c0prime/results/bootstrap.json; code: p1/c0prime_report.py; prediction: followups/c0prime/prereg.yaml.
