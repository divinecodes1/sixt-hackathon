# Video narration

Voice: synthesized Microsoft Zira Desktop.

## Where is that car's odometer right now?

This is team Divinecodes, presenting Project Two: mileage forecasting and erroneous mileage detection. We built a local pipeline and an interactive demonstration to estimate a rental car's current mileage, forecast future mileage, and identify reports that deserve a closer look.

## The problem: readings arrive late

During a long rental, the latest recorded odometer may be weeks out of date. SIXT still needs to value the car and decide when to remove it from the rental fleet. A nowcast estimates mileage today. A forecast estimates mileage on a future date. Suspicious reading detection helps analysts find possible entry mistakes or unusual usage.

## We connected the supplied Parquet data

The development sample contains nearly two point seven million status rows across twenty seven thousand, six hundred and thirty vehicles. We added Parquet support and streaming fleet loading. The separate inference file has one hundred and sixty three thousand, forty seven missing mileage targets. We keep those targets separate from model tuning and do not use the empty organizer prediction or error columns as features.

## Understand the input fields

Each row is a vehicle status update. The anonymous vehicle identifier groups the history. The timestamp tells us when a row was recorded, while the mileage field contains the stored odometer. Rental status, handover, return date and rental product describe the rental context. Vehicle category and planned utilisation help estimate usage. The maximum mileage field is a business limit, not a substitute for an actual reading. Some descriptive fields are available in the source without being used by every model.

## What data preparation actually does

The loader supports CSV and Parquet, validates required fields, groups observations by vehicle, removes duplicate readings, and combines rental coverage. Missing or non finite mileage values are not treated as real readings. The fleet audit found more than six hundred thousand rows with return dates later than their recorded timestamps, so a return field can be a plan. The stale handover pattern also has exceptions. These findings are documented as assumptions and validation questions, not hidden by the pipeline.

## The key insight: two different clocks

Our main insight is that the date a mileage value belongs to can differ from the date the system first knows it. Some On Rent rows contain older handover mileage. We retime those values, but never reveal them before their row was recorded. We apply the same availability boundary to rental metadata and changing vehicle categories. The fleet pattern is not universal, so we document the assumption rather than treating every row as certain truth.

## The prediction logic in plain language

The simplest baseline keeps the last reading unchanged. The average rate baseline adds the vehicle's historical daily mileage multiplied by the gap. Our rental aware model estimates separate driving rates for rented days and idle days. It adds each rate multiplied by the corresponding number of days. Unknown days after the last recorded status use planned utilisation. For future dates, the model estimates remaining rental exposure from available rental history and then the utilisation plan. Recorded defleet status stops planning new rentals.

## All six candidates, on the same targets

Sparse vehicle histories borrow strength from broader product and vehicle category groups. The recent rental aware variant downweights older usage. The blend averages rental aware and average rate predictions. The robust candidate cleans already observed isolated typos and clips historical interval rates. All six candidates are measured on the same targets. Earlier validation selects recent rental aware for current mileage and the blend for forecasts. More complexity does not automatically win: the plain rental aware model is worse than average rate for forecast error, and the robust candidate does not win the selected tasks.

## Compare methods, then evaluate honestly

We compared the last recorded reading, an average daily rate, rental aware models, a recent usage variant, a blend, and a robust rate candidate. Earlier validation chooses the model separately for each task. A different later period calibrates the prediction ranges. Final evaluation uses later readings on held out vehicles. Future field mutation tests check that changing future rows cannot change earlier predictions.

## The exact evaluation protocol

The stable hash split reserves five thousand, five hundred and fifty nine vehicles for final testing and uses twenty two thousand, seventy one for training fleet priors. Initial training ends on March thirty first, twenty twenty five. Model selection uses later training vehicle targets through July twenty first. A separate subsequent period through November eleventh calibrates ranges. Final models fit at that cutoff and are evaluated afterwards on held out vehicles. Held out vehicles may supply their own earlier history, but their outcomes never train fleet priors. Suspicious test targets are retained rather than removed to improve the score.

## What the reported metrics mean

Mean absolute error, or M A E, is the average absolute distance between the estimate and recorded target. It is our primary selection metric. M A P E expresses error as a percentage of the odometer, using a minimum denominator of one kilometre, so small or erroneous readings can dominate it. W A P E compares error with the distance driven since the last known reading. Bias shows whether estimates systematically overshoot or undershoot. Skill measures improvement over the last reading baseline. Nowcasts use a rolling origin one day before a return source target; forecasts use the fixed cutoff.

## The selected models: more than one metric

The selected current mileage model has an odometer percentage error of seven point two eight percent, compared with nine point five four percent for the last reading baseline. Its signed bias is about minus one hundred and forty four kilometres. The selected forecast has percentage error of seventeen point three one percent, compared with thirty eight point zero one percent for the last reading baseline, and bias of about plus one hundred and fourteen kilometres. Distance based weighted error is also reported. These complementary metrics help reveal systematic behaviour that a single average can hide.

## Live walkthrough: estimate the current mileage

Here is the working dashboard. Every vehicle in this demonstration is made up. Select a car on the left. The first card shows its last recorded mileage and the age of that reading. The orange card shows the model's current estimate and a prediction range. The timeline connects the known history to the estimate, making the gap visible instead of hiding the uncertainty.

## Change the planning horizon

Next, change the forecast horizon from thirty days to ninety days. The future estimate and its range update using outputs precomputed by the Python models. Longer horizons can require much wider ranges. The page also supports searching, filtering, and exporting the selected estimate as a CSV. The demo works offline and needs no API key.

## How reliable are the prediction ranges?

The ranges are calibrated from earlier prediction errors, separately from choosing the model. Their width scales with the square root of the time since the last reading, with separate gap buckets where enough calibration examples exist. The target is ninety percent coverage. Measured current mileage coverage is ninety point seven percent, with mean full width of one thousand, six hundred and eleven kilometres. Forecast coverage is ninety five point six percent, with a much wider mean range. These are measured results, not guarantees under fleet shifts, temporal change, or dependent repeated readings.

## Make suspicious reports explainable

The review queue includes an intentionally invented mileage spike. Each signal shows the report date, the reading, and a reason for investigation. Our rules cover isolated spikes or dips, decreases, implausible rates, movement without recorded rentals, unchanged readings during rental days, and model residual outliers. A flag is a request for review. It is not proof of fraud, and real precision still requires domain expert labels.

## The detection rules and their safeguards

An isolated spike or dip is identified between consistent neighbours and removed before the other rules run, so one typo does not create a cascade. A decrease is more than ten kilometres below an earlier maximum and is reported once per episode unless it drops further. An implausible rate exceeds fifteen hundred kilometres a day. Movement without a recorded rental exceeds three hundred kilometres. Unchanged fresh return readings are checked after at least three rental days. Residual outliers need a robust z score above eight and at least a thousand kilometres of disagreement. Some rules need later neighbours, so the queue is retrospective. Same day differences alone are not errors.

## Measured results on held-out data

On held out development readings, current mileage error falls from five hundred and sixty one kilometres for the last reading baseline to four hundred and fifteen. Forecast error falls from seven thousand, three hundred and seventy six kilometres to two thousand, seven hundred and thirty four. Those are reductions of twenty six percent and sixty two point nine percent. The selected models also beat the stronger average rate baseline. These are fleet evaluation results, separate from the synthetic dashboard.

## Look beyond the overall average

Overall averages can hide difficult cases. Long term current mileage error is five hundred and twenty seven kilometres on only one hundred and five targets. Long term forecast error is three thousand, seven hundred and ninety six on one hundred and forty targets. Current mileage error beyond a sixty day stale reading gap reaches five thousand and forty nine kilometres, on only twelve targets. Those small groups need caution. The report separates stale reading gap buckets from future lead time buckets. Historical mode of product is not a perfect current contract label, and this sample is dominated by short term rentals.

## Measure detection, report its limits

In a controlled development benchmark, the detector caught four hundred and fifty one of four hundred and seventy nine injected mistakes: ninety four point two percent episode recall. Exact corrupted reading recall was ninety three point nine percent. Episode recall can also credit the reading immediately before a rollback. This does not establish real world precision. Untouched readings may already contain errors, and some flags may reflect missing or stale operational data.

## Detection recall by injected mistake

The injected error benchmark uses fixed random seeds on a deterministic development cohort, restricted to training vehicles and rows recorded by February first, twenty twenty five. Detection catches every injected extra digit, about ninety seven percent of missing digits, ninety percent of transposed digits, ninety nine percent of rollback episodes, and seventy nine percent of stuck readings. Small digit changes can resemble ordinary driving. These controlled results test particular mistake types, not every real anomaly. Thresholds were not selected using final held out outcomes.

## The review workload is part of the result

The full fleet scan flags eighty four point two two readings per thousand, so review workload matters. Across benchmark seeds, five thousand, nine hundred and sixty five untouched readings are flagged. They may contain existing errors, missing rental records, or stale data artifacts, so this is not a measured false positive rate. Comparing against the original flag set gives one hundred and twenty two additional untouched flags after injection. The local review file includes neighbouring readings and rental context. Human adjudication is still pending, and we do not claim real precision.

## What the full-fleet detector flagged

The aggregate report also breaks down the full fleet review workload by rule. Movement without a recorded rental and unchanged readings contribute many signals, and require care because operational records can be incomplete or stale. Isolated typos, implausible rates, decreases and residual disagreements contribute the remaining signals. A reading can trigger more than one rule, so the signal total is not a count of independently confirmed bad readings. The local context review helps analysts distinguish likely entry errors, unusual but plausible usage, and possible pipeline artifacts.

## The missing-mileage output is complete

We filled all one hundred and sixty three thousand, forty seven missing mileage targets and preserved the original table. Most use the vehicle's own earlier history with a range. Three thousand, seven hundred and forty five have no usable own history, so they receive an explicitly flagged fleet cohort fallback. Those fallbacks have no calibrated range and need review. The error column stays unchanged because the masked ground truth is unavailable.

## What is in the completed prediction output?

The completed Parquet file preserves all six hundred and fifty six thousand, six hundred and one rows and the original columns. Observed history ends on July first, twenty twenty six; missing targets run from July second to November eleventh. Targets after a vehicle's latest recorded status use the forecast model from that status date. Fleet priors and calibration use earlier quarter start snapshots from a bounded thousand vehicle development cohort. Cold start fallbacks use category and model year where supported. They are not validated by the history based accuracy table, have no calibrated range, and require review. No masked target accuracy is claimed.

## A reproducible project, ready for review

The project includes reproducible commands, measured aggregate evidence, thirty one passing tests, an offline dashboard, and a five slide presentation. A clean source copy runs the public example without organizer data. The next step is a shadow mode pilot: confirm measurement semantics, label representative flags, and validate long term rentals and range coverage. We demonstrate a working decision aid, not proven fraud detection, guaranteed savings, or production readiness.

## Where the implementation lives

The main implementation is mileage dot py. It contains timeline construction, prediction models, backtesting, uncertainty and flags. Run baseline is the evaluation entry point, and profile data produces aggregate checks. Flag benchmark injects known mistakes, while review flags creates contextual triage material. Predict missing writes inference outputs, and test mileage checks correctness and information boundaries. Synthetic fleet and synthetic evaluation scripts support method checks; their older archived results are not presented as current fleet performance. The interactive dashboard is generated from actual Python outputs on made up vehicles.

## How to run and reproduce the project

From the Project Two folder, create and activate a virtual environment, then install requirements. The model code needs numpy, and Duck D B reads Parquet. Run the unit tests and the public example before supplying organizer data explicitly. Run baseline evaluates the fleet and saves aggregate metrics; predict missing produces the completed inference table. Build demo creates the offline dashboard. Exact platform commands, flag benchmark options, date specific nowcast and forecast exports, and reproduction instructions are in the submission. The measured full pipeline batch took about eleven hundred seconds on this machine, not milliseconds per request.

## How an analyst would use the outputs

A daily batch could give valuation analysts estimated mileage, the age of the last reading and uncertainty. Defleet planners could use future mileage and a separate mileage limit alert. Exceeding a contract or planning limit is a business alert, not automatically a data error. A review team should inspect the largest discrepancies with context, then confirm or reject them. Start in shadow mode and measure review workload and decision quality. We have not measured financial savings, and no monetary benefit is asserted without a SIXT study.

## What remains uncertain or unfinished

Several limitations remain. Retiming all On Rent values is a working interpretation, not a proven rule for every vehicle. Return source targets can be stale or wrong, and return days differ from arbitrary valuation days. Rolling nowcasts are one day ahead evaluation proxies, not direct observation of hidden daily mileage. Long term groups are small. Cold start fallbacks require separate validation. Calibrated ranges can shift over time, and flags need expert labels. A future pilot should confirm source semantics, obtain fresh long term readings, and monitor errors and coverage over time.

## How the deliverables match the rubric

The official rubric allocates fifteen points to understanding the problem, twenty five to approach, twenty five to results, fifteen to business relevance, and ten each to code and presentation. These are the jury's maximums, not a score we award ourselves. The repository contains the implementation, write up, aggregate evidence, five slide deck, short video and detailed walkthrough. Existing tracked organizer datasets still require publishing permission or exclusion, and repository rules require confirmation before a push. This complete walkthrough explains the work; the separate short cut respects the one minute video submission limit.
