"""Project 2 baseline: nowcast + forecast backtest and mileage flags.

    python run_baseline.py [file.csv] [--cutoff YYYY-MM-DD]
Default input: first CSV in data/ (organizer data, git-ignored), else example_file.csv.
Writes results/metrics.json, results/flags.csv and prints a summary.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

import mileage as M

HERE = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--cutoff", help="time split for held-out periods (default: 80th percentile of reading dates)")
    ap.add_argument("--out", default=str(HERE / "results"))
    a = ap.parse_args(argv)
    found = sorted((HERE / "data").glob("*.csv")) or [HERE / "example_file.csv"]
    path = Path(a.csv) if a.csv else found[0]

    rows = M.load_rows(str(path))
    fleet = M.build_fleet(rows)
    n_obs = sum(len(v.obs_day) for v in fleet.values())
    print(f"{path.name}: {len(rows)} rows, {len(fleet)} vehicles, {n_obs} distinct readings")

    cutoff = date.fromisoformat(a.cutoff).toordinal() if a.cutoff else None
    res = M.backtest(fleet, cutoff)
    print(f"held-out period after {res['cutoff']}; vehicles train/test {res['n_train_vehicles']}/"
          f"{res['n_test_vehicles']}" + ("  (fewer than 10 vehicles: no vehicle hold-out)" if len(fleet) < 10 else ""))
    for task in ("nowcast", "forecast"):
        r = res[task]
        print(f"\n{task.upper()} ({r['n']} target readings)   MAE km | MAPE odometer | WAPE distance driven")
        for name, groups in r["models"].items():
            g = groups.get("all")
            if g:
                print(f"  {name:<12} {g['MAE_km']:>8.0f}   {g['MAPE_odometer']:>8.2%}   {g['WAPE_distance']:>8.2f}")
        best = r["models"].get("rent_aware", {})
        per_h = "  ".join(f"{h}: {v['MAE_km']:.0f} (n={v['n']})" for h, v in best.items() if h != "all")
        if per_h:
            print(f"  rent_aware MAE by gap/horizon: {per_h}")

    fl = M.flags(fleet)
    res["flags"] = dict(Counter(f["rule"] for f in fl))
    res["starter_flags_on_raw_rows"] = M.naive_flags(rows)
    print(f"\nFLAGS: {len(fl)} readings flagged {res['flags'] or ''}; the starter's raw-timestamp rules flag "
          f"{res['starter_flags_on_raw_rows']} (mostly stale OnRent readings, see EDA.md)")
    for f in sorted(fl, key=lambda f: -f["score"])[:10]:
        print(f"  {f['date']}  {f['vhcl_anon_id'][:10]}  {f['km']:>9.0f} km  {f['rule']:<20} {f['detail']}")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(res, indent=1))
    with open(out / "flags.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["vhcl_anon_id", "date", "km", "source", "rule", "detail", "score"])
        w.writeheader()
        w.writerows(fl)
    print(f"\nwrote {out / 'metrics.json'} and {out / 'flags.csv'}")
    return res


if __name__ == "__main__":
    main()
