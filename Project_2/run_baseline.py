"""Project 2: nowcast + forecast backtest, prediction intervals and mileage flags.

    python run_baseline.py [file.csv] [--cutoff YYYY-MM-DD] [--asof YYYY-MM-DD]
Default input: public example_file.csv. Supply organizer CSV/Parquet explicitly.
Writes results/metrics.json, results/flags.csv and prints a summary. With --asof, also writes
results/nowcast_<date>.csv: today's estimate per vehicle with a 90% interval (the product output; git-ignored).

Protocol (no leakage): a reading counts as known only from the day its row was written. Model choice per task and
the interval width come from a validation cutoff before the test cutoff, on training vehicles; the reported numbers
are on held-out vehicles (when there are 10+) after the test cutoff.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from datetime import date
from pathlib import Path

import mileage as M

HERE = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--cutoff", help="time split for held-out periods (default: 80th percentile of reading dates)")
    ap.add_argument("--asof", help="also write per-vehicle nowcasts for this date (default: no export)")
    ap.add_argument('--forecast-date', help='also export predictions at a future date; requires --asof')
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--max-vehicles", type=int, help="deterministic vehicle subset for bounded development")
    ap.add_argument("--validation-only", action="store_true", help="do not inspect held-out test outcomes")
    ap.add_argument("--skip-flags", action="store_true")
    a = ap.parse_args(argv)
    if a.forecast_date and not a.asof:
        ap.error('--forecast-date requires --asof')
    found = [HERE / "example_file.csv"]  # explicit organizer input prevents accidental test-file selection
    path = Path(a.csv) if a.csv else found[0]

    started = time.perf_counter()
    fleet, n_rows, starter_flags = M.load_fleet(str(path), a.max_vehicles)
    n_obs = sum(len(v.obs_day) for v in fleet.values())
    products = Counter(v.product for v in fleet.values())
    print(f"{path.name}: {n_rows} rows, {len(fleet)} vehicles, {n_obs} distinct readings, products {dict(products)}")

    cutoff = date.fromisoformat(a.cutoff).toordinal() if a.cutoff else None
    res = M.backtest(fleet, cutoff, evaluate_test=not a.validation_only)
    res["input"] = path.name
    res["input_rows"] = n_rows
    res["distinct_readings"] = n_obs
    res["max_vehicles"] = a.max_vehicles
    if a.validation_only:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'validation.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
        for task in ('nowcast', 'forecast'):
            print(task, 'chosen:', res['selected'][task])
            for name, groups in res['validation'][task]['models'].items():
                print(name, groups.get('all'))
        return res
    print(f"test period after {res['cutoff']} (validation cutoff {res['validation_cutoff']}); vehicles train/test "
          f"{res['n_train_vehicles']}/{res['n_test_vehicles']}"
          + ("  (fewer than 10 vehicles: no vehicle hold-out)" if len(fleet) < 10 else ""))
    for task in ("nowcast", "forecast"):
        r, sel = res[task], res["selected"][task]
        print(f"\n{task.upper()} ({r['n']} target readings)      MAE km   bias km  MAPE odo  WAPE dist  skill vs naive"
              f"  {100 * (1 - res['alpha']):.0f}% interval coverage")
        for name, groups in r["models"].items():
            g = groups.get("all")
            if not g:
                continue
            cov = res["intervals"][task][name].get("all", {}).get("coverage")
            mark = " <- chosen on validation" if name == sel else ""
            print(f"  {name:<18} {g['MAE_km']:>8.0f} {g['bias_km']:>+9.0f} {g['MAPE_odometer']:>9.2%} "
                  f"{g['WAPE_distance']:>10.2f} {g['skill_vs_naive']:>+15.2f}  "
                  f"{'n/a (too few validation targets)' if cov is None else f'{cov:.0%}'}{mark}")
        per_h = "  ".join(f"{h}: {v['MAE_km']:.0f} (n={v['n']})" for h, v in r["models"].get(sel, {}).items()
                          if h != "all")
        if per_h:
            print(f"  {sel} MAE by days since the last known reading: {per_h}")

    fl = [] if a.skip_flags else M.flags(fleet)
    res["flags"] = dict(Counter(f["rule"] for f in fl))
    res["flags_per_1000_readings"] = round(1000 * len({(f['vhcl_anon_id'], f['date'], f['km']) for f in fl})
                                           / max(n_obs, 1), 2)
    res["starter_flags_on_raw_rows"] = starter_flags
    print(f"\nFLAGS: {len(fl)} flags ({res['flags_per_1000_readings']} flagged readings per 1,000) {res['flags'] or ''}; "
          f"the starter's raw-timestamp rules flag {res['starter_flags_on_raw_rows']} "
          "(raw ordering; some may be stale OnRent artifacts, see SUBMISSION.md)")
    res['runtime_seconds'] = time.perf_counter() - started

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(res, indent=1))
    detailed = out if path.name == 'example_file.csv' or 'synthetic' in path.parts else HERE / 'results' / 'local'
    detailed.mkdir(parents=True, exist_ok=True)
    with open(detailed / "flags.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["vhcl_anon_id", "date", "km", "source", "rule", "detail", "score"])
        w.writeheader()
        w.writerows(fl)
    print(f"\nwrote {out / 'metrics.json'} and {detailed / 'flags.csv'}")

    if a.asof:
        asof = date.fromisoformat(a.asof).toordinal()
        # Historical exports must choose their model without seeing later validation outcomes.
        selection = M.backtest(fleet, asof, evaluate_test=False)['selected']
        table = M.nowcast_table(fleet, asof, selection['nowcast'], res["alpha"])
        p = detailed / f"nowcast_{a.asof}.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]) if table else ["vhcl_anon_id"])
            w.writeheader()
            w.writerows(table)
        print(f"wrote {p}: {len(table)} vehicles, model {selection['nowcast']}")
        if a.forecast_date:
            target = date.fromisoformat(a.forecast_date).toordinal()
            table = M.nowcast_table(fleet, asof, selection['forecast'], res['alpha'], target=target)
            p = detailed / f'forecast_{a.forecast_date}.csv'
            with p.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(table[0]) if table else ['vhcl_anon_id'])
                w.writeheader()
                w.writerows(table)
            print(f'wrote {p}: {len(table)} future mileage estimates')
    return res


if __name__ == "__main__":
    main()
