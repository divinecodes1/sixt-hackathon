# SIXT Project 3: Judge the Judge — implementation playbook

Reference repository: https://github.com/sixt-hackathon-2026/sixt-hackathon-2026/tree/main/Project_3

## Inspect in this order

1. `README.md`, `starter_pack/DATACARD.md`, `starter_pack/JUDGE1_CRITERION.md`, `starter_pack/policy.md`.
2. `starter_pack/run_judge.py`, `starter_pack/score.py`, `starter_pack/diagnose.py`.
3. `starter_pack/baseline_judge.py`, `starter_pack/my_judge.py`, `starter_pack/baseline_report.txt`.
4. `starter_pack/dev_pairs_fast.jsonl`, then full dev; `starter_pack/RECIPE.md`.

## Key metrics and constraints

- Development set: 226 pairs, 119-pair fast subset, languages EN/DE/FR/ES/IT.
- Nine development edit types: harmless `filler_padding`, `polite_opener`, `padding_removal`, `sentence_reorder`, `translation`; harmful `hedge_removal`, `condition_removal`, `wrong_number`, `wrong_policy_detail`.
- `catch` requires `(original, edited) == ('pass', 'fail')` for harmful cases.
- `keep` requires `('pass', 'pass')` for harmless cases.
- Macro average each family over edit types, then harmonic mean. Check per-language results and Cohen's kappa; assess repeat consistency separately.
- Hidden cases include unseen source replies, unseen edits, and new phrasings. A second criterion is introduced during the event. No criterion-specific source-based branches.
- Model exactly `claude-haiku-4.5`; `<=3` calls per reply, no cross-call memory. Run `--isolate` to validate compatibility. If repeat consistency is being tested, unset `JUDGE_LLM_CACHE`.

## Recommended judge design

Use one semantic pass with explicit evidence-first decomposition:

1. Understand customer question and claimed commitments in the reply; ignore greetings, style, wording order.
2. Map commitments to relevant policy clauses; identify policy scope, prerequisites, exceptions, uncertainty, timing, and quantity.
3. Compare **each affirmative commitment** with the policy. Ask: Does the reply assert a stronger guarantee, looser condition, broader scope, more generous value, or incorrect detail than warranted?
4. Apply the **criterion text exactly**: the overpromise criterion allows underpromises and generic reassurance, but a different criterion may not. Never transplant that behavior as hardcoded logic.
5. Emit one unambiguous PASS/FAIL. Optionally allow structured intermediate extraction inside a single call, but budget tokens and validate the final decision.

A second call should have an explicit purpose: e.g. focused counterargument on borderline interpretations. A third call requires measured improvement. Avoid voting with three identical temperature-0 prompts.

## Candidate experiments, in order

- Baseline reproduce and error diagnosis; capture per-edit/per-language numbers.
- Criterion-aware decomposition with evidence quotes from **the input policy** and strict parsing.
- Null-safe checks and deterministic numeric grounding, gated by criterion and relevance; do not reject every number absent from the policy (dates and questions may include unrelated numbers).
- Clause-specific second-pass verification only for ambiguous/high-risk cases, while preserving the three-call limit.
- Carefully selected training examples for prompt guidance only from supplied `prepare` dev input; keep `judge` independent of labels and pairs.
- Ablations, grouped by `source_id`, to verify gains do not depend on wording templates.

## Starter commands

From `Project_3/starter_pack/`:

```bash
python3 score.py baseline_dev_verdicts.csv dev_pairs.jsonl
python3 diagnose.py baseline_dev_verdicts.csv dev_pairs.jsonl
python3 run_judge.py --judge my_judge.py --pairs dev_pairs_fast.jsonl --criterion JUDGE1_CRITERION.md --policy policy.md --dev dev_pairs.jsonl --out mine_fast.csv
python3 score.py mine_fast.csv dev_pairs_fast.jsonl --baseline baseline_dev_verdicts.csv
```

Run network-dependent commands only after checking environment and valid authorization, and never fabricate scores. For isolation run `run_judge.py ... --isolate --workers 1`. Check `--repeat` with a second run and caching disabled.

## Timeline and integrity

Before freeze: evaluate and save real metrics, copy final working judge to `starter_pack/final_judge.py`, verify dependencies and runtime. At 16:00 commit and record exact SHA. After the hidden unlabeled data is released, run code **without changes** on both criteria twice, produce `submission/criterion1_run1.csv`, `criterion1_run2.csv`, `criterion2_run1.csv`, `criterion2_run2.csv`, then submit by 16:45. Do not inspect or guess hidden labels.
