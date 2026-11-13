"""Safe live demo on made-up vehicles. No organizer data or network required."""
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

import mileage as M
from synth_fleet import generate


def save(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ['no_records'])
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = generate(n_vehicles=40, days=240, seed=7)
    # An invented typo within the known history, so the live review needs no future rows.
    returns = {}
    for row in rows:
        if row['on_rent_status'] == 'NotOnRent':
            returns.setdefault(row['vhcl_anon_id'], []).append(row)
    history = max(returns.values(), key=len)
    mistake = history[len(history) // 2]
    mistake['vhcl_current_mileage'] = str(float(mistake['vhcl_current_mileage']) + 90000)
    fleet = M.build_fleet(rows)
    asof = max(d for v in fleet.values() for d in v.obs_day) - 20
    selection = M.backtest(fleet, cutoff=asof, evaluate_test=False)['selected']
    now = M.nowcast_table(fleet, asof, selection['nowcast'])
    future = M.nowcast_table(fleet, asof, selection['forecast'], target=asof + 30)
    known_fleet = {vid: v.view(asof) for vid, v in fleet.items()}
    flags = sorted(M.flags(known_fleet), key=lambda f: -f['score'])
    out = Path(__file__).parent / 'results/demo'
    out.mkdir(parents=True, exist_ok=True)
    save(out / 'nowcasts.csv', now)
    save(out / 'forecasts.csv', future)
    save(out / 'flags.csv', flags)
    summary = {'data': 'entirely synthetic; demonstration, not SIXT performance',
               'asof': date.fromordinal(asof).isoformat(), 'models': selection,
               'nowcasts': len(now), 'forecasts': len(future), 'rules': dict(Counter(f['rule'] for f in flags))}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    print('\nMade-up vehicle examples:')
    for row in now[:3]:
        print(f"{row['vhcl_anon_id'][:8]}: last {row['last_km']:,.0f} km; estimate {row['nowcast_km']:,.0f}; "
              f"range {row['low_km']} to {row['high_km']}; {row['quality_status']}")
    print('\nLargest review candidates (mock data):')
    for f in flags[:3]:
        print(f"{f['rule']}: {f['detail']}")
    print(f'\nCSV artifacts: {out}')
    return fleet, asof, selection, now, future, flags


if __name__ == '__main__':
    main()
