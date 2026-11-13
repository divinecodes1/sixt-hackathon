"""Project 2: nowcast + forecast backtest, prediction intervals and mileage flags.

    python run_baseline.py [file.csv] [--cutoff YYYY-MM-DD] [--asof YYYY-MM-DD]
Default input: first CSV in data/ (organizer data, git-ignored), else example_file.csv.
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
    ap.add_argument("--out", default=str(HERE / "results"))
    a = ap.parse_args(argv)
    found = sorted((HERE / "data").glob("*.csv")) or [HERE / "example_file.csv"]
    path = Path(a.csv) if a.csv else found[0]

    rows = M.load_rows(str(path))
    fleet = M.build_fleet(rows)
    n_obs = sum(len(v.obs_day) for v in fleet.values())
    products = Counter(v.product for v in fleet.values())
    print(f"{path.name}: {len(rows)} rows, {len(fleet)} vehicles, {n_obs} distinct readings, products {dict(products)}")

    cutoff = date.fromisoformat(a.cutoff).toordinal() if a.cutoff else None
    res = M.backtest(fleet, cutoff)
    res["input"] = path.name
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

    fl = M.flags(fleet)
    res["flags"] = dict(Counter(f["rule"] for f in fl))
    res["flags_per_1000_readings"] = round(1000 * len({(f['vhcl_anon_id'], f['date'], f['km']) for f in fl})
                                           / max(n_obs, 1), 2)
    res["starter_flags_on_raw_rows"] = M.naive_flags(rows)
    print(f"\nFLAGS: {len(fl)} flags ({res['flags_per_1000_readings']} flagged readings per 1,000) {res['flags'] or ''}; "
          f"the starter's raw-timestamp rules flag {res['starter_flags_on_raw_rows']} "
          "(mostly stale OnRent readings, see EDA.md)")
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

    if a.asof:
        asof = date.fromisoformat(a.asof).toordinal()
        table = M.nowcast_table(fleet, asof, res["selected"]["nowcast"], res["alpha"])
        p = out / f"nowcast_{a.asof}.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]) if table else ["vhcl_anon_id"])
            w.writeheader()
            w.writerows(table)
        print(f"wrote {p}: {len(table)} vehicles, model {res['selected']['nowcast']}")
    return res


if __name__ == "__main__":
    main()
