"""Complete-project chapters and a coverage checklist for the long video."""


def expand(original, metrics, benchmark, inference):
    m, b, inf = metrics, benchmark, inference
    selected = m['selected']
    nc = m['intervals']['nowcast'][selected['nowcast']]['all']
    fc = m['intervals']['forecast'][selected['forecast']]['all']
    additions = {}
    def after(key, *scenes):
        additions.setdefault(key, []).extend(scenes)

    after('data',
        dict(id='fields', title='Understand the input fields', subtitle='A row is a status update, not necessarily a new reading',
             points=['Vehicle ID, recorded timestamp and odometer value', 'Rental status, handover, return date and rental product',
                     'Vehicle category and planned utilisation', 'Maximum mileage is a limit, not an odometer reading'],
             narration="Each row is a vehicle status update. The anonymous vehicle identifier groups the history. The timestamp tells us when a row was recorded, while the mileage field contains the stored odometer. Rental status, handover, return date and rental product describe the rental context. Vehicle category and planned utilisation help estimate usage. The maximum mileage field is a business limit, not a substitute for an actual reading. Some descriptive fields are available in the source without being used by every model."),
        dict(id='quality', title='What data preparation actually does', subtitle='Validate, normalize and retain the limitations',
             points=['Read CSV or Parquet; group observations by vehicle', 'Remove duplicate readings and combine rental coverage',
                     'Reject missing or non-finite mileage values', 'Planned returns and stale readings require interpretation'],
             narration="The loader supports CSV and Parquet, validates required fields, groups observations by vehicle, removes duplicate readings, and combines rental coverage. Missing or non finite mileage values are not treated as real readings. The fleet audit found more than six hundred thousand rows with return dates later than their recorded timestamps, so a return field can be a plan. The stale handover pattern also has exceptions. These findings are documented as assumptions and validation questions, not hidden by the pipeline.")
    )
    after('timing',
        dict(id='formula', title='The prediction logic in plain language', subtitle='Start from a known reading, then estimate the missing distance',
             points=['Last-reading baseline: assume no additional distance', 'Average-rate baseline: historical kilometres per calendar day',
                     'Rental-aware: separate rented-day and idle-day rates', 'Future rental exposure uses the available plan and history'],
             narration="The simplest baseline keeps the last reading unchanged. The average rate baseline adds the vehicle's historical daily mileage multiplied by the gap. Our rental aware model estimates separate driving rates for rented days and idle days. It adds each rate multiplied by the corresponding number of days. Unknown days after the last recorded status use planned utilisation. For future dates, the model estimates remaining rental exposure from available rental history and then the utilisation plan. Recorded defleet status stops planning new rentals."),
        dict(id='variants', title='All six candidates, on the same targets', subtitle='Validation selected recent rental-aware nowcasts and blended forecasts',
             table=[['Model', 'Nowcast MAE km', 'Forecast MAE km']] +
                   [[name, f"{m['nowcast']['models'][name]['all']['MAE_km']:,.0f}",
                     f"{m['forecast']['models'][name]['all']['MAE_km']:,.0f}"] for name in m['nowcast']['models']],
             narration="Sparse vehicle histories borrow strength from broader product and vehicle category groups. The recent rental aware variant downweights older usage. The blend averages rental aware and average rate predictions. The robust candidate cleans already observed isolated typos and clips historical interval rates. All six candidates are measured on the same targets. Earlier validation selects recent rental aware for current mileage and the blend for forecasts. More complexity does not automatically win: the plain rental aware model is worse than average rate for forecast error, and the robust candidate does not win the selected tasks.")
    )
    after('method',
        dict(id='split', title='The exact evaluation protocol', subtitle='Separate vehicles, separate periods, separate decisions',
             points=[f"Training vehicles: {m['n_train_vehicles']:,} · held-out vehicles: {m['n_test_vehicles']:,}",
                     f"Training origin: {m['validation_cutoff']} · selection through {m['calibration_start']}",
                     f"Calibration through {m['cutoff']} · final test afterwards",
                     f"Test targets: {m['nowcast']['n']:,} nowcast / {m['forecast']['n']:,} forecast"],
             narration="The stable hash split reserves five thousand, five hundred and fifty nine vehicles for final testing and uses twenty two thousand, seventy one for training fleet priors. Initial training ends on March thirty first, twenty twenty five. Model selection uses later training vehicle targets through July twenty first. A separate subsequent period through November eleventh calibrates ranges. Final models fit at that cutoff and are evaluated afterwards on held out vehicles. Held out vehicles may supply their own earlier history, but their outcomes never train fleet priors. Suspicious test targets are retained rather than removed to improve the score."),
        dict(id='metrics', title='What the reported metrics mean', subtitle='Use several views of error, not a flattering percentage alone',
             points=['MAE: average absolute error in kilometres; primary selection metric',
                     'MAPE: percentage of odometer; sensitive to small or wrong values',
                     'WAPE: absolute error relative to distance since the last reading',
                     'Bias: signed over- or under-prediction; skill compares with last reading'],
             narration="Mean absolute error, or M A E, is the average absolute distance between the estimate and recorded target. It is our primary selection metric. M A P E expresses error as a percentage of the odometer, using a minimum denominator of one kilometre, so small or erroneous readings can dominate it. W A P E compares error with the distance driven since the last known reading. Bias shows whether estimates systematically overshoot or undershoot. Skill measures improvement over the last reading baseline. Nowcasts use a rolling origin one day before a return source target; forecasts use the fixed cutoff.")
    )
    after('metrics',
        dict(id='metrics_values', title='The selected models: more than one metric', subtitle='All values come from the held-out evaluation report',
             table=[['Task', 'MAE km', 'MAPE', 'Bias km']] +
                [[task, f"{m[task]['models'][selected[task]]['all']['MAE_km']:,.0f}",
                  f"{m[task]['models'][selected[task]]['all']['MAPE_odometer']:.2%}",
                  f"{m[task]['models'][selected[task]]['all']['bias_km']:+,.0f}"]
                 for task in ('nowcast', 'forecast')],
             points=['Selected nowcast WAPE: 0.74 · selected forecast WAPE: 0.37',
                     'Negative bias underestimates; positive bias overestimates'],
             narration="The selected current mileage model has an odometer percentage error of seven point two eight percent, compared with nine point five four percent for the last reading baseline. Its signed bias is about minus one hundred and forty four kilometres. The selected forecast has percentage error of seventeen point three one percent, compared with thirty eight point zero one percent for the last reading baseline, and bias of about plus one hundred and fourteen kilometres. Distance based weighted error is also reported. These complementary metrics help reveal systematic behaviour that a single average can hide.")
    )
    after('forecast',
        dict(id='ranges', title='How reliable are the prediction ranges?', subtitle='90% calibration target · measured coverage is not a guarantee',
             table=[['Task', 'Held-out coverage', 'Mean full width km'],
                    ['Current mileage', f"{nc['coverage']:.1%}", f"{nc['mean_width_km']:,.0f}"],
                    ['Future mileage', f"{fc['coverage']:.1%}", f"{fc['mean_width_km']:,.0f}"]],
             points=['Calibrate residual quantiles separately from model selection', 'Scale by stale-reading gap and use horizon buckets'],
             narration="The ranges are calibrated from earlier prediction errors, separately from choosing the model. Their width scales with the square root of the time since the last reading, with separate gap buckets where enough calibration examples exist. The target is ninety percent coverage. Measured current mileage coverage is ninety point seven percent, with mean full width of one thousand, six hundred and eleven kilometres. Forecast coverage is ninety five point six percent, with a much wider mean range. These are measured results, not guarantees under fleet shifts, temporal change, or dependent repeated readings.")
    )
    after('review',
        dict(id='rules', title='The detection rules and their safeguards', subtitle='Historical triage, not an online fraud verdict',
             points=['Isolated typo: compare with consistent neighbouring readings', 'Decrease: more than 10 km below an earlier maximum',
                     'Rate over 1,500 km/day; movement over 300 km without a rental', 'Fresh unchanged readings: rental days; residuals: robust z and km gap'],
             narration="An isolated spike or dip is identified between consistent neighbours and removed before the other rules run, so one typo does not create a cascade. A decrease is more than ten kilometres below an earlier maximum and is reported once per episode unless it drops further. An implausible rate exceeds fifteen hundred kilometres a day. Movement without a recorded rental exceeds three hundred kilometres. Unchanged fresh return readings are checked after at least three rental days. Residual outliers need a robust z score above eight and at least a thousand kilometres of disagreement. Some rules need later neighbours, so the queue is retrospective. Same day differences alone are not errors.")
    )
    long_now = m['nowcast']['by_segment']['product:LongTerm']['models'][selected['nowcast']]['all']
    long_future = m['forecast']['by_segment']['product:LongTerm']['models'][selected['forecast']]['all']
    after('results',
        dict(id='segments', title='Look beyond the overall average', subtitle='Long rentals and long gaps are the difficult cases',
             table=[['Group', 'Targets', 'Selected MAE km'],
                    ['LongTerm nowcast', str(long_now['n']), f"{long_now['MAE_km']:,.0f}"],
                    ['LongTerm forecast', str(long_future['n']), f"{long_future['MAE_km']:,.0f}"],
                    ['Nowcast gap over 60 days', '12', '5,049']],
             points=['Gap since last reading differs from forecast lead time', 'LongTerm evidence is much smaller than ShortTerm evidence'],
             narration="Overall averages can hide difficult cases. Long term current mileage error is five hundred and twenty seven kilometres on only one hundred and five targets. Long term forecast error is three thousand, seven hundred and ninety six on one hundred and forty targets. Current mileage error beyond a sixty day stale reading gap reaches five thousand and forty nine kilometres, on only twelve targets. Those small groups need caution. The report separates stale reading gap buckets from future lead time buckets. Historical mode of product is not a perfect current contract label, and this sample is dominated by short term rentals.")
    )
    after('flags',
        dict(id='benchmark_types', title='Detection recall by injected mistake', subtitle='Fixed seeds · earlier development rows · training vehicles only',
             table=[['Injected mistake', 'Detected / injected', 'Recall']] +
                  [[kind.replace('_', ' '), f"{b['caught'][kind]} / {b['injected'][kind]}",
                    f"{b['caught'][kind]/b['injected'][kind]:.1%}"]
                   for kind in ('extra_digit', 'missing_digit', 'transposed', 'rollback', 'stuck')],
             narration="The injected error benchmark uses fixed random seeds on a deterministic development cohort, restricted to training vehicles and rows recorded by February first, twenty twenty five. Detection catches every injected extra digit, about ninety seven percent of missing digits, ninety percent of transposed digits, ninety nine percent of rollback episodes, and seventy nine percent of stuck readings. Small digit changes can resemble ordinary driving. These controlled results test particular mistake types, not every real anomaly. Thresholds were not selected using final held out outcomes."),
        dict(id='workload', title='The review workload is part of the result', subtitle='Detection sensitivity alone is not enough',
             stats=[(f"{m['flags_per_1000_readings']:.2f}", 'flagged readings per 1,000'), (f"{b['flagged_untouched']:,}", 'untouched readings flagged'), (str(b['additional_untouched_flags']), 'additional untouched flags after injection')],
             points=['Untouched is not the same as confirmed correct', 'No real precision or false-positive rate is claimed'],
             narration="The full fleet scan flags eighty four point two two readings per thousand, so review workload matters. Across benchmark seeds, five thousand, nine hundred and sixty five untouched readings are flagged. They may contain existing errors, missing rental records, or stale data artifacts, so this is not a measured false positive rate. Comparing against the original flag set gives one hundred and twenty two additional untouched flags after injection. The local review file includes neighbouring readings and rental context. Human adjudication is still pending, and we do not claim real precision.")
    )
    after('workload',
        dict(id='rule_counts', title='What the full-fleet detector flagged', subtitle='Signals by rule · one reading can produce multiple signals',
             table=[['Rule', 'Signals']] +
                   [[rule.replace('_', ' '), f"{count:,}"] for rule, count in m['flags'].items()],
             narration="The aggregate report also breaks down the full fleet review workload by rule. Movement without a recorded rental and unchanged readings contribute many signals, and require care because operational records can be incomplete or stale. Isolated typos, implausible rates, decreases and residual disagreements contribute the remaining signals. A reading can trigger more than one rule, so the signal total is not a count of independently confirmed bad readings. The local context review helps analysts distinguish likely entry errors, unusual but plausible usage, and possible pipeline artifacts.")
    )
    after('inference',
        dict(id='exports', title='What is in the completed prediction output?', subtitle='Future dates require forecasts, not invented live rental information',
             points=['656,601 original rows and their original columns preserved',
                     'Masked dates: 2 July–11 November 2026; observed history ends 1 July',
                     'Past quarter-start priors from a bounded development cohort',
                     'Prediction column filled; error column unchanged without ground truth'],
             narration="The completed Parquet file preserves all six hundred and fifty six thousand, six hundred and one rows and the original columns. Observed history ends on July first, twenty twenty six; missing targets run from July second to November eleventh. Targets after a vehicle's latest recorded status use the forecast model from that status date. Fleet priors and calibration use earlier quarter start snapshots from a bounded thousand vehicle development cohort. Cold start fallbacks use category and model year where supported. They are not validated by the history based accuracy table, have no calibrated range, and require review. No masked target accuracy is claimed.")
    )
    after('delivery',
        dict(id='files', title='Where the implementation lives', subtitle='A reproducible pipeline, not only a dashboard',
             points=['mileage.py: timeline, models, evaluation, intervals and flags',
                     'run_baseline.py / profile_data.py: evaluation and aggregate audit',
                     'flag_benchmark.py / review_flags.py: detection evidence and context',
                     'predict_missing.py / test_mileage.py: exports and regression checks'],
             narration="The main implementation is mileage dot py. It contains timeline construction, prediction models, backtesting, uncertainty and flags. Run baseline is the evaluation entry point, and profile data produces aggregate checks. Flag benchmark injects known mistakes, while review flags creates contextual triage material. Predict missing writes inference outputs, and test mileage checks correctness and information boundaries. Synthetic fleet and synthetic evaluation scripts support method checks; their older archived results are not presented as current fleet performance. The interactive dashboard is generated from actual Python outputs on made up vehicles."),
        dict(id='commands', title='How to run and reproduce the project', subtitle='Run from Project_2 · Python 3.11+ · minimal model dependencies',
             commands=['python -m pip install -r requirements.txt',
                       'python -m unittest test_mileage -v',
                       'python run_baseline.py example_file.csv --out results/example',
                       'python run_baseline.py data/data_30_percent_sample.parquet',
                       'python predict_missing.py',
                       'python submission/build_demo.py'],
             narration="From the Project Two folder, create and activate a virtual environment, then install requirements. The model code needs numpy, and Duck D B reads Parquet. Run the unit tests and the public example before supplying organizer data explicitly. Run baseline evaluates the fleet and saves aggregate metrics; predict missing produces the completed inference table. Build demo creates the offline dashboard. Exact platform commands, flag benchmark options, date specific nowcast and forecast exports, and reproduction instructions are in the submission. The measured full pipeline batch took about eleven hundred seconds on this machine, not milliseconds per request."),
        dict(id='business', title='How an analyst would use the outputs', subtitle='A daily batch and a controlled review process',
             points=['Valuation: estimated mileage, reading age and uncertainty',
                     'Defleet planning: future mileage and separate limit alerts',
                     'Review queue: context, severity and human confirmation',
                     'Shadow mode first; measure decision quality and workload'],
             narration="A daily batch could give valuation analysts estimated mileage, the age of the last reading and uncertainty. Defleet planners could use future mileage and a separate mileage limit alert. Exceeding a contract or planning limit is a business alert, not automatically a data error. A review team should inspect the largest discrepancies with context, then confirm or reject them. Start in shadow mode and measure review workload and decision quality. We have not measured financial savings, and no monetary benefit is asserted without a SIXT study."),
        dict(id='limits', title='What remains uncertain or unfinished', subtitle='Honest limitations are part of a strong evaluation',
             points=['Confirm handover and actual-versus-planned return semantics',
                     'Recorded targets can be stale or wrong; arbitrary-day truth is missing',
                     'Validate long-term rentals, cold starts and shifted range coverage',
                     'Get expert flag labels before automated decisions'],
             narration="Several limitations remain. Retiming all On Rent values is a working interpretation, not a proven rule for every vehicle. Return source targets can be stale or wrong, and return days differ from arbitrary valuation days. Rolling nowcasts are one day ahead evaluation proxies, not direct observation of hidden daily mileage. Long term groups are small. Cold start fallbacks require separate validation. Calibrated ranges can shift over time, and flags need expert labels. A future pilot should confirm source semantics, obtain fresh long term readings, and monitor errors and coverage over time."),
        dict(id='rubric', title='How the deliverables match the rubric', subtitle='Evidence and reproducibility support the pitch',
             points=['Problem 15 · approach 25 · measured results 25',
                     'Business relevance 15 · code 10 · presentation 10',
                     'Code, write-up, aggregate evidence, slides and short video',
                     'Resolve tracked datasets and obtain approval before publication'],
             narration="The official rubric allocates fifteen points to understanding the problem, twenty five to approach, twenty five to results, fifteen to business relevance, and ten each to code and presentation. These are the jury's maximums, not a score we award ourselves. The repository contains the implementation, write up, aggregate evidence, five slide deck, short video and detailed walkthrough. Existing tracked organizer datasets still require publishing permission or exclusion, and repository rules require confirmation before a push. This complete walkthrough explains the work; the separate short cut respects the one minute video submission limit.")
    )
    expanded = []
    def visit(scene):
        expanded.append(scene)
        for added in additions.get(scene['id'], []):
            visit(added)
    for scene in original:
        visit(scene)
    return expanded
