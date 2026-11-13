---
name: hackathon-submission
description: Final SIXT Hackathon 2026 submission checklist (deadline 16:45, 13 Nov) - SUBMISSION.md complete with no TBDs, demo video or slides present, no secrets or real data committed, repo public and pushed. Use before any final push, or when the user asks "are we ready to submit", "check the submission", or about the deadline.
---

# Hackathon submission check

The submission is the public GitHub repo link from the registration form, as pushed at 16:45. Run every check and report a pass/fail list; fix only what the user approves.

## 1. Required files, per project folder the team submits (Project_3 primary, Project_2 if submitted)
- `SUBMISSION.md` following `SUBMISSION_TEMPLATE.md`: team name, which project, problem and approach, models table, results with a baseline on held-out data, exact "How to run", demo path, next steps.
  - `grep -n "TBD" Project_*/SUBMISSION.md Project_3/starter_pack/RECIPE.md` must print nothing, or every remaining TBD is explained.
  - Every number must trace to a results file in the repo (`Project_3/results/*_report.txt`, `Project_2/results/metrics.json`).
- `submission/demo.mp4` (≤1 min, <50 MB) **or** `submission/slides.pdf` (≤5 slides), inside the project folder.
- Project 3 only: `Project_3/submission/criterion{1,2}_run{1,2}.csv` and the recipe (`starter_pack/RECIPE.md`) referenced from SUBMISSION.md.

```bash
ls -la Project_*/submission/ 2>/dev/null
du -h Project_*/submission/demo.mp4 2>/dev/null
python3 -c 'import sys,re; d=open(sys.argv[1],"rb").read(); print(len(re.findall(rb"/Type\s*/Page[^s]", d)), "pages")' Project_3/submission/slides.pdf 2>/dev/null
```

## 2. Nothing that disqualifies
```bash
git ls-files | grep -Ei '(^|/)\.env$|\.pem$|\.key$|cache.*\.json$|(^|/)data/|hidden'
git grep -nE 'sk-[A-Za-z0-9]{16,}|JUDGE_LLM_API_KEY=.+' -- ':!*.example'
git log -p --all -S'JUDGE_LLM_API_KEY=' --oneline | head
```
All must print nothing, except `CodeRabbit_Python/sample_project` (a deliberate fake key) and `.env.example` (empty value). A real key in any commit, even a deleted one, needs the user to rotate it with the organizers: tell them immediately.

## 3. Reproducibility
From a clean clone in a temporary directory (`git clone <repo-url> "$(mktemp -d)/repo"`), the "How to run" commands that need no key must work: Project 3 `python3 -m unittest test_final_judge -v` and `python3 offline_rule_check.py`; Project 2 `python -m unittest test_mileage -v` and `python run_baseline.py` on the example file.

## 4. Pushed and public
```bash
git status --short          # nothing important left uncommitted
git log origin/main..HEAD --oneline   # empty = everything pushed
gh repo view --json visibility,url    # visibility must be PUBLIC
```
Push only after the user confirms. Remind them that Project 3's final_judge.py counts as of the 16:00 commit; later edits to it don't count.

## 5. Pitch prep (if finalists)
3 min + 2 min Q&A. Story: problem → main insight → method vs baseline → measured numbers → limits → how SIXT uses it. Jury scores: problem 15, approach 25, results 25, relevance 15, code 10, demo 10.
