#!/usr/bin/env bash
# 16:00 scored runs: the frozen final_judge.py on both hidden test sets, twice each, with claude-haiku-4.5.
# Usage (from anywhere):
#   set -a; . Project_3/.env; set +a
#   bash Project_3/run_submission.sh <hidden_criterion1.jsonl> <CRITERION2.md> <dev_pairs_criterion2.jsonl> <hidden_criterion2.jsonl>
# Writes Project_3/submission/criterion{1,2}_run{1,2}.csv (+ .log). WORKERS (default 8) sets parallel replies per run;
# the 4 runs go in parallel (PARALLEL=0 for one after another).
set -euo pipefail
[ $# -eq 4 ] || { sed -n '2,7p' "$0"; exit 2; }
abs() { (cd "$(dirname "$1")" && printf '%s/%s\n' "$(pwd)" "$(basename "$1")"); }
C1_CASES="$(abs "$1")"; C2_CRIT="$(abs "$2")"; C2_DEV="$(abs "$3")"; C2_CASES="$(abs "$4")"
cd "$(dirname "${BASH_SOURCE[0]}")"
OUT="$(pwd)/submission"; mkdir -p "$OUT"
cd starter_pack
unset JUDGE_LLM_CACHE   # a response cache would fake run-to-run consistency: never on for scored runs
[ "${JUDGE_LLM_MODEL:-}" = "claude-haiku-4.5" ] || { echo "JUDGE_LLM_MODEL must be claude-haiku-4.5"; exit 1; }
PY="${PYTHON:-python3}"
export JUDGE_LLM_MAX_RETRIES="${JUDGE_LLM_MAX_RETRIES:-10}"  # one flaky reply must not abort a scored run
# The four runs are independent (stateless judge, temperature 0), so they run in parallel to fit the 45-minute
# window. PARALLEL=0 runs them one after another. Each run's progress goes to submission/<name>.log.
one() {  # one <criterion> <run>
  if [ "$1" = 1 ]; then set -- "$C1_CASES" JUDGE1_CRITERION.md dev_pairs.jsonl "criterion1_run$2"
  else set -- "$C2_CASES" "$C2_CRIT" "$C2_DEV" "criterion2_run$2"; fi
  "$PY" run_judge.py --judge final_judge.py --pairs "$1" --criterion "$2" --policy policy.md \
      --dev "$3" --out "$OUT/$4.csv" --workers "${WORKERS:-8}" > "$OUT/$4.log" 2>&1
}
pids=(); names=()
for run in 1 2; do
  for crit in 1 2; do
    if [ "${PARALLEL:-1}" = 1 ]; then one "$crit" "$run" & pids+=($!); names+=("criterion${crit}_run$run")
    else one "$crit" "$run" || { echo "FAILED: criterion${crit}_run$run (see $OUT/criterion${crit}_run$run.log)"; exit 1; }; fi
  done
done
fail=0
for i in "${!pids[@]}"; do
  wait "${pids[$i]}" || { echo "FAILED: ${names[$i]} (see $OUT/${names[$i]}.log)"; fail=1; }
done
[ "$fail" = 0 ] || exit 1
echo "Done. Commit and push Project_3/submission/criterion*_run*.csv"
