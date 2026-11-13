---
name: p3-judge-iterate
description: Improve Project 3's final_judge.py safely - one change at a time, measured by grouped cross-validation and leave-one-edit-type-out, logged in an experiments table, kept only if the combined score rises without breaking the rules. Use when asked to improve, tune, ablate or fix the judge's prompts, rules or aggregation before the 16:00 freeze. Not for running the scored submission.
---

# Project 3: improving the judge

Goal: raise **combined** (harmonic mean of macro catch and macro keep) on unseen replies and unseen edit types, and keep run-to-run consistency high. Measure with the p3-dev-eval skill's commands. Never change `final_judge.py` after the 16:00 freeze commit.

## The rules a change must not break
- One reply per `judge()` call, no state between calls, thread-safe (only read module data after `prepare()`).
- Nothing criterion-specific in code: no keyword lists used as verdicts, no branches on edit-type names, no texts copied from dev. Lexicons may only be hints to the LLM.
- At most 3 LLM calls per reply; `prepare()` deterministic and LLM-free; temperature 0; no response cache in reported runs.
- After each change: `python3 -m unittest test_final_judge -v` (update the mock in the test if prompts change shape).

## Where the points are (baseline on dev)
condition_removal catch 0.067 and false fails on correct originals (pass rate 0.858) cost the most; then hedge_removal 0.50 and sentence_reorder keep 0.733. Catch needs the original to pass too, so every false fail on a good reply costs both catch and keep.

## Experiment ladder (from docs/research_report.md; the current judge is roughly A5)
| Id | Variant | Question |
|---|---|---|
| A2 | call 1 only, verdict from fields, no verify | How much catch does the structured check give alone? |
| A4 | + verify call on candidate fails | Keep recovered vs catch lost |
| A5 | + holistic tiebreak (current) | Is the third call worth it? |
| B | call 1 split: precision call + separate condition/hedge recall call, verify kept | Does a separate recall pass raise condition catch? |
| C | three differently framed calls at T=0, majority | Does diversity beat verify? |
| E | examples: with vs without construction notes; 8 vs all types | Few-shot effect |
| L | leave-one-edit-type-out (script below) | Transfer to unseen edit types |
| S | `bash run_stress.sh` (from `Project_3/`): 11 edit types that are NOT in dev (`stress/make_stress.py`) | Transfer to new harmless and harmful types (the hidden set has some) |
| R | number rule in hint mode instead of verdict mode, scored on dev CV **and** S | The rule fires on 30/35 harmless `stricter_number` stress edits (rule-only keep 0.143 there); in verdict mode those pass only if call 1 overturns the rule. Keep verdict mode only if S `stricter_number` keep stays high |

Run S once on the current judge before changing anything; it is the reference for every later change. The stress set is a measuring stick only: never copy its edits into prompts or examples.

Implement variants behind a module constant (e.g. `PIPELINE = "A5"`), not an environment variable, so the frozen file has exactly one behaviour. Delete dead variants before the freeze.

## Loop
1. Write the hypothesis in one line (which failure type, why the change should help).
2. Make one change. Run unit tests.
3. Fast check: `bash run_dev.sh dev_pairs_fast.jsonl` (from `Project_3/`). Read `diagnose.py` output for the targeted type.
4. If promising, full check: `bash run_dev.sh` (226 cases, twice).
5. Keep only if combined rises by more than noise (dev has 9 source replies; one case moves a type by 3–7 points, so treat < ~0.02 as noise) **and** keep doesn't drop on any harmless type by more than one case's worth. Otherwise revert (`git checkout -- starter_pack/final_judge.py`).
6. Log every run, kept or not, in `Project_3/results/experiments.md`:
   `| date-time | variant | pairs | combined | catch | keep | kappa | same verdict | calls/reply | kept? | note |`

## Leave-one-edit-type-out
The hidden set has edit types not in dev. To estimate transfer, run from `Project_3/starter_pack` with the `.env` loaded:
```bash
python3 <this skill's folder>/scripts/loeto.py --dry                     # split sizes, no LLM
python3 <this skill's folder>/scripts/loeto.py --pairs dev_pairs_fast.jsonl --out ../results/loeto_fast.csv
```
(`<this skill's folder>` is `../../.claude/skills/p3-judge-iterate` for Claude, `../../.agents/skills/p3-judge-iterate` for Codex.) For each edit type, `prepare()` sees only the other types' examples. Note: without wrong_number examples the number rule correctly drops to hint mode, which is what an unseen numeric edit type would face. Report per-type catch/keep next to the normal CV numbers.

## Before the freeze
Hand over to the p3-rules-auditor agent (or re-read the rules above line by line against the diff: `git diff <last-freeze-candidate> -- starter_pack/final_judge.py`).
