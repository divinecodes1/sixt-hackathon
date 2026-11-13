---
name: p3-dev-eval
description: Measure Project 3's final_judge.py on the dev set with claude-haiku-4.5 (offline tests, grouped cross-validation run twice, scoring vs baseline, diagnosis) and record the numbers. Use when asked to evaluate, benchmark, test or improve the judge, or to fill the TBD numbers in RECIPE.md / SUBMISSION.md.
---

# Project 3: dev evaluation of the judge

Work from `Project_3/`. Never invent or estimate a number: every figure written to a doc must come from a `score.py` output produced in this session.

## 1. Preconditions
- `Project_3/.env` exists with `JUDGE_LLM_BASE_URL`, `JUDGE_LLM_API_KEY`, `JUDGE_LLM_MODEL=claude-haiku-4.5`. Never print, echo or commit the key. Load with `set -a; . ./.env; set +a`.
- `JUDGE_LLM_CACHE` must be **unset** for any run whose consistency is reported (a cache fakes consistency and breaks the no-state rule). It may be set only for quick local iteration, and those numbers are not reported.

## 2. Offline checks (no key, always run first)
```bash
cd Project_3/starter_pack
python3 -m unittest test_final_judge -v
python3 offline_rule_check.py
```
Both must pass before spending LLM budget. If tests fail, stop and report the failure output.

## 3. Endpoint smoke test (one call)
Confirm the gateway really serves Haiku 4.5 and accepts temperature 0:
```bash
curl -sS "$JUDGE_LLM_BASE_URL/chat/completions" -H "Authorization: Bearer $JUDGE_LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"'"$JUDGE_LLM_MODEL"'","temperature":0,"max_tokens":5,"messages":[{"role":"user","content":"Say PASS"}]}' \
  | python3 -c 'import json,sys; b=json.load(sys.stdin); print(b.get("model"), b["choices"][0]["message"]["content"])'
```
If the reported model is not a Haiku 4.5 id, stop and tell the user.

## 4. Iterate fast, then measure on the full set
- Fast loop (119 cases): `bash run_dev.sh dev_pairs_fast.jsonl` (file arguments are relative to `starter_pack/`).
- Final numbers (226 cases): `bash run_dev.sh` (defaults to `dev_pairs.jsonl`, `JUDGE1_CRITERION.md`).
- Output: `Project_3/results/<name>_cv_run{1,2}.csv` and `<name>_report.txt`. The stderr line `LLM calls …, parse failures …, models reported …` must show 0 or very few parse failures and only Haiku 4.5 model ids.
- Optional: `WORKERS=4` if the endpoint returns HTTP 429.

## 5. Diagnose
```bash
cd Project_3/starter_pack
python3 diagnose.py ../results/dev_pairs_cv_run1.csv dev_pairs.jsonl --examples 3
```
Name the 2–3 costliest failure types and show example replies. Remember: dev has only 9 source replies, so one case moves a per-type rate by 3–7 points. Don't over-read small differences.

## 6. Changing the judge: rules that must hold
- `judge()` sees one reply; no state across calls; nothing criterion-specific hard-coded (no keyword lists used as verdicts, no branches on edit-type names); ≤3 LLM calls per reply; `prepare()` stays deterministic and LLM-free.
- Every change is measured with cross-validation (`run_dev.sh`), never by scoring on examples the judge was shown.
- Re-run step 2 after every code change.

## 7. Record results
Update the TBD cells in `Project_3/starter_pack/RECIPE.md` (Step 4 table) and `Project_3/SUBMISSION.md` (Models and Results tables) with combined / macro catch / macro keep / kappa / same-verdict from the report. Add per-type notes only if they come from the report. Keep "what did not work" honest.
