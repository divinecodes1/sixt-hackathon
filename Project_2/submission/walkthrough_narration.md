# Video narration

Voice: synthesized Microsoft Zira Desktop.

## Where is that car's odometer right now?

This is team Divinecodes, presenting Project Two: mileage forecasting and erroneous mileage detection. We built a local pipeline and an interactive demonstration to estimate a rental car's current mileage, forecast future mileage, and identify reports that deserve a closer look.

## The problem: readings arrive late

During a long rental, the latest recorded odometer may be weeks out of date. SIXT still needs to value the car and decide when to remove it from the rental fleet. A nowcast estimates mileage today. A forecast estimates mileage on a future date. Suspicious reading detection helps analysts find possible entry mistakes or unusual usage.

## We connected the supplied Parquet data

The development sample contains nearly two point seven million status rows across twenty seven thousand, six hundred and thirty vehicles. We added Parquet support and streaming fleet loading. The separate inference file has one hundred and sixty three thousand, forty seven missing mileage targets. We keep those targets separate from model tuning and do not use the empty organizer prediction or error columns as features.

## The key insight: two different clocks

Our main insight is that the date a mileage value belongs to can differ from the date the system first knows it. Some On Rent rows contain older handover mileage. We retime those values, but never reveal them before their row was recorded. We apply the same availability boundary to rental metadata and changing vehicle categories. The fleet pattern is not universal, so we document the assumption rather than treating every row as certain truth.

## Compare methods, then evaluate honestly

We compared the last recorded reading, an average daily rate, rental aware models, a recent usage variant, a blend, and a robust rate candidate. Earlier validation chooses the model separately for each task. A different later period calibrates the prediction ranges. Final evaluation uses later readings on held out vehicles. Future field mutation tests check that changing future rows cannot change earlier predictions.

## Live walkthrough: estimate the current mileage

Here is the working dashboard. Every vehicle in this demonstration is made up. Select a car on the left. The first card shows its last recorded mileage and the age of that reading. The orange card shows the model's current estimate and a prediction range. The timeline connects the known history to the estimate, making the gap visible instead of hiding the uncertainty.

## Change the planning horizon

Next, change the forecast horizon from thirty days to ninety days. The future estimate and its range update using outputs precomputed by the Python models. Longer horizons can require much wider ranges. The page also supports searching, filtering, and exporting the selected estimate as a CSV. The demo works offline and needs no API key.

## Make suspicious reports explainable

The review queue includes an intentionally invented mileage spike. Each signal shows the report date, the reading, and a reason for investigation. Our rules cover isolated spikes or dips, decreases, implausible rates, movement without recorded rentals, unchanged readings during rental days, and model residual outliers. A flag is a request for review. It is not proof of fraud, and real precision still requires domain expert labels.

## Measured results on held-out data

On held out development readings, current mileage error falls from five hundred and sixty one kilometres for the last reading baseline to four hundred and fifteen. Forecast error falls from seven thousand, three hundred and seventy six kilometres to two thousand, seven hundred and thirty four. Those are reductions of twenty six percent and sixty two point nine percent. The selected models also beat the stronger average rate baseline. These are fleet evaluation results, separate from the synthetic dashboard.

## Measure detection, report its limits

In a controlled development benchmark, the detector caught four hundred and fifty one of four hundred and seventy nine injected mistakes: ninety four point two percent episode recall. Exact corrupted reading recall was ninety three point nine percent. Episode recall can also credit the reading immediately before a rollback. This does not establish real world precision. Untouched readings may already contain errors, and some flags may reflect missing or stale operational data.

## The missing-mileage output is complete

We filled all one hundred and sixty three thousand, forty seven missing mileage targets and preserved the original table. Most use the vehicle's own earlier history with a range. Three thousand, seven hundred and forty five have no usable own history, so they receive an explicitly flagged fleet cohort fallback. Those fallbacks have no calibrated range and need review. The error column stays unchanged because the masked ground truth is unavailable.

## A reproducible project, ready for review

The project includes reproducible commands, measured aggregate evidence, thirty one passing tests, an offline dashboard, and a five slide presentation. A clean source copy runs the public example without organizer data. The next step is a shadow mode pilot: confirm measurement semantics, label representative flags, and validate long term rentals and range coverage. We demonstrate a working decision aid, not proven fraud detection, guaranteed savings, or production readiness.
