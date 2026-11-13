# Experiments log (final_judge.py settings)

Every number below is produced by score.py.

| time | variant | set | combined | catch | keep | kappa | same verdict | calls/reply | note |
|---|---|---|---|---|---|---|---|---|---|
| 11-13 10:26 | base | dev (dev_pairs_fast.jsonl) | 0.716 | 0.733 | 0.700 | 0.599 | n/a | 0.66 | current final_judge.py |
| 11-13 10:48 | S_second_look | dev (dev_pairs_fast.jsonl) | 0.724 | 0.767 | 0.687 | 0.617 | n/a | 0.66 | call 2 re-checks passes whose own fields show a policy difference |
| 11-13 11:14 | C_evidence | dev (dev_pairs_fast.jsonl) | 0.700 | 0.733 | 0.670 | 0.587 | n/a | 1.81 | kept conditions must quote the reply; unproven ones go to call 2 |
| 11-13 11:23 | base | dev (dev_pairs.jsonl) | 0.754 | 0.750 | 0.758 | 0.623 | 0.974 | 1.73 | current final_judge.py |
| 11-13 11:26 | V_deanchor | dev (dev_pairs_fast.jsonl) | 0.680 | 0.683 | 0.677 | 0.530 | n/a | 1.80 | call 2 sees where to look, not the first reviewer's conclusion |
| 11-13 11:40 | H_hedge | dev (dev_pairs_fast.jsonl) | 0.700 | 0.750 | 0.657 | 0.552 | n/a | 1.72 | certainty from the original words; quantities to scope; gloss last |
| 11-13 11:42 | CKHV | dev (dev_pairs_30.jsonl) | 0.585 | 0.521 | 0.667 | 0.444 | n/a | 1.65 | all four evidence switches |
| 11-13 11:44 | C_evidence | dev (dev_pairs_30.jsonl) | 0.656 | 0.646 | 0.667 | 0.547 | n/a | 1.73 | kept conditions must quote the reply; unproven ones go to call 2 |
| 11-13 11:47 | CKHV | dev (dev_pairs_113.jsonl) | 0.646 | 0.579 | 0.732 | 0.515 | n/a | 1.68 | all four evidence switches |
| 11-13 11:50 | C_evidence | dev (dev_pairs_113.jsonl) | 0.662 | 0.594 | 0.749 | 0.537 | n/a | 1.79 | kept conditions must quote the reply; unproven ones go to call 2 |
| 11-13 11:48 | base (run_dev.sh, run B) | dev (dev_pairs.jsonl) | 0.721 | 0.700 | 0.744 | 0.575 | 0.974 | n/a | same code as the 11:23 base row: run-to-run noise 0.033 |
| 11-13 12:11 | base (run_dev.sh, run C) | dev (dev_pairs.jsonl) | 0.731 | 0.723 | 0.739 | 0.601 | 1.000 | 1.75 | same code; 412 calls per run, 0 parse failures, model claude-haiku-4.5 |
| 11-13 12:13 | W_witness (run 1 only; scored 12:17) | dev (dev_pairs.jsonl) | 0.850 | 0.813 | 0.891 | 0.767 | n/a | n/a | call 2 confirms only with the reply's exact words + a concrete case; CSV kept in commit 821ebd8 |
| 11-13 12:21 | W_witness | dev (dev_pairs.jsonl) | 0.850 | 0.813 | 0.891 | 0.767 | 1.000 | 1.88 | call 2 confirms only with the reply's exact words + a concrete case: fewer false confirms on correct originals |
| 11-13 12:33 | shipped default (VERIFY_WITNESS, run_dev.sh) | dev (dev_pairs.jsonl) | 0.850 | 0.813 | 0.891 | 0.772 | 0.991 | 1.88 | 441 + 436 calls, 1 parse failure per run, model claude-haiku-4.5 |
| 11-13 12:51 | J_adjudicate | dev (dev_pairs.jsonl) | 0.833 | 0.795 | 0.876 | 0.732 | 1.000 | 1.89 | call 3 weighs both reviewers' arguments instead of judging afresh |
| 11-13 12:57 | WX | dev (dev_pairs.jsonl) | 0.832 | 0.800 | 0.867 | 0.735 | 1.000 | 1.84 | witness + labelled examples in call 2 |
| 11-13 13:38 | N_hedge_not_condition | dev (dev_pairs.jsonl) | 0.842 | 0.807 | 0.879 | 0.765 | 1.000 | 1.83 | call 2: a certainty word does not state a dropped condition (on top of the shipped witness check) |
| 11-13 13:52 | criterion 2 (surprise), shipped judge unchanged | c2 dev (73 pairs) | 0.776 | 0.767 | 0.785 | 0.657 | 1.000 | n/a | baseline 0.652 / 0.600 / 0.715; 207 calls per run, 0 parse failures |
| 11-13 14:00 | T_trust_reject | dev (dev_pairs.jsonl) | 0.845 | 0.762 | 0.949 | 0.789 | 1.000 | 1.57 | call 2 answered and confirmed nothing: pass, no call 3 |
| 11-13 14:00 | T_trust_reject, criterion 2 | c2 dev (73 pairs) | 0.863 | 0.833 | 0.895 | 0.771 | 1.000 | n/a | 169 calls per run, 0 parse failures; shipped judge 0.776 on the same pairs |
| 11-13 14:06 | shipped (TRUST_VERIFY_REJECT), run_dev.sh, criterion 2 | c2 dev (73 pairs) | 0.883 | 0.867 | 0.900 | 0.788 | 1.000 | n/a | same code as the 14:00 row (0.863): between-pair noise 0.020 |
| 11-13 14:05 | shipped (TRUST_VERIFY_REJECT), run_dev.sh, criterion 1 | dev (dev_pairs.jsonl) | 0.845 | 0.762 | 0.949 | 0.789 | 1.000 | 1.57 | 369 calls per run, 1 parse failure per run |
