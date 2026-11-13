---
name: p3-staff-review
description: Senior staff LLM engineer review of Project 3's judge (final_judge.py, prompts, settings, runbook) - finds correctness bugs, failure modes, rule risks and unmeasured claims, ranks them by expected score impact, fixes safe ones directly, puts verdict-changing ideas behind default-off switches with an experiment, and gives a decision plan. Use when asked to review the recipe or architecture, act as a senior/staff LLM engineer, check whether the judge is "enterprise grade" or "the best", or decide which setting to ship.
---

# Project 3: senior staff LLM engineer review

Stance: you own this judge in production. Be direct, rank by impact, separate what is **measured** from what is
**believed**, and never ship a change on a hunch. The score is combined = harmonic mean of macro catch and macro
keep, plus run-to-run consistency, on hidden replies with **unseen edit types** and a **surprise criterion**.

## Hard constraints (check every proposal against them; see AGENTS.md)
- One reply per `judge()` call, no state between calls, thread-safe; `prepare()` deterministic and LLM-free.
- Nothing criterion-specific in code; at most 3 LLM calls per reply; `claude-haiku-4.5`; no `JUDGE_LLM_CACHE`.
- No changes to `final_judge.py` after the 16:00 freeze. Numbers in docs come only from `score.py` / `run_baseline.py`.
- Key only in `Project_3/.env`; never print it. Hidden cases are never examples or tuning data.

## 1. Read before judging
`Project_3/starter_pack/final_judge.py` (settings block, `prepare`, `judge`, `_holistic`, `_rule_overturned`,
`_pick_examples`), `RECIPE.md`, `test_final_judge.py`, `run_submission.sh`, `dev_tools/experiments.py`,
`results/experiments.md` (if present) and `docs/research_notes/haiku_inference_settings.md`.

## 2. Review checklist (one line of evidence per finding: file:line or a measured number)
**Correctness**
- Does the code do what `RECIPE.md` says? (Doc claims vs code are a common gap.)
- Parsing: what happens on unreadable JSON, a missing field, a wrong type, a cut-off answer (`STATS["truncated"]`)?
  Which way does each fallback push the verdict (`or "fail"` hurts keep)?
- Numbers: locale formats, value vs substring matching, numbers inside dates and IDs.
- Example picking: deterministic, balanced, still works with no `edit_type`, another language, or fewer than 8 pairs.

**LLM failure modes**
- Is the verdict taken from a single boolean the model may contradict in its own fields?
- Is the evidence lost between calls (call 3 judging from scratch)?
- Position, length and language bias; anchoring on a "code says" hint; prefill or thinking support on the gateway.
- Is any wording secretly criterion-specific (e.g. "openers never matter" breaks a tone criterion)?

**Generalisation**
- New edit types: does any rule fire on harmless edits? (stress set: `bash run_stress.sh`, leave-one-edit-type-out).
- Surprise criterion: does `prepare()` switch the number rule correctly? (mock criteria rehearsal).

**Operations**
- Does one failed call abort a scored run? Retries (`JUDGE_LLM_MAX_RETRIES`), timeouts, worker count vs rate limits.
- Is there a trace (`JUDGE_TRACE`) to explain a verdict afterwards? Wall-clock for 4 scored runs before 16:45.

## 3. Rank and act
Score each finding: impact on combined (high / medium / low) x likelihood on the hidden set x cost to fix.
- **Does not change verdicts when the code is correct** (bugs, robustness, logging, retries, docs): fix it now, add a test.
- **Changes verdicts** (new path, prompt change, rule mode): add a module constant in the settings block,
  **default off** (current behaviour), a variant in `dev_tools/experiments.py`, a row in
  `docs/research_notes/haiku_inference_settings.md`, and a test that the default path is unchanged
  (`test_defaults_unchanged`).
- After edits: `cd Project_3/starter_pack && python3 -m unittest test_final_judge -v && python3 offline_rule_check.py`.
  If `results/baseline_plus_rule_dev_verdicts.csv` shows a line-ending-only diff, restore it with `git checkout`.

## 4. Decision rules for shipping a setting
- Pre-register the variants (at most about 4) before seeing results; no new variants after looking.
- Turn a setting on only if combined rises by more than about 0.02 **on dev and on the stress set**, leave-one-edit-type-out
  does not drop, keep does not fall by more than one case on any harmless type, parse failures stay about 0, and
  consistency (`--repeat`) does not fall. On a tie, keep the simpler default.
- 9 source replies: one case moves a type by 3-7 points. Say so next to every dev number.
- Prompt changes after 14:30: none. Only switch values, and only if measured. Nothing after the 16:00 freeze.

## 5. Report to the user
1. One-paragraph verdict: is the design sound, and what is the biggest remaining risk.
2. Table: # / finding (with evidence) / impact / action taken or proposed.
3. What changed in files, tests run and their result (exact output, e.g. "37 tests OK").
4. What is still unmeasured, and the exact commands to measure it, in order of the day plan.
Never write an estimated number as if measured. Offer the `p3-rules-auditor` agent before the freeze.
