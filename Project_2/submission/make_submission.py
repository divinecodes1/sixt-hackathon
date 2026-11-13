"""Build the write-up, EDA and five-slide deck from measured aggregate JSON.

Run from Project_2: python submission/make_submission.py
Then print slides.html with headless Chrome (commands in SUBMISSION.md).
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'submission'


def read(name):
    return json.loads((ROOT / 'results' / name).read_text(encoding='utf-8'))


def chart(metrics, task):
    selected = metrics['selected'][task]
    names = list(dict.fromkeys(['naive_last', 'mean_rate', selected]))
    values = [metrics[task]['models'][n]['all']['MAE_km'] for n in names]
    maximum = max(values)
    bars = []
    for i, (name, value) in enumerate(zip(names, values)):
        y = 32 + 75 * i
        w = 420 * value / maximum
        color = '#ff5f00' if name == selected else '#85909d'
        bars.append(f'<text x="0" y="{y+15}" font-size="17">{name}</text>'
                    f'<rect x="195" y="{y}" width="{w:.1f}" height="28" rx="4" fill="{color}"/>'
                    f'<text x="{205+w:.1f}" y="{y+21}" font-size="20" font-weight="bold">{value:,.0f}</text>')
    return '<svg viewBox="0 0 740 280" role="img" aria-label="MAE in kilometres, lower is better">' + ''.join(bars) + '</svg>'


def build():
    m, p, b = read('metrics.json'), read('data_profile.json'), read('flag_benchmark.json')
    if m['n_vehicles'] < 10 or m['input'] != 'data_30_percent_sample.parquet':
        raise ValueError('Final full-sample metrics are required; refuse to publish example results as fleet evidence.')
    selected = m['selected']
    now = m['nowcast']['models'][selected['nowcast']]['all']
    forecast = m['forecast']['models'][selected['forecast']]['all']
    total, caught = sum(b['injected'].values()), sum(b['caught'].values())
    exact = sum(b['exact_caught'].values())
    recall = caught / total
    pair = p['same_day_pairs']
    rows = []
    for name in m['nowcast']['models']:
        n = m['nowcast']['models'][name]['all']
        f = m['forecast']['models'][name]['all']
        use = ', '.join(task for task in ('nowcast', 'forecast') if selected[task] == name) or 'candidate / baseline'
        rows.append(f"| {name} | {n['MAE_km']:,.0f} | {n['MAPE_odometer']:.2%} | {f['MAE_km']:,.0f} | {f['MAPE_odometer']:.2%} | {use} |")
    model_table = '\n'.join(rows)
    interval_rows = []
    for task in ('nowcast', 'forecast'):
        coverage = m['intervals'][task][selected[task]].get('all', {})
        interval_rows.append(f"| {task} | {coverage.get('coverage', 0):.1%} | {coverage.get('mean_width_km', 0):,.0f} |")
    flag_rows = '\n'.join(f"| {kind} | {b['injected'].get(kind,0)} | {b['caught'].get(kind,0)} | "
                          f"{b['caught'].get(kind,0)/max(b['injected'].get(kind,0),1):.1%} |" for kind in b['injected'])
    segments = []
    for task in ('nowcast', 'forecast'):
        for key, result in m[task].get('by_segment', {}).items():
            if not key.startswith('product:'):
                continue
            s = result['models'][selected[task]].get('all')
            if s:
                segments.append(f"| {task} | {key.removeprefix('product:')} | {s['n']:,} | {s['MAE_km']:,.0f} |")
    inference_path = ROOT / 'results/test_inference_summary.json'
    if inference_path.exists():
        inf = read('test_inference_summary.json')
        inference = (f"Masked-file inference: {inf['predicted']:,} of {inf['masked_targets']:,} missing-mileage rows received "
                     f"an estimate; {inf['without_past_reading']:,} had no own past reading, of which "
                     f"{inf.get('fleet_prior_predictions', 0):,} receive an explicitly flagged cohort-median fallback. "
                     f"{inf.get('unsupported', 0):,} remain unsupported. "
                     f"{inf['with_interval']:,} estimates have a calibrated range. Detailed output: "
                     "`results/local/test_predictions.csv` and `results/local/test_completed.parquet` (not public). "
                     "The completed table preserves the original columns and fills `sixt_predicted_mileage_interp`; "
                     "`sixt_error` remains unchanged. There are no ground-truth labels for these masked rows; no test accuracy is claimed.")
    else:
        inference = ('`predict_missing.py` exports estimates for the missing-mileage rows in `test_data.parquet`. '
                     'Its detailed output stays in `results/local/`. No accuracy is claimed on missing ground truth.')
    submission = f'''# Submission: Project 2 — Divinecodes

## Authors
**Team:** Divinecodes. **Project:** Project 2, Mileage Forecasting & Erroneous Mileage Detection.

## Problem and approach
SIXT needs current mileage for valuation and future mileage for defleet planning while rental readings are delayed.
We deliver nowcasts, forecasts, measured prediction ranges, a retrospective review queue, and masked-file inference.

The key engineering insight is that **measurement time and information-availability time differ**. OnRent mileage
often belongs to handover; the row may arrive later. We retime the reading but never make its mileage, rental metadata,
product or vehicle category available before the row was recorded. Future-field mutation tests guard this boundary.
After the last recorded status, a missing rental row is not evidence of idleness: the utilisation plan fills that gap.
An OnRent row is not necessarily a completed rental: {p['date_checks']['return_after_recorded']:,} rows have a return date later than their recorded date.

## Models and why
All models run locally: numpy plus DuckDB for Parquet. No API, credentials or paid inference.
`naive_last` holds mileage constant; `mean_rate` extrapolates calendar-day usage. Rental-aware models separately fit
nonnegative rented/idle rates, shrink sparse histories toward product/category priors, calibrate utilisation, and stop
planning new rentals after recorded defleet. The recent variant downweights old usage. `blend` averages mean-rate
and rental-aware predictions. `robust_rate` cleans already-observed isolated typos and clips historical interval rates.

| Model (own statistical code; no external weights) | Nowcast MAE km | Nowcast MAPE | Forecast MAE km | Forecast MAPE | Validation choice |
|---|---:|---:|---:|---:|---|
{model_table}

Measured total pipeline runtime: {m['runtime_seconds']:,.1f} seconds on this machine, including reading, evaluation and flags.
This is a batch measurement, not a per-request latency benchmark or an infrastructure-cost estimate.

## Results and evaluation protocol
Input: **{m['input_rows']:,} rows, {m['n_vehicles']:,} vehicles**, {m['distinct_readings']:,} distinct retimed readings.
Train/test vehicle split by stable hash: **{m['n_train_vehicles']:,}/{m['n_test_vehicles']:,}**.
Held-out vehicles supply their own earlier history, as they would in deployment; they never train fleet priors.

- Models train at {m['validation_cutoff']}; model choice uses subsequent training-vehicle targets through {m['calibration_start']}.
- Separate later targets through {m['cutoff']} calibrate ranges. This avoids reusing selection outcomes for calibration.
- Final models fit at {m['cutoff']}; test targets are later readings on held-out vehicles.
- Nowcast: rolling origin one day before each fresh recorded return-source target. Forecast: fixed origin at the test cutoff.
- Final model choice is **{selected['nowcast']}** for nowcast and **{selected['forecast']}** for forecast, using validation MAE only.
- Test targets: **{m['nowcast']['n']:,} nowcast / {m['forecast']['n']:,} forecast**. No target is removed because our detector dislikes it.

Against the last-reading baseline, the selected nowcast reduces MAE by **{now['skill_vs_naive']:.1%}**;
the selected forecast by **{forecast['skill_vs_naive']:.1%}**. The full table includes the stronger mean-rate baseline.
MAE is primary. MAPE divides by max(recorded odometer, 1 km), so zero/near-zero and erroneous targets can dominate it.
WAPE of distance since the last reading, bias and errors by gap are in `results/metrics.json`.
Forecast lead-time buckets are separately reported under `by_segment/lead_time:*`; these differ from stale-reading gap buckets.

| Task | Measured range coverage (90% target) | Mean full range width km |
|---|---:|---:|
{chr(10).join(interval_rows)}

| Task | Rental product known at origin | Targets | Selected MAE km |
|---|---|---:|---:|
{chr(10).join(segments)}

### Suspicious-reading evidence
Flags cover isolated spikes/dips, persistent decreases, implausible rates, movement without a recorded rental,
unchanged fresh readings despite rental days, and robust residual outliers. Scores are estimated discrepant kilometres.
A same-day difference alone is deliberately insufficient: multiple legitimate rentals can happen in a day.
Total flagged readings: **{m['flags_per_1000_readings']:.2f} per 1,000**. Per-rule counts are in the metrics file.

Injected-error benchmark: deterministic development cohort, training vehicles only, rows recorded by {b['before']},
{b['seeds']} fixed seeds. Thresholds were not tuned on final held-out outcomes.

| Injected error | Injected | Detected | Recall |
|---|---:|---:|---:|
{flag_rows}

Overall episode recall: **{caught}/{total} ({recall:.1%})**. Exact corrupted-reading recall: **{exact}/{total} ({exact/total:.1%})**.
Episode recall gives a rollback credit if its first lowered reading or its immediately preceding reading is flagged.
Untouched readings flagged: **{b['flagged_untouched']:,}/{b['untouched']:,}**; these can include existing errors or stale-data artifacts,
so this is **not measured false-positive rate or precision**. Additional untouched flags beyond the original flag set:
**{b['additional_untouched_flags']:,}**. The benchmark also records recall among originally unflagged injected readings.

`results/local/flag_review.md` gives local reading/rental context for top flags. Human domain adjudication remains pending;
no confirmed-fraud or precision claim is made. Public examples in the slides are conceptual, not copied vehicle records.

### Masked inference
{inference}
The two supplied vehicle sets do not overlap (metadata check). Their prediction/error columns are empty;
we do not use them as features or invent errors where the ground truth is missing.
Targets later than a vehicle's last recorded status use the forecast recipe and an origin at that status;
they are not treated as observed current-rental snapshots. Quarter-start development snapshots precede that origin.
Cold-start cohort medians use vehicle category/model year where sufficient development examples exist.
They are explicitly marked for review, have no calibrated range, and are not validated by the vehicle-history MAE above.

### Limits and what did not work
- Retiming all OnRent values is a working schema interpretation, not a fleet-wide proven fact. Of {pair['pairs']:,} same-day
  paired vehicle-days, {pair['onrent_lower']:,} have lower OnRent mileage, {pair['equal']:,} are equal and {pair['onrent_higher']:,} are higher.
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
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m unittest test_mileage -v
.\\.venv\\Scripts\\python.exe run_baseline.py example_file.csv --out results/example
# Organizer files must be provided locally; they are not needed for the public example.
.\\.venv\\Scripts\\python.exe profile_data.py data/data_30_percent_sample.parquet
.\\.venv\\Scripts\\python.exe run_baseline.py data/data_30_percent_sample.parquet --out results
.\\.venv\\Scripts\\python.exe flag_benchmark.py data/data_30_percent_sample.parquet --max-vehicles 1000 --training-only --before 2025-02-01 --rate 0.02 --seeds 3 --out results/flag_benchmark.json
.\\.venv\\Scripts\\python.exe predict_missing.py
.\\.venv\\Scripts\\python.exe submission/make_submission.py
```

Linux/macOS: replace `.\\.venv\\Scripts\\python.exe` with `.venv/bin/python`, or use `bash setup.sh` for the public example.
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
Narrated videos: `submission/demo.mp4` is the one-minute submission cut;
`submission/walkthrough.mp4` is the detailed explanation. Both include captions and synthesized English narration.
Measured video duration, size and decode checks are in `submission/video_report.json`.
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
'''
    (ROOT / 'SUBMISSION.md').write_text(submission, encoding='utf-8')
    eda = f'''# Project 2: measured data investigation

Source: `results/data_profile.json`, `results/metrics.json`, `results/flag_benchmark.json`.

## Data and missingness
The development sample contains {p['rows']:,} rows and {p['vehicles']:,} vehicles, from
{p['vhcl_fct_taken_datm']['min']} to {p['vhcl_fct_taken_datm']['max']}.
Mileage ranges from {p['vhcl_current_mileage']['min']:,} to {p['vhcl_current_mileage']['max']:,} km.
`uti_plan` is missing in {p['missing']['uti_plan']:,} rows; recorded values lie within [0,1].
`sixt_predicted_mileage_interp` and `sixt_error` are entirely empty, and excluded from model features.

## Measurement time versus availability
The original public example has stale handover odometers on OnRent rows. The larger sample is less uniform:
among {pair['pairs']:,} same-day vehicle/status pairs, {pair['onrent_lower']:,} OnRent maxima are lower,
{pair['equal']:,} equal and {pair['onrent_higher']:,} higher than the NotOnRent maxima.
This supports investigating stale values, but does not prove every OnRent odometer belongs to handover.
Multiple rentals in a day and day-level timestamps also make same-day differences ambiguous.

{p['date_checks']['return_after_recorded']:,} rows have a return date later than the row timestamp;
{p['date_checks']['handover_after_recorded']:,} have handover after the row timestamp.
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
The detector flags {m['flags_per_1000_readings']:.2f} readings per 1,000 after retiming. The raw starter rules produce
{m['starter_flags_on_raw_rows']:,} flags; unlike the tiny example, they cannot all be called artifacts.
Top contexts are in ignored results/local/flag_review.md. Isolated spikes/dips include plausible digit mistakes;
long unchanged series and movement without rentals remain ambiguous. Human adjudication is pending.
Injected episode recall is {recall:.1%}; exact corrupted-reading recall is {exact/total:.1%}.
There are {b['additional_untouched_flags']:,} additional untouched flags beyond existing flags across the benchmark seeds.
Neither untouched-flag rate nor model disagreement establishes real precision.

## Supplied masked file
Metadata inspection found missing mileage and empty output columns in test_data.parquet; no target outcomes
were used for tuning. predict_missing.py uses only past readings from those vehicles and past development priors.
See results/test_schema.json and, after inference, results/test_inference_summary.json.

## Remaining external validation
Confirm OnRent measurement semantics, actual/planned return dates, and public-data permission with the project owners.
Obtain expert labels and direct long-term/current-mileage ground truth before any production claim.
'''
    (ROOT / 'EDA.md').write_text(eda, encoding='utf-8')
    style = '''@page{size:13.333in 7.5in;margin:0}*{box-sizing:border-box}body{margin:0;font-family:Arial,Helvetica,sans-serif;color:#14202c;background:#e9edf2}section{width:13.333in;height:7.5in;padding:.48in .65in;background:#fff;break-after:page;page-break-after:always;overflow:hidden;position:relative}section:last-child{break-after:auto}h1{font-size:32pt;line-height:1.12;margin:0 0 .22in;letter-spacing:-1px}h2{font-size:21pt;margin:.16in 0}p,li{font-size:18pt;line-height:1.35}p{margin:.12in 0}.accent{color:#e95400}.eyebrow{font-size:12pt;font-weight:bold;letter-spacing:2px;color:#b84b00;margin-bottom:.18in}.small{font-size:12pt;line-height:1.35;color:#526070}.grid{display:grid;grid-template-columns:1fr 1fr;gap:.3in}.card{background:#f1f4f7;padding:.22in;border-radius:12px}.big{font-size:40pt;font-weight:bold;line-height:1.1}footer{position:absolute;bottom:.22in;left:.65in;font-size:10pt;color:#526070}.step{padding:.18in;border-left:5px solid #ff5f00;margin:.14in 0;background:#f1f4f7}.step b{font-size:20pt}.step p{font-size:16pt}svg{width:100%;max-height:2.35in}table{width:100%;border-collapse:collapse;font-size:16pt}td,th{padding:10px;border-bottom:1px solid #d7dde4;text-align:left}.preview section{display:none}.preview section.show{display:block}@media print{body{background:#fff}.preview section{display:block}}'''
    slides = [
        f'''<div class="eyebrow">DIVINECODES / PROJECT 2</div><h1>Where is that car's odometer<br><span class="accent">right now?</span></h1><p>Delayed readings make valuation and defleet decisions uncertain.</p><div class="grid"><div class="card"><div class="big">{m['n_vehicles']:,}</div><p>development vehicles</p><div class="small">{m['input_rows']:,} supplied status rows</div></div><div class="card"><h2>One operational workflow</h2><p>Estimate today.<br>Forecast the next decision.<br>Review suspicious reports.</p></div></div><footer>Divinecodes · Project 2 · github.com/divinecodes1/sixt-hackathon · 1 / 5</footer>''',
        f'''<div class="eyebrow">THE INSIGHT</div><h1>A timestamp is not always<br><span class="accent">a fresh odometer reading.</span></h1><div class="step"><b>Two clocks, one reading</b><p>Measurement date: when the mileage belongs.<br>Availability date: when a prediction may first use it.</p></div><p>Retiming stale handover values helps, but future-recorded rental rows must stay hidden.</p><div class="card"><p><b>{pair['onrent_lower']:,}</b> paired vehicle-days have lower OnRent mileage.<br><b>{pair['onrent_higher']:,}</b> have higher mileage: the pattern needs qualification.</p><div class="small">Aggregate fleet evidence; no individual vehicle records shown.</div></div><footer>Source: results/data_profile.json · 2 / 5</footer>''',
        f'''<div class="eyebrow">THE METHOD</div><h1>Predict with the information<br><span class="accent">available at the time.</span></h1><div class="step"><b>1 · Establish the timeline</b><p>Retimed readings + recorded availability for mileage, rentals and category.</p></div><div class="step"><b>2 · Compare simple and rental-aware models</b><p>Choose on validation; calibrate ranges on a separate later period.</p></div><div class="step"><b>3 · Deliver an estimate and a review queue</b><p>Per-vehicle output, age of last reading, uncertainty and explainable flags.</p></div><p class="small">Stable vehicle holdout + later periods. No LLM or paid inference. Future-field mutation tests protect the boundary.</p><footer>Measured choices: {selected['nowcast']} / {selected['forecast']} · 3 / 5</footer>''',
        f'''<div class="eyebrow">HELD-OUT RESULTS · MAE KM · LOWER IS BETTER</div><h1>Measured against <span class="accent">two baselines.</span></h1><div class="grid"><div><h2>Nowcast · {m['nowcast']['n']:,} targets</h2>{chart(m,'nowcast')}</div><div><h2>Forecast · {m['forecast']['n']:,} targets</h2>{chart(m,'forecast')}</div></div><div class="card"><p><b>{now['skill_vs_naive']:.1%}</b> lower nowcast MAE vs last reading · <b>{forecast['skill_vs_naive']:.1%}</b> lower forecast MAE</p><div class="small">Validation-selected models shown in orange. Error-injection episode recall: {recall:.1%}; exact-reading recall: {exact/total:.1%}. Real flag precision is not yet known. Recorded target mileage may itself contain errors.</div></div><footer>Source: results/metrics.json and results/flag_benchmark.json · 4 / 5</footer>''',
        '''<div class="eyebrow">HOW SIXT COULD USE IT</div><h1>A daily decision aid,<br><span class="accent">with explicit uncertainty.</span></h1><div class="grid"><div class="card"><h2>Valuation &amp; defleet</h2><p>Current and future mileage.<br>Reading age and prediction range.<br>Separate mileage-limit alerts.</p></div><div class="card"><h2>Review operations</h2><p>Largest discrepancies first.<br>Context before accusation.<br>Human confirmation before action.</p></div></div><p><b>Next:</b> confirm status semantics, label real flags, and validate long-term rentals and range coverage in shadow mode.</p><p class="small">Runnable local demo uses made-up vehicles. No proven fraud, monetary savings, production readiness or hidden-test accuracy is claimed.</p><footer>Code + aggregate evidence + reproducible five-slide deck · 5 / 5</footer>'''
    ]
    document = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Divinecodes · Project 2</title><style>' + style + '</style><body>'
    document += ''.join('<section>' + s + '</section>' for s in slides)
    document += '''<script>const n=Number(location.hash.slice(1));if(n){document.body.classList.add('preview');document.querySelectorAll('section')[n-1]?.classList.add('show');}</script></body></html>'''
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'slides.html').write_text(document, encoding='utf-8')
    files = ['mileage.py', 'run_baseline.py', 'predict_missing.py', 'flag_benchmark.py', 'test_mileage.py',
             'results/metrics.json', 'results/flag_benchmark.json', 'results/data_profile.json']
    provenance = {'source_and_evidence_sha256': {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
        'dependencies': {name: importlib.metadata.version(name) for name in ('numpy', 'duckdb')},
        'evaluation_input': m['input'], 'test_outcomes_used_for_tuning': False}
    (ROOT / 'results/provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    print('Built SUBMISSION.md, EDA.md and submission/slides.html from measured aggregates.')


if __name__ == '__main__':
    build()
