# Practical implementation of a binary multilingual LLM judge on Claude Haiku 4.5 through an OpenAI-compatible endpoint

Research date: 2026-11-12. All docs were fetched live from platform.claude.com, which docs.claude.com and docs.anthropic.com now redirect to. Inferences are labelled as inferences.

## Q1. Claude Haiku 4.5: facts, and Anthropic's prompting guidance for classifiers and judges

### Takeaway
Haiku 4.5 (`claude-haiku-4-5-20251001`) is now a *legacy* model with a 200K context window, 64K max output, $1/$5 per MTok and manual extended thinking. It still supports prefill and temperature, which Claude 4.6+ models do not. Anthropic's guidance for a judge prompt:
- Put long material (the policy) first and the question last.
- Wrap each part in XML tags.
- Give 3–5 examples in `<example>` tags.
- For classification, use an enum, structured outputs or a tag-delimited answer.

### Cited Findings
- **Release and positioning.** Released October 15, 2025, as Anthropic's small model, priced at $1 per MTok input and $5 per MTok output. Pitched for low-latency work such as chat assistants and customer service agents. Claimed "similar levels of coding performance [to Sonnet 4] but at one-third the cost and more than twice the speed." — [Anthropic announcement](https://www.anthropic.com/news/claude-haiku-4-5)
- **Specs.** Model ID `claude-haiku-4-5-20251001`, alias `claude-haiku-4-5`. Context window 200K tokens, max output 64K. Thinking is "Extended" (manual `budget_tokens`, not adaptive), and the effort parameter is not supported. Reliable knowledge cutoff Feb 2025, training data cutoff Jul 2025. — [Haiku 4.5 model page](https://platform.claude.com/docs/en/models/haiku-4-5/overview)
- **Lifecycle (as of Nov 2026).** Status is "Active (legacy)", with retirement "Not sooner than October 15, 2026". Anthropic recommends migrating to Claude Haiku 5.5, whose description reads "For high-volume, latency-sensitive tasks such as classification, extraction, and routing". Anthropic gives at least 60 days' notice before retirement. — [Haiku 4.5 page](https://platform.claude.com/docs/en/models/haiku-4-5/overview); [Model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations); [Models overview](https://platform.claude.com/docs/en/models/overview)
- **Benchmarks.** The announcement cites a 128K thinking budget for most of its benchmarks. It also reports MMMLU (multilingual MMLU) results, but no number was in the extracted text. — [Announcement](https://www.anthropic.com/news/claude-haiku-4-5)
- **Prompting guidance for Haiku 4.5.** The best-practices guide explicitly covers Haiku 4.5. — [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **XML tags.** "XML tags help Claude parse complex prompts unambiguously, especially when your prompt mixes instructions, context, examples, and variable inputs. Wrapping each type of content in its own tag (for example, `<instructions>`, `<context>`, `<input>`) reduces misinterpretation." — [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Long documents first.** "Place your long documents and inputs near the top of your prompt, above your query, instructions, and examples." "Queries at the end can improve response quality by up to 30 percent in tests, especially with complex, multidocument inputs." — [same](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Examples.** "Wrap examples in `<example>` tags (multiple examples in `<examples>` tags)… Include 3–5 examples for best results." — [same](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Prefill on newer models.** Prefill is "no longer supported starting with Claude 4.6 models… Earlier models continue to support prefills." So Haiku 4.5 still supports prefill.
- **Output-format control.** The guide's recommended pattern is: "For classification tasks, use either tools with an enum field containing your valid labels or structured outputs." Alternatively, "direct the model to output within XML tags… If the occasional preamble slips through, strip it in post-processing." — [same](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Prefill mechanics.** If the final message has the `assistant` role, the response continues from it. Example: `{"role":"assistant","content":"The best answer is ("}`. — [Messages API reference](https://platform.claude.com/docs/en/api/messages/create)

### Inferences
- **Recommended message layout (inference from the guidance above).**
  - *System message:* the role ("strict QA judge for customer-support replies") and the output contract.
  - *User message, in this order:*
    1. `<policy>` (English, longest part first)
    2. `<criterion>`
    3. `<question>`
    4. `<reply lang="de">`
    5. 2–4 `<example>` blocks with balanced pass and fail cases
    6. Final instruction: "Think briefly in `<reasoning>` (≤5 sentences, in English), then output `<verdict>PASS</verdict>` or `<verdict>FAIL</verdict>`."
- **Do not rely on the model's own knowledge.** Haiku 4.5's knowledge cutoff (Feb 2025) does not matter here, because the policy is supplied in the prompt. The prompt should say "judge only against the policy text provided".
- **Legacy status risk.** Haiku 4.5 is past its "not sooner than" retirement date. The hackathon endpoint may stop serving it, or may route the name elsewhere. Log `response.model` on every call to detect silent substitution.

### Gaps
- No published numbers specifically on Haiku 4.5 as a binary judge or classifier (accuracy versus Sonnet) were found.
- Haiku 4.5's MMMLU score was not extractable from the announcement text.

## Q2. Determinism: is temperature 0 deterministic on Claude, and how do you maximize run-to-run agreement?

### Takeaway
No. Temperature 0 on hosted Claude, Haiku 4.5 included, reduces but does not eliminate verdict flips. Flips concentrate on borderline items. Haiku 4.5 still accepts `temperature: 0` via the OpenAI-compatible layer and API version 2023-06-01, but the 2026-10-21 native API version rejects all sampling params. The most reliable consistency levers are:
- short, tightly-rubric'd reasoning
- explicit decision rules for edge cases
- majority voting within the 3-call budget
- (if the rules allow) caching verdicts by input hash

### Cited Findings
- **Root cause of nondeterminism at temperature 0.** Batch-size variance on inference servers: "the load (and thus batch-size) nondeterministically varies." In the source's experiment, 1000 completions at temperature 0 gave 80 unique outputs. Batch-invariant kernels made all 1000 identical. — [Thinking Machines, "Defeating Nondeterminism in LLM Inference"](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- **No seed.** `seed` is "Ignored" in the OpenAI-compatible layer, so there is no seed-based reproducibility, and `system_fingerprint` is "Always empty". — [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)
- **Temperature in the compat layer.** `temperature` is accepted "Between 0 and 1 (inclusive)". Claude 4.7+ return 400 for values below 1, which does not affect Haiku 4.5. Setting both `temperature` and `top_p` returns a 400 error. — [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)
- **Temperature in native API version 2026-10-21.** Sending `temperature`, `top_p` or `top_k` "returns a 400 error, even at the parameter's default value." On models that accept other values, a request that lowered temperature "loses that effect… If a request relies on a non-default value, either stop sending the parameter, or keep that request on `2023-06-01`." — [Migration to 2026-10-21](https://platform.claude.com/docs/en/api/migration-2026-10-21)
- **Empirical flips on Claude judges.** A 2026 preprint tested Claude Haiku 4.5 and Sonnet 4.6 as graders under forced greedy decoding (top_k=1). Haiku "flipped the same item at the same rate as Sonnet." 1–2 of 7 borderline items stayed non-reproducible in every condition, and on Sonnet 4.6 one item split 8/2 over 10 runs. Its mitigations:
  - pin temperature 0
  - run multiple epochs and report variance
  - treat grader disagreement as a health metric
  - log the effective config

  The sample is small (N=10 per item), so the findings are qualitative. — [arXiv:2606.26185, "Necessary but Not Sufficient"](https://huggingface.co/papers/2606.26185.md)
- **Majority votes need many trials.** With two OpenAI judges, 11 trials were needed on average for a majority vote to recover the 50-trial reference verdict with 95% probability. — [arXiv:2606.13685, "The Coin Flip Judge?"](https://arxiv.org/pdf/2606.13685) (secondary, search-snippet level)
- **Conflicting evidence.** One study found judges "consistent in their verdicts when subjected to repeated sampling" (5 runs, temperature 0, TruthfulQA). — [arXiv:2408.09235](https://arxiv.org/pdf/2408.09235) (search-snippet level)

### Inferences
- **Instability sits at the decision boundary.** Most replies will be stable at temperature 0. The run-to-run disagreement budget is consumed by borderline replies, which matches the preprint's finding. Make the rubric decisive on borderline cases. For example: "If the reply omits a fact required by the policy, FAIL. If it only rephrases, PASS." Also state a default tie-break such as "If uncertain, output FAIL", or PASS if the scorer penalises false fails more.
- **Short, structured reasoning helps.** It narrows the space of generations and therefore the divergence points, compared with long free-form CoT. Put the verdict token in a fixed tag at the end so the parse is unaffected by wording drift.
- **Voting within the 3-call cap.** Call 1 at temperature 0. Optionally make a second call. If calls 1 and 2 disagree, use call 3 as the tie-breaker. This roughly halves the extra cost versus always doing 3 calls. Note that k=3 voting does not fully remove flips, given the 11-trial figure above.
- **Verdict cache across runs.** If the hackathon rules allow state across runs, a persistent cache keyed on `sha256(model + prompt_version + question + criterion + reply)` guarantees identical verdicts across the two consistency runs. This is the single biggest consistency lever. Check the rules first, since it could be viewed as gaming.
- **Proxy may not forward temperature.** If the hackathon's OpenAI-compatible endpoint is a proxy (LiteLLM, OpenRouter, Bedrock gateway), check that it actually forwards `temperature: 0`. Some gateways drop or override sampling params.

### Gaps
- No Anthropic-published flip-rate numbers for temperature 0 were found.
- The exact current wording in Anthropic's docs that "temperature 0.0 is not fully deterministic" was not re-verified; it is only quoted by secondary sources such as [Agno](https://www.agno.com/articles/honor-temperature-0-on-claude-for-deterministic-output).

## Q3. Structured JSON output through the OpenAI-compatible layer, and parsing the verdict robustly

### Takeaway
Through Anthropic's own compatibility layer:
- `response_format` works only as `json_schema` with `strict: true`. `json_object` returns 400.
- `stop` works for non-whitespace sequences.
- `n` must be 1.
- System messages are hoisted into Claude's `system`.

For a stdlib-urllib client against an unknown proxy, the most portable choice is plain text with XML-tagged output and a regex parse, with structured output as an optional upgrade.

### Cited Findings
- **`response_format`.** "Only `json_schema` with `strict: true` is accepted… Any other value, including `json_object` and `text`, returns a 400 error." — [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)
- **`strict` on tools is ignored.** "tool use JSON is not guaranteed to follow the supplied schema." — [same](https://platform.claude.com/docs/en/api/openai-sdk)
- **System and developer messages.** They are "hoisted and concatenated into the top-level `system` field, wherever they appear," joined with a single `\n". — [same](https://platform.claude.com/docs/en/api/openai-sdk)
- **Field support.**

  | Field | Support |
  |---|---|
  | `max_tokens` / `max_completion_tokens` | Fully supported |
  | `stop` | "All non-whitespace stop sequences work" |
  | `n` | Must be 1 |
  | `logprobs` | Ignored, so no confidence scores from logprobs |
  | `seed` | Ignored |
  | `reasoning_effort` | Ignored |
  | `usage.prompt_tokens_details` | Always empty, so no cache stats |

  Assistant-role `content` (string) is "Fully supported". — [same](https://platform.claude.com/docs/en/api/openai-sdk)
- **Thinking via the compat layer.** Haiku 4.5 needs `"thinking": {"type":"enabled","budget_tokens":N}` with N ≥ 1,024 and N < `max_tokens`. The response does not include the thinking text. — [same](https://platform.claude.com/docs/en/api/openai-sdk)
- **Production status.** Anthropic says the compat layer "is primarily intended to test and compare model capabilities, and is not considered a long-term or production-ready solution." — [same](https://platform.claude.com/docs/en/api/openai-sdk)
- **Structured outputs on Haiku 4.5.**
  - Haiku 4.5 is supported.
  - The first use of a schema adds grammar-compile latency, and compiled grammars are cached 24h.
  - `enum` of strings is supported. `additionalProperties` must be `false`.
  - min/max numeric and string-length constraints are unsupported (400 error).
  - Structured outputs add an extra system prompt, so input tokens rise.

  — [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

### Inferences
- **Option A (portable, recommended).** Plain text response with `<reasoning>…</reasoning><verdict>PASS|FAIL</verdict>`.
  - Parse with `re.findall(r"<verdict>\s*(PASS|FAIL)\s*</verdict>", text, re.I)` and take the **last** match.
  - Fallback 1: the last standalone PASS/FAIL token in the final 50 characters.
  - Fallback 2: re-ask once (counts toward the 3-call cap) or apply the default tie-break.
  - Do **not** set `stop=["</verdict>"]`. Stop sequences are excluded from the returned text, so the closing tag disappears. If you use it, make the regex tolerate a missing closing tag.
- **Option B: `response_format` json_schema.** Use `{"type":"json_schema","json_schema":{"name":"verdict","strict":true,"schema":{"type":"object","properties":{"reasoning":{"type":"string"},"verdict":{"type":"string","enum":["PASS","FAIL"]}},"required":["reasoning","verdict"],"additionalProperties":false}}}`. List `reasoning` before `verdict` so the model reasons first.
  - This guarantees parseability on Anthropic's endpoint.
  - Risk: a third-party proxy may reject it or translate it differently. Test once before relying on it.
- **Option C: prefill.** Haiku 4.5 still supports prefill, so ending `messages` with `{"role":"assistant","content":"<reasoning>"}` should force the format. It is not documented whether every proxy passes a trailing assistant message as prefill. Verify with one test call.
- **Use the full `max_tokens` budget for the tags.** Set `max_tokens` so reasoning plus the verdict tag always fit (e.g. 300–400). Check `finish_reason == "length"` and treat it as a parse failure.

### Gaps
- It was not verified how the specific hackathon endpoint (likely a gateway, not api.anthropic.com) handles `response_format`, `stop` and trailing assistant messages. Run one smoke test per feature.

## Q4. Output tokens, latency, throughput and rate-limit tactics

### Takeaway
Haiku 4.5 non-reasoning runs at about 90–100 output tok/s with roughly 0.7–1.0 s time to first token. A short reasoning judge (about 100–200 output tokens) should take about 2–3 s per call. 450 replies × ≤3 calls × 4 runs fits in 45 minutes with modest concurrency (8–16) and retry with backoff. Avoid extended thinking: it pushes latency to 10–18 s per call.

### Cited Findings
- **Non-reasoning speed.** About 91 tok/s on Anthropic's API, about 102 on Amazon. Time to first token is about 1.0 s on Anthropic and 0.66 s on Vertex (median, 72h window). — [Artificial Analysis, Haiku 4.5 providers](https://artificialanalysis.ai/models/claude-4-5-haiku/providers) (snapshot figures vary)
- **Reasoning variant.** End-to-end latency is about 10–18 s, including thinking. — [Artificial Analysis, Haiku 4.5 reasoning](https://artificialanalysis.ai/models/claude-4-5-haiku-reasoning/providers)
- **Anthropic rate limits for Haiku 4.5.**

  | Tier | RPM | ITPM | OTPM |
  |---|---|---|---|
  | Start | 1,000 | 2M | 400K |
  | Build | 5,000 | 5M | 1M |
  | Scale | 10,000 | 10M | 2M |

  The limiter is a token bucket, and a 60 RPM limit "might be enforced as 1 request per second." — [Rate limits](https://platform.claude.com/docs/en/api/rate-limits)
- **Ramp limits.** "After a sharp increase in usage, requests can return a 429 error even while you're under your ITPM and OTPM rate limits. A burst of requests within a few seconds can also count." Advice: "Start scheduled or bulk jobs at a low rate and spread requests evenly." Honor `retry-after`. — [Rate limits](https://platform.claude.com/docs/en/api/rate-limits)
- **`max_tokens` does not count against OTPM.** "The `max_tokens` parameter does not factor into OTPM rate limit calculations." — [Rate limits](https://platform.claude.com/docs/en/api/rate-limits)
- **Headers through the compat layer.** It returns `retry-after` and `x-ratelimit-remaining-*` / `x-ratelimit-reset-*`. — [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)

### Inferences
- **Per-call latency.** About 150 output tokens at roughly 90 tok/s is about 1.7 s, plus about 1 s TTFT, so **about 2.5–3 s per call**. A 2–3K-token prompt adds little prefill time.
- **Per-run time.** 450 calls × 3 s / 12 workers ≈ 2 minutes per run with 1 call per reply, or about 6 minutes with 3 calls. Four runs fit comfortably in 45 minutes.
- **Request rate.** At about 4–5 req/s (240–300 RPM), even the Start tier (1,000 RPM) has headroom. The binding constraint is likely the hackathon proxy's own quota, which is unknown.
- **stdlib client pattern.** Use `concurrent.futures.ThreadPoolExecutor(max_workers=8–16)` with `urllib.request` and a per-request `timeout=60`.
  - Retry on 429, 5xx, 529 (overloaded) and `URLError`, with exponential backoff and jitter (1, 2, 4, 8 s, max 5 tries). Honor `retry-after`.
  - Ramp up concurrency over the first 30 s to avoid ramp-limit 429s.
  - Write results incrementally to disk so a crash doesn't lose a run.
- **Fallback must be deterministic.** A failed call must not silently become a random verdict. A deterministic fallback (the default tie-break) keeps the two runs consistent.
- **No extended thinking.** Its minimum is 1,024 budget tokens, it adds about 10 s per call, and its output isn't returned via the compat layer. Use a short visible `<reasoning>` block instead.

### Gaps
- The hackathon endpoint's rate limits and its latency overhead are unknown. Measure p50/p95 latency with a 20-request pilot.

## Q5. Multilingual judging (EN/DE/FR/ES/IT): accuracy, English pivoting, cross-lingual consistency

### Takeaway
For high-resource European languages, Claude's capability gap versus English is small: about 1–3% relative on Global-MMLU for current Haiku. The multilingual LLM-as-judge literature still finds judges noticeably *inconsistent across languages*: average Fleiss' κ ≈ 0.3 across 25 languages, with rank inversions on pragmatic criteria. The evidence on "translate to English first" is mixed: it can introduce translationese and score shifts. A pragmatic design:
- keep the reply in its original language
- give the policy and rubric in English
- have the model reason in English, explicitly citing the relevant phrase from the original-language reply
- validate per-language pass rates on a labelled sample

### Cited Findings
- **Global-MMLU relative to English.** Current Haiku (Haiku 5.5): Spanish 98.1%, Italian 97.7%, French 97.7%, German 97.4% of its English score. Anthropic notes "Differences of less than about 1 percentage point are within measurement noise." Haiku 4.5 is no longer in this table. — [Multilingual support](https://platform.claude.com/docs/en/build-with-claude/multilingual-support)
- **Anthropic's multilingual advice.** "Explicitly stating the input and output languages you want improves reliability." "Submit text in its native script." State the language in the system prompt. — [Multilingual support](https://platform.claude.com/docs/en/build-with-claude/multilingual-support)
- **Fu & Liu (2025): multilingual judges are unreliable.** Five models, five tasks, 25 languages, average Fleiss' κ "approximately 0.3". Consistency is "particularly poor in low-resource languages." "Neither training on multilingual data nor increasing model scale directly improves judgment consistency." An ensemble strategy improves consistency. Conclusion: "LLMs are not yet reliable for evaluating multilingual predictions." — [arXiv:2505.12201](https://arxiv.org/abs/2505.12201)
- **Fu & Lu (2026): languages carry complementary signal.** "sampling judgments across languages yields a higher performance upper bound than single-language judging." Their SEMJ method (multilingual variants, then judgments, then reflection on inconsistent ones) beats voting and reflection baselines on accuracy and cross-lingual consistency. — [arXiv:2606.08092](https://arxiv.org/abs/2606.08092)
- **Chung & Freienthal (2026): pragmatic criteria are unstable across languages.** On synthetic customer-support dialogues (Estonian/Finnish/Hungarian), surface metrics are stable across languages. Pragmatic judgments (coherence, instruction-following) show "rank inversions and near-zero correlations." Recommendation: calibrate judges per language against human baselines. — [arXiv:2602.02287](https://arxiv.org/abs/2602.02287)
- **CE-Judge (2025).** It translates the instruction and response to English only to *generate checklists*, but judges the untranslated text "to avoid translation bias." Its per-language accuracy is not English-dominant (en 0.81, fr 0.72, bn 0.84). It does not isolate the effect of translation. — [arXiv:2507.06774](https://arxiv.org/html/2507.06774v2)
- **Translation can shift scores.**
  - A 2026 preprint names "translationese bias", where multilingual judges favour text resembling translated English. — [alphaxiv 2603.10351](https://www.alphaxiv.org/abs/2603.10351.md) (search-snippet level)
  - Another study found a GPT-3.5 judge scored native-language pairs slightly higher than their English translations. — [ACL GlobalNLP 2025](https://aclanthology.org/anthology-files/pdf/globalnlp/2025.globalnlp-1.21.pdf) (search-snippet level)
- **Criteria decomposition transfers better.** Decomposing evaluation into explicit criteria is proposed to transfer better across languages than holistic judging. — [arXiv:2603.18557](https://arxiv.org/pdf/2603.18557) (search-snippet level)

### Inferences
- **Small gap, real but manageable risk.** For DE/FR/ES/IT the raw comprehension gap on Haiku-class models is small, so most cross-lingual inconsistency risk comes from *criterion interpretation*, not comprehension. That favours:
  1. an English rubric with concrete, language-independent checks (facts, numbers, dates, prices, conditions, prohibited promises);
  2. asking the model to quote the relevant span of the original-language reply and gloss it in English inside `<reasoning>`, which grounds it without a full translation;
  3. a fixed reasoning language (English) so that rubric terms map identically across languages.
- **Avoid a separate translation call.** A full translate-then-judge pipeline spends one of the 3 calls and risks translation errors on exactly the details a "meaning edit" judge must catch, such as negations, modal verbs ("kann" vs "muss") and numbers. Mitigate with an in-prompt instruction: "Pay special attention to negation, modality, numbers, dates and conditions; these often differ subtly across languages."
- **Measure per language.** Measure per-language PASS rates and agreement on the labelled dev set. If one language is systematically stricter or laxer, add language-specific few-shot examples, e.g. one German and one French `<example>`.
- **SEMJ is out of budget.** The cross-language upper-bound result suggests a 2-language vote (original plus English rendering) could help, but it costs calls. Use it only for borderline cases detected by call-1/call-2 disagreement.

### Gaps
- No paper was found that reports Claude Haiku 4.5 specifically as a multilingual judge on DE/FR/ES/IT.
- No controlled study was found that isolates "reason in English" versus "reason in the reply's language" for Claude judges.
- MM-Eval (pairwise multilingual meta-eval) numbers were not retrieved.

## Q6. Prompt caching for the repeated policy-and-criterion prefix

### Takeaway
It will not work here. Prompt caching is not supported through Anthropic's OpenAI-compatible layer. Even natively, Haiku 4.5 requires at least 4,096 tokens in the cacheable prefix, and shorter prefixes silently go uncached. Plan for full-price, uncached input; at Haiku pricing this is cheap anyway.

### Cited Findings
- **Not supported via compat.** "Prompt caching is not supported, but it is supported in the Anthropic SDKs." — [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)
- **Minimum length.** Haiku 4.5's minimum cacheable length is "4,096 tokens". "Any requests to cache fewer than this number of tokens are processed without caching, and no error is returned." — [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- **TTL and pricing.** Default TTL is 5 minutes, refreshed on use; a 1h option exists. For Haiku 4.5: 5m write $1.25/MTok, 1h write $2/MTok, read $0.10/MTok. — [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching); [Haiku 4.5 page](https://platform.claude.com/docs/en/models/haiku-4-5/overview)
- **Cache reads and rate limits.** Cache reads don't count toward ITPM. This is mainly a throughput lever on the native API. — [Rate limits](https://platform.claude.com/docs/en/api/rate-limits)

### Inferences
- **Keep the prompt order cache-friendly anyway.** Put the static prefix first (system, then policy, then criterion, then examples) and the variable parts (question, reply) last. That order matches Anthropic's long-docs-first advice, enables caching if the endpoint ever supports it, and costs nothing.
- **Cost estimate.** About 3K input tokens × 450 × 3 calls × 4 runs ≈ 16M input tokens, roughly $16. Output at about 200 tokens per call ≈ 1.1M tokens, roughly $5.5. Caching wouldn't materially matter.

### Gaps
- It is unknown whether the hackathon gateway adds its own caching layer. Watch `usage.prompt_tokens` and latency for hints, though `prompt_tokens_details` is always empty via compat.
