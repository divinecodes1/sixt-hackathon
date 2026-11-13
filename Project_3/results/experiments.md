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
