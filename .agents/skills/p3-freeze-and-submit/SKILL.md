---
name: p3-freeze-and-submit
description: Project 3 code freeze at 16:00 and the scored submission runs - commit the final judge, unpack hidden_cases.zip, run final_judge.py twice on both hidden sets with claude-haiku-4.5, sanity-check the four CSVs and push them by 16:45. Use when the user mentions code freeze, hidden cases, hidden_cases.zip, submission runs or criterion*_run*.csv.
---

# Project 3: freeze and scored runs

The organizers rerun a sample with the 16:00 commit. Results that don't match the code are disqualified. So: no code change after the freeze commit, no other model, no hand-edited CSVs, no response cache.

## 1. Freeze (before 16:00)
1. Run the offline tests: `cd Project_3/starter_pack && python3 -m unittest test_final_judge -v`. Stop if they fail.
2. `git status` — the freeze commit must contain `starter_pack/final_judge.py` and anything it imports (`baseline_judge.py`). Make sure `.env` and any cache JSON are not staged (`git diff --cached --name-only`).
3. Commit: `git commit -m "Code freeze: final_judge.py"` and record the hash (`git rev-parse HEAD`). Ask the user before pushing, then `git push`.
4. From now on, do not edit `final_judge.py` or `baseline_judge.py`. If the user asks to, warn that it invalidates the submission.

## 2. Unpack the hidden cases (after 16:00)
Unpack into its own folder, outside `starter_pack/`, and do not commit it:
```bash
mkdir -p Project_3/hidden && cd Project_3/hidden && unzip -o /path/to/hidden_cases.zip && ls -la
```
Identify the criterion-1 file, the criterion-2 file, and confirm the criterion-2 `CRITERION.md` / labelled dev pairs are the ones from the afternoon (`Project_3/criterion2/`). The hidden files have no labels: do not try to score them, and never use them as examples or for tuning.

Check each hidden file has the fields `run_judge.py` needs:
```bash
python3 -c 'import json,sys
for p in sys.argv[1:]:
    cs=[json.loads(l) for l in open(p) if l.strip()]
    need={"case_id","orig_lang","question_original","original","lang","question","edited"}
    print(p, len(cs), "missing:", sorted(need-set().union(*map(set,cs))))' Project_3/hidden/*.jsonl
```

## 3. Scored runs
```bash
cd Project_3
set -a; . ./.env; set +a
unset JUDGE_LLM_CACHE
bash run_submission.sh hidden/<criterion1>.jsonl criterion2/CRITERION.md criterion2/c2_dev_pairs.jsonl hidden/<criterion2>.jsonl
```
It refuses to run unless `JUDGE_LLM_MODEL=claude-haiku-4.5`. On HTTP 429, rerun with `WORKERS=4`. Budget about 6 min per run at 3 calls/reply; four runs must finish well before 16:45, so start immediately.

## 4. Sanity checks
```bash
cd Project_3/submission
wc -l criterion*_run*.csv
python3 - <<'EOF'
import csv
for c in (1, 2):
    a, b = ({r["case_id"]: (r["original"], r["edited"]) for r in csv.DictReader(open(f"criterion{c}_run{k}.csv"))} for k in (1, 2))
    same = sum(a[i] == b.get(i) for i in a) / len(a)
    fails = sum(v[1] == "fail" for v in a.values()) / len(a)
    print(f"criterion {c}: {len(a)} cases, runs agree on {same:.1%} of cases, edited-fail rate {fails:.1%}")
EOF
```
Row counts must equal the number of hidden cases per criterion. Flag an all-pass or all-fail run, or agreement far below dev consistency.

## 5. Push (by 16:45)
Commit `Project_3/submission/criterion{1,2}_run{1,2}.csv` only (not `hidden/`, not `.env`). Ask the user, then push. Then run the hackathon-submission skill's final checklist.
