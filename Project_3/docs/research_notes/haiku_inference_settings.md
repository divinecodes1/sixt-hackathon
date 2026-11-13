# Claude Haiku 4.5: what we can change, and what the evidence says

Research date: 2026-11-13. Builds on `haiku_multilingual_practice.md` (specs, prompt layout, determinism, JSON output).

## What is published about the model
Anthropic does not publish Haiku 4.5's internal design (parameter count, layers, attention). The
[system card](https://assets.anthropic.com/m/99128ddd009bdcb/Claude-Haiku-4-5-System-Card.pdf) is mainly a safety
document: training used reinforcement learning from human and AI feedback, and the model is a hybrid reasoning model
that answers directly by default and can switch on extended thinking. It is the first Haiku with extended thinking.
Thinking is manual (`budget_tokens` of at least 1024, below `max_tokens`), not adaptive
([model page](https://platform.claude.com/docs/en/models/haiku-4-5/overview)).

Consequence for us: no fine-tuning, no architecture tweaks. "Model tweaks" means inference settings and prompt
construction. The rules fix the model and allow at most 3 calls per reply.

## The settings we can test, as switches in final_judge.py
| Setting | Evidence | Risk | Experiment |
|---|---|---|---|
| `THINKING_BUDGET` (extended thinking on call 1) | Mixed. Thinking mode raised small judges' accuracy on RewardBench ([2509.13332](https://arxiv.org/html/2509.13332)); no-CoT beat CoT in 14 of 16 settings in another study ([2503.03064](https://arxiv.org/html/2503.03064v1)); longer thinking does not track accuracy ([Think-J](https://arxiv.org/html/2505.14268v1)). | Thinking requires the default temperature (1), so run-to-run consistency can drop, and consistency is scored. Slower and costlier. | `T_think1k`, `T_think3k` with `--repeat` |
| `EXAMPLE_STYLE = "contrast"` (minimal pairs) | Grading research argues for boundary pairs that look alike but get different labels ([GUIDE, 2603.00465](https://arxiv.org/html/2603.00465v1)); no direct LLM-judge benchmark found. | Longer prompt; could cue the judge to look for a diff it cannot see. | `E_contrast` |
| `PREFILL` (answer starts with `<json>`) | Haiku 4.5 still supports prefill; Anthropic recommends prefill or structured output for strict formats. | Some gateways reject a trailing assistant message: check with `probe_gateway.py`. | `P_prefill` |
| `NUMBER_RULE_MAX = "hint"` | Our stress set: the rule fires on 30 of 35 harmless stricter-number edits. | Loses the certain catch on wrong numbers. | `R_hint` with `--stress` |
| `SECOND_LOOK` (call 2 re-checks a pass whose fields show a policy difference) | Staff review: by default the verdict uses only the model's `violates_criterion` boolean, so a dropped condition the model itself recorded can still pass. Symmetric (looser and stricter), so it assumes no criterion direction. | More call-2 traffic; can raise false fails if harmless differences get confirmed. | `S_second_look` |
| `ADJUDICATE` (call 3 sees both arguments) | Staff review: on a disagreement the default call 3 judges from scratch with the weakest prompt, discarding both reviewers' evidence. | Anchoring on whichever argument is phrased more confidently. | `J_adjudicate`, `SJ` |
| `VERIFY_EXAMPLES` (call 2 also sees the labelled examples) | Staff review 13 Nov, from `results/dev_pairs_trace.jsonl` joined with dev labels: 26 of 28 false fails on pass-labelled replies take the path `call1_fail>verify_confirms` (call 2 confirmed call 1's false alarm); call 2 is the only call without calibration examples. | Examples also show harmful edits labelled FAIL, so call 2 may confirm more; longer prompt. | `X_verify_examples` with `--repeat` |
| `VERIFY_SCOPED` (call 2 checks whether the limitation is stated anywhere and whether the condition limits this sentence's promise) | Dev run C (12:11) trace with reasons: 9 of 45 correct originals fail; call 2 confirms "dropped" conditions that the reply hedges elsewhere ("we will try", "often") or that govern a different promise (card rules on a sentence stating only the deposit amount). Overlaps with `VERIFY_WITNESS` (same target, different mechanism). | Could explain away real condition removals when another hedge is nearby (e.g. dropped "subject to availability" next to "often"): watch condition_removal and hedge_removal catch. | `Q_scoped_verify` with `--repeat` |
| `HEDGE_NOT_CONDITION` (call 2: a certainty word does not state a dropped condition) | Shipped-judge trace 12:22: 3 of 4 condition_removal misses are call 2 rejecting because the reply still says "often". **Measured 13:38: 0.842 vs 0.850 shipped (2 runs); not shipped.** | Lowered hedge_removal catch (0.750) and keep on translation/polite_opener. | `N_hedge_not_condition` |
| **`TRUST_VERIFY_REJECT`** (call 2 answered and proved no finding: pass, no call 3) | Criterion-2 error analysis (`results/c2_error_analysis.md`): in 8 of 17 errors call 3, judging from scratch, failed replies call 2 had cleared; on criterion 1 the same path caught 12 bad replies. Offline simulation from the traces, then real runs: **criterion 1 0.850 → 0.845, criterion 2 0.776 → 0.863 (2 runs) and 0.883 (official `run_dev.sh` pair, 14:06). Shipped 14:05**, added after the surprise arrived (disclosed). | Criterion-1 catch falls 0.813 → 0.762 (condition_removal 0.800 → 0.667, hedge_removal 0.800 → 0.700). | `T_trust_reject` |

| `VERIFY_WITNESS` (**on since 12:25**: call 2 confirms only with the reply's exact words + a concrete misleading case; code checks the words) | Dev run C trace: false fails on correct originals are call-1 alarms that call 2 confirmed. Measured on dev (`results/experiments.md`): 0.850 combined vs 0.721-0.754 for three base runs, same verdict 1.000. | Prompt designed on the same dev failures it is scored on (upper bound). It tells call 2 that call 1 "raises many false alarms", a prior that may cost catch under the surprise criterion. On dev, call 3 (holistic) decides about 30% of replies. | `W_witness`, control `W_off` |

Settings we rejected: temperature above 0 with voting (adds the variance that is scored), structured outputs as the
default (support depends on the gateway; `probe_gateway.py` reports it), a response cache (breaks the no-state rule).

## How a setting is chosen
`dev_tools/experiments.py` runs each variant on a temporary copy of the judge with grouped cross-validation, logs
`results/experiments.md`, and the winner is set by hand in `final_judge.py` only if combined rises above noise
(about 0.02) without keep dropping by more than one case on a harmless type, on dev **and** on the stress set.
