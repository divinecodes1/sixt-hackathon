---
name: p3-mock-criterion-rehearsal
description: Rehearse Project 3's 14:30 surprise-criterion handoff before it happens - build two mock criteria (one numeric, one about tone/filler where openers DO matter) with relabelled dev pairs, check that prepare() switches the number rule correctly, run the unchanged judge and the baseline on them, and time the handoff. Use when asked to test generalisation to a new criterion, rehearse the surprise task, or check the recipe is criterion-agnostic.
---

# Project 3: surprise-criterion rehearsal

Why: everything else is tuned on "over-promise". The research report names a mock criterion that is not about policy numbers as the single most valuable pre-freeze experiment. The mocks are relabelled dev data, so they test the recipe, not the hidden set.

## 1. Build the mocks (no LLM)
From `Project_3/starter_pack`:
```bash
python3 <this skill's folder>/scripts/make_mocks.py
```
(`<this skill's folder>` is `../../.claude/skills/p3-mock-criterion-rehearsal` for Claude, `../../.agents/skills/p3-mock-criterion-rehearsal` for Codex.)

It writes `Project_3/mock_criteria/{numbers,filler}/` with `CRITERION.md`, `c2_dev_pairs.jsonl` (the "few labelled examples", from 2 source replies) and `eval_pairs.jsonl` (other source replies, stratified), and prints what `prepare()` decides:
- **numbers** ("does the reply state a number that differs from the policy?"): only wrong_number edits fail. Expect number rule = `verdict`.
- **filler** ("does the reply contain unnecessary pleasantries or filler?"): polite_opener and filler_padding edits fail; wrong_number edits are now harmless. Expect number rule = `off` (it fires on a pass example). This also tests that the judge does not ignore openers when the criterion is about them.

Labels come from construction and are approximate (e.g. an original that already sounds chatty). Say so with any number you report. `mock_criteria/` is scratch: don't commit it unless the user asks.

## 2. Run the unchanged judge (needs the key; .env loaded, JUDGE_LLM_CACHE unset)
For each mock `M` in `numbers filler`, from `starter_pack`:
```bash
time python3 run_judge.py --judge final_judge.py --pairs ../mock_criteria/M/eval_pairs.jsonl \
  --criterion ../mock_criteria/M/CRITERION.md --policy policy.md --dev ../mock_criteria/M/c2_dev_pairs.jsonl \
  --out ../results/mock_M_ours.csv
python3 run_judge.py --judge baseline_judge.py --pairs ../mock_criteria/M/eval_pairs.jsonl \
  --criterion ../mock_criteria/M/CRITERION.md --policy policy.md --out ../results/mock_M_base.csv
python3 score.py ../results/mock_M_ours.csv ../mock_criteria/M/eval_pairs.jsonl --baseline ../results/mock_M_base.csv
```

## 3. Read the result
- Ours ≥ baseline on both mocks: the recipe transfers. Record it in `RECIPE.md` (Surprise criterion section, as "rehearsal on mock criteria").
- Ours < baseline on a mock: find which part is criterion-specific in practice (prompt wording that assumes over-promising, the verify call's "dropping a condition makes it stronger" principle applied where it doesn't belong, example selection). Fix it generically via the p3-judge-iterate loop, then re-run **both** criterion 1 CV and the mocks. Never special-case a mock.
- Note the wall-clock time of step 2: the real handoff has ~90 minutes including two scored runs per criterion.

## 4. Handoff drill (do it once end to end)
Pretend `mock_criteria/filler` just arrived and follow the p3-surprise-criterion skill literally, timing each step. Fix any step in that skill that was unclear or broke.
