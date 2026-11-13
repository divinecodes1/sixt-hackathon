# Submission: Project 2 - Divinecodes

## Authors

**Team name:** Divinecodes  
**Project:** Project 2: Mileage Forecasting & Erroneous Mileage Detection

## Problem and approach

SIXT may receive a car's mileage weeks after it was driven. Valuation and vehicle-sale planning still need an estimate today. We address both requested tasks:

- **A. Mileage prediction:** estimate the current odometer reading (nowcast) and its future value (forecast), with an uncertainty range.
- **B. Erroneous-reading detection:** flag reports that conflict with the car's usage history, with a reason and a discrepancy score for human review.

Our Python pipeline uses past mileage, rental dates/status, rental product, vehicle category and planned utilisation. It estimates separate driving rates for rented and idle days. Cars with little history borrow information from similar cars. Future usage combines historical patterns with planned utilisation; recorded defleet status stops planning new rentals.

**Key assumption:** repeated OnRent mileage often represents the handover reading rather than a fresh measurement. We assign it to handover for modelling, but only use it after its status row was recorded. This interpretation needs domain confirmation. Future rows and their attributes are excluded from earlier predictions.

For detection, we combine prediction-residual outliers with rules for isolated spikes/dips, decreasing mileage, implausible daily rates, movement without a recorded rental, and unchanged readings despite rental days. These are suspicious reports, not confirmed fraud.

## Models and why

All six models are our own statistical implementations, run locally with NumPy and DuckDB. They use no external model weights, API keys or paid inference. All were compared on the same held-out targets.

| Model | Main idea | Nowcast MAE (km) | Nowcast MAPE | Forecast MAE (km) | Forecast MAPE | Selected? |
|---|---|---:|---:|---:|---:|---|
| naive_last | Keep the last reading unchanged | 561 | 9.54% | 7,376 | 38.01% | Reference baseline |
| mean_rate | Extend average daily driving | 474 | 9.07% | 2,995 | 20.42% | Stronger baseline |
| rent_aware | Separate rented and idle-day rates | 423 | 7.35% | 3,255 | 18.33% | No |
| rent_aware_recent | Give recent usage more weight | **415** | **7.28%** | 3,176 | 17.91% | **Nowcast** |
| blend | Average mean_rate and rent_aware | 435 | 7.77% | **2,734** | **17.31%** | **Forecast** |
| robust_rate | Reduce the influence of past anomalous readings | 431 | 8.46% | 2,747 | 18.24% | No |

Selection uses validation MAE, not final test performance. Measured batch runtime was **1,109.5 seconds**, including loading, evaluation and flags. Per-item latency and infrastructure cost were not benchmarked.

## Results

### A. Mileage prediction

The development file contains **2,699,762 rows and 27,630 vehicles**. A stable vehicle-ID hash separates **22,071 training vehicles** from **5,559 held-out vehicles**. Held-out cars contribute their own available past history at prediction time, but do not train fleet priors.

Models train at **2025-03-31**. Later training-vehicle targets through **2025-07-21** select the models; separate targets through **2025-11-11** calibrate uncertainty ranges. Final evaluation uses readings after **2025-11-11** on held-out vehicles: **20,732 nowcast targets** and **14,274 forecast targets**. Nowcasts use an origin one day before a fresh return-source reading; forecasts use the fixed test cutoff. Suspicious targets are not removed to improve scores.

**MAE** is the average absolute error in kilometres; lower is better. **MAPE** is the average absolute error as a percentage of recorded odometer mileage, using a minimum denominator of 1 km. These are error measures, not classification accuracy.

The selected nowcast reduces MAE by **26.0%** versus the last-reading baseline; the selected forecast reduces it by **62.9%**. The table also includes the stronger mean-rate baseline.

Ranges target 90% coverage. Measured coverage was **90.7% for nowcasts** and **95.6% for forecasts**, with average full widths of **1,611 km** and **13,366 km** respectively. Coverage means the recorded value fell inside the range; it does not mean the point estimate was that percentage accurate.

Evidence: [results/metrics.json](results/metrics.json), including bias and errors by reading age, forecast lead time and rental product; [results/data_profile.json](results/data_profile.json) contains the data audit.

### B. Erroneous-reading detection

There are no confirmed wrong-reading labels. We therefore measured detection using injected errors in a development-only cohort: training vehicles, rows recorded by **2025-02-01**, and three fixed seeds. Thresholds were not tuned on final held-out outcomes.

The detector caught **450 of 479 corrupted readings (93.9%)**. Allowing a rollback to be identified at its first lowered reading or the immediately preceding reading gives **451 of 479 episodes (94.2%)**. The benchmark includes extra/missing digits, rollbacks, stuck readings and transposed digits.

It also flagged **5,965 of 85,519 untouched readings**, including **122 additional flags** beyond the original flag set. Untouched readings can already contain errors, so this is not a measured false-positive rate. Across the development fleet, **84.22 readings per 1,000** were flagged. Real flag precision and domain plausibility still need expert review.

Evidence: [results/flag_benchmark.json](results/flag_benchmark.json) and the rule counts in [results/metrics.json](results/metrics.json).

### Supplied masked-file inference

We produced estimates for **all 163,047 missing-mileage rows**. Of these, **159,302** have historical estimates with calibrated ranges; **3,745** lack their own past reading and receive a clearly marked cohort-median fallback without a calibrated range. The completed file preserves the original columns, fills `sixt_predicted_mileage_interp`, and leaves `sixt_error` unchanged.

The inference runner uses a bounded development cohort and past quarter-start snapshots to build priors; its fallback performance is not established by the held-out vehicle-history scores above. The masked file has no target labels, so filling every row is **completion, not measured accuracy**.

Evidence: [results/test_inference_summary.json](results/test_inference_summary.json) and [results/inference_validation.json](results/inference_validation.json). Vehicle-level outputs are generated locally, not included in the public package.

### Limitations

- Recorded return mileage can be stale or incorrect; it is a proxy for true odometer mileage. One-day-before-return nowcasts do not directly validate every possible valuation day.
- Short-term rentals dominate. The held-out long-term groups have only **105 nowcast** and **140 forecast** targets, so long-term performance needs more validation.
- Forecast ranges are wide. Reported coverage is empirical, not guaranteed under changes in fleet or usage.
- Missing rental records and unusual driving can create false alarms. Human-confirmed flag precision is not yet available.

## How to run

Python **3.11+**; checked locally with Python 3.14. No environment variables or API keys are required. From the repository root on Windows:

```powershell
cd Project_2
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest test_mileage -v
.\.venv\Scripts\python.exe run_baseline.py example_file.csv --out results/example
```

The public example runs without organizer data; its scores are only a smoke check. To reproduce the fleet results, provide the supplied Parquet files locally in the ignored `data/` directory and follow [README.md: Reproduce the supplied-data analysis](README.md#reproduce-the-supplied-data-analysis). That section also documents inference, generated outputs, and Linux/macOS setup. Use a separate example output directory to preserve the recorded fleet metrics.

## Demo

[submission/slides.pdf](submission/slides.pdf) is the required presentation deliverable: **five slides**. The additional [submission/demo.html](submission/demo.html) is a self-contained offline demo: open it in a browser to compare current mileage, change forecast horizons and review suspicious readings. It uses made-up vehicles and actual model outputs.

## Next steps

Run a daily shadow-mode batch for valuation and defleet analysts, showing estimates, uncertainty and a prioritised review queue. Ask domain experts to label flags and confirm rental-date semantics; collect fresh long-term readings and recalibrate by product and forecast horizon. Measure review workload and valuation impact before claiming financial savings.

**Publication status:** organizer files and detailed outputs are excluded from the working package, but earlier git commits still contain the supplied data. Publication permission or history cleanup remains necessary before final submission; the current cleanup is not yet committed or pushed.
