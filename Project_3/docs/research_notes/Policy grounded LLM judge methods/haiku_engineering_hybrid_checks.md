# Haiku 4.5 engineering settings and deterministic hybrid checks for a policy-compliance judge

Research date: 2026-11-13. This is a short pass. It skips what `../haiku_inference_settings.md` and `../haiku_multilingual_practice.md` already cover: model specs, temperature-0 non-determinism, `response_format` limits, rate-limit tiers, and latency figures. The code facts come from reading `starter_pack/final_judge.py`, `baseline_judge.py` and `run_judge.py` on 2026-11-13. All other claims are cited.

## Q1. Official Haiku 4.5 facts: thinking constraints, prefill, structured outputs, temperature

### Takeaway
Thinking on Haiku 4.5 has four hard constraints:
- It is manual "extended" thinking only. `adaptive` returns a 400 error.
- `budget_tokens` must be at least 1,024 and below `max_tokens`.
- While thinking is on, you cannot prefill the answer.
- While thinking is on, `temperature` and `top_k` are incompatible.

So thinking and prefill are mutually exclusive, and thinking costs us temperature 0. `final_judge._chat` already handles both: it drops the prefill and omits temperature when thinking is set. Without thinking, Haiku 4.5 keeps both prefill and temperature 0 on API versions before 2026-10-21.

### Cited Findings
- **Thinking modes by model.** In the per-model table, Haiku 4.5's thinking is "Extended only", its default is "Off", and `"adaptive"` is "Rejected with 400". — [Troubleshooting thinking](https://platform.claude.com/docs/en/build-with-claude/thinking-troubleshooting)
- **Budget rules.** `budget_tokens` has a "Minimum of 1,024 tokens. The API rejects smaller values" and must be "Less than `max_tokens`". The budget "is a target rather than a strict cap". For simple tasks, the docs advise to "start near the 1,024-token minimum". — [Extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- **Interleaved thinking.** "Claude Haiku 4.5 does not support interleaved thinking." — [Extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- **Prefill.** "Claude 4.6 and later models … reject a prefilled final assistant turn with a 400 error … On earlier models, you can't prefill the assistant response while thinking is on." — [Thinking, Limits and feature compatibility](https://platform.claude.com/docs/en/build-with-claude/thinking)
- **Sampling parameters.**
  - "On older models in API versions before `2026-10-21`, the restriction applies only while thinking is on: `temperature` and `top_k` are incompatible with thinking, and `top_p` is allowed at values between 0.95 and 1."
  - Under API version `2026-10-21`, sending `temperature`, `top_p` or `top_k` "at any value returns a 400 error on every model".

  — [Thinking](https://platform.claude.com/docs/en/build-with-claude/thinking)
- **Forced tool use.** It "is incompatible with manual extended thinking". This matters only if someone later moves the verdict into a forced tool call. — [Thinking](https://platform.claude.com/docs/en/build-with-claude/thinking)
- **Thinking tokens are billed output.** The billed count is reported in `usage.output_tokens_details.thinking_tokens`, which is native API only. The compat layer's `completion_tokens_details` is "Always empty". — [Extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking); [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)
- **Structured outputs.** Native structured outputs cover "Sonnet 4.5+, Opus 4.5+, and Haiku 4.5". This is LiteLLM's statement. The Anthropic page was cited in the earlier note. — [LiteLLM Anthropic provider](https://docs.litellm.ai/docs/providers/anthropic)
- **Temperature-0 determinism.** In this pass I found no Anthropic sentence saying that temperature 0 is fully deterministic. The compat layer documents `seed` as "Ignored" and `system_fingerprint` as "Always empty", so there is no reproducibility handle. — [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)

### Inferences
- **`THINKING_BUDGET > 0` changes the sampler, not only the reasoning depth.** It forces default sampling, i.e. temperature 1. Run-to-run consistency is scored, so the thinking setting needs `--repeat` runs to measure flips. A dev accuracy gain alone is not enough evidence.
- **The `PREFILL` and `THINKING_BUDGET` switches cannot both be on for the same call.** The code already enforces this: `prefill = ""` when thinking is set. Keep it that way, and say so in the experiments log, so that nobody reads "P_prefill + T_think" as a combination that ran.
- **If the gateway ever moves to `anthropic-version: 2026-10-21`, `temperature: 0` becomes a 400 error on every call.** On an error other than 429/5xx, the judge would fail every call (see Q4).

### Gaps
- I did not see what API version the hackathon gateway pins. Only the gateway probe (`probe_gateway.py`) can tell.

## Q2. Anthropic's OpenAI compatibility layer and LiteLLM: what passes through

### Takeaway
On Anthropic's own `/v1/chat/completions`:
- `temperature` (0–1), a trailing assistant message (prefill), `stop`, `max_tokens` and `thinking` as an extra body field all work.
- `response_format` must be `json_schema` with `strict: true`.
- The thinking text is not returned.
- Prompt caching is unsupported.

LiteLLM also forwards these, but adds its own defaults and mappings. Whether the gateway is Anthropic's layer, LiteLLM or another proxy is unknown, so a one-call probe per feature stays mandatory.

### Cited Findings
- **Anthropic compatibility layer, request fields.**
  - Thinking: "set the `thinking` field of the request body to `{"type": "enabled", "budget_tokens": N}`. `N` must be at least 1,024 and less than `max_tokens`".
  - Thinking output: "The response doesn't include Claude's thinking".
  - Adaptive thinking: `{"type":"adaptive"}` returns a 400 error.
  - Assistant `content` (string): "Fully supported".
  - `temperature`: "Between 0 and 1 … Values greater than 1 are capped at 1".
  - `temperature` together with `top_p`: a 400 error.

  — [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)
- **Anthropic compatibility layer, other gotchas.**
  - "Most unsupported fields are silently ignored rather than producing errors". A misspelled parameter fails silently.
  - "Prompt caching is not supported".
  - System messages are hoisted and concatenated with `\n`.
  - The layer "is not considered a long-term or production-ready solution".
  - Rate-limit headers: `retry-after` and `x-ratelimit-remaining-*` are "Fully supported", and `x-request-id` carries the Claude request ID.

  — [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)
- **LiteLLM parameters.**
  - OpenAI params it forwards to Anthropic: `stream, stop, temperature, top_p, max_tokens, max_completion_tokens, tools, tool_choice, extra_headers, parallel_tool_calls, response_format, user, reasoning_effort`.
  - It sends a default `max_tokens=4096` when the request omits it.

  — [LiteLLM Anthropic provider](https://docs.litellm.ai/docs/providers/anthropic)
- **LiteLLM prefill.** A trailing `assistant` message works as prefill, but "the returned completion does not include the prefill text, so you must prepend it yourself". Our code already handles both cases (`if prefill and not text.lstrip().startswith(prefill)`). — [LiteLLM Anthropic provider](https://docs.litellm.ai/docs/providers/anthropic)
- **LiteLLM thinking.**
  - `reasoning_effort` on pre-4.6 models maps low → 1024, medium → 2048, high → 4096 `budget_tokens`.
  - On 4.6/4.7 it maps to adaptive thinking plus `output_config.effort` instead.
  - You can also "pass the native `thinking` parameter directly".

  — [LiteLLM Anthropic provider](https://docs.litellm.ai/docs/providers/anthropic)
- **LiteLLM structured outputs.** It sends native `output_format` for Haiku 4.5 and newer. For older models it falls back to a forced `json_tool_call` tool. — [LiteLLM Anthropic provider](https://docs.litellm.ai/docs/providers/anthropic)
- **Community report: prefill on Haiku 4.5.** A GitHub issue reports a "does not support assistant message prefill" 400 error on claude-haiku-4.5. This contradicts Anthropic's docs and is unverified. It may come from a proxy, or from the model name being routed to a 4.6+ model. — [QwenLM/qwen-code#8039 (search result)](https://github.com/QwenLM/qwen-code/issues/8039); compare [Agno prefill note](https://www.agno.com/articles/fix-assistant-message-prefill-compatibility-for-claude-4-6-across-all-providers.md)

### Inferences
- **Prefill can fail silently.** If the gateway silently drops a trailing assistant message instead of returning a 400 error, the model writes a normal answer and our prepend still yields parseable `<json>`. If the gateway rejects it, every call fails. The probe must test PREFILL before the switch is flipped.
- **Missing temperature must be detected.** If the gateway drops `temperature`, both runs sample at temperature 1. The only external sign is a high flip rate on `--repeat`. Log the effective request body in the trace once per run.
- **Silent model substitution must be detected.** `STATS["models"]` already records `body["model"]`. Fail loudly if it is not a Haiku 4.5 ID, since a 4.6+ model would 400 on prefill.

### Gaps
- The gateway's identity is unknown: Anthropic, LiteLLM, Bedrock or OpenRouter. LiteLLM docs do not say how `temperature` is handled when `thinking` is passed. The docs I read do not mention `drop_params` / `modify_params`.

## Q3. Criterion-agnostic deterministic checks as hints

### Takeaway
The current number rule only sees digit tokens: `_NUM = r"(?<![\w.,])\d+(?:[.,]\d+)*"`. As a result:
- A reply that writes "zwei Wochen", "trente jours" or "fourteen days" is invisible to it.
- So is a policy that writes numbers in words.

Cheap, criterion-agnostic extractors for a small lexicon fit in about 60 lines of stdlib code:
- number words, roughly 0–31 plus the tens, hundred and dozen
- duration units
- currency
- modal and quantifier words
- condition markers and negation

They could feed a `<code_check>` hint. The evidence base for these hybrids:
- Domain papers report that rule-based checks catch numeric errors that semantic similarity misses, but none ablates the rule component.
- The anchoring literature warns that any visible cue pulls the verdict.

So the hints must be (a) neutral and bidirectional, (b) self-validated in `prepare()` the way the number rule is, and (c) measured with the leave-one-edit-type-out protocol.

### Cited Findings
- **Numeric checks must match value and unit.** A clinical-summary verifier combines LLM generation with an LLM-independent fact-checker using "numerical tests for correctness and logical checks". It reports P 0.890, R 0.823 and F1 0.856 on 3,786 propositions from 104 summaries. No ablation of the rule components was reported. — [arXiv:2512.16189](https://arxiv.org/abs/2512.16189)
- **Other hybrids are mostly descriptive.** A tolerance-based numeric filter on LLM explanations rejected 0% of outputs, which is weak evidence of benefit. A survey lists rule-based "logic validators" as a guardrail category without evaluating them. — [arXiv:2605.16452](https://arxiv.org/pdf/2605.16452); [arXiv:2508.01781](https://arxiv.org/pdf/2508.01781)
- **Hint anchoring.** LLMs are sensitive to biased hints, and "CoT, ignoring anchor hints, and reflection" did not remove the effect. — [arXiv:2412.06593](https://arxiv.org/abs/2412.06593)
- **Prior-score anchoring.** In one study, prior scores shown to a judge biased 7 of 8 models. This figure comes from a secondary summary. — [arXiv:2608.25869](https://arxiv.org/pdf/2608.25869)
- **Rationalization bias.** Judges align verdicts with non-evidential cues. Two mitigations were tested: blinding the cue until after judging, and requiring criterion-wise evidence before the verdict. — [arXiv:2605.23970](https://www.alphaxiv.org/abs/2605.23970)
- **Off-the-shelf number-word parsing.** The `text2num` package (Allo-Media) parses number words in FR, ES, EN, PT, DE, NL and IT, e.g. `text2num("ein und achtzig", "de") == 81`. It is a third-party dependency, so a hand lexicon is safer for a stdlib-only judge. — [text2num on GitHub](https://github.com/allo-media/text2num); [PyPI](https://pypi.org/project/text2num)

### Inferences
- **What to extract.** The design below is our own; no source prescribes it. Normalise both the policy and the reply into a set of typed tokens, then diff them. Each class:
  - **Number words to values.**
    - EN: one to twelve, twenty, thirty, hundred, dozen, half
    - DE: eins/ein/eine, zwei … zwölf, zwanzig, dreißig, hundert, halb
    - FR: un/une, deux … douze, vingt, trente, cent, demi
    - ES: uno/una, dos … doce, veinte, treinta, cien(to), medio
    - IT: uno/una, due … dodici, venti, trenta, cento, mezzo

    Add these values to `numbers_in()` so `policy_numbers` and `unknown_numbers` see them. Gate it with word boundaries and drop the articles "un/une/ein/uno" unless a unit follows. Otherwise "un client" becomes the number 1 and fires on harmless replies, which would make `_validate_number_rule` switch the rule off.
  - **Units and durations.** Normalise:
    - hours: h, Std., heures, horas, ore
    - days: Tage, jours, días, giorni
    - weeks: Wochen, semaines, semanas, settimane
    - months: Monate, mois, meses, mesi
    - currency: €, EUR, euro(s)
    - distance: km

    Then check (value, unit) pairs, not bare values. That catches "24 h → 48 h" even when 48 appears elsewhere in the policy for another unit. This is the value+unit idea from 2512.16189.
  - **Modal and quantifier lexicon.** Look for these words in the reply but not near the matching policy sentence, or the reverse:
    - EN: always, never, all, any, every, guaranteed, must, may, only
    - DE: immer, nie/niemals, alle, jede(r/s), garantiert, muss, kann, nur
    - FR: toujours, jamais, tous/toutes, garanti, doit, peut, seulement/uniquement
    - ES: siempre, nunca, todos, garantizado, debe, puede, solo
    - IT: sempre, mai, tutti, garantito, deve, può, solo

    Language detection is unnecessary, because the union lexicon has few cross-language collisions. Known collisions: "mai" is also the French month, and "solo"/"only" style words are common. Keep this as a count diff, not a verdict.
  - **Condition markers.**
    - EN: if, unless, provided that, as long as, only if
    - DE: wenn, falls, sofern, solange, vorausgesetzt, außer
    - FR: si, sauf si, à condition que, pourvu que, tant que
    - ES: si, salvo que, siempre que, a menos que, con tal de que
    - IT: se, purché, a meno che, a condizione che, sempre che

    Fire a hint when the policy sentence that shares the reply's number/unit carries a condition marker and the reply sentence carries none. That is the "dropped condition" pattern.

    Note that ES "siempre que" means "provided that", not "always". Match multiword markers before single modals.
  - **Negation.** EN not/no/never/without, DE nicht/kein/ohne, FR ne…pas/sans/aucun, ES no/sin/ningún, IT non/senza/nessun. The hint is a parity mismatch around a shared number/unit anchor. It is noisy, so keep it last in priority.
- **How to show hints (anti-anchoring).** Phrase every hint neutrally and in both directions:

  > Code found these items that differ between the reply and the policy: [...]. They may be harmless rewording. Decide yourself.

  Never say "violation". Prefer putting hints in call 2 (the second look), after call 1 has recorded its own claims, so the call-1 verdict stays unanchored. This follows the blinding mitigation in 2605.23970.
- **Self-validation on labelled examples (extend `_validate_number_rule`).** For each hint class h, compute on `_labelled_replies(dev_pairs)`:
  - `fire_pass` = fires on pass replies / pass replies
  - `fire_fail` = fires on fail replies / fail replies

  Then assign a mode:

  | Condition | Mode |
  |---|---|
  | `fire_pass == 0` and `fire_fail > 0` | `verdict`-capable (as now for numbers) |
  | `fire_fail - fire_pass ≥ δ` (e.g. 0.2) | `hint` |
  | otherwise | `off` |

  This is deterministic, uses only the labelled examples given to `prepare()`, and is criterion-agnostic, so it stays within the rules. With very few examples, require a minimum of about 3 fail fires before a class becomes `hint`. Otherwise one lucky fire turns a noisy lexicon on.
- **Measure the hints in two ways.**
  - Within each CV fold, pass only the training-fold examples to `prepare()`. This is already what `crossval.py` does, so the self-validation is honest.
  - Run leave-one-edit-type-out. A hint class that only helps on the edit type it was "learned" from is overfitting.

### Gaps
- No found study measures the accuracy gain from adding deterministic hints to an LLM judge prompt for policy compliance. The direction of the effect is unproven for our task. The dev CV must decide.
- No multilingual modal or condition lexicon with a cited evaluation was found. The word lists above are linguistic common knowledge, not sourced.

## Q4. Retry and parallelism for about 500 replies × up to 3 calls × 2 runs in 45 minutes

### Takeaway
The volume is at most 3,000 calls per criterion pair of runs, and at most 6,000 for both hidden sets. The previous note's per-call estimate of about 3 s is an inference from latency snapshots, not a measurement. Under that estimate, `run_judge.py --workers 8–12` finishes each run in a few minutes. The real risks are correctness, not speed:
1. `_RETRY_STATUS = {429, 500, 502, 503, 504}` does not include **529 (overloaded)**.
2. An unretried error raises `LLMError` for that reply.
3. A thundering-herd start can trip ramp-up 429s.

### Cited Findings
- **Ramp-up limits.** "After a sharp increase in usage, requests can return a 429 error even while you're under your ITPM and OTPM rate limits. A burst of requests within a few seconds can also count." The advice is to start bulk jobs at a low rate and honour `retry-after`. — [Rate limits](https://platform.claude.com/docs/en/api/rate-limits) (also in the earlier note)
- **Headers through the compat layer.** It returns `retry-after` and `x-ratelimit-remaining-requests/tokens`. — [OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)
- **Code fact: retry wait.** `baseline_judge._wait` honours `Retry-After`, capped at 60 s, with otherwise `2**attempt + jitter`. `MAX_RETRIES` defaults to 6. `run_judge.py` defaults to `--workers 5`. (Our repo: `starter_pack/baseline_judge.py:54,82`, `run_judge.py:86,123`.)
- **Status 529.** Anthropic uses HTTP 529 for "overloaded_error". Source: [Errors](https://platform.claude.com/docs/en/api/errors). This is from training knowledge plus the error page title; the exact wording was not re-fetched this pass.

### Inferences
- **Add 529 to the retried statuses** in `final_judge._chat`. Use a local set, so `baseline_judge.py` stays unchanged. A gateway may pass 529 through unchanged.
- **Stagger the start.** Run the hidden sets with `--workers 8`, or have each worker sleep `random.uniform(0, 2)` before its first call. Do not run both criteria at once with high worker counts.
- **Total retry wait.** With `MAX_RETRIES=6`, the worst case is about 2+4+8+16+32+60 ≈ 2 min per call. That is fine for liveness.
- **Fallback verdicts.** A reply whose call 2 or 3 fails after retries should fall back to the call-1 verdict, a deterministic and documented fallback. Losing the reply or raising is worse. Check that the judge does this. I did not verify the full control flow in this pass.
- **Two runs in parallel.** Running run 1 and run 2 concurrently halves wall time but doubles the burst. Run them sequentially unless time is short.

### Gaps
- The gateway's rate limits and whether it emits 529 are unknown. A 20-call pilot with `--workers 8` before 16:00 answers both.

## Ranked changes to final_judge.py (all behind default-off switches, measured by CV + LOETO before shipping)

1. **Retry 529 (and 408) in `_chat`.** Use a local status set; no verdict change. This is pure robustness and is safe to ship before freeze without an experiment. It is backed by Q4.
2. **Number words in `numbers_in()`** (switch `NUMBER_WORDS`). This is a small EN/DE/FR/ES/IT lexicon, 0–31 plus tens, hundred, dozen and half, with article guard words. It fixes the rule's blind spot for spelled-out numbers on both the policy and the reply side. Measure:
   - whether `_validate_number_rule` still picks the same mode on dev
   - the stress set's harmless-fire count
2. **Unit-aware numbers** (switch `NUMBER_UNITS`). Compare (value, normalised unit) pairs instead of bare values, which reduces both false "not in policy" fires and misses. Keep it as a hint unless the validation reaches `fire_pass == 0`.
3. **Neutral lexicon-diff hints for modals, quantifiers, conditions and negation** (switch `LEXICON_HINTS`).
   - Each class is self-validated in `prepare()` with the `fire_fail - fire_pass ≥ δ` rule.
   - Hints are shown only in call 2, phrased in both directions ("may be harmless").
   - Highest upside on dropped-condition and certainty edits, and highest anchoring risk. Ship only if LOETO holds.
4. **Gateway guard at startup.** Fail loudly in three cases:
   - `STATS["models"]` is not a Haiku 4.5 ID.
   - `PREFILL` is on and the probe shows the trailing assistant message was rejected.
   - Any call returns a 400 error mentioning temperature. This would mean API version 2026-10-21; in that case retry once without `temperature`.

   No verdict change.
5. **Thinking experiment hygiene, not a code change.** Report `T_think*` only with `--repeat` flip rates, because thinking forces default sampling and disables prefill on Haiku 4.5 (Q1). Expect lower consistency. Ship thinking only if the combined score, consistency included, rises.
