# Submission: Project 3, team Divinecodes

> **Status (13 Nov, 12:35):** shipped `VERIFY_WITNESS` (dev 0.850 combined, same score in 3 runs; `score.py`).
> Still open: the surprise criterion (14:30) and the hidden-set runs (16:00). Every number here comes from
> `score.py`; nothing is estimated.

## Authors
**Team name:** Divinecodes

**Project:** Project 3: Judge the Judge (Meta-Evaluation of LLM-as-Judge)

## Problem and approach
AI judges decide whether a chatbot change is better. They ignore harmless rewording, which is good, but they miss
small edits that change the meaning: a dropped "if the car is not reserved", "usually" → "always". Those edits turn
replies into promises the company cannot keep. The baseline judge catches only **7%** of dropped conditions and also
fails **14%** of correct replies.

Our idea: a judge that sees one reply cannot notice an absence by reading holistically, so we make the absence
explicit. For every claim, the judge lists the conditions and hedges the **policy** attaches to it and ticks each one
off as kept or dropped. Code then makes the decision. The recipe (full version in
[`starter_pack/RECIPE.md`](starter_pack/RECIPE.md)):

1. **Self-validating code rule.** A number not found in the policy fails the reply, but only if `prepare()` finds
   that the rule never fires on a pass example of the current criterion. Otherwise it becomes a hint or switches
   off. Dev: 35/35 wrong-number edits, 0/417 false fires.
2. **Call 1: claim-by-claim check against the policy, in both directions,** as JSON (quote, policy rule, number
   direction, conditions kept/dropped, certainty 0–3, scope, violates_criterion). The verdict is computed in code.
3. **Call 2: verify suspected fails only,** in a fresh context, to cut false fails on good replies. It may confirm a
   fail only by copying the reply's exact violating words and naming a concrete case where a reader is misled; code
   checks the words are really in the reply, and an unproven confirm goes to call 3.
4. **Call 3: tie-break** only if calls 1 and 2 disagree.

Constraints we respect: one reply per call; no state between calls (`prepare()` is deterministic and makes no LLM
calls; no response cache in scored runs); nothing criterion-specific is hard-coded (examples and rule modes come
from the labelled pairs); at most 3 calls per reply; `claude-haiku-4.5` at temperature 0.

Assumptions: the surprise criterion arrives with labelled pairs in the `dev_pairs.jsonl` format (`edit_type`,
`edit_note`, labels). If fields are missing, `prepare()` falls back to defaults. The hidden cases use the same
schema as dev.

## Models and why
The model is fixed by the rules: `claude-haiku-4.5`. What we compare is the recipe, on the same held-out data
(3-fold cross-validation grouped by source reply).

| Model / recipe | Open-weight or closed | Where it runs | combined / catch / keep (dev, CV) | Calls and time per reply | Chosen? |
| --- | --- | --- | --- | --- | --- |
| baseline_judge.py, claude-haiku-4.5 | closed | API (SIXT endpoint) | 0.697 / 0.592 / 0.847 | 1 call | no, it is the reference |
| final_judge.py before the witness check, claude-haiku-4.5 | closed | API (SIXT endpoint) | 0.754 / 0.750 / 0.758 (run A); 0.721 / 0.700 / 0.744 (run B); 0.731 / 0.723 / 0.739 (run C) | 1–3 calls, 1.73 on average | no, replaced at 12:25 |
| **final_judge.py, shipped (`VERIFY_WITNESS`), claude-haiku-4.5** | closed | API (SIXT endpoint) | **0.850 / 0.813 / 0.891** | 1–3 calls, 1.88 on average | **yes**, the required model |

## Results
Measured on `dev_pairs.jsonl` with grouped cross-validation (`run_dev.sh`); the hidden-set scores come from the
organizers.

| Criterion | Judge | combined | macro catch | macro keep | kappa | consistency (same verdict) |
|---|---|---|---|---|---|---|
| 1 (over-promise) | Baseline | 0.697 | 0.592 | 0.847 | 0.531 | n/a |
| 1 (over-promise) | Baseline + number rule (offline) | 0.697 | 0.592 | 0.847 | 0.531 | n/a |
| 1 (over-promise) | **Ours, run A** (11:23) | 0.754 | 0.750 | 0.758 | 0.623 | 0.974 |
| 1 (over-promise) | **Ours, run B** (11:48, same code) | 0.721 | 0.700 | 0.744 | 0.575 | 0.974 |
| 1 (over-promise) | **Ours, run C** (12:11, same code) | 0.731 | 0.723 | 0.739 | 0.601 | 1.000 |
| 1 (over-promise) | **Ours, shipped** (`VERIFY_WITNESS`, 12:33) | **0.850** | **0.813** | **0.891** | **0.772** | **0.991** |
| 2 (surprise) | Baseline | *TBD* | | | | |
| 2 (surprise) | **Ours, unchanged** | *TBD* | | | | |

Baseline per edit type (catch): condition_removal 0.067, hedge_removal 0.500, wrong_number 0.800,
wrong_policy_detail 1.000. Keep: sentence_reorder 0.733, filler_padding 0.800, translation 0.833,
polite_opener 0.867, padding_removal 1.000.

Ours, shipped (12:33), per edit type (baseline in brackets): catch condition_removal 0.800 (0.067), hedge_removal
0.800 (0.500), wrong_number 0.771 (0.800), wrong_policy_detail 0.880 (1.000); keep sentence_reorder 0.800 (0.733),
filler_padding 0.867 (0.800), translation 0.889 (0.833), polite_opener 0.900 (0.867), padding_removal 1.000 (1.000).
Correct originals pass 0.920 (0.858). Per language combined: en 0.968, fr 0.848, it 0.805, es 0.796, de 0.780.

Before the witness check (run A / run B; baseline in brackets): catch condition_removal 0.667 / 0.633 (0.067),
hedge_removal 0.700 / 0.600 (0.500), wrong_number 0.714 / 0.686 (0.800), wrong_policy_detail 0.920 / 0.880 (1.000);
keep sentence_reorder 0.600 / 0.567 (0.733), filler_padding 0.667 / 0.667 (0.800), translation 0.722 / 0.722 (0.833),
polite_opener 0.800 / 0.767 (0.867), padding_removal 1.000 / 1.000 (1.000). Correct originals pass 0.805 / 0.765
(baseline 0.858).

Honest notes so far:
- **Where we win and lose.** Catch on dropped conditions rises from 0.067 to 0.633–0.667, but keep falls below the baseline.
  The decision trace shows why: almost all false fails on good replies come from call 1 raising a false alarm that call 2
  confirms (path `call1_fail>verify_confirms`). In run C, 9 of the 45 distinct correct originals fail this way, for example a deposit-amount sentence failed for
  not repeating the card rules. **Fixed by the witness check** (`VERIFY_WITNESS`): call 2 must quote the violating
  words and name a concrete misleading case. Correct originals now pass 0.920 and keep rises above the baseline.
- **Caveat on the witness gain.** Its prompt was written after reading false fails on this same dev set, so the dev
  number is an upper bound: cross-validation separates the examples, not the prompt design. The hidden set will tell.
- **Run-to-run noise is larger than most variant gains.** Three runs of identical code give 0.754, 0.721 and 0.731
  combined, although 97.4–100% of verdicts are the same within a run pair; a setting ships only if it wins in both repeats.
- The number rule alone adds nothing on top of the baseline, which already fails every wrong-number edit. Its misses
  come from failing the correct original. The rule makes those catches cost no LLM call and holds no matter how the
  model behaves.
- Dev has only 9 source replies, so cases are strongly correlated. One case moves a per-type rate by 3–7 points.
- The hidden set contains edit types that are not in dev. Our design checks principles (conditions, certainty,
  scope, numbers) rather than the dev edit types, but we cannot measure that transfer on dev alone.

## How to run
Python 3.11+, standard library only (no packages to install).
```bash
git clone https://github.com/divinecodes1/sixt-hackathon.git && cd sixt-hackathon/Project_3
cp .env.example .env          # fill in JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY; JUDGE_LLM_MODEL=claude-haiku-4.5
set -a; . ./.env; set +a

cd starter_pack && python3 -m unittest test_final_judge -v && python3 offline_rule_check.py && cd ..   # no key needed
bash run_dev.sh                                      # dev: 3-fold CV, run twice, scored vs baseline -> results/
bash run_submission.sh <hidden_c1.jsonl> <CRITERION2.md> <dev_pairs_c2.jsonl> <hidden_c2.jsonl>   # -> submission/
```
Environment variables (names only): `JUDGE_LLM_BASE_URL`, `JUDGE_LLM_API_KEY`, `JUDGE_LLM_MODEL`; optional
`JUDGE_MAX_TOKENS` (default 3000), `WORKERS` (default 8). Never set `JUDGE_LLM_CACHE` for scored runs.

Single run, as the organizers do it:
```bash
cd starter_pack
python3 run_judge.py --judge final_judge.py --pairs <cases.jsonl> --criterion <CRITERION.md> --policy policy.md \
    --dev <labelled_pairs.jsonl> --out <verdicts.csv>
```

## Demo
[`submission/slides.pdf`](submission/slides.pdf) (5 slides), built from the score.py reports by `submission/make_slides.py` (rerun it after the criterion-2 run to fill that row). Live demo: `python3 demo/server.py` (or `--mock` offline), then http://127.0.0.1:8765.

## Next steps
- Done 12:35: `W_witness` measured in 3 runs and shipped; `X_verify_examples`, `VERIFY_SCOPED`, `J_adjudicate` and
  `S_second_look` parked (one decision per day, see `PLAN.md`). Next: mock-criterion rehearsal, then the surprise.
  The stress set was not run on the LLM (team decision on 13 Nov: dev only).
- Variant tests from the research plan: a separate recall call for conditions vs the verify call; three differently
  framed calls with a majority vote.
- For SIXT: run the recipe as a release gate for chatbot changes. A reply that drops a policy condition is blocked
  with the quoted policy clause as the explanation, so a reviewer can act on it in seconds.
