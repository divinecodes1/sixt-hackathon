# Project 2 evaluation decisions

## Protocol, fixed before inspecting final held-out outcomes

- Input: `data_30_percent_sample.parquet`; do not tune on `test_data.parquet`.
- Sampled development runs use SHA256(`development:` + vehicle id) order, independently of the vehicle holdout hash.
- Fleet priors use only training vehicles. Held-out vehicles retain their own past readings (the deployment setting), never their future outcomes.
- Training cutoff: earlier than model-selection and calibration periods. Model selection uses the first half of the pre-test validation window; interval calibration uses its second half. Final test is later, on held-out vehicles.
- Choose lowest validation MAE separately for nowcast and forecast. Do not override the choice after seeing test results.
- Candidate methods: last reading, historical mean calendar rate, rental-aware rates, recent rental-aware rates, their blend, causal robust calendar rate.
- Robust rate was added to test whether removing observed one-off typos and clipping interval rates helps. It is a candidate, not assumed superior.
- No final test target is removed because the detector dislikes it. Recorded readings may themselves contain mistakes; report this label limitation and raw MAPE's sensitivity to zero/near-zero readings.
- Intervals target 90% coverage but time/fleet shifts and repeated readings violate ideal exchangeability. Report measured coverage and width.
- Final rental-aware methods restrict rental records, product and vehicle attributes to their recorded day. Unknown days after the last recorded status use the utilisation plan. Earlier development runs assumed an operational handover feed and are superseded; their scores are not final evidence.
- Flags are retrospective triage, not online fraud decisions. A same-day difference alone is not flagged: multiple legitimate rentals can occur on one day.
- The copied-reading rule applies only to fresh-return-source rows, not already-known stale handover rows.

## Evidence files

- `development_v2/validation.json`: bounded development rehearsal with separate selection/calibration windows.
- `development_full/validation.json`: earlier all-vehicle selection rehearsal using the superseded operational-handover assumption. Do not quote as final evidence.
- `development_strict/validation.json`: bounded rehearsal of final strict row-availability logic.
- `metrics.json`: final full-development-sample held-out evaluation, after decisions above.
- `flag_benchmark.json`: error injection on training vehicles and earlier periods; thresholds remain unchanged from the original method.
- `flag_review_summary.json`: aggregate context-review summary; detailed review is local and ignored. Human adjudication is not claimed.

The initial sampling implementation accidentally used the same hash order as the holdout and selected only test vehicles. It produced no validation metrics. Domain-separated sampling fixed it before any model decisions; that empty run is not evidence.
