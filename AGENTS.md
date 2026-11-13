# Agent guide: team Divinecodes, SIXT Hackathon 2026

Read by Codex (AGENTS.md) and by Claude Code (imported from CLAUDE.md). Hackathon day: Friday 13 Nov 2026, submission 16:45.

## Projects in this repo
- **Project_3 (primary): Judge the Judge.** `starter_pack/final_judge.py` is our judge (rule + up to 3 claude-haiku-4.5 calls). Recipe: `starter_pack/RECIPE.md`. Write-up: `SUBMISSION.md`.
- **Project_2 (second): odometer nowcast + flags.** `mileage.py`, `run_baseline.py`, `EDA.md`, `SUBMISSION.md`.
- `CodeRabbit_Python/`, `runbook/`, `arxiv_templates/` are organizer material: don't modify.

## Hard rules (breaking them disqualifies the team)
- No secrets in git: the key lives in `Project_3/.env` (git-ignored). Never print or commit it.
- Public or mock data only. Organizer data goes in `Project_2/data/` (git-ignored); hidden test cases never get committed, used as examples or used for tuning.
- Project 3 judge: one reply per call, no state between calls, nothing criterion-specific hard-coded, at most 3 LLM calls per reply, must run on `claude-haiku-4.5`, no response cache (`JUDGE_LLM_CACHE` unset) in any reported or scored run. No changes to `final_judge.py` after the 16:00 freeze commit.
- Never write an estimated number into a doc: only numbers produced by `score.py` / `run_baseline.py` in the repo.
- Stay in the project folders; push only to our fork, and only after the user confirms.

## Skills
Same content for both agents: `.claude/skills/<name>/SKILL.md` (Claude Code) and `.agents/skills/<name>/SKILL.md` (Codex; invoke with `$name` or `/skills`). Open the matching file and follow it when the task fits.

| Skill | Use when | Day plan |
|---|---|---|
| `p3-dev-eval` | Measuring the judge on dev; filling the TBD numbers | morning |
| `p3-judge-iterate` | Improving the judge: one change, CV + leave-one-edit-type-out, experiments log | morning |
| `p3-staff-engineer` | Own Project 3 end to end: orient, pick the next task from the clock, build behind switches, ship rule | all day |
| `senior-staff-llm-developer` | General staff-level LLM engineering: design, adversarial review, evaluation protocol (imported package, has a Project 3 profile) | any time |
| `p3-staff-review` | Senior staff LLM engineer review of the judge: bugs, failure modes, ranked fixes, default-off switches, ship rules | morning, before freeze |
| `p3-mock-criterion-rehearsal` | Rehearsing the surprise criterion with two mock criteria | before 14:30 |
| `p3-surprise-criterion` | ~14:30: the new criterion and labelled examples arrive | 14:30 |
| `p3-freeze-and-submit` | 16:00 code freeze, hidden cases, the four scored runs | 16:00 |
| `p2-full-data-run` | The full Project 2 dataset arrives; first results | when data arrives |
| `p2-model-improve` | Beating the baseline, blends, segment priors, prediction intervals | after first results |
| `p2-flag-review` | Flags: injected-error recall, false-flag rate, review of top flags | after first results |
| `submission-slides` | `submission/slides.pdf` (≤5 slides) from measured results | ~16:00 |
| `hackathon-submission` | Final checks before 16:45 | 16:30 |

## Agents
Claude Code: `.claude/agents/<name>.md`. Codex: `.codex/agents/<name>.toml` (generated).

| Agent | Does | Edits files? |
|---|---|---|
| `p3-judge-engineer` | Improves and measures the Project 3 judge (skills: p3-dev-eval, p3-judge-iterate, p3-mock-criterion-rehearsal) | yes |
| `p3-staff-llm-engineer` | Senior staff LLM engineer: owns the judge, reviews, builds, measures, decides (skills: p3-staff-engineer, p3-staff-review, p3-judge-iterate, p3-dev-eval) | yes |
| `senior-staff-llm-developer` | Staff LLM developer for design reviews, adversarial reviews and evaluation design (skills: senior-staff-llm-developer, p3-staff-review) | yes |
| `p3-rules-auditor` | Compliance audit of the judge vs the hackathon rules, before freeze and scored runs | no |
| `p2-mileage-modeler` | Runs, improves and reports Project 2 (skills: p2-full-data-run, p2-model-improve, p2-flag-review) | yes |
| `submission-reviewer` | Jury-style score against the 100-point rubric, top fixes | no |

Edit skills and agents only in `.claude/`, then run `python3 scripts/sync_agent_config.py` to regenerate `.agents/skills/` and `.codex/agents/`.

## Quick commands (no key needed)
```bash
cd Project_3/starter_pack && python3 -m unittest test_final_judge -v && python3 offline_rule_check.py
cd Project_2 && python -m unittest test_mileage -v && python run_baseline.py
```
