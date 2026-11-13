# Our recipe for building an LLM judge (team Divinecodes)

A repeatable recipe for a criterion you have never seen. Code: `final_judge.py`. Only the inputs change between
criteria: the criterion text, the policy and a few labelled example pairs. Numbers come from `score.py`.
Background research with sources: [`../docs/research_report.md`](../docs/research_report.md).

## Step 1. Diagnose
We read `baseline_report.txt` and `diagnose.py` output for the baseline on `dev_pairs.jsonl` (226 cases).

| Where it fails | Baseline | Why |
|---|---|---|
| condition_removal | catch **0.067** | The judge sees one reply. A dropped condition is an *absence*; holistic judging does not look for it. |
| hedge_removal | catch 0.500 | "usually" → "always" looks like a normal, confident reply. |
| correct originals | pass only **0.858** | The judge fails 1 in 7 *good* replies. This costs catch AND keep, because both need the original to pass. |
| sentence_reorder / filler | keep 0.733 / 0.800 | Same content, different surface, different verdict. |

Finding we did not expect: the baseline already fails **every** wrong-number edit it sees (35/35 edited replies
fail). Its 0.80 catch on wrong_number comes only from failing the correct original in 7 of 35 cases. So false fails on
good replies, not missed numbers, are the second-biggest cost after dropped conditions.

The published evidence matches this pattern. In a study of 7 judges including claude-haiku-4.5 (arXiv 2608.24419),
hedge removal was the least-detected edit, and condition removal was also weak. FBI (EMNLP 2024) found that judges
detect removed facts 6% of the time without a reference and 48% with one.

- Check: the costliest failure types are dropped conditions, hedge removal and false fails on correct replies.

## Step 2. Split: rules vs. LLM
**Rule (code): "a number in the reply that appears nowhere in the reference policy".** Locale-aware number parsing
("1.000,50", "12,5"). The rule is never hard-wired; `prepare()` validates it on the labelled examples of the
current criterion:
- **off** if it fires on any example labelled pass (for example a criterion where numbers do not matter);
- **verdict** if it fires only on examples labelled fail. A hit fails the reply unless call 1 explicitly finds
  that number equal to or stricter than the policy, which protects against unseen harmless numbers such as "24/7";
- **hint** otherwise. The hit is shown to the LLM as a `<code_check>`.

On dev (`offline_rule_check.py`, no LLM): it fires on 35/35 wrong_number edits and on **0 of 417** other replies
(all originals and all harmless edits). It chose verdict mode in all 3 cross-validation folds.
The LLM keeps everything else: conditions, hedges, scope, policy details, and the criterion itself.

- Check: the rule never fails a harmless edit on dev (0/417).

## Step 3. Improve the LLM part
1. **Claim-by-claim check against the reference, in both directions (call 1, JSON).** For each claim the model
   quotes the policy rule and lists **every condition the policy attaches**, each with status kept / dropped /
   not_applicable. It also rates certainty on a 0–3 scale for both policy and reply (covering DE/FR/ES/IT wording)
   and records scope and number direction. Only then does it decide `violates_criterion`. This turns "spot what is
   missing" into "tick off a list". The research's strongest lever: references and explicit absence checks.
2. **The candidate verdict is aggregated in code** from the per-claim `violates_criterion` booleans (any claim
   violates → candidate fail), not from a free-text PASS/FAIL. The other fields (conditions, certainty, scope,
   number direction) are the model's working; by default they do not change the verdict. With `SECOND_LOOK = True`
   (off until measured), a pass whose own fields record a difference from the policy, in either direction, gets
   call 2 to decide whether that difference matters under the criterion.
3. **Invariance wording that stays criterion-agnostic:** "greeting, filler, sentence order, length, politeness and
   language matter only if the criterion is about them". Nothing says "openers never matter", so a tone criterion
   still works.
4. **Verify only suspected fails (call 2, fresh context).** It confirms or rejects each finding, which targets the
   false fails on good replies. It states the general principle that "leaving out a condition the reference
   attaches makes the statement stronger, not briefer", so it does not explain real omissions away.
   **Shipped 12:25: `VERIFY_WITNESS = True`.** Call 2 confirms only if it copies the reply's exact words that violate
   the criterion and names one concrete case where a reader is misled; code checks the words are in the reply, and an
   unproven confirm counts as a rejection (it went to call 3 until 14:05; with `TRUST_VERIFY_REJECT` the reply passes).
   **Shipped 14:05: `TRUST_VERIFY_REJECT = True`** (from the criterion-2 error analysis): if call 2
   answers every finding and proves none, the reply passes; call 3 runs only when call 2's answer is unreadable or
   leaves a finding unanswered (guard added 14:20; in the 14:03 traces call 2 always answered every finding, so the
   measured verdicts are unchanged).
5. **Fallback (call 3)**, since 14:05 only when call 2's answer is unreadable or partial (before: whenever calls 1 and 2
   disagreed): an independent holistic judgment with examples. With
   `ADJUDICATE = True` (off until measured), call 3 sees both reviewers' arguments and checks each one against the
   reply, instead of judging from scratch.
6. **Evidence switches (built, off until measured; `../docs/reports/Policy grounded LLM judge methods.md`).** `CONDITION_EVIDENCE`: a condition marked kept must quote the reply, and code checks the quote; unproven ones go to call 2. `CLAUSE_IDS`: `prepare()` numbers the policy clauses (no LLM, format-generic); call 1 cites a clause id and its exact words, and code checks them. `HEDGE_FROM_QUOTE`: certainty is rated from the copied original hedge words, and quantity words go to scope. `VERIFY_DEANCHOR`: call 2 sees only where to look, not the first reviewer's conclusion. Findings raised by code (not by call 1) that call 2 rejects end in pass, without a call 3. `VERIFY_EXAMPLES`: call 2 also sees the labelled examples, aimed at the false confirms on good replies (staff review, 13 Nov).
7. **Examples picked by code** from the labelled pairs: one per edit type, English first, alternating labels, at most
   8 (more rounds per type when there are fewer types, e.g. no `edit_type` given). The construction note (what was changed) is shown as the rationale. Temperature 0 everywhere. Reasoning in
   English with quotes in the original language. At most 3 calls per reply; no state between calls.

- Check: catch goes up on dev without keep going down. **Measured (3 runs): catch goes up (0.592 → 0.700–0.750), keep
  goes down (0.847 → 0.739–0.758).** The false fails are the open problem (Step 4).

**Operational safeguards (no effect on verdicts).** Newer Anthropic API versions reject `temperature` with HTTP 400; the judge then resends that request without it (counted in `STATS["temperature_dropped"]`, reported by `crossval.py`; `JUDGE_LLM_OMIT_TEMPERATURE=1` skips the rejected attempt), and `dev_tools/probe_gateway.py` tests this separately from the key. HTTP 408 and 529 (overloaded) are retried. `run_submission.sh` raises the retry budget to 10 so one
rate-limited reply cannot abort a scored run; `JUDGE_TRACE=<file>` writes one JSON line per reply (decision path,
calls used, rule hits, reply hash, never the text) and is never read back; `MAX_TOKENS` is 3000 so long JSON
answers are not cut off (`STATS["truncated"]` counts any that are). The code rule's overturn check compares number
values, not substrings, so "19" is not confirmed by a claim quoting "190".

## Step 4. Verify
Dev numbers use **grouped cross-validation by source reply** (`crossval.py`): the examples shown to the judge never
come from the source replies being scored. Run twice for consistency: `bash run_dev.sh`.

| | combined | catch | keep | kappa | same verdict (2 runs) |
|---|---|---|---|---|---|
| Baseline (precomputed) | 0.697 | 0.592 | 0.847 | 0.531 | n/a |
| Baseline + number rule (offline) | 0.697 | 0.592 | 0.847 | 0.531 | n/a |
| Ours, claude-haiku-4.5, 3-fold CV, run A | 0.754 | 0.750 | 0.758 | 0.623 | 0.974 |
| Ours, same code, run B | 0.721 | 0.700 | 0.744 | 0.575 | 0.974 |
| Ours, same code, run C (12:11) | 0.731 | 0.723 | 0.739 | 0.601 | 1.000 |
| Ours + `VERIFY_WITNESS` (12:21, experiments.py) | 0.850 | 0.813 | 0.891 | 0.767 | 1.000 |
| Ours, `VERIFY_WITNESS` only (`run_dev.sh`, 12:33) | 0.850 | 0.813 | 0.891 | 0.772 | 0.991 |
| **Ours, shipped: + `TRUST_VERIFY_REJECT` (`run_dev.sh`, 14:05)** | **0.845** | **0.762** | **0.949** | **0.789** | **1.000** |

The `VERIFY_WITNESS` prompt was written after reading run C's false fails on this same dev set, so its dev gain is
an upper bound: cross-validation keeps the examples apart, not the prompt design. 9 source replies per type: one
case moves a type by 3-7 points. Reports: `../results/exp_W_witness_dev_dev_pairs_report.txt` (variant) and
`../results/dev_pairs_report.txt` (now the 14:05 shipped run: 1.57 calls per reply, 1 parse failure per run, model
`claude-haiku-4.5`). With `VERIFY_WITNESS` only (12:33), per edit type: catch condition_removal 0.800, hedge_removal 0.800, wrong_number 0.771,
wrong_policy_detail 0.880; keep sentence_reorder 0.800, filler_padding 0.867, translation 0.889, polite_opener 0.900,
padding_removal 1.000; correct originals pass 0.920 (baseline 0.858).

Per language and per edit type: `../results/exp_base_dev_dev_pairs_report.txt` (run A), `../results/experiments.md`
(run B, summary row only) and `../results/dev_eval_1200.log` (run C). Condition_removal catch rises from 0.067 to 0.633–0.667, hedge_removal from
0.500 to 0.600–0.700. Correct originals pass only 0.765–0.805 (baseline 0.858), so every harmless type loses keep.
The trace (`JUDGE_TRACE`) shows the path: nearly all false fails on pass-labelled replies are call-1 alarms that call 2
confirmed. The two runs of identical code differ by 0.033 combined: a setting has to win in both repeats.

**Diagnosis (run C, `diagnose.py` + trace with reasons).** 9 of the 45 distinct correct originals fail, and each one
sinks every pair built on it (catch and keep). Costliest types: filler_padding (47% wrong), sentence_reorder (37%),
condition_removal (33%). The false fails share one pattern: call 1 marks a policy condition as dropped although the
reply hedges elsewhere ("we will try to reserve one", "often") or the condition governs something the claim does not
promise (deposit card rules on a sentence that only states the amount), and call 2 confirms it.

Settings screened so far (`../results/experiments.md`, 30-case fast subset, base 0.716): `S_second_look` 0.724,
`C_evidence` 0.700, `H_hedge` 0.700, `V_deanchor` 0.680. None clears the +0.02 bar, so all stay off.

**Edit types not in dev.** The hidden set has new edit types, and leave-one-edit-type-out only rotates the 9 dev
types. So we hand-wrote 99 stress cases of 11 new types (`../stress/make_stress.py`, our own mock edits, never used as
examples): harmless `stricter_number`, `number_format`, `hedge_addition`, `paraphrase`, `condition_moved`,
`register_change`; harmful `scope_widening`, `negation_flip`, `added_commitment`, `number_in_policy` (a generous
number that occurs elsewhere in the policy) and `number_as_word`. `bash ../run_stress.sh` scores ours vs the baseline.

| Stress set (99 cases) | combined | catch | keep | same verdict (2 runs) |
|---|---|---|---|---|
| Number rule alone (offline) | 0.000 | 0.000 | 0.857 | n/a |
| Baseline, claude-haiku-4.5 | not run (team decision 13 Nov: dev only) | | | |
| Ours, claude-haiku-4.5 | not run (team decision 13 Nov: dev only) | | | |

What the offline row shows: the rule catches none of the new harmful types (they are the LLM's job), and it fires
on 30 of 35 harmless `stricter_number` edits (keep 0.143 there): in verdict mode those replies pass only if call 1
explicitly finds the number stricter than the policy. Whether verdict mode survives is decided by measuring that
type (experiment R in the iterate skill).

- Check: the gain holds on edit types and phrasings you did not tune on (leave-one-edit-type-out and the stress set).

## Surprise criterion
Nothing changes in the code. `prepare()` re-validates the number rule against the new examples (it switches itself
off or to hint mode if the new criterion does not reward it) and picks new examples from the new pairs.

| | combined | catch | keep |
|---|---|---|---|
| Baseline (`baseline_judge.py`, one run) | 0.652 | 0.600 | 0.715 |
| Ours, recipe unchanged at 13:52 (2 runs, same verdict 1.000) | 0.776 | 0.767 | 0.785 |
| **Ours, shipped: + `TRUST_VERIFY_REJECT`** (`run_dev.sh` 14:06, same verdict 1.000) | **0.883** | **0.867** | **0.900** |
| same code, earlier pair of runs (14:00) | 0.863 | 0.833 | 0.895 |

Criterion 2: "does the reply state the policy correctly?", errors in both directions. 73 labelled pairs from `criterion2/` (upstream commit 0cb5c94), 9 source replies, 3-fold CV grouped by source; `prepare()` chose number rule `verdict`. Small set: one case moves a type by 10 points.
Ours per edit type: catch wrong_policy_detail 1.000, wrong_number 0.700, condition_removal 0.600; keep padding_removal
1.000, polite_opener 0.800, sentence_reorder 0.800, filler_padding 0.700, translation 0.625. Correct originals pass
0.849. Weakest language: it (0.609). Reports: `../results/c2_dev_pairs_report.txt`, `../results/c2_vs_baseline_report.txt`.

Why lower than criterion 1 (full analysis: `../results/c2_error_analysis.md`): 11 of the 17 wrong pairs are lost because a
correct original fails. The criterion's "leaving out a condition makes the statement incorrect" makes the judge flag
omissions that the reply covers in another sentence ("we will try to reserve one") or that belong to a different promise
(card rules on a deposit amount). Call 3, which judges from scratch, overturns call 2's correct rejections here (6
good replies failed, 1 bad reply caught), while on criterion 1 it catches 12 bad replies. One source reply (child
seats) drives 9 of the 17 errors.

**What we changed after the criterion-2 error analysis.** The analysis pointed at call 3, a step that is not specific to any
criterion, so we made call 2's rejection final (`TRUST_VERIFY_REJECT`, 14:05) and measured it on both criteria before
shipping: criterion 2 0.776 → **0.883** (0.863 in an earlier pair of runs; catch 0.867, keep 0.900; per type:
wrong_policy_detail 1.000, wrong_number 0.900, condition_removal 0.700; keep translation 1.000, polite_opener 0.900,
sentence_reorder and filler_padding 0.800; correct originals pass 0.945), criterion 1 0.850 → **0.845**. **Trade-off:** on criterion 1, keep rises (0.891 →
0.949, correct originals pass 0.965) but catch falls (0.813 → 0.762): condition_removal 0.800 → 0.667, hedge_removal
0.800 → 0.700. Reports: `../results/dev_pairs_report.txt`, `../results/c2_vs_baseline_report.txt`.

**Rehearsal on two mock criteria (12:35, one run each, `results/mock_{numbers,filler}_report.txt`).** Relabelled dev
data, built by `.claude/skills/p3-mock-criterion-rehearsal/scripts/make_mocks.py`; labels come from construction and
are approximate. `prepare()` chose verdict mode for the numbers mock and switched the rule off for the filler mock.

| Mock criterion | baseline combined | ours combined | ours catch | ours keep |
|---|---|---|---|---|
| numbers ("a number differs from the policy", 81 cases) | 0.933 | 0.974 | 1.000 | 0.950 |
| filler ("unnecessary pleasantries or filler", 65 cases) | 0.543 | 0.776 | 0.825 | 0.733 |

Most of the remaining errors are in the mock labels, not the judge: on the filler mock, 5 "pass" originals end with
"we hope you enjoy your trip" in some language (real filler), and on the numbers mock the 4 false fails are "half the
daily rate" edits labelled harmless. Raw catch is 1.000 on both. The judge does flag openers when the criterion is
about them, so the invariance wording is not secretly criterion-1-specific.

Handoff drill (filler mock as if it had just arrived, following the `p3-surprise-criterion` skill): store, validate,
`prepare()` check, CV twice and baseline took about 20 s of compute; each mock run took 77 s. With 2 source ids one
of the 3 folds is empty (harmless), and a fold that sees only 3 examples may pick number rule `hint`.

## What did not work
- **Telling call 2 that a hedge is not a condition** (`HEDGE_NOT_CONDITION`, 13:38, two full-dev runs): 0.842 vs 0.850
  shipped. Aimed at the remaining condition_removal misses ("often" read as covering a dropped "subject to
  availability"), it left that type at 0.800, lowered hedge_removal to 0.750 and keep on translation and polite_opener.
  Off. Last experiment before the 14:30 prompt freeze.
- **Evidence switches did not help** on the fast subset (base 0.716): `C_evidence` 0.700, `H_hedge` 0.700,
  `V_deanchor` 0.680. All four together (`CKHV`) scored lowest on both subsets it ran on. They stay off.
- **Adding the number rule to the baseline gives +0.000.** The baseline already fails every wrong-number edit; its
  losses on that type come from failing correct originals. The rule saves an LLM call and makes those catches certain,
  but the gain has to come from fewer false fails.
- **Rejected on purpose:** a response cache to fake run-to-run consistency (it breaks the no-state rule), sampling
  above temperature 0 for voting (adds exactly the variance that is scored), long generated rubrics (they hurt in FBI),
  and LLM calls inside `prepare()` (they would differ between scored runs).
