---
name: p2-full-data-run
description: Run Project 2 (mileage nowcast/forecast and erroneous-mileage flags) on the organizers' full dataset - place the CSV in the git-ignored data/ folder, validate the schema, run tests and run_baseline.py, check whether the stale-OnRent finding holds, and update EDA.md and SUBMISSION.md with measured numbers. Use when the user gets the Project 2 data or asks for Project 2 results.
---

# Project 2: full-data run

Work from `Project_2/`. Python 3.11+, numpy for our code (`. .venv/bin/activate` if `bash setup.sh` was run).

## 1. Data placement (never commit data)
```bash
mkdir -p Project_2/data && cp /path/to/full.csv Project_2/data/
git check-ignore -v Project_2/data/full.csv   # must print a matching .gitignore rule
```
If `check-ignore` prints nothing, stop: the file would be committed.

## 2. Schema check
```bash
python3 -c 'import csv,sys; r=csv.DictReader(open(sys.argv[1],encoding="utf-8")); print(r.fieldnames); print(sum(1 for _ in r),"rows")' Project_2/data/full.csv
```
Compare with the header of `example_file.csv`. `mileage.py` needs at least `vhcl_anon_id`, `vhcl_fct_taken_datm`, `vhcl_current_mileage`, `on_rent_status`, `rntl_handover_date`, `rntl_return_date`, `vehicle_level`, `uti_plan`, `vhcl_max_mileage`. Report missing or renamed columns before running.

## 3. Tests, then the backtest
```bash
cd Project_2
python -m unittest test_mileage -v
python run_baseline.py                       # first CSV in data/
python run_baseline.py data/full.csv --cutoff YYYY-MM-DD   # optional explicit time split
```
Outputs: `results/metrics.json`, `results/flags.csv` (add `--asof YYYY-MM-DD` for `results/nowcast_<date>.csv`, git-ignored). Then `python flag_benchmark.py data/<file>.csv --rate 0.02` for flag recall on the real data. On the full data, 20% of vehicles are held out by hash (only when there are 10+ vehicles).

## 4. What to report
- Nowcast and forecast MAE / MAPE / WAPE for `naive_last`, `mean_rate`, `rent_aware`, overall and by gap/horizon bucket. State plainly where `rent_aware` loses (on the example it lost the forecast).
- The stale-OnRent check: the starter's raw-timestamp flag count (`starter_flags_on_raw_rows`) vs our flag counts by rule. If our `decrease` flags are still many, the handover re-timing may not hold fleet-wide: investigate before claiming it.
- The top 10 flags with their details, and whether they look plausible (big jumps, rollbacks, movement without a rental).

## 5. Update the docs with measured numbers only
- `EDA.md`: replace the "Open questions for the full data" with answers.
- `SUBMISSION.md`: replace every *TBD* with numbers from `results/metrics.json`; update the status line.

## 6. Data caution
`results/flags.csv` and `metrics.json` are committed. On the full data, flags.csv lists (salt-hashed) vehicle ids and readings. Before committing it, ask the user whether to commit it as is, aggregate it, or ask the project owners first. The repo rule is public or mock data only.
