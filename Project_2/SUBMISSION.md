# Submission: Project 2 — Divinecodes

## Authors
**Team:** Divinecodes. **Project:** Project 2, Mileage Forecasting & Erroneous Mileage Detection.

## Problem and approach
SIXT needs current mileage for valuation and future mileage for defleet planning while rental readings are delayed.
We deliver nowcasts, forecasts, measured prediction ranges, a retrospective review queue, and masked-file inference.

The key engineering insight is that **measurement time and information-availability time differ**. OnRent mileage
often belongs to handover; the row may arrive later. We retime the reading but never make its mileage, rental metadata,
product or vehicle category available before the row was recorded. Future-field mutation tests guard this boundary.
After the last recorded status, a missing rental row is not evidence of idleness: the utilisation plan fills that gap.
An OnRent row is not necessarily a completed rental: 634,082 rows have a return date later than their recorded date.

## Models and why
All models run locally: numpy plus DuckDB for Parquet. No API, credentials or paid inference.
`naive_last` holds mileage constant; `mean_rate` extrapolates calendar-day usage. Rental-aware models separately fit
nonnegative rented/idle rates, shrink sparse histories toward product/category priors, calibrate utilisation, and stop
planning new rentals after recorded defleet. The recent variant downweights old usage. `blend` averages mean-rate
and rental-aware predictions. `robust_rate` cleans already-observed isolated typos and clips historical interval rates.

| Model (own statistical code; no external weights) | Nowcast MAE km | Nowcast MAPE | Forecast MAE km | Forecast MAPE | Validation choice |
|---|---:|---:|---:|---:|---|
| naive_last | 561 | 9.54% | 7,376 | 38.01% | candidate / baseline |
| mean_rate | 474 | 9.07% | 2,995 | 20.42% | candidate / baseline |
| rent_aware | 423 | 7.35% | 3,255 | 18.33% | candidate / baseline |
| rent_aware_recent | 415 | 7.28% | 3,176 | 17.91% | nowcast |
| blend | 435 | 7.77% | 2,734 | 17.31% | forecast |
| robust_rate | 431 | 8.46% | 2,747 | 18.24% | candidate / baseline |

Measured total pipeline runtime: 1,109.5 seconds on this machine, including reading, evaluation and flags.
This is a batch measurement, not a per-request latency benchmark or an infrastructure-cost estimate.

## Results and evaluation protocol
Input: **2,699,762 rows, 27,630 vehicles**, 1,889,253 distinct retimed readings.
Train/test vehicle split by stable hash: **22,071/5,559**.
Held-out vehicles supply their own earlier history, as they would in deployment; they never train fleet priors.

- Models train at 2025-03-31; model choice uses subsequent training-vehicle targets through 2025-07-21.
- Separate later targets through 2025-11-11 calibrate ranges. This avoids reusing selection outcomes for calibration.
- Final models fit at 2025-11-11; test targets are later readings on held-out vehicles.
- Nowcast: rolling origin one day before each fresh recorded return-source target. Forecast: fixed origin at the test cutoff.
- Final model choice is **rent_aware_recent** for nowcast and **blend** for forecast, using validation MAE only.
- Test targets: **20,732 nowcast / 14,274 forecast**. No target is removed because our detector dislikes it.

Against the last-reading baseline, the selected nowcast reduces MAE by **26.0%**;
the selected forecast by **62.9%**. The full table includes the stronger mean-rate baseline.
MAE is primary. MAPE divides by max(recorded odometer, 1 km), so zero/near-zero and erroneous targets can dominate it.
WAPE of distance since the last reading, bias and errors by gap are in `results/metrics.json`.
Forecast lead-time buckets are separately reported under `by_segment/lead_time:*`; these differ from stale-reading gap buckets.

| Task | Measured range coverage (90% target) | Mean full range width km |
|---|---:|---:|
| nowcast | 90.7% | 1,611 |
| forecast | 95.6% | 13,366 |

| Task | Rental product known at origin | Targets | Selected MAE km |
|---|---|---:|---:|
| nowcast | ShortTerm | 20,620 | 414 |
| nowcast | LongTerm | 105 | 527 |
| nowcast | ? | 7 | 254 |
| forecast | ShortTerm | 14,134 | 2,724 |
| forecast | LongTerm | 140 | 3,796 |

### Suspicious-reading evidence
Flags cover isolated spikes/dips, persistent decreases, implausible rates, movement without a recorded rental,
unchanged fresh readings despite rental days, and robust residual outliers. Scores are estimated discrepant kilometres.
A same-day difference alone is deliberately insufficient: multiple legitimate rentals can happen in a day.
Total flagged readings: **84.22 per 1,000**. Per-rule counts are in the metrics file.

Injected-error benchmark: deterministic development cohort, training vehicles only, rows recorded by 2025-02-01,
3 fixed seeds. Thresholds were not tuned on final held-out outcomes.

| Injected error | Injected | Detected | Recall |
|---|---:|---:|---:|
| extra_digit | 101 | 101 | 100.0% |
| missing_digit | 114 | 111 | 97.4% |
| rollback | 110 | 109 | 99.1% |
| stuck | 76 | 60 | 78.9% |
| transposed | 78 | 70 | 89.7% |

Overall episode recall: **451/479 (94.2%)**. Exact corrupted-reading recall: **450/479 (93.9%)**.
Episode recall gives a rollback credit if its first lowered reading or its immediately preceding reading is flagged.
Untouched readings flagged: **5,965/85,519**; these can include existing errors or stale-data artifacts,
so this is **not measured false-positive rate or precision**. Additional untouched flags beyond the original flag set:
**122**. The benchmark also records recall among originally unflagged injected readings.

`results/local/flag_review.md` gives local reading/rental context for top flags. Human domain adjudication remains pending;
no confirmed-fraud or precision claim is made. Public examples in the slides are conceptual, not copied vehicle records.

### Masked inference
Masked-file inference: 163,047 of 163,047 missing-mileage rows received an estimate; 3,745 had no own past reading, of which 3,745 receive an explicitly flagged cohort-median fallback. 0 remain unsupported. 159,302 estimates have a calibrated range. Detailed output: `results/local/test_predictions.csv` and `results/local/test_completed.parquet` (not public). The completed table preserves the original columns and fills `sixt_predicted_mileage_interp`; `sixt_error` remains unchanged. There are no ground-truth labels for these masked rows; no test accuracy is claimed.
The two supplied vehicle sets do not overlap (metadata check). Their prediction/error columns are empty;
we do not use them as features or invent errors where the ground truth is missing.
Targets later than a vehicle's last recorded status use the forecast recipe and an origin at that status;
they are not treated as observed current-rental snapshots. Quarter-start development snapshots precede that origin.
Cold-start cohort medians use vehicle category/model year where sufficient development examples exist.
They are explicitly marked for review, have no calibrated range, and are not validated by the vehicle-history MAE above.

### Limits and what did not work
- Retiming all OnRent values is a working schema interpretation, not a fleet-wide proven fact. Of 609,671 same-day
  paired vehicle-days, 424,008 have lower OnRent mileage, 171,003 are equal and 14,660 are higher.
- The sample is dominated by short-term observations. Product is the historical mode known at the origin, not a perfect current-contract label.
- Return-source readings may be stale or wrong. There is no independent odometer ground truth; raw-target MAE is a transparent proxy.
- Observed return days differ from arbitrary valuation days. Rolling nowcasts are one-day-ahead proxies, not direct labels of hidden daily mileage.
- Conformal ranges do not guarantee 90% coverage under temporal/fleet shift or dependent repeated readings; measured coverage is reported above.
- Long-horizon and long-term errors need separate monitoring. Unusual driving, transfers and missing rentals can trigger flags without an entry error.
- Earlier synthetic numbers used the older availability assumption and are archived method checks, not current performance claims.

## How to run
Python 3.11+; verified here with Python 3.14. From the repository root:

```powershell
cd Project_2
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest test_mileage -v
.\.venv\Scripts\python.exe run_baseline.py example_file.csv --out results/example
# Organizer files must be provided locally; they are not needed for the public example.
.\.venv\Scripts\python.exe profile_data.py data/data_30_percent_sample.parquet
.\.venv\Scripts\python.exe run_baseline.py data/data_30_percent_sample.parquet --out results
.\.venv\Scripts\python.exe flag_benchmark.py data/data_30_percent_sample.parquet --max-vehicles 1000 --training-only --before 2025-02-01 --rate 0.02 --seeds 3 --out results/flag_benchmark.json
.\.venv\Scripts\python.exe predict_missing.py
.\.venv\Scripts\python.exe submission/make_submission.py
```

Linux/macOS: replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`, or use `bash setup.sh` for the public example.
The Windows commands above need no PowerShell policy change; `setup.ps1` is optional where scripts are permitted.
`python run_baseline.py` always uses the public example; input selection is explicit.
For historical product exports: `python run_baseline.py example_file.csv --out results/example --asof 2024-08-01 --forecast-date 2024-08-31`.
The export reselects its model using validation before its as-of date. Missing calibration is explicit rather than an invented range.
Vehicle-level organizer outputs go to ignored `results/local/`; aggregate evidence stays in `results/`.

## Demo
**`submission/slides.pdf`**, five slides. Reproducible source: `submission/slides.html` and this generator.
Rebuild the PDF with `python submission/render_slides.py` (installed Chrome, Chromium or Edge).
The safe live walkthrough is `python demo.py`, which creates made-up vehicles and exports nowcasts, future mileage and a review queue.
For the interactive visual walkthrough, open `submission/demo.html` in a browser.
Rebuild it with `python submission/build_demo.py`; all data and charts are embedded for offline use.
No real vehicle examples are needed in the public pitch.

## Business relevance and next steps
A daily batch can publish mileage estimates, their age/range and an explicit review status for valuation analysts.
Forecast exports support defleet planning; mileage-limit alerts are separate from suspected data errors.
Start in shadow mode: prioritize the largest discrepancies, ask domain experts to label a review sample, and measure workload/precision.
Then validate actual versus planned return semantics, obtain fresh monthly long-term readings, and calibrate ranges separately by product/horizon.
No monetary savings are asserted without a SIXT valuation/cost study.

## Submission safety
The code and aggregate evidence are prepared locally. Existing tracked Parquet files require owner confirmation or exclusion
before publication; an ignore rule does not remove files already tracked in git. No push is authorized by this write-up.
The public repository must contain code, this write-up, aggregate results and the deck by 16:45 on 13 November 2026.
