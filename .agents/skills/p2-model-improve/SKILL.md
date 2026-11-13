---
name: p2-model-improve
description: Improve Project 2's mileage nowcast and forecast in mileage.py - add a model to the backtest, segment priors, defleet/LongTerm handling, blends, and calibrated prediction intervals (split conformal on gap-scaled residuals) - with leakage-free evaluation against naive_last and mean_rate. Use when asked to beat the baseline, improve the forecast, add uncertainty/intervals, or tune Project 2 models.
---

# Project 2: better nowcast, forecast and intervals

Judged on: error on held-out vehicles / periods (MAE, MAPE) vs a naive baseline, per task. Work in `Project_2/`, numpy + stdlib for model code.

## How mileage.py is wired
- Every model has `fit(fleet, train_ids, cutoff)` and `predict(v, cutoff, target, nowcast) -> km | None`. Add the class to `MODELS`; `backtest()` scores it for nowcast and forecast, per horizon bucket, picks the model per task on the **validation cutoff** (`selected`), and fits split-conformal intervals (`intervals`, ±q·√gap, α = 0.1).
- `Vehicle`: `obs_day/obs_km/obs_src/obs_known`, merged `rentals`, `uti`, `level`, `vtype`, `product`, `region`, `max_mileage`, `defleet_day`. A reading is measured on `obs_day` but only **known** from `obs_known` (the OnRent row is written at return). Always go through `v.view(day)`; `test_no_leakage_after_cutoff` checks it.
- Already in place: `RentAware` (hierarchical empirical-Bayes priors product > level > vtype with ≥ 20 intervals, `uti_plan` calibrated on 30-day windows, expected remaining rental time for cars on rent at the cutoff, zero rentals after defleet), `RentAwareRecent` (half-life 60 days), `Blend`.
- `nowcast_table(fleet, asof, ...)` / `run_baseline.py --asof` writes the per-vehicle product output with a 90% range.

## Test bed without the real data
- `python synth_fleet.py` writes `synthetic/fleet.csv` (git-ignored, organizers' schema, stale-OnRent pattern). It is built on the rental-days assumption, so it **favours** rent_aware: a method check, never evidence.
- `python run_baseline.py synthetic/fleet.csv --out results/synthetic`; `python synth_eval.py` (5 fleets, mean ± sd, chosen model and coverage) is the stability check before trusting a change.

## Known weaknesses (where to work next)
1. Forecast bias at return readings (synthetic −1,212 km): targets are return days, which follow on-rent days (EDA.md finding 4). Don't tune the plan to the evaluation; a target-aware evaluation or a report of the bias is the honest fix.
2. Forecast coverage varies (78–96% over seeds): √gap scaling is too narrow on long horizons. Try per-bucket q or linear scaling, judged on validation only.
3. Validation doesn't always pick the test winner: report it, don't override it.
4. LongTerm cars with monthly self-reports: check on the full data whether those readings exist and how they're stamped.

## No leakage
- Fit priors only on training vehicles and readings known by the cutoff. Choose variants on the validation cutoff, report once on the test cutoff.
- Forecast may use only rentals handed over by the cutoff plus `uti_plan`; nowcast may use rentals handed over by the target day.

## Finishing a change
`python -m unittest test_mileage -v` (add a test for the new model on synthetic data), then `python run_baseline.py`, then update the models table and results in `SUBMISSION.md` with the printed numbers, including where the new model loses.
