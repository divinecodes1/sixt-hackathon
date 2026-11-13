# Submission: Project 2, team Divinecodes

> **Status (12 Nov, evening):** the full pipeline (nowcast, forecast, 90% intervals, flags, injected-error benchmark)
> runs and is tested. It is measured on the 57-row example file (1 vehicle: indicative only) and on a synthetic fleet
> built in the organizers' schema (method check, **not** evidence about SIXT's fleet). Numbers on the full data are
> *TBD* (it arrives on 13 Nov). Nothing here is estimated or invented: every number comes from a file in `results/`.

## Authors
**Team name:** Divinecodes

**Project:** Project 2: Where is that car's odometer *right now*? (Mileage Forecasting & Erroneous Mileage Detection)

## Problem and approach
Valuation and defleet decisions need today's mileage, but for long rentals we only see the odometer when the car comes
back. We **nowcast** current mileage with a 90% range, **forecast** future mileage and **flag** readings that do not fit.

1. **Fix the data model first** ([EDA.md](EDA.md)).
   - An OnRent row carries the odometer from its rental's *handover*, stamped at the return. Read naively, the
     example's mileage "drops" 12 times and the starter flags all 12. We place those readings at the handover.
   - Such a reading is only *known* when the rental ends (weeks later for long rentals). Every model and the backtest
     only use readings known by their origin date; a test rewrites everything after the cutoff and checks that no
     prediction changes.
2. **Rental-aware predictor:** mileage = last known reading + r_rent × rental days + r_idle × idle days.
   - Nowcast: the rental days so far are known from the current rental status (the car left the counter).
   - Forecast: a car on rent at the cutoff stays out for its *expected remaining* rental time (learned from completed
     rentals of the same product, given the days already run); after that, the utilisation plan (`uti_plan`),
     calibrated against realised rental days on 30-day windows before the cutoff; zero new rentals after defleet.
   - Rates per vehicle (non-negative least squares) shrunk towards a hierarchical prior: rental product > vehicle
     level > vehicle type (empirical Bayes, so new vehicles and long-term cars get sensible rates).
   - Variants: time-decayed rates (`rent_aware_recent`) and a blend with the starter's mean rate (`blend`).
3. **Leakage-free model choice and intervals:** a validation cutoff before the test cutoff (training vehicles only)
   picks the model per task and calibrates a split-conformal interval: ± q·√(days since the last known reading),
   with q calibrated per horizon bucket (1–7, 8–14, 15–30, 31–60, >60 days); a bucket longer than any validated one
   uses the longest validated bucket's q, never less than the overall q.
4. **Flags** (each is "check this reading", never "fraud"). Every flag's `score` is the estimated km the reading
   is off by, so one sorted list is the review queue across rules:
   - `isolated_outlier`: a one-off typo (extra or missing digit) between two consistent neighbours. It is removed
     before the other rules, so one typo no longer flags every later reading;
   - `decrease` below the running maximum (a rollback: the highest reading is a floor on true mileage), flagged
     once per episode (or when it drops further), not on every later reading still below the old maximum;
   - `implausible_rate` > 1,500 km/day; `moved_without_rental` > 300 km with no rental;
     `no_movement_on_rent`: unchanged although on rent ≥ 3 days (copied or under-reported reading);
   - `residual_outlier`: robust z > 8 (scale per rental product once it has 30+ residuals) and ≥ 1,000 km from
     the nowcast.

## Models and why
No ML library, no LLM: numpy and the standard library, milliseconds per vehicle.

| Model | Open-weight or closed | Where it runs | Main metric(s) | Cost and time | Chosen? |
| --- | --- | --- | --- | --- | --- |
| naive_last (last reading) | n/a (rule) | local | MAE, skill = 0 by definition | ms | no, the floor |
| mean_rate (starter: last + average km/day) | n/a | local | MAE, MAPE, WAPE, skill vs naive | ms | baseline; chosen on the example file |
| rent_aware (rental days, hierarchical priors) | own, numpy | local | same + 90% interval coverage | ms | chosen on the synthetic fleet (both tasks) |
| rent_aware_recent (time-decayed rates) | own, numpy | local | same | ms | candidate |
| blend (mean_rate + rent_aware) | own, numpy | local | same | ms | candidate |

The choice is made per task on the validation period by `backtest()`, never on the test period.

## Results
Metrics: MAE in km, MAPE of the odometer (flattering, because odometers are large), WAPE of the distance driven since
the last known reading, skill = 1 − MAE / MAE(naive_last) on the same targets (MASE-like), and interval coverage.

**Example file** (1 vehicle, 5 held-out return readings: indicative only; `results/metrics.json`):

| Task | naive_last | mean_rate | rent_aware | blend |
|---|---|---|---|---|
| Nowcast MAE km | 419 | 133 | 116 | 125 |
| Forecast MAE km | 2,588 | 667 | 881 | 774 |

Validation chose mean_rate for both tasks. Too few validation targets for an interval. Flags: 0 (the starter: 12, all
artifacts of the stale OnRent rows).

**Synthetic fleet** (300 vehicles in the organizers' schema and row pattern, 15% long-term; generated by
`synth_fleet.py`, *made up*, and built on the same rental-days assumption as our model, so it favours it):

| Task, held-out vehicles after the cutoff | naive_last | mean_rate | rent_aware | blend | 90% coverage (chosen) |
|---|---|---|---|---|---|
| Nowcast MAE km (`results/synthetic/run_baseline.txt`, 122 targets) | 3,001 | 974 | **710** | 829 | 86% |
| Forecast MAE km (same run) | 7,190 | 1,346 | 1,455 | **1,243** | 90% |
| Nowcast MAE km, 5 fleets (`results/synthetic/seeds.json`) | 2,559 ± 149 | 739 ± 139 | **550 ± 55** | 610 ± 92 | 86–95% |
| Forecast MAE km, 5 fleets (same file) | 7,179 ± 160 | 1,476 ± 101 | 1,384 ± 183 | **1,362 ± 112** | 88–95% |

Nowcast error grows with the days since the last known reading (rent_aware, one fleet: 245 km at 1–7 days, 957 km
at 15–30 days, 3,095 km beyond 60 days): exactly where long rentals hurt.

**Flags, injected errors** (`results/synthetic/flag_benchmark.txt`, 2% of return readings corrupted, 3 seeds):

| Error type | extra digit | missing digit | transposed digits | rollback | stuck reading | all |
|---|---|---|---|---|---|---|
| Recall | 100% | 100% | 69% | 96% | 79% | **91%** |

Untouched readings flagged: 2.9 per 1,000 (67 of 23,426: residual_outlier 31, isolated_outlier 19,
moved_without_rental 14, implausible_rate 8). The residual threshold (z 8, 1,000 km) was chosen with this benchmark
to keep that rate low (a looser threshold caught more errors but flagged many more untouched readings).

**What did not work / limits**
- The forecast under-predicts at return readings (bias −1,212 km on the synthetic run). Return readings follow on-rent
  days by construction, while our plan calibration targets arbitrary days ([EDA.md](EDA.md) finding 4). We report it
  instead of tuning to the evaluation.
- Validation does not always pick the test winner (forecast on the synthetic run: rent_aware chosen, blend better).
- Forecast interval coverage varied by fleet (78–96%) with one √gap-scaled width; calibrating the width per horizon
  bucket narrowed it to 88–95% (`results/synthetic/seeds.json`). Beyond the horizons seen in validation the
  intervals are now conservative (wider than needed) rather than too narrow.
- Transposed digits that change the reading by little are hard to tell apart from normal driving (69%).
- One vehicle in the example; synthetic numbers check the method, not SIXT's reality. Full data: *TBD 13 Nov*.

## How to run
Python 3.11+, numpy only for our code (`requirements.txt` also lists pandas, scikit-learn and matplotlib for
exploration).
```bash
cd Project_2
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install numpy
python -m unittest test_mileage -v                  # 21 tests, incl. no-leakage and the flag benchmark
python run_baseline.py                              # first CSV in data/ (git-ignored), else example_file.csv
python run_baseline.py data/<file>.csv --asof 2024-08-01   # + per-vehicle nowcast with 90% range (git-ignored)
python flag_benchmark.py data/<file>.csv            # injected-error recall and false-flag rate on that data
python synth_fleet.py && python run_baseline.py synthetic/fleet.csv --out results/synthetic   # synthetic check
python synth_eval.py                                # 5 synthetic fleets: stability of the ranking
```
Outputs: `results/metrics.json`, `results/flags.csv`, `results/synthetic/*`. No secrets or environment variables.

## Demo
`submission/slides.pdf`: *to be added on 13 Nov.*

## Next steps
- Rerun everything on the full data; check the flag thresholds with `flag_benchmark.py` there and send the top flags
  to a domain expert for plausibility.
- Long-term rentals: model monthly self-reported readings, and use the contract's planned return date if SIXT has it.
- Intervals that widen linearly for long forecast horizons, or adaptive conformal updates over time.
- For SIXT: a daily job that publishes a nowcast per vehicle with its range (`--asof`), plus a review queue of flagged
  readings ordered by score.
