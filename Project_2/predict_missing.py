"""Infer masked mileage without using later readings from the same vehicle.

Output stays in results/local/. Model recipe is fixed on development vehicles.
Fleet priors and interval calibration are refreshed at quarter starts using only
development records available then. A deterministic development cohort bounds
runtime; test vehicles contribute only their own already-recorded history.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import mileage as M


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--development', default='data/data_30_percent_sample.parquet')
    ap.add_argument('--input', default='data/test_data.parquet')
    ap.add_argument('--metrics', default='results/metrics.json')
    ap.add_argument('--prior-vehicles', type=int, default=1000)
    ap.add_argument('--out', type=Path, default=Path('results/local/test_predictions.csv'))
    ap.add_argument('--completed-output', type=Path, default=Path('results/local/test_completed.parquet'))
    a = ap.parse_args()
    started = time.perf_counter()
    recipes = json.loads(Path(a.metrics).read_text())['selected']
    recipes.setdefault('forecast', recipes['nowcast'])
    development, _, _ = M.load_fleet(a.development, a.prior_vehicles)
    fleet, n_rows, _ = M.load_fleet(a.input)
    if set(development) & set(fleet):
        raise ValueError('Development and inference vehicles overlap; refuse possible target leakage.')
    con = duckdb.connect(config={'threads': 1})
    con.read_parquet(a.input).create_view('input_rows')
    targets = con.execute('''SELECT input_row, vhcl_anon_id, vhcl_fct_taken_datm, vehicle_level, model_year FROM
        (SELECT row_number() OVER () - 1 AS input_row, * FROM input_rows)
        WHERE vhcl_current_mileage IS NULL ORDER BY vhcl_fct_taken_datm, vhcl_anon_id, input_row''').fetchall()
    con.close()
    snapshots = {}
    cold_snapshots = {}
    con = duckdb.connect()
    con.read_parquet(a.development).create_view('development_rows')
    years = dict(con.execute('SELECT vhcl_anon_id, max(model_year) FROM development_rows GROUP BY 1').fetchall())
    con.close()
    counts = {'input': Path(a.input).name, 'input_rows': n_rows, 'masked_targets': len(targets),
              'predicted': 0, 'without_past_reading': 0, 'with_interval': 0,
              'fleet_prior_predictions': 0, 'unsupported': 0,
              'recipes': recipes, 'prior_vehicles': len(development), 'nowcast_targets': 0, 'forecast_targets': 0,
              'snapshot_policy': 'quarter-start before prediction origin, past rows only'}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['input_row', 'vhcl_anon_id', 'asof', 'target_date', 'task', 'model',
                                'last_reading_date', 'gap_days', 'predicted_mileage', 'low_km', 'high_km', 'status'])
        writer.writeheader()
        for index, vid, timestamp, level, year in targets:
            target = M._day(str(timestamp))
            d = date.fromordinal(target)
            v = fleet.get(vid)
            origin = min(target, v.latest_recorded_day or target) if v is not None else target
            task = 'forecast' if origin < target else 'nowcast'
            recipe = recipes[task]
            seen = v.view(origin) if v is not None else None
            n = seen.known_before(origin + 1) if seen is not None else 0
            row = {'input_row': index, 'vhcl_anon_id': vid, 'asof': date.fromordinal(origin).isoformat(),
                   'target_date': d.isoformat(), 'task': task, 'model': recipe,
                   'status': 'insufficient_history'}
            if n:
                origin_date = date.fromordinal(origin)
                quarter = date(origin_date.year, ((origin_date.month - 1) // 3) * 3 + 1, 1).toordinal() - 1
                key = (task, quarter, recipe)
                if key not in snapshots:
                    ids = set(development)
                    cls = M.MODEL_BY_NAME[recipe]
                    model = cls().fit(development, ids, quarter)
                    cal_cut = quarter - 90
                    cal = cls().fit(development, ids, cal_cut)
                    qs = M.interval_q(M.predictions(development, ids, cal_cut, task, [cal], upto=quarter), recipe)
                    snapshots[key] = (model, qs)
                    print(f'{task} snapshot {date.fromordinal(quarter)}; calibration: {bool(qs)}', flush=True)
                model, qs = snapshots[key]
                pred = model.predict(seen, origin, target, nowcast=task == 'nowcast')
                gap = target - seen.obs_day[n - 1]
                q = M.q_for(qs, gap)
                half = q * math.sqrt(max(gap, 1)) if q is not None else None
                row.update(last_reading_date=date.fromordinal(seen.obs_day[n - 1]).isoformat(),
                           gap_days=gap, predicted_mileage=round(pred, 0),
                           low_km=round(max(0, pred - half), 0) if half is not None else '',
                           high_km=round(pred + half, 0) if half is not None else '',
                           status='estimated' if half is not None else 'insufficient_calibration')
                counts['predicted'] += 1
                counts[task + '_targets'] += 1
                counts['with_interval'] += half is not None
            else:
                counts['without_past_reading'] += 1
                # No anchor is available for a new vehicle. Use an explicitly
                # labelled cohort-median fallback, never pretend it is a
                # vehicle-specific or conformally calibrated estimate.
                quarter = date(d.year, ((d.month - 1) // 3) * 3 + 1, 1).toordinal() - 1
                if quarter not in cold_snapshots:
                    entries = []
                    for dev_id, vehicle in development.items():
                        prefix = vehicle.view(quarter)
                        n_dev = prefix.known_before(quarter + 1)
                        if not n_dev:
                            continue
                        base = M.MeanRate().predict(prefix, quarter, quarter, nowcast=False)
                        following = M.MeanRate().predict(prefix, quarter, quarter + 1, nowcast=False)
                        entries.append((prefix.level, years.get(dev_id), base, following - base))
                    cold_snapshots[quarter] = entries
                entries = cold_snapshots[quarter]
                group = [e for e in entries if e[0] == level and e[1] == year]
                if len(group) < 10:
                    group = [e for e in entries if e[1] == year]
                if len(group) < 10:
                    group = [e for e in entries if e[0] == level]
                if len(group) < 10:
                    group = entries
                if group:
                    estimate = float(np.median([e[2] + e[3] * (target - quarter) for e in group]))
                    row.update(predicted_mileage=round(max(estimate, 0), 0), model='cohort_median_calendar',
                               status='fleet_prior_only_requires_review')
                    counts['predicted'] += 1
                    counts['fleet_prior_predictions'] += 1
                else:
                    counts['unsupported'] += 1
            writer.writerow(row)
    # Preserve original rows and columns. Do not invent errors without truth.
    con = duckdb.connect(config={'threads': 1})
    con.read_parquet(a.input).create_view('original')
    con.read_csv(str(a.out), header=True).create_view('predictions')
    columns = [r[0] for r in con.execute('DESCRIBE original').fetchall()]
    expressions = []
    for column in columns:
        quoted = '"' + column.replace('"', '""') + '"'
        if column == 'sixt_predicted_mileage_interp':
            expressions.append(f'coalesce(o.{quoted}, try_cast(p.predicted_mileage AS DOUBLE)) AS {quoted}')
        else:
            expressions.append('o.' + quoted)
    query = (f"SELECT {', '.join(expressions)} FROM "
             '(SELECT row_number() OVER ()-1 AS input_row, * FROM original) o '
             'LEFT JOIN predictions p ON o.input_row = p.input_row ORDER BY o.input_row')
    a.completed_output.parent.mkdir(parents=True, exist_ok=True)
    con.sql(query).write_parquet(str(a.completed_output))
    con.read_parquet(str(a.completed_output)).create_view('completed')
    counts['completed_rows'], counts['completed_prediction_values'] = con.execute(
        'SELECT count(*), count(sixt_predicted_mileage_interp) FROM completed').fetchone()
    if counts['completed_rows'] != n_rows or counts['completed_prediction_values'] != counts['predicted']:
        raise RuntimeError('Completed-table row/prediction count failed validation')
    con.close()
    counts['runtime_seconds'] = time.perf_counter() - started
    Path('results/test_inference_summary.json').write_text(json.dumps(counts, indent=2), encoding='utf-8')
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
