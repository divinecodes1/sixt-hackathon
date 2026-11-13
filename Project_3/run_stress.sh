#!/usr/bin/env bash
# Transfer check on edit types that are NOT in dev (stress/stress_pairs.jsonl, our own mock edits, 11 new types).
# Runs final_judge.py twice (consistency) and the baseline once, all with claude-haiku-4.5, and scores them.
# The judge gets the full dev_pairs.jsonl as its labelled examples: none of the stress edit types appear there.
# Usage:
#   set -a; . Project_3/.env; set +a
#   bash Project_3/run_stress.sh
# Writes Project_3/results/stress_{ours_run1,ours_run2,base}.csv and stress_report.txt.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
RES="$(pwd)/results"; mkdir -p "$RES"
cd starter_pack
PY="${PYTHON:-python3}"
unset JUDGE_LLM_CACHE
"$PY" ../stress/make_stress.py
PAIRS=../stress/stress_pairs.jsonl
for run in 1 2; do
  "$PY" run_judge.py --judge final_judge.py --pairs "$PAIRS" --criterion JUDGE1_CRITERION.md --policy policy.md \
      --dev dev_pairs.jsonl --out "$RES/stress_ours_run$run.csv" --workers "${WORKERS:-8}"
done
"$PY" run_judge.py --judge baseline_judge.py --pairs "$PAIRS" --criterion JUDGE1_CRITERION.md --policy policy.md \
    --out "$RES/stress_base.csv" --workers "${WORKERS:-8}"
"$PY" score.py "$RES/stress_ours_run1.csv" "$PAIRS" --baseline "$RES/stress_base.csv" \
    --repeat "$RES/stress_ours_run2.csv" | tee "$RES/stress_report.txt"
