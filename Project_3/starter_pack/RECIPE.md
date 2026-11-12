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
2. **The verdict is computed in code** from the fields (any claim violates → candidate fail), not from a free-text
   PASS/FAIL. Fields are more stable run to run than a holistic token.
3. **Invariance wording that stays criterion-agnostic:** "greeting, filler, sentence order, length, politeness and
   language matter only if the criterion is about them". Nothing says "openers never matter", so a tone criterion
   still works.
4. **Verify only suspected fails (call 2, fresh context).** It confirms or rejects each finding, which targets the
   false fails on good replies. It states the general principle that "leaving out a condition the reference
   attaches makes the statement stronger, not briefer", so it does not explain real omissions away.
5. **Tie-break (call 3)** only when calls 1 and 2 disagree: an independent holistic judgment with examples.
6. **Examples picked by code** from the labelled pairs: one per edit type, English first, alternating labels, at most
   8. The construction note (what was changed) is shown as the rationale. Temperature 0 everywhere. Reasoning in
   English with quotes in the original language. At most 3 calls per reply; no state between calls.

- Check: catch goes up on dev without keep going down. *To be measured on 13 Nov with the provided key (Step 4).*

## Step 4. Verify
Dev numbers use **grouped cross-validation by source reply** (`crossval.py`): the examples shown to the judge never
come from the source replies being scored. Run twice for consistency: `bash run_dev.sh`.

| | combined | catch | keep | kappa | same verdict (2 runs) |
|---|---|---|---|---|---|
| Baseline (precomputed) | 0.697 | 0.592 | 0.847 | 0.531 | n/a |
| Baseline + number rule (offline) | 0.697 | 0.592 | 0.847 | 0.531 | n/a |
| Ours, claude-haiku-4.5, 3-fold CV | *TBD 13 Nov* | | | | |

Per language and per edit type: see `../results/dev_pairs_report.txt` once run.

- Check: the gain holds on edit types and phrasings you did not tune on. Leave-one-edit-type-out is planned.

## Surprise criterion
Nothing changes in the code. `prepare()` re-validates the number rule against the new examples (it switches itself
off or to hint mode if the new criterion does not reward it) and picks new examples from the new pairs.

| | combined | catch | keep |
|---|---|---|---|
| Baseline | *TBD* | | |
| Ours, recipe unchanged | *TBD* | | |

## What did not work
- **Adding the number rule to the baseline gives +0.000.** The baseline already fails every wrong-number edit; its
  losses on that type come from failing correct originals. The rule saves an LLM call and makes those catches certain,
  but the gain has to come from fewer false fails.
- **Rejected on purpose:** a response cache to fake run-to-run consistency (it breaks the no-state rule), sampling
  above temperature 0 for voting (adds exactly the variance that is scored), long generated rubrics (they hurt in FBI),
  and LLM calls inside `prepare()` (they would differ between scored runs).
