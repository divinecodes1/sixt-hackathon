# Spending a 3-call budget on a small judge (claude-haiku-4.5): aggregation, reasoning, few-shot, determinism (13 Nov 2026)

Short, focused pass of about 17 tool calls. It **extends** `../rubric_prompting_methods.md` (sections 2–5 and 7), `../haiku_inference_settings.md` and the two sibling notes. Findings already there are not repeated, only referenced (for example Yamauchi 2506.13639 on greedy vs. sampled, PoLL, TICK maj@k, CoT with detailed criteria, MSwR few-shot, and Luo et al.'s asymmetric errors). Tags: [fetched] means I read the primary page; [search] means search-snippet level only; (unverified) means I could not confirm the claim from a primary source.

Context: `final_judge.py` sends call 1 as claim-by-claim JSON at T=0 through an OpenAI-compatible `/chat/completions` gateway. Call 2 verifies suspected fails, and call 3 breaks ties. Switches exist for `THINKING_BUDGET`, `SECOND_LOOK`, `ADJUDICATE`, `PREFILL` and `EXAMPLE_STYLE`.

## Q1. Verify-on-fail cascade vs. 3-vote majority vs. differently framed calls vs. generate-then-critique

### Takeaway
No study compares these four options head-to-head for one small model at T=0, so the choice has to be measured on dev. The indirect evidence points in two directions:
- **Same-prompt voting at T=0 adds almost nothing**, because the three calls are nearly identical. Its gains (+1 to +2.5 balanced-accuracy points) come from sampling at T>0, which adds run-to-run variance.
- **Asking the same model to "re-check" its own verdict is risky.** Challenged models flip often and lose accuracy. A verify-on-fail step is only safe if it is framed as an *independent, evidence-anchored check* (quote the policy clause, quote the reply span) and never as "are you sure?". A cascade with a calibrated confidence threshold (Trust-or-Escalate) is the best-founded form of "only spend calls when unsure".

### Cited Findings
- **Majority-of-3 vs. single run vs. no sampling (Rating Roulette)**, balanced accuracy vs. humans on SummaC (binary):
  - Llama 3.1: single run 59.1 ± 2.06, majority 61.4, no sampling 58.4
  - DeepSeek-R1: 69.8 ± 0.50, majority 72.3, no sampling 69.3
  - Qwen 3: 79.4 ± 0.32, majority 80.6, no sampling 79.2
  - The authors frame this as a trade-off between self-reliability and performance. — [arXiv 2510.27106](https://arxiv.org/html/2510.27106) [fetched]
- **Run-to-run reliability (same paper).** Intra-rater Krippendorff α across 3 runs on SummaC binary was 0.326 for Llama 3.1, 0.628 for DeepSeek-R1 and 0.788 for Qwen 3. On the 3-way MT-Bench task, Qwen 3 gave the same verdict in all 3 runs on only 61.3% of items. Going to 5 runs made no significant difference. — [arXiv 2510.27106](https://arxiv.org/html/2510.27106) [fetched]
- **FlipFlop: "Are you sure?" challenges.** Across 10 LLMs and 7 classification tasks, models flipped their answer **46%** of the time on average when challenged, and accuracy fell by **17%** on average between the first and final answers. Fine-tuning reduced the drop by 60% but did not remove it. The abstract does not name the models, so I cannot say whether Claude was included. — [arXiv 2311.08596](https://arxiv.org/abs/2311.08596) [fetched abstract]
- **Intrinsic self-correction.** Without external feedback, LLMs struggle to self-correct reasoning, and performance sometimes *degrades* after self-correction. Earlier positive results relied on oracle labels. Self-correction works better on style and appropriateness tasks. — [Huang et al., ICLR 2024, arXiv 2310.01798](https://arxiv.org/abs/2310.01798) [search; exact table numbers not extracted]
- **Cascaded selective evaluation (Trust or Escalate).** A judge abstains or escalates when its calibrated confidence is low. "Simulated Annotators" estimates confidence from in-context-learning variants. A cascade starting from Mistral-7B guaranteed over 80% human agreement at almost 80% coverage on a Chatbot Arena subset where GPT-4 alone rarely reaches 80%. — [Jung, Brahman, Choi, ICLR 2025, arXiv 2407.18370](https://arxiv.org/abs/2407.18370) [search]
- **Follow-up questions raise recall.** Removing the interrogation step in LM-vs-LM cut recall by 6–10% (already in `rubric_prompting_methods.md` section 5). — [Eugene Yan](https://eugeneyan.com/writing/llm-evaluators/)

### Inferences
- (Inference) At T=0 with one model, a "3-vote majority of the same prompt" makes three nearly identical calls. Its benefit comes only from residual nondeterminism, so it is mostly wasted budget. Votes only buy diversity if the three calls use **different framings** (PoLL-style), and even then the evidence is indirect.
- (Inference) The current cascade (call 2 only on suspected fails) is a reasonable use of budget, *provided* call 2 re-derives the verdict from the policy text and the reply. If call 2 instead receives call 1's conclusion and is asked to confirm it, FlipFlop and self-correction results predict two problems: verdict flips toward "pass" (lower catch) and sensitivity to wording. `VERIFY_INSTRUCTIONS` currently says "Another reviewer says the reply violates…". That is a mild challenge framing. It is better than "are you sure", but it still anchors the model.
- (Inference) The asymmetry matters here. Call 2 only sees suspected fails, so any sycophantic drift becomes "overturn to pass". That protects keep and costs catch. Watch catch per edit type when call 2 is on.
- (Inference) The tie-break in call 3 is the closest thing to a selective-evaluation cascade. Spending it only when calls 1 and 2 disagree is consistent with Trust-or-Escalate, which spends calls only when uncertain.

### Gaps
- I found no study of verify-on-fail vs. majority-of-3 vs. diverse framings for binary policy compliance with one small model at T=0, so this must be measured on dev.
- I did not check whether Claude Haiku was among FlipFlop's 10 models.

## Q2. CoT vs. short reasoning vs. extended thinking: effect on accuracy and consistency

### Takeaway
For a small judge with a detailed criterion and policy, **short, structured, bounded reasoning** is the best-supported choice. Long or free-form reasoning lowers run-to-run agreement, because instability grows with output length. On Haiku 4.5, extended thinking forces the default temperature, so it trades the scored consistency for an unproven accuracy gain.

### Cited Findings
- **Output length vs. stability (Atil et al.).** Tested at T=0, top-p 1 and a fixed seed, with 10 runs: GPT-3.5, GPT-4o, Llama-3-70B/8B and Mixtral. Output length was strongly or moderately **negatively correlated** with agreement on both raw strings and parsed answers, and positively correlated with the max–min accuracy spread. The authors recommend capping max tokens. — [arXiv 2408.04667v5](https://arxiv.org/html/2408.04667v5) [fetched]
- **CoT and run-to-run reliability (Rating Roulette).** Few-shot and CoT prompting changed intra-rater α by **less than 0.01** on SummaC. In that setting, CoT neither helped nor hurt consistency. — [arXiv 2510.27106](https://arxiv.org/html/2510.27106) [fetched]
- **Rankings can flip between runs (ReasonBENCH).** The top reasoning strategy or model beat its nearest competitor in only 77% and 88% of head-to-head runs. — [alphaXiv 2512.07795](https://www.alphaxiv.org/abs/2512.07795.md) [search]
- **Explanation requirement.** Arize says several studies show that requiring explanations reduces variance across repeated judgments. It also says explicit CoT is unnecessary for reasoning models, where it mainly adds tokens. — [Arize](https://arize.com/blog/evidence-based-prompting-strategies-for-llm-as-a-judge-explanations-and-chain-of-thought/) [search; vendor blog]
- **Extended thinking on Haiku 4.5 is manual only.** `budget_tokens` must be at least 1,024 and below `max_tokens`. Adaptive thinking returns a 400 error on Haiku 4.5. Anthropic's guidance for simple tasks is to start near 1,024. — [Anthropic extended-thinking docs](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) [fetched]
- **Thinking constraints.** On older models (Haiku 4.5 included) before API version `2026-10-21`, "`temperature` and `top_k` are incompatible with thinking, and `top_p` is allowed at values between 0.95 and 1". On earlier models "you can't prefill the assistant response while thinking is on". — [Anthropic thinking docs, "Limits and feature compatibility"](https://platform.claude.com/docs/en/build-with-claude/thinking) [fetched]

### Inferences
- (Inference) Keep call 1's reasoning **inside short JSON fields**: quoted span, policy clause, difference, and the verdict last. Cap `max_tokens` near what the longest legitimate answer needs. Atil et al. tie length to instability. Our current `MAX_TOKENS=3000` is only a ceiling and has no effect unless the prompt also asks for brevity, for example "at most N claims, one sentence each".
- (Inference) `THINKING_BUDGET>0` means temperature 1. Even if accuracy rises, the two scored runs can diverge. Ship it only if `--repeat` shows run-to-run flips no worse than the T=0 configuration. A priori it is the riskiest switch for the consistency criterion.

### Gaps
- I found no Haiku-4.5-specific measurement of CoT, short reasoning or thinking for a binary compliance judge.
- An arXiv paper on temperature in LLM-as-a-judge (2603.28304) reportedly says a reasoning phase "can lead to fundamentally divergent outputs". The PDF was too large to fetch, so this is (unverified).

## Q3. Few-shot examples for judges: count, contrastive pairs, rationales, induced bias

### Takeaway
New evidence in this pass is thin and adds little beyond `rubric_prompting_methods.md` section 2: balanced labels, rationales, and contrast pairs drawn from training data only. One new data point is that few-shot prompting did not change run-to-run reliability. Order and selection effects in in-context learning are real for classification, so use a **fixed, deterministic order** and alternate the labels.

### Cited Findings
- **Few-shot did not change consistency.** In Rating Roulette, few-shot and CoT changed intra-rater α by less than 0.01. — [arXiv 2510.27106](https://arxiv.org/html/2510.27106) [fetched]
- **Shot selection and order (WOAH 2025).** On toxic-language in-context learning with 3B–72B open models, selecting shots by annotator-disagreement entropy (borderline cases) can improve performance, and example order changes behaviour. In-context learning often underperformed fine-tuned encoders. — [WOAH 2025](https://preview.aclanthology.org/landing_page/2025.woah-1.5.pdf) [search]
- **Selection bias.** Decisions change under equivalence-preserving perturbations such as label renaming and option permutation, both in LLM-as-judge and in in-context classification. — [Preprints.org manuscript](https://www.preprints.org/frontend/manuscript/56b8dd21ae6e4c5ddb0fc11df6c791e4/download_pub) [search, abstract-level only]

### Inferences
- (Inference) `_pick_examples` should be deterministic: a fixed sort, not a dict or set order, and labels alternating pass and fail. That way the two scored runs see byte-identical prompts. Byte-identical prompts are the only lever we control against T=0 drift.
- (Inference) With 2–4 surprise-criterion examples, borderline cases with a one-line rationale matter most. That fits the "disagreement-entropy" shot-selection result.

### Gaps
- I found no primary 2025–26 study on the effect of shot count or minimal pairs in *binary* LLM judges. The main evidence remains MSwR (2406.11629) and the practitioner guidance already cited.

## Q4. How deterministic is Claude at temperature 0, and what reduces verdict flips?

### Takeaway
Anthropic does not promise determinism. Secondary mirrors of the SDK and API docs quote "even with a temperature of 0.0, the results will not be fully deterministic". There is also no `seed` parameter. A **major new risk**: Anthropic's current docs say that from API version `2026-10-21`, a request that includes `temperature` "at any value returns a 400 error on every model". On newer models (Haiku 5.5, Opus 4.7+), non-default sampling parameters are rejected regardless of version. Whether `temperature: 0` still reaches Haiku 4.5 therefore depends on the API version our OpenAI-compatible gateway pins. Measured T=0 nondeterminism on other models: up to about 15% accuracy spread over 10 runs, and parsed-answer agreement much higher than raw-string agreement.

### Cited Findings
- **Anthropic docs on sampling parameters:** "Starting with API version `2026-10-21`, a request that includes `temperature`, `top_p`, or `top_k` at any value returns a 400 error on every model." The docs also say "On older models in API versions before `2026-10-21`, the restriction applies only while thinking is on". — [Anthropic thinking docs](https://platform.claude.com/docs/en/build-with-claude/thinking) [fetched]
- **T=0 is "not fully deterministic".** This wording comes from the Messages API reference, quoted via an SDK docs mirror and blogs. I could not open the primary page section (too large to fetch). — [tessl.io SDK mirror](https://tessl.io/registry/tessl/pypi-anthropic/0.74.0/files/docs/messages.md); [Unstract](https://unstract.com/blog/understanding-why-deterministic-output-from-llms-is-nearly-impossible/) [search, secondary]
- **No seed.** The Anthropic API reportedly ignores or does not offer `seed`. — [pramana reproducibility notes](https://syd-ppt.github.io/pramana/reproducibility.html) (unverified against Anthropic docs)
- **Measured T=0 drift on non-Claude models (Atil et al.):**
  - Max–min accuracy differed by up to about 15% across 10 runs, and best-to-worst possible accuracy by up to 70%. "None of the LLMs consistently delivers repeatable accuracy across all tasks".
  - Parsed-answer agreement beat raw-string agreement. For example, GPT-3.5 few-shot on geometric shapes reached 62.8% parsed agreement vs. 25.2% raw.
  - The authors recommend capping max tokens and reporting the max–min across runs.
  - [arXiv 2408.04667v5](https://arxiv.org/html/2408.04667v5) [fetched]
- **Serving effects.** For a 7B reasoning model, GPU count, GPU type and batch size alone caused up to 9% accuracy variation. — [arXiv 2506.09501](https://arxiv.org/pdf/2506.09501v2) [search]
- **Cause.** Batch-size variance, non-batch-invariant kernels and floating-point non-associativity (Thinking Machines Lab, as cited in arXiv 2604.22411). — [arXiv 2604.22411](https://arxiv.org/html/2604.22411v1) [search, secondary]

### Inferences
- (Inference) **Action: check what the gateway does with `temperature: 0`.** Possible outcomes:
  - It drops `temperature` silently, so we get T=1 and lower consistency.
  - It returns a 400 error, so retries and parse failures follow.
  - It passes `temperature` through under a pre-2026-10-21 API version, which is fine.
  - A one-off probe with `probe_gateway.py` plus two identical calls answers this. Report the result in `RECIPE.md`.
- (Inference) What reduces verdict flips, in order:
  1. **Byte-identical prompts.** Use fixed example order, no timestamps and no dict-order dependence.
  2. **Short outputs**, with the verdict decided from a small structured field.
  3. **Flips matter only where they cross the decision.** A code rule or a quoted-span check makes a verdict independent of the wording drift around it.
  4. **Avoid T=1 paths** (thinking).
  5. **Treat a disagreement between calls as uncertainty.** Resolve it with an evidence-anchored call 3, not a re-ask.
- (Inference) Rating Roulette shows majority-of-3 adds about 1–2.5 points of accuracy *under sampling*. At T=0 the gain is near zero, so for us it does not justify replacing the cascade.

### Gaps
- No public measurement of Haiku 4.5's verdict-flip rate at T=0. Our own `--repeat` runs on dev are the only source.
- The exact gateway API version is unknown, so it needs a probe.

## Ranked changes to our design (all inference; evidence strength in brackets)

1. **Probe temperature handling in the gateway before the freeze.**
   - Send two identical calls with `temperature: 0`, log any 400 errors, and compare outputs byte for byte.
   - If temperature is rejected or ignored, consistency planning changes: lean harder on short structured outputs and code rules.
   - [Strong: primary Anthropic docs on the `2026-10-21` sampling-parameter removal; effect on our gateway unknown]
2. **Keep the cascade, but de-anchor call 2.**
   - Rewrite `VERIFY_INSTRUCTIONS` so call 2 independently re-derives each flagged point from the quoted policy clause and reply span.
   - Do not frame it as "another reviewer says it violates; confirm". Do not show call 1's verdict, only the *locations* to inspect.
   - Measure catch per edit type with call 2 on vs. off.
   - [Moderate: FlipFlop 46% flips and −17% accuracy; Huang et al. on self-correction; indirect for judges]
3. **Bound call-1 output length.**
   - In the prompt, ask for at most N claims with one short sentence per field and the verdict last. Set `max_tokens` close to the real need.
   - Compare run-to-run flips with `--repeat`.
   - [Moderate: Atil et al., length negatively correlated with agreement and positively with accuracy spread; non-Claude models]
4. **Keep `THINKING_BUDGET=0` for the scored runs.**
   - Turn it on only if `--repeat` shows equal or fewer flips *and* the combined score rises above noise.
   - [Moderate: Anthropic docs say thinking is incompatible with temperature/prefill on Haiku 4.5; mixed accuracy evidence already in `haiku_inference_settings.md`]
5. **Do not use same-prompt majority-of-3 at T=0.**
   - If we ever vote, vote across differently framed prompts (checklist, holistic, adversarial), and only if it beats the cascade on dev.
   - [Weak to moderate: Rating Roulette gains of +1 to +2.5 points come from sampling, and no-sampling ≈ single run]
6. **Make example selection and order deterministic, with alternating labels and borderline-first.**
   - Check that `_pick_examples` produces a byte-identical prompt across runs.
   - [Weak to moderate: ICL order and selection effects; WOAH 2025; Rating Roulette shows few-shot does not change α]
