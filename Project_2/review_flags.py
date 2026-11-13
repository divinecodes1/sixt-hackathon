"""Write a LOCAL review queue with context; publish aggregate counts only.

This is a triage aid, not a domain-expert adjudication. Same-day differences alone
are not errors: multiple rentals/returns can legitimately occur on one day.
"""
import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

import mileage as M


def write_review(fleet, flags, directory):
    directory.mkdir(parents=True, exist_ok=True)
    lines = ['# LOCAL flag review: automated context, human confirmation required', '',
             'Do not publish this file. Findings are provisional; no case is confirmed fraud.', '',
             '| Rule | Vehicle | Reading | Previous / next | Rental days since previous | Assessment |',
             '|---|---|---|---|---:|---|']
    counts = Counter()
    for f in sorted(flags, key=lambda f: -f['score']):
        if counts[f['rule']] >= 5:
            continue
        counts[f['rule']] += 1
        v = fleet[f['vhcl_anon_id']]
        d = M._day(f['date'])
        idx = next((i for i, (day, km) in enumerate(zip(v.obs_day, v.obs_km)) if day == d and km == f['km']), 0)
        context = []
        for i in (idx - 1, idx + 1):
            if 0 <= i < len(v.obs_day):
                context.append(f'{date.fromordinal(v.obs_day[i])}: {v.obs_km[i]:.0f} km ({v.obs_src[i]})')
        rd = M.rental_days(v, v.obs_day[max(0, idx - 1)], d)
        assessment = {
            'isolated_outlier': 'Candidate entry error; verify handover timing and neighbouring records',
            'decrease': 'Candidate rollback or delayed/corrected report; verify measurement date',
            'implausible_rate': 'Candidate jump; check units, transfers and timestamp granularity',
            'residual_outlier': 'Unusual usage or entry error; model disagreement alone is insufficient',
            'moved_without_rental': 'Could be a transfer or missing rental; operational review',
            'no_movement_on_rent': 'Could be copied value or stale status; verify a new reading was taken'
        }[f['rule']]
        lines.append(f"| {f['rule']} | {v.vid[:8]} | {f['date']}: {f['km']:.0f} km | {' / '.join(context)} | {rd:.0f} | {assessment} |")
    (directory / 'flag_review.md').write_text('\n'.join(lines), encoding='utf-8')
    return {'reviewed_automatically': dict(counts), 'human_confirmed': 0,
            'note': 'Automated context only; domain-expert review pending. No precision claim.'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input')
    ap.add_argument('--max-vehicles', type=int, default=1000)
    a = ap.parse_args()
    fleet, n, _ = M.load_fleet(a.input, a.max_vehicles)
    flags = M.flags(fleet)
    root = Path(__file__).parent / 'results'
    result = write_review(fleet, flags, root / 'local')
    result.update({'input_rows': n, 'vehicles': len(fleet), 'rules': dict(Counter(f['rule'] for f in flags))})
    (root / 'flag_review_summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
