#!/usr/bin/env bash
# Dev evaluation of final_judge.py: grouped cross-validation (examples never come from the scored source replies),
# run twice to measure consistency, scored against the baseline.
# Usage:
#   set -a; . Project_3/.env; set +a
#   bash Project_3/run_dev.sh [pairs.jsonl] [criterion.md]     (defaults: dev_pairs.jsonl, JUDGE1_CRITERION.md)
# Writes Project_3/results/<pairs-name>_cv_run{1,2}.csv and <pairs-name>_report.txt.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
RES="$(pwd)/results"; mkdir -p "$RES"
cd starter_pack
PAIRS="${1:-dev_pairs.jsonl}"; CRIT="${2:-JUDGE1_CRITERION.md}"; NAME="$(basename "$PAIRS" .jsonl)"
PY="${PYTHON:-python3}"
unset JUDGE_LLM_CACHE
for run in 1 2; do
  "$PY" crossval.py --judge final_judge.py --pairs "$PAIRS" --criterion "$CRIT" --policy policy.md \
      --out "$RES/${NAME}_cv_run$run.csv" --workers "${WORKERS:-8}"
done
BASE=(); [ "$NAME" = dev_pairs ] || [ "$NAME" = dev_pairs_fast ] && BASE=(--baseline baseline_dev_verdicts.csv)
"$PY" score.py "$RES/${NAME}_cv_run1.csv" "$PAIRS" "${BASE[@]}" --repeat "$RES/${NAME}_cv_run2.csv" \
    | tee "$RES/${NAME}_report.txt"
