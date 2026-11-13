#!/usr/bin/env bash
# 16:00 scored runs: the frozen final_judge.py on both hidden test sets, twice each, with claude-haiku-4.5.
# Usage (from anywhere):
#   set -a; . Project_3/.env; set +a
#   bash Project_3/run_submission.sh <hidden_criterion1.jsonl> <CRITERION2.md> <dev_pairs_criterion2.jsonl> <hidden_criterion2.jsonl>
# Writes Project_3/submission/criterion{1,2}_run{1,2}.csv. WORKERS (default 8) sets parallel replies.
set -euo pipefail
[ $# -eq 4 ] || { sed -n '2,6p' "$0"; exit 2; }
abs() { (cd "$(dirname "$1")" && printf '%s/%s\n' "$(pwd)" "$(basename "$1")"); }
C1_CASES="$(abs "$1")"; C2_CRIT="$(abs "$2")"; C2_DEV="$(abs "$3")"; C2_CASES="$(abs "$4")"
cd "$(dirname "${BASH_SOURCE[0]}")"
OUT="$(pwd)/submission"; mkdir -p "$OUT"
cd starter_pack
unset JUDGE_LLM_CACHE   # a response cache would fake run-to-run consistency: never on for scored runs
[ "${JUDGE_LLM_MODEL:-}" = "claude-haiku-4.5" ] || { echo "JUDGE_LLM_MODEL must be claude-haiku-4.5"; exit 1; }
PY="${PYTHON:-python3}"
export JUDGE_LLM_MAX_RETRIES="${JUDGE_LLM_MAX_RETRIES:-10}"  # one flaky reply must not abort a scored run
for run in 1 2; do
  "$PY" run_judge.py --judge final_judge.py --pairs "$C1_CASES" --criterion JUDGE1_CRITERION.md --policy policy.md \
      --dev dev_pairs.jsonl --out "$OUT/criterion1_run$run.csv" --workers "${WORKERS:-8}"
  "$PY" run_judge.py --judge final_judge.py --pairs "$C2_CASES" --criterion "$C2_CRIT" --policy policy.md \
      --dev "$C2_DEV" --out "$OUT/criterion2_run$run.csv" --workers "${WORKERS:-8}"
done
echo "Done. Commit and push Project_3/submission/criterion*_run*.csv"
