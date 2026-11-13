# Submission: Project 3, team Divinecodes

> **Status (13 Nov, 16:23):** shipped judge = `VERIFY_WITNESS` + `TRUST_VERIFY_REJECT` (+ a coverage guard at 14:20,
> see below). Dev: criterion 1 **0.845** (0.846 in a second pair of runs), criterion 2 (surprise) **0.883** (0.863 in two
> other pairs), same verdict 1.000 within each pair of runs. Rules audit at 14:30: no rule broken. All four hidden-set
> verdict CSVs are complete: 291 cases for criterion 1 and 311 for criterion 2, with 100% agreement between the two
> runs of each criterion. Criterion 1 had no parse failures; each criterion-2 run had one unreadable model answer,
> conservatively counted as fail. Hidden scores are not reported because the organizers do not provide ground-truth labels.
> Every performance number here comes from `score.py`; nothing is estimated.
>
> **Code freeze (13 Nov, 15:46):** `starter_pack/final_judge.py` is frozen as last changed in commit `c331641` (14:30, comments only), sha256 `d6673c0469e4fd01…`. The scored runs use exactly this file; it is not changed after the freeze.
>
> **Change history:** `TRUST_VERIFY_REJECT` (14:05) came from our error analysis of the criterion-2 dev pairs
> (`results/c2_error_analysis.md`), which showed call 3 overturning correct call-2 rejections. It is generic (nothing
> criterion-specific) and was measured on both criteria before shipping; before it, criterion 2 scored 0.776.

## Authors
**Team name:** Divinecodes

**Project:** Project 3: Judge the Judge (Meta-Evaluation of LLM-as-Judge)

**Live demo:** https://divinecodes-judge-the-judge.vercel.app (the judge on real `claude-haiku-4.5`; try a labelled case or your own reply)

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
   checks the words are really in the reply. **If call 2 answers every finding and proves none, the reply passes.**
4. **Call 3: holistic fallback** only if call 2's answer is unreadable or leaves a finding unanswered (1.57 calls
   per reply on dev).

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
| final_judge.py with `VERIFY_WITNESS` only (12:25–14:05), claude-haiku-4.5 | closed | API (SIXT endpoint) | 0.850 / 0.813 / 0.891 | 1–3 calls, 1.88 on average | no, replaced at 14:05 |
| **final_judge.py, shipped (`VERIFY_WITNESS` + `TRUST_VERIFY_REJECT`), claude-haiku-4.5** | closed | API (SIXT endpoint) | **0.845 / 0.762 / 0.949** (criterion 2: **0.883 / 0.867 / 0.900**) | 1–3 calls, 1.57 on average | **yes**, the required model |

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
| 1 (over-promise) | Ours, `VERIFY_WITNESS` only (12:33) | 0.850 | 0.813 | 0.891 | 0.772 | 0.991 |
| 1 (over-promise) | **Ours, shipped** (+ `TRUST_VERIFY_REJECT`, 14:05) | **0.845** | **0.762** | **0.949** | **0.789** | **1.000** |
| 1 (over-promise) | same + coverage guard, second pair of runs (14:21) | 0.846 | 0.754 | 0.962 | 0.782 | 1.000 |
| 2 (surprise) | Baseline | 0.652 | 0.600 | 0.715 | 0.394 | n/a |
| 2 (surprise) | Ours, unchanged at 13:52 (`VERIFY_WITNESS` only) | 0.776 | 0.767 | 0.785 | 0.657 | 1.000 |
| 2 (surprise) | **Ours, shipped** (+ `TRUST_VERIFY_REJECT`, `run_dev.sh` 14:06) | **0.883** | **0.867** | **0.900** | **0.788** | **1.000** |
| 2 (surprise) | same code, earlier pair of runs (14:00) | 0.863 | 0.833 | 0.895 | 0.771 | 1.000 |
| 2 (surprise) | same + coverage guard, third pair of runs (14:21) | 0.863 | 0.833 | 0.895 | 0.771 | 1.000 |

Criterion 2 (surprise, "does the reply state the policy correctly?"): 73 labelled pairs from `criterion2/` (upstream commit 0cb5c94), 9 source replies, 3-fold CV grouped by source; `prepare()` chose number rule `verdict`. Small set: one case moves a type by 10 points.

Baseline per edit type (catch): condition_removal 0.067, hedge_removal 0.500, wrong_number 0.800,
wrong_policy_detail 1.000. Keep: sentence_reorder 0.733, filler_padding 0.800, translation 0.833,
polite_opener 0.867, padding_removal 1.000.

**Shipped (14:05), criterion 1, per edit type** (baseline in brackets): catch condition_removal 0.667 (0.067),
hedge_removal 0.700 (0.500), wrong_number 0.800 (0.800), wrong_policy_detail 0.880 (1.000); keep sentence_reorder
0.933 (0.733), filler_padding 0.933 (0.800), translation 0.944 (0.833), polite_opener 0.933 (0.867), padding_removal
1.000 (1.000). Correct originals pass 0.965 (0.858).

**Shipped, criterion 2, per edit type** (`run_dev.sh` 14:06): catch wrong_policy_detail 1.000, wrong_number 0.900,
condition_removal 0.700; keep translation 1.000, padding_removal 1.000, polite_opener 0.900, sentence_reorder 0.800,
filler_padding 0.800. Correct originals pass 0.945. Weakest language: de (0.762).

**The trade-off of the 14:05 change.** On criterion 1 it moves the judge toward keeping: keep 0.891 → 0.949, but
catch 0.813 → 0.762, with **condition_removal catch 0.800 → 0.667** and hedge_removal 0.800 → 0.700. Combined is
flat (0.850 → 0.845, within run-to-run noise). On criterion 2 it removes the main error source (call 3 failing
replies call 2 had cleared): 0.776 → 0.883 (0.863 in an earlier pair of runs). Average over both criteria: 0.813 → 0.864.
Between separate pairs of runs the same code moved by 0.020 on criterion 2 although each pair agreed on every
verdict: "same verdict 1.000" is consistency within a pair, not a guarantee across time.

**Coverage guard (14:20, after the staff review).** Call 2's rejection is final only if call 2 answered every
finding of call 1; a partial answer goes to call 3. In the 14:03 traces call 2 always answered every finding
(174 of 174 replies), so it is a safeguard for unseen data. Re-run with it (14:21): criterion 1 0.846 (5 cases differ from
14:06: 3 newly passed, 2 newly failed), criterion 2 0.863 (verdict for verdict the same as the 14:00 pair without the guard):
the differences from the 14:06 runs are session-to-session noise.

With `VERIFY_WITNESS` only (12:33), per edit type (baseline in brackets): catch condition_removal 0.800 (0.067), hedge_removal
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
- **Why criterion 2 first scored lower, and the 14:05 change** (`results/c2_error_analysis.md`): 17 of 73 pairs were
  wrong; 11 because a correct original failed. In 8 of the 17, call 2 had correctly cleared the reply and call 3,
  judging from scratch under "leaving out a condition makes the statement incorrect", failed it anyway. On criterion 1
  the same call 3 caught 12 bad replies. We made call 2's rejection final (`TRUST_VERIFY_REJECT`): measured
  criterion 2 0.776 → 0.883 and criterion 1 0.850 → 0.845, at the cost of criterion-1 dropped-condition catch
  (0.800 → 0.667).
- **The hedge words in the witness prompt** ("try", "often", "most", "can", "may" or similar) are examples inside
  the call-2 prompt of wording that already leaves room, not a code rule: no code matches them, and they can only
  lead call 2 to reject a finding. With the same prompt, the filler mock criterion (where hedges are irrelevant) still
  beat the baseline (0.776 vs 0.543, `results/mock_filler_report.txt`).
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
**Live:** https://divinecodes-judge-the-judge.vercel.app (Vercel, the unchanged `final_judge.py` on real
`claude-haiku-4.5`; criterion 1, criterion 2 and the two mock criteria; the API key is a Vercel sensitive
environment variable, never sent to the browser). Entry point `api/index.py`, config `vercel.json`.

[`submission/demo_narrated.mp4`](submission/demo_narrated.mp4) (6 min 22 s, 14 MB, English voice-over): the full
walkthrough: problem, insight, the recipe step by step, the architecture's decision paths
(`submission/architecture_diagram.html`), the rules kept and the scoring, three live verdicts on the hosted demo (a dropped condition caught, a harmless
opener kept, a typed "always … guaranteed" reply failed), the surprise criterion, and the measured results. The live
lines are written from what the page showed; the voice is Piper, generated locally.

[`submission/slides.pdf`](submission/slides.pdf) (5 slides, the required deliverable): problem, insight, architecture, results from the
`score.py` reports, and what it means for SIXT.
Local demo: `python3 demo/server.py` (or `--mock` offline), then http://127.0.0.1:8765.

## Next steps
- Shipped: `VERIFY_WITNESS` (12:25) and `TRUST_VERIFY_REJECT` (14:05). Measured and not shipped: `HEDGE_NOT_CONDITION`
  (0.842), `J_adjudicate` (0.833), `WX` (0.832); parked: `X_verify_examples`, `VERIFY_SCOPED`, `S_second_look`.
  The stress set was not run on the LLM (team decision on 13 Nov: dev only).
- Win back criterion-1 dropped-condition catch (0.667) without the call-3 false fails: the remaining misses are call 2
  reading a hedge ("often") as the dropped condition (`results/c2_error_analysis.md`, case 5).
- Variant tests from the research plan: a separate recall call for conditions vs the verify call; three differently
  framed calls with a majority vote.
- For SIXT: run the recipe as a release gate for chatbot changes. A reply that drops a policy condition is blocked
  with the quoted policy clause as the explanation, so a reviewer can act on it in seconds.
