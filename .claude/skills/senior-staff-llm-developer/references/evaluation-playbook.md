# Evaluation and experiment protocol

## Evaluation ladder

1. **Interface checks:** correct signature, valid `pass|fail` return, no exceptions for supported inputs, no leaking state.
2. **Small regression suite:** expected pass/fail on synthetic edge cases, multilingual paraphrases, empty or irrelevant clauses, numeric boundary cases.
3. **Fast dev:** score every change on the official smaller set, slice by edit and language.
4. **Full dev:** only promising candidates; preserve exact version and config.
5. **Grouped holdout:** hold out entire source IDs when designing prompts/heuristics; never select on the same held-out group repeatedly.
6. **Repeat consistency:** run independently with caching disabled and compare; agreement alone is not correctness.
7. **Unseen evaluation:** perform only according to organizer rules; do not reverse engineer hidden labels.

## Experiment log schema

| Date | Git SHA | Hypothesis | Change | Model | Calls/item | Macro catch | Macro keep | Combined | Kappa | Worst slice | Latency/cost | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

Include dataset size, errors, parsing failures, and whether numbers are measured or expected. Choose changes by robustness and correctness, not only highest dev combined score.

## Statistical cautions

Do not present 226 correlated pairs as 226 independent source scenarios; original source IDs are few. Slicing is essential; confidence intervals should be grouped by source if feasible. A strong aggregate metric can hide a 0% slice. Avoid uncalibrated percentage precision and untested claims of generalization.
