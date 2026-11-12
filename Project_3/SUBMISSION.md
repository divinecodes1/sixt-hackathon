# Submission: Project 3, team Divinecodes

> **Status (12 Nov, evening):** code, tests, recipe and research are in place. All LLM numbers below are marked
> *TBD*: they are measured on 13 Nov with the `claude-haiku-4.5` key handed out on site. Nothing in this file is
> estimated or invented.

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
3. **Call 2: verify suspected fails only,** in a fresh context, to cut false fails on good replies.
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
| final_judge.py, claude-haiku-4.5 | closed | API (SIXT endpoint) | *TBD 13 Nov* | 1–3 calls, *TBD* s | yes, the required model |

## Results
Measured on `dev_pairs.jsonl` with grouped cross-validation (`run_dev.sh`); the hidden-set scores come from the
organizers.

| Criterion | Judge | combined | macro catch | macro keep | kappa | consistency (same verdict) |
|---|---|---|---|---|---|---|
| 1 (over-promise) | Baseline | 0.697 | 0.592 | 0.847 | 0.531 | n/a |
| 1 (over-promise) | Baseline + number rule (offline) | 0.697 | 0.592 | 0.847 | 0.531 | n/a |
| 1 (over-promise) | **Ours** | *TBD* | *TBD* | *TBD* | *TBD* | *TBD* |
| 2 (surprise) | Baseline | *TBD* | | | | |
| 2 (surprise) | **Ours, unchanged** | *TBD* | | | | |

Baseline per edit type (catch): condition_removal 0.067, hedge_removal 0.500, wrong_number 0.800,
wrong_policy_detail 1.000. Keep: sentence_reorder 0.733, filler_padding 0.800, translation 0.833,
polite_opener 0.867, padding_removal 1.000.

Honest notes so far:
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
`JUDGE_MAX_TOKENS` (default 1600), `WORKERS` (default 8). Never set `JUDGE_LLM_CACHE` for scored runs.

Single run, as the organizers do it:
```bash
cd starter_pack
python3 run_judge.py --judge final_judge.py --pairs <cases.jsonl> --criterion <CRITERION.md> --policy policy.md \
    --dev <labelled_pairs.jsonl> --out <verdicts.csv>
```

## Demo
`submission/slides.pdf` (max 5 slides): *to be added on 13 Nov with the measured numbers.*

## Next steps
- Leave-one-edit-type-out evaluation and two mock criteria (one not about the policy) to test transfer before the
  surprise.
- Variant tests from the research plan: a separate recall call for conditions vs the verify call; three differently
  framed calls with a majority vote.
- For SIXT: run the recipe as a release gate for chatbot changes. A reply that drops a policy condition is blocked
  with the quoted policy clause as the explanation, so a reviewer can act on it in seconds.
