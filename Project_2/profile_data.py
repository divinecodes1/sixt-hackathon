"""Aggregate development-data checks. Never reads test_data.parquet or prints vehicle ids."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def profile(path: Path) -> dict:
    if 'test' in path.stem.lower():
        raise ValueError('Reserved test data: use the development sample for investigation.')
    con = duckdb.connect()
    con.read_parquet(str(path)).create_view('d')
    # Only aggregate results leave this process.
    schema = con.execute('DESCRIBE d').fetchall()
    columns = [r[0] for r in schema]
    out = {'input': path.name, 'rows': con.execute('SELECT count(*) FROM d').fetchone()[0], 'columns': columns,
           'dtypes': {r[0]: r[1] for r in schema},
           'missing': {c: con.execute(f'SELECT count(*) FROM d WHERE "{c}" IS NULL').fetchone()[0] for c in columns}}
    if 'vhcl_anon_id' in columns:
        out['vehicles'] = con.execute('SELECT count(DISTINCT vhcl_anon_id) FROM d').fetchone()[0]
    for c in ('on_rent_status', 'rental_product', 'vehicle_level', 'status_code_anonymized'):
        if c in columns:
            out[c] = {str(k): int(v) for k, v in con.execute(f'SELECT "{c}", count(*) FROM d GROUP BY 1').fetchall()}
    for c in ('vhcl_fct_taken_datm', 'rntl_handover_date', 'rntl_return_date'):
        if c in columns:
            lo, hi = con.execute(f'SELECT min("{c}"), max("{c}") FROM d').fetchone()
            out[c] = {'min': str(lo), 'max': str(hi)}
    for c in ('vhcl_current_mileage', 'uti_plan'):
        if c in columns:
            lo, mid, hi, neg = con.execute(f'SELECT min("{c}"), median("{c}"), max("{c}"), count(*) FILTER(WHERE "{c}"<0) FROM d').fetchone()
            out[c] = {'min': lo, 'median': mid, 'max': hi, 'negative': neg}
    out['same_day_pairs'] = dict(zip(('pairs', 'onrent_lower', 'equal', 'onrent_higher'), con.execute('''
        WITH x AS (SELECT vhcl_anon_id, substr(vhcl_fct_taken_datm,1,10) AS day,
          max(vhcl_current_mileage) FILTER(WHERE on_rent_status='OnRent') AS rented,
          max(vhcl_current_mileage) FILTER(WHERE on_rent_status='NotOnRent') AS returned
          FROM d GROUP BY 1,2)
        SELECT count(*), count(*) FILTER(WHERE rented<returned), count(*) FILTER(WHERE rented=returned),
          count(*) FILTER(WHERE rented>returned) FROM x WHERE rented IS NOT NULL AND returned IS NOT NULL
        ''').fetchone()))
    out['date_checks'] = dict(zip(('handover_after_recorded', 'return_before_handover', 'return_after_recorded'),
        con.execute('''SELECT
        count(*) FILTER(WHERE rntl_handover_date > substr(vhcl_fct_taken_datm,1,10)),
        count(*) FILTER(WHERE rntl_return_date < rntl_handover_date),
        count(*) FILTER(WHERE rntl_return_date > substr(vhcl_fct_taken_datm,1,10)) FROM d''').fetchone()))
    con.close()
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('--out', type=Path, default=Path('results/data_profile.json'))
    a = ap.parse_args()
    result = profile(a.input)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
