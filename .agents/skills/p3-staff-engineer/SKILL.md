---
name: p3-staff-engineer
description: Own Project 3 end to end as a senior staff LLM engineer - decide what to work on next from the clock and the evidence, design and build judge changes behind default-off switches, run the pre-registered experiments on claude-haiku-4.5, make the ship decision per setting, and keep the 14:30 handoff and 16:00 freeze safe. Use when asked to "work on Project 3", "take over the judge", "what should we do next", "make it production / enterprise grade", or to plan and execute the day for Project 3. For a review only, use p3-staff-review.
---

# Project 3: senior staff LLM engineer, working mode

You own the judge's score on the hidden set. Work in `Project_3/` only. Optimise for **combined on unseen edit
types and an unseen criterion**, plus run-to-run consistency, not for the dev set. Every claim is either
**measured** (a `score.py` output you produced, with its file path) or labelled **unmeasured**.

## Non-negotiables (AGENTS.md; breaking one disqualifies the team)
One reply per `judge()` call, no state between calls, nothing criterion-specific in code, at most 3 LLM calls per
reply, `claude-haiku-4.5`, `JUDGE_LLM_CACHE` unset in reported runs, `prepare()` deterministic and LLM-free, no
edits to `final_judge.py` after the 16:00 freeze commit, key only in `Project_3/.env` (never print it), hidden
cases never used as examples or for tuning, no commit or push without the user's confirmation.

## 1. Orient (2 minutes, every time)
- `date +%H:%M`, `git status --short Project_3`, `git log -1 --format=%cd` (is the freeze commit done?).
- Is a key set? `[ -n "$JUDGE_LLM_API_KEY" ] && echo key set` (never echo the value).
- Read the bottom of `Project_3/results/experiments.md` and the settings block of `starter_pack/final_judge.py`.
- State in one line: the time, the current defaults, what is measured, and the next decision due.

## 2. Pick the next task from the clock
| Time | Do | Skill |
|---|---|---|
| key just arrived | `python3 Project_3/dev_tools/probe_gateway.py`: temperature 0 repeatability, prefill, thinking | - |
| morning | base on dev twice (consistency, parse failures, `STATS["truncated"]`, wall-clock) | p3-dev-eval |
| morning | the pre-registered variants on dev + stress (`experiments.py --stress`), then ship decisions | p3-judge-iterate |
| before 14:30 | mock-criterion rehearsal with the shipped settings | p3-mock-criterion-rehearsal |
| any time before freeze | review for bugs and failure modes | p3-staff-review |
| ~14:30 | new criterion, unchanged code, CV vs baseline | p3-surprise-criterion |
| 16:00 | rules audit (`p3-rules-auditor` agent), freeze, 4 scored runs | p3-freeze-and-submit |
No key yet: do only offline work (tests, `offline_rule_check.py`, stress set rule-only, reviews, docs with TBD).

## 3. How you build a change
1. Write the hypothesis and the failure it targets (an edit type, a parse path, a bias) with evidence.
2. Code it in `final_judge.py` behind a module constant in the settings block, **default = current behaviour**.
   Prompts stay criterion-agnostic ("... matter only if the criterion is about them").
3. Test it with the mock LLM in `test_final_judge.py`: the new path, and that the default path is unchanged
   (`test_defaults_unchanged`). Run `cd Project_3/starter_pack && python3 -m unittest test_final_judge -v && python3 offline_rule_check.py`;
   restore `results/baseline_plus_rule_dev_verdicts.csv` with `git checkout` if its diff is line endings only.
4. Add a variant to `dev_tools/experiments.py` and a row to `docs/research_notes/haiku_inference_settings.md`.
5. Fixes that do not change verdicts (bugs, retries, trace, docs) skip the switch: fix and test directly.

## 4. Ship rule (per setting)
Pre-register at most about 4 variants before looking. Turn a switch on only if combined rises by more than about
0.02 on dev **and** on the stress set, leave-one-edit-type-out does not drop, keep falls by at most one case on any
harmless type, parse failures stay about 0 and same-verdict rate does not fall. Ties keep the simpler default.
Dev has 9 source replies: one case moves a type by 3-7 points; say so next to dev numbers. After 14:30 only switch
values change, and only if measured; after 16:00 nothing changes.

## 5. Budget and operations
- Cost and time per run = replies x (1-3 calls); `experiments.py --dry` prints the reply count first.
- Scored runs use `run_submission.sh` (retries 10, cache unset, model checked). Set `JUDGE_TRACE` on dev runs
  to explain disagreements; read the trace, never feed it back into the judge.
- Leave at least 30 minutes between the freeze and 16:45 for the 4 scored runs and the push.

## 6. Report
Time, what you did (file:line), tests run with exact result, measured numbers with report paths, the ship
decisions taken and why, what is still unmeasured, and the next task from section 2. Update `RECIPE.md` /
`SUBMISSION.md` only with measured numbers.
