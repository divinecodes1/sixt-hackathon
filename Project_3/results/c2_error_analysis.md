# Criterion 2 (surprise): error analysis

Shipped judge, code unchanged. Scores from `score.py` (`c2_vs_baseline_report.txt`): ours 0.776 / 0.767 / 0.785,
baseline 0.652 / 0.600 / 0.715. The case counts below come from `c2_diag_trace.jsonl`, a re-run with
`JUDGE_TRACE_REASONS=1` that reproduced the same score (0.776), joined with the labels in `criterion2/c2_dev_pairs.jsonl`.

**17 of 73 pairs are wrong.**
- 11 are lost because a **correct original fails**: 7 originals fail, and each one sinks every pair built on it.
- 6 are lost on the **edited reply**: 5 harmless edits failed, 1 harmful edit passed.

## By cause (corner cases)

| # | Corner case | Pairs lost | Example |
|---|---|---|---|
| 1 | **A hedge in another sentence covers the policy's condition.** The policy says child seats are "on request, subject to availability (no guarantee)". The reply says "can be added" in one sentence and "we will try to reserve one" in the next. The judge reads the first sentence alone and calls the condition dropped. One source reply, in 4 languages and its harmless edits | 9 | S483245dc it/fr/es; J2D-0039, -0054, -0062, -0122 |
| 2 | **Frequency word versus scope word.** The policy says "some branches offer this by phone". The reply says "we can often extend". The judge reads "often" as "all branches" (wider scope) | 3 | Scfebe081 de/en |
| 3 | **Part of a condition dropped in a reply that is still labelled correct.** "Some branches can also extend by phone, if the car is not reserved" does not say "before the return time". Under this criterion's wording, the label "pass" is debatable | 2 | S8fbb9708 en |
| 4 | **A condition that belongs to a different promise.** "The blocked amount is 500 EUR" is failed for not repeating the credit-card rules (main driver's name, no debit cards), which are about how the deposit is paid, not how much it is | 2 | Sba0e1315 it; J2D-0156 |
| 5 | **A hedge read as covering a dropped condition (miss).** "Paid upgrades are often possible" with "depending on availability" removed: call 2 counts "spesso" (often) as the condition | 1 | J2D-0139 |

By source reply: the child-seat reply accounts for 9 of the 17, extension/late return for 5, the deposit for 2, the upgrade for 1.

## By decision path

| Path | Pairs lost | What happens |
|---|---|---|
| call 1 fail → call 2 confirms | 8 | Both calls read an omission as a violation (cases 1, 2) |
| call 1 fail → call 2 rejects → **call 3 fails it** | 8 | Call 2 correctly cleared the reply; call 3 judges from scratch, with the criterion's "leaving out a condition makes the statement incorrect", and fails it (cases 1, 3, 4) |
| call 3 passes a harmful edit | 1 | Case 5 |

When call 2 rejects call 1's findings and call 3 decides from scratch:

| | correct reply failed | bad reply caught | bad reply missed |
|---|---|---|---|
| Criterion 1 (shipped run, 12:22) | 7 | 12 | 8 |
| Criterion 2 | 6 | 1 | 1 |

## Why criterion 2 scores lower than criterion 1 (0.776 vs 0.850)

1. **The criterion text is stricter about omissions.** "Leaving out a condition … makes the statement incorrect" pushes call 1 and call 3 to flag every policy qualifier the reply does not repeat, including ones covered elsewhere (case 1) or belonging to another promise (case 4). Correct originals pass 0.849 here, against 0.920 on criterion 1.
2. **Call 3 helps on criterion 1 but hurts on criterion 2.** It catches 12 bad replies on criterion 1 but fails 6 good ones on criterion 2 while catching 1 (table above). Changing it would trade the criterion-1 catches for criterion-2 keep.
3. **The witness check was designed on criterion-1 dev errors.** That gain does not carry over fully to a stricter criterion.
4. **Small set, one dominant source reply.** 73 pairs from 9 source replies, and one reply (child seats) drives 9 of the 17 errors. One case moves an edit type by 10 points.
5. **Some labels are debatable under this criterion's wording** (case 3).

## What we did about it (14:05, disclosed)

The judge ran on this criterion unchanged first (0.776 above). Cases 1–5 would need prompt changes tuned on these 73
examples, so they stay as known limitations. The call-3 path is not criterion-specific, so we tested one generic
change: **`TRUST_VERIFY_REJECT`**, where call 2's rejection is final and call 3 only runs if call 2's answer is
unreadable. We simulated it offline from the traces first, then measured it for real on both criteria (2 runs each,
same verdict 1.000):

| | criterion 1 | criterion 2 |
|---|---|---|
| Before (witness check only) | 0.850 / 0.813 / 0.891 | 0.776 / 0.767 / 0.785 |
| **Shipped (+ `TRUST_VERIFY_REJECT`), `run_dev.sh` 14:06** | **0.845 / 0.762 / 0.949** | **0.883 / 0.867 / 0.900** |
| same code, earlier pair of runs (14:00) | 0.845 / 0.762 / 0.949 | 0.863 / 0.833 / 0.895 |

(combined / catch / keep, `score.py`.)

**Trade-off:** on criterion 1, dropped-condition catch falls from 0.800 to 0.667 and dropped-hedge catch from 0.800
to 0.700, while keep rises. The user chose to ship it at 14:05. `SUBMISSION.md` states that it was added after the
surprise data was seen.
