---
name: p3-surprise-criterion
description: Handle the Project 3 surprise criterion (about 14:30 on 13 Nov) - store the new CRITERION.md and labelled dev_pairs.jsonl without overwriting the originals, validate them, and run the unchanged final_judge.py on them with cross-validation against the baseline. Use when the user mentions the surprise/second criterion, criterion 2, or receives a new CRITERION.md.
---

# Project 3: the surprise criterion

The recipe must run **unchanged**: only `--criterion` and `--dev` change. Do not edit `final_judge.py` for the new criterion. If something looks broken, report it to the user instead of patching around it for this criterion specifically.

## 1. Store the inputs separately
The organizers' file is also called `dev_pairs.jsonl`. Save it as `c2_dev_pairs.jsonl`: never overwrite `starter_pack/dev_pairs.jsonl`, and `run_dev.sh` names its outputs after the file and would score a file named `dev_pairs*` against the criterion-1 baseline (crashing `score.py` after the paid runs).
```bash
mkdir -p Project_3/criterion2
# copy the received files to:
#   Project_3/criterion2/CRITERION.md
#   Project_3/criterion2/c2_dev_pairs.jsonl
```
Read `CRITERION.md` fully and summarize it for the user in 2–3 lines.

## 2. Validate the examples
```bash
cd Project_3/starter_pack
python3 - <<'EOF'
import json, collections
cs = [json.loads(l) for l in open("../criterion2/c2_dev_pairs.jsonl", encoding="utf-8") if l.strip()]
need = {"case_id","source_id","lang","orig_lang","question_original","question","original","edited",
        "edit_type","edit_family","edited_label"}
print(len(cs), "cases; missing fields:", sorted(need - set().union(*map(set, cs))))
print(collections.Counter((c.get("edit_family"), c.get("edit_type")) for c in cs))
print(collections.Counter(c.get("lang") for c in cs), "sources:", len({c.get("source_id") for c in cs}))
EOF
```
`final_judge.prepare()` falls back to defaults for missing fields, but missing `source_id` breaks `crossval.py`, and missing `edit_family`/`edited_label` breaks `score.py`. Report any gap.

## 3. Check what prepare() decides (no LLM)
```bash
python3 -c '
import final_judge as fj, run_judge
fj.prepare(open("../criterion2/CRITERION.md").read(), open("policy.md").read(), run_judge._jsonl("../criterion2/c2_dev_pairs.jsonl"))
print("number rule:", fj.CONFIG["number_rule"]); print(fj.CONFIG["examples_text"][:1500])'
```
Expect the number rule to switch itself `off` or to `hint` if the criterion is not about numbers. Tell the user which mode it picked and why.

## 4. Measure (needs the key; follow the p3-dev-eval preconditions: .env loaded, JUDGE_LLM_CACHE unset)
Ours, cross-validated, twice:
```bash
bash Project_3/run_dev.sh ../criterion2/c2_dev_pairs.jsonl ../criterion2/CRITERION.md
```
Baseline on the same cases (run_dev.sh only has a precomputed baseline for criterion 1):
```bash
cd Project_3/starter_pack
python3 run_judge.py --judge baseline_judge.py --pairs ../criterion2/c2_dev_pairs.jsonl \
  --criterion ../criterion2/CRITERION.md --policy policy.md --out ../results/c2_baseline.csv
python3 score.py ../results/c2_dev_pairs_cv_run1.csv ../criterion2/c2_dev_pairs.jsonl \
  --baseline ../results/c2_baseline.csv --repeat ../results/c2_dev_pairs_cv_run2.csv
```
Outputs: `Project_3/results/c2_dev_pairs_cv_run{1,2}.csv` and `c2_dev_pairs_report.txt` (no baseline in that report; the baseline comparison is the score.py call above).

With few examples and few source ids, cross-validation folds are tiny: say so next to the numbers. Rehearsed 13 Nov
on a mock (12 cases, 2 source ids): one of the 3 folds is empty (harmless, no crash) and a fold that sees only 3
examples may pick number rule `hint` instead of `off`; the whole step took about 20 s. A 12-case score is not
evidence of quality: report n next to it.

## 5. Record
Fill the "Surprise criterion" table in `starter_pack/RECIPE.md` and the criterion 2 rows in `SUBMISSION.md`.
Save the baseline comparison as `results/c2_vs_baseline_report.txt` (the score.py call above, `| tee`) and rebuild the
slides: `cd Project_3/submission && python3 make_slides.py && google-chrome --headless --no-pdf-header-footer
--print-to-pdf="$PWD/slides.pdf" "file://$PWD/slides.html"` (they read `c2_dev_pairs_report.txt` and that file). Remind the user that code freeze is 16:00 (see the p3-freeze-and-submit skill).
