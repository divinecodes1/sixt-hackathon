# Submission: Project 2, team Divinecodes

> **Status (12 Nov, evening):** the baseline pipeline, tests and EDA are in place, run on the 57-row example file
> only. Numbers on the full data are *TBD* (it arrives on 13 Nov). Nothing here is estimated or invented.

## Authors
**Team name:** Divinecodes

**Project:** Project 2: Where is that car's odometer *right now*? (Mileage Forecasting & Erroneous Mileage Detection)

## Problem and approach
Valuation and defleet decisions need today's mileage, but for long rentals we only see the odometer when the car comes
back. We **nowcast** current mileage, **forecast** future mileage and **flag** readings that do not fit.

1. **Fix the data model first.** Rows with `on_rent_status = OnRent` carry a stale odometer value from the rental's
   handover, stamped with a later timestamp ([EDA.md](EDA.md)). Read naively, the example vehicle's mileage "drops" 12
   times, and the starter flags all 12. We time those readings at the handover. False decreases drop to 0 flagged.
2. **Rental-aware predictor:** mileage = last true reading + r_rent × rental days + r_idle × idle days.
   - For nowcasting, rental days come from known handovers; for forecasting, from `uti_plan`.
   - Rates are fitted per vehicle (non-negative least squares) and shrunk towards a vehicle-level prior
     (empirical Bayes, so new vehicles still get sensible rates).
3. **Flags:**
   - rules: odometer decrease beyond 10 km, more than 1500 km/day, or more than 300 km gained with no known rental;
   - residual outliers: robust z-score above 4 on the nowcast residual, scaled by √gap so long gaps are not flagged
     just for being long.

## Models and why
| Model | Open-weight or closed | Where it runs | Main metric(s) | Cost and time | Chosen? |
| --- | --- | --- | --- | --- | --- |
| naive_last (last reading) | n/a (rule) | local | nowcast MAE *TBD* | ms | no, floor |
| mean_rate (starter: last + average km/day) | n/a | local | *TBD* | ms | no, baseline |
| rent_aware (rental-day rates + shrinkage) | n/a (own, numpy) | local | *TBD* | ms | *TBD on full data* |

## Results
Backtest: a time split at the 80th percentile of reading dates (held-out period); on the full data, also 20% of
vehicles held out by hash. Targets are only real return readings. The nowcast predicts each held-out reading from
everything measured before that day; the forecast predicts all held-out readings from the cutoff.

Example file (1 vehicle, **4 held-out readings: indicative only, not evidence**):

| Task | naive_last MAE km | mean_rate MAE km | rent_aware MAE km |
|---|---|---|---|
| Nowcast | 269 | 112 | 108 |
| Forecast | 2680 | 1280 | 1637 |

Flags on the example: 0 (the starter: 12, all artifacts of the stale OnRent rows).
On synthetic data with known rates (`test_mileage.py`): rent_aware < mean_rate < naive_last on nowcast MAE, and
injected rollbacks and typos are caught.

Full data: *TBD 13 Nov*, with MAE, MAPE and WAPE of distance driven by horizon bucket, and how plausible the flags are.

## How to run
Python 3.11+, numpy only for our code (`requirements.txt` also lists pandas, scikit-learn and matplotlib for
exploration).
```bash
cd Project_2
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install numpy
python -m unittest test_mileage -v
python run_baseline.py                 # first CSV in data/ (git-ignored), else example_file.csv
python run_baseline.py data/<file>.csv --cutoff 2024-07-01   # optional explicit time split
```
Outputs: `results/metrics.json`, `results/flags.csv`. No secrets or environment variables are needed.

## Demo
`submission/slides.pdf`: *to be added on 13 Nov.*

## Next steps
- Calibrate the thresholds on the full data, and send a sample of flags to a domain expert for plausibility.
- Prediction intervals (quantiles of the scaled residuals), so valuation can see the uncertainty, not only a point.
- Segment priors by vehicle_type and region; the LongTerm vs ShortTerm rental product.
- For SIXT: a daily job that publishes a nowcast per vehicle with an interval, plus a review queue of flagged readings.
