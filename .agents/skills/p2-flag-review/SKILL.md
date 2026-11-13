---
name: p2-flag-review
description: Make Project 2's erroneous-mileage flags plausible and measurable - check each flag rule, add generic rules (digit typos, readings below the running maximum, conflicting same-day readings), measure recall and false-flag rate with injected errors, and produce a short review table of the top flags for the domain expert. Use when asked about flags, anomalies, fraud, rollbacks, wrong mileage reports or Problem B.
---

# Project 2: flag review (Problem B)

There are no labels for "this report was wrong", so results are judged on **how plausible the flagged reports are**. Two kinds of evidence: (1) injected errors with known answers, (2) a readable review of real top flags. A flag means "check this reading", never "fraud".

## Current rules (mileage.flags)
`isolated_outliers()` runs first; those readings are removed (`without()`) before the other rules, so one typo doesn't cascade.
| rule | fires when | note |
|---|---|---|
| isolated_outlier | a spike or dip whose two neighbours agree with each other | one-off typo (extra/missing digit) |
| decrease | > 10 km below the running maximum (`DECREASE_TOL_KM`) | persistent rollback; the max is a floor on true mileage |
| implausible_rate | > 1500 km/day since the previous reading (`MAX_KM_PER_DAY`) | |
| moved_without_rental | > 300 km gained with no known rental (`IDLE_MOVE_KM`) | can be a missing rental row, not misuse |
| no_movement_on_rent | moved ≤ 10 km over ≥ 3 rental days (`STUCK_RENTAL_DAYS`) | copied / under-reported reading |
| residual_outlier | robust z > 8 **and** ≥ 1000 km from the nowcast (`RESIDUAL_Z`, `RESIDUAL_MIN_KM`) | thresholds chosen with the benchmark |
Stale OnRent rows are re-timed to handover first: never flag those as decreases (EDA.md finding 1).

Still open: same-day conflicts (two fresh readings on one day that disagree); `vhcl_max_mileage` exceeded, which is a business alert for its own column and not a data error.

## Measure with injected errors: `flag_benchmark.py`
```bash
cd Project_2 && python flag_benchmark.py data/<file>.csv --rate 0.02 --seeds 3
```
Injects extra_digit, missing_digit, transposed, rollback and stuck errors into fresh return readings (fixed seeds, one per vehicle). Prints recall per type, the rules that fired, and the flag rate on untouched readings (an upper bound on false flags, because real data has real errors). Synthetic reference: `results/synthetic/flag_benchmark.txt` (all types 91%, 3.0 untouched readings flagged per 1,000). Re-tune a threshold only on this benchmark and keep `FleetScale.test_benchmark_recall_and_false_flags` passing.

## Review the real top flags
Write `Project_2/results/flag_review.md`: the top flags by score per rule (about 5 each), each with the readings before/after (date, km, source), the rental around it and a one-line verdict: *likely data error*, *plausible but unusual*, or *artifact of our pipeline*. Count the artifacts honestly: they are bugs to fix, not flags. The vehicle id column may be truncated (first 8 characters) for readability.

## Report
In `SUBMISSION.md` Results: flags per 1,000 readings by rule, injected-error recall and false-flag rate, and 2–3 example flags from the review. Before committing `flags.csv` or `flag_review.md` built from the organizers' data, follow the data caution in the p2-full-data-run skill.
