"""Build a self-contained offline demo from actual model outputs on mock vehicles."""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import mileage as M
import demo


def main():
    fleet, asof, selection, now, _, flags = demo.main()
    forecasts = {str(h): {r['vhcl_anon_id']: r for r in M.nowcast_table(
        fleet, asof, selection['forecast'], target=asof + h)} for h in (7, 30, 60, 90)}
    vehicles = []
    for i, row in enumerate(now, 1):
        vid = row['vhcl_anon_id']
        v = fleet[vid].view(asof)
        vehicles.append({'id': vid, 'name': f'Demo car {i:02d}', 'level': v.level,
                         'type': v.vtype, 'product': M.product_at(v, asof), 'now': row,
                         'history': [{'date': date.fromordinal(d).isoformat(), 'km': km}
                                     for d, km in zip(v.obs_day, v.obs_km) if d <= asof],
                         'forecasts': {h: table[vid] for h, table in forecasts.items()},
                         'flags': [f for f in flags if f['vhcl_anon_id'] == vid]})
    data = {'asof': date.fromordinal(asof).isoformat(), 'vehicles': vehicles,
            'models': selection, 'flags': flags, 'data_kind': 'synthetic'}
    source = Path(__file__).with_name('demo_template.html').read_text(encoding='utf-8')
    encoded = json.dumps(data, separators=(',', ':')).replace('<', '\\u003c')
    target = Path(__file__).with_name('demo.html')
    target.write_text(source.replace('/*DEMO_DATA*/null', encoded), encoding='utf-8')
    print(f'Open {target}')


if __name__ == '__main__':
    main()
