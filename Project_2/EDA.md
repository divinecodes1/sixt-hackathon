# Project 2: measured data investigation

Source: `results/data_profile.json`, `results/metrics.json`, `results/flag_benchmark.json`.

## Data and missingness
The development sample contains 2,699,762 rows and 27,630 vehicles, from
2022-01-02 00:00:00.000 to 2026-07-01 00:00:00.000.
Mileage ranges from 0 to 999,999 km.
`uti_plan` is missing in 44,599 rows; recorded values lie within [0,1].
`sixt_predicted_mileage_interp` and `sixt_error` are entirely empty, and excluded from model features.

## Measurement time versus availability
The original public example has stale handover odometers on OnRent rows. The larger sample is less uniform:
among 609,671 same-day vehicle/status pairs, 424,008 OnRent maxima are lower,
171,003 equal and 14,660 higher than the NotOnRent maxima.
This supports investigating stale values, but does not prove every OnRent odometer belongs to handover.
Multiple rentals in a day and day-level timestamps also make same-day differences ambiguous.

634,082 rows have a return date later than the row timestamp;
14 have handover after the row timestamp.
Future returns can be plans. We do not assume all rows were created at rental closure.
The retiming rule clamps measurement day to the recorded day if handover is later.

Earlier code treated future-recorded handovers as already known. The final code restricts rental metadata,
product and category to recorded availability, as well as the odometer. A test changes all future fields
and checks every model's earlier prediction. Unknown days after the latest status use the historical utilisation plan.

## Evaluation
Separate model selection, interval calibration and held-out test windows are described in SUBMISSION.md.
Recorded targets are kept even if suspicious. MAE, MAPE, WAPE, bias, stale-reading gap buckets, forecast lead-time
buckets and rental-product groups are stored in metrics.json. Return-day evaluation does not directly measure
unobserved arbitrary-day mileage. This limitation remains even with a correct temporal split.

## Flags and review
The detector flags 84.22 readings per 1,000 after retiming. The raw starter rules produce
42,108 flags; unlike the tiny example, they cannot all be called artifacts.
Top contexts are in ignored results/local/flag_review.md. Isolated spikes/dips include plausible digit mistakes;
long unchanged series and movement without rentals remain ambiguous. Human adjudication is pending.
Injected episode recall is 94.2%; exact corrupted-reading recall is 93.9%.
There are 122 additional untouched flags beyond existing flags across the benchmark seeds.
Neither untouched-flag rate nor model disagreement establishes real precision.

## Supplied masked file
Metadata inspection found missing mileage and empty output columns in test_data.parquet; no target outcomes
were used for tuning. predict_missing.py uses only past readings from those vehicles and past development priors.
See results/test_schema.json and, after inference, results/test_inference_summary.json.

## Remaining external validation
Confirm OnRent measurement semantics, actual/planned return dates, and public-data permission with the project owners.
Obtain expert labels and direct long-term/current-mileage ground truth before any production claim.
