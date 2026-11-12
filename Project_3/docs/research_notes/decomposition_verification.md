# Claim Decomposition and Reference-Grounded Verification for a Single-Reply Policy Judge

Scope: methods that split a response into claims and check each against a reference (here, the company policy), and how to fit them into claude-haiku-4.5 with at most 3 LLM calls per reply. Sections marked "Inferences" are my own reasoning about how this applies to the hackathon task. They are not findings from the sources.

## Q1. How do FActScore, SAFE, RefChecker, MiniCheck, AlignScore/SummaC and QA-based metrics decompose and verify, how well do they catch subtle errors, and what do they cost?

### Takeaway
All of these use "decompose then verify": split the response into atomic facts, sentences or triplets, then label each one supported, contradicted or neutral against evidence. The LLM-AggreFact results show that small fine-tuned checkers (MiniCheck, AlignScore) or one strong LLM call reach about GPT-4 accuracy. Fine-grained decomposition costs 2-4x more and does not reliably improve accuracy. Granularity and context preservation matter more than how fine the split is.

### Cited Findings
- **FActScore** (Min et al., 2023) splits a long generation into atomic facts and reports the fraction supported by a knowledge source. Its automated estimator uses retrieval plus a strong LM. The paper reports less than 2% error versus humans. — [FActScore arXiv 2305.14251](https://arxiv.org/abs/2305.14251)
- **Cost of FActScore-style checking:** biographies contain 26-41 atomic facts, each checked against 5 documents, which comes to 130-205 entailment checks per response. — [MiniCheck paper](https://arxiv.org/html/2404.10774v2)
- **SAFE** (Google DeepMind, 2024) uses an LLM to split a response into individual facts, then checks each one with multi-step Google Search queries. The implementation used gpt-3.5-turbo-0125 plus Serper. — [Long-form factuality, arXiv 2403.18802](https://arxiv.org/abs/2403.18802v2)
- On about 16k facts, SAFE agreed with crowdsourced annotators 72% of the time. On 100 sampled disagreements, SAFE was judged right 76% of the time. — [arXiv 2403.18802](https://arxiv.org/pdf/2403.18802)
- Rating one response cost about $0.19 with SAFE versus about $4.00 with human annotation, as reported by press coverage. — [the-decoder](https://the-decoder.com/large-language-models-with-google-access-outperform-humans-in-factual-accuracy-study-finds/)
- Critics note that the baseline was crowd workers, not expert fact-checkers, so the "superhuman" framing is contested. — [VentureBeat](https://venturebeat.com/ai/google-deepmind-unveils-superhuman-ai-system-that-excels-in-fact-checking-saving-costs-and-improving-accuracy)
- **RefChecker** (Amazon, EMNLP 2024): an extractor turns the response into knowledge triplets (subject, predicate, object). A checker labels each triplet against a reference as Entailment, Contradiction or Neutral. — [RefChecker arXiv 2405.14486](https://arxiv.org/abs/2405.14486); code at [github.com/amazon-science/RefChecker](https://github.com/amazon-science/RefChecker)
- RefChecker's authors report that triplet-level checking beats response-, sentence- and sub-sentence-level checking. The size of the gain differs by version: 6.8-26.1 points in arXiv v1 and 18.2-27.2 points in the EMNLP version. — [arXiv html v1](https://arxiv.org/html/2405.14486v1); [ACL Anthology 2024.emnlp-main.395](https://preview.aclanthology.org/setup/2024.emnlp-main.395)
- A review notes that RefChecker gives only basic localization of which part of the reference supports or contradicts a claim. — [themoonlight review](https://www.themoonlight.io/review/refchecker-reference-based-fine-grained-hallucination-checker-and-benchmark-for-large-language-models)
- **MiniCheck** (Tang, Laban and Durrett, EMNLP 2024) checks each sentence against grounding documents. It is trained on synthetic data (C2D and D2C) built so that a claim needs several facts, each requiring two document sentences combined, to be verified. — [MiniCheck arXiv 2404.10774](https://arxiv.org/html/2404.10774v2)
- LLM-AggreFact balanced accuracy (average over 10 datasets): MiniCheck-FT5 (770M) 74.7, GPT-4 75.3, Claude-3 Opus 74.1, Claude-2.1 70.7, AlignScore 70.4, SummaC-ZS 67.9, SummaC-CV 62.1. — [MiniCheck paper](https://arxiv.org/html/2404.10774v2)
- **Cost** on the 13K-example test set: MiniCheck-FT5 $0.24, AlignScore $0.20, GPT-4 $107, Claude-3 Opus $165, GPT-4 with claim decomposition $212. — [MiniCheck paper](https://arxiv.org/html/2404.10774v2)
- **Decomposition did not consistently help.** Change in average balanced accuracy with decomposition: GPT-4 +0.3, SummaC-ZS +1.2, AlignScore +1.1, MiniCheck-FT5 −1.4, SummaC-CV −3.3. Inference cost rose 2-4x, and the authors advise against decomposition without a clear benefit. — [MiniCheck paper](https://arxiv.org/html/2404.10774v2)
- Current LLM-AggreFact leaderboard (no update date shown on the page): top systems score about 78.5-79.5 (nimble-v4-max 79.5, Clef 79.0). Bespoke-MiniCheck-7B 77.4, Claude-3.5 Sonnet 77.2, gpt-4o-2024-05-13 75.9, MiniCheck-Flan-T5-L 75.0. No Haiku model is listed. — [llm-aggrefact.github.io](https://llm-aggrefact.github.io/)
- **AlignScore** (ACL 2023) is a RoBERTa model (125M or 355M) trained as a unified "information alignment" function over many tasks. The 355M version matches or beats ChatGPT- and GPT-4-based metrics. On the SummaC benchmark it averages 88.6 AUC-ROC, versus 81.0 for SummaC-Conv and 72.5 for QuestEval (QA-based). — [AlignScore arXiv 2305.16739](https://arxiv.org/pdf/2305.16739); [ACL Anthology](https://aclanthology.org/2023.acl-long.634.pdf)
- QA-based QuestEval varies widely across datasets in the AlignScore comparison: 60.4 on CGS and 85.8 on FRANK. — [AlignScore paper](https://arxiv.org/pdf/2305.16739)
- **Granularity research (2024-2026):** decompose-then-verify faces a trade-off. Atomic facts lose context needed for verification, while coarse statements are too broad for the verifier. — [TriQua arXiv 2608.05228](https://arxiv.org/pdf/2608.05228)
- The decomposition step "can have a significant effect on downstream factuality scores." — [arXiv 2412.13175](https://export.arxiv.org/pdf/2412.13175)
- Different decomposition prompts trade off precision, verifiability and coverage. — [arXiv 2503.15354](https://arxiv.org/pdf/2503.15354)
- Subclaims should match the granularity the verifier expects ("atomicity alignment"). — [arXiv 2602.21857](https://arxiv.org/pdf/2602.21857)
- **Claimify** (Microsoft, ACL 2025) aims to keep critical context in each extracted claim. It flags referential and structural ambiguity and refuses to extract a claim when the reading can't be resolved. Each claim should be understandable alone and should "minimize the risk of excluding critical context." — [Microsoft Research](https://www.microsoft.com/en-us/research/?p=1134179); [ACL 2025 paper](https://preview.aclanthology.org/landing_page/2025.acl-long.348.pdf)

### Inferences (applicability, my own)
- Here the "reference" is a short policy table, not retrieved web pages, so the expensive part of SAFE and FActScore (retrieval plus many checks) disappears. A whole policy fits in one Haiku context, which makes a single-call "extract + verify" design realistic.
- The MiniCheck result that decomposition adds about 0 points with GPT-4 suggests Haiku may not need a separate decomposition call. However, LLM-AggreFact mostly tests unsupported or contradicted content. Our failure modes (dropped condition, hedge removal) are different, so decomposition may still help when its purpose is to make conditions and hedges explicit as fields, not to split facts finer.
- Atomic-fact decomposition can strip exactly the qualifiers we need, such as "if not reserved" or "usually." Following Claimify, the extraction schema should keep qualifiers attached to each claim, for example `{claim, condition_stated, hedge_stated, number}`, so verification can compare them.
- RefChecker-style triplets lose conditions and modality, because conditions do not fit naturally into (subject, predicate, object). They are a poor fit for this task unless extended with condition and modality slots.

### Gaps
- I found no LLM-AggreFact numbers for claude-haiku-4.5. Only Claude-3.5 Sonnet (77.2) and older Claude models are listed.
- I did not fetch the FActScore paper itself. The less-than-2% estimator error figure comes from my knowledge of the abstract at the cited URL and should be checked there.
- I found no source testing whether these checkers catch hedge removal or more-generous numbers specifically.

## Q2. Can these methods detect omissions and missing conditions (checking from the reference to the response)?

### Takeaway
Standard faithfulness checkers verify only response → reference. They are precision-oriented and do not see omissions by design: a reply that drops "if the car is not reserved" contains no unsupported claim, only a weaker condition. Omission detection needs a recall direction (keyfact or reference → response). LLMs are measurably poor at noticing absence unless the gap is made explicit.

### Cited Findings
- **AbsenceBench** (2025): given the original and edited text, models must name what was removed. Claude-3.7-Sonnet (thinking) averages 69.6 F1; Gemini-2.5-flash (thinking) 71.2. On GitHub PRs the best score is only 40.0. — [AbsenceBench arXiv 2506.11440](https://arxiv.org/html/2506.11440)
- AbsenceBench authors' explanation: "Transformer attention mechanisms cannot easily attend to 'gaps' in documents," because absences do not correspond to specific keys. — [arXiv abs 2506.11440](https://arxiv.org/abs/2506.11440)
- Inserting explicit `<missing line>` placeholders raised F1 a lot. Claude-3.7-Sonnet went from 66.9 to 83.3, GPT-4.1-mini from 35.5 to 52.1, and Llama-4-Maverick from 40.2 to 62.1. The paper's own headline average conflicts with itself (35.7% vs 41.9%). — [AbsenceBench](https://arxiv.org/html/2506.11440)
- Thinking or inference-time compute improved F1 by only about 7.9%, at about 8K extra thinking tokens. Counter-intuitively, fewer omissions made the task harder. — [AbsenceBench](https://arxiv.org/html/2506.11440)
- **MED-OMIT** turns the source (a doctor-patient chat) into a set of facts, then checks which facts are fully or partly missing from the summary, weighted by importance. This is the reference → response direction. — [MED-OMIT arXiv 2311.08303](https://arxiv.org/abs/2311.08303v1)
- An EMNLP 2025 Industry paper notes that existing datasets focus on hallucinations and inconsistencies, "leaving a gap" for omission evaluation. It proposes EmbedKDECheck (embeddings plus anomaly detection) and compares it against SelfCheckGPT, ChainPoll, G-Eval and GPTScore. — [ACL Anthology 2025.emnlp-industry.22](https://aclanthology.org/2025.emnlp-industry.22.pdf)
- **FineSurE** (ACL 2024) uses an LLM to (a) fact-check each summary sentence (faithfulness) and (b) align a list of keyfacts to summary sentences (completeness), with keyfacts auto-extracted when none are given. It reports particular gains on completeness and conciseness, and results depend strongly on the LLM backbone. — [FineSurE arXiv 2407.00908](https://arxiv.org/html/2407.00908v3); code at [github.com/DISL-Lab/FineSurE-ACL24](https://github.com/DISL-Lab/FineSurE-ACL24)
- Claimify measures extraction "coverage" alongside entailment, which shows that coverage (recall) is treated as a separate axis from precision. — [ACL 2025 Claimify paper](https://preview.aclanthology.org/landing_page/2025.acl-long.348.pdf)

### Inferences (applicability, my own)
- The judge never sees the original reply, but it does see the policy, so the policy can serve as the "keyfact list." Run a FineSurE-style recall pass: for each policy rule the reply touches (the "relevant" rules), list the attached conditions and hedges, then check whether each is present, weakened or absent in the reply. This turns "notice what's missing" (hard per AbsenceBench) into "check a listed item" (the placeholder effect: making the gap explicit helped by about 17-24 F1 points for strong models).
- The relevance filter matters, because harmless replies legitimately omit unrelated policy rows. Only conditions attached to a policy rule that the reply actually asserts should count. Suggested rule: "if the reply makes a claim derived from rule R, every condition or hedge of R must be preserved or not contradicted; omitting it turns a conditional promise into an unconditional one, which is a fail."
- Bidirectional check per matched claim: (1) reply claim → policy (is it supported, with no more generous number?), then (2) policy rule → reply claim (are R's qualifiers kept?). This is a light form of bidirectional entailment, and both steps fit into one JSON response.

### Gaps
- I found no paper that evaluates omission of conditional qualifiers specifically, as opposed to missing facts or lines, or bidirectional NLI used for conditional promises.
- I found no numbers for FineSurE's completeness accuracy on non-summarization tasks.

## Q3. How sensitive are NLI and entailment models to modality and quantifiers ("always" vs "usually", "all" vs "some")?

### Takeaway
Quantifiers and modality are a known weak spot for NLI models. Proportional quantifiers (most, few) and existential or negated forms are hardest. I found no benchmark that targets frequency hedges or conditional commitments ("subject to availability") directly, so the judge prompt must make hedge comparison explicit rather than rely on implicit entailment.

### Cited Findings
- About 10% of NLI benchmark hypotheses contain quantifiers. Proportional quantifiers are harder than counting or Aristotelian ones for BERT and RoBERTa. — [Generalized Quantifiers, arXiv 2204.10615](https://arxiv.org/pdf/2204.10615)
- **EQUATE**: nine published NLI models fail to beat a majority-class baseline on average across its quantitative-reasoning test sets (8,606 pairs). — [EQUATE arXiv 1901.03735](https://ar5iv.labs.arxiv.org/html/1901.03735)
- A natural-logic synthetic dataset modifies sentences with universal quantifiers ("every", "always"), existential quantifiers and negation. Zero-shot NLI performance is poor, "especially for modified sentences with negation and existential quantifiers." — [arXiv 2307.05034](https://arxiv.org/html/2307.05034v3)
- MultiNLI lists modality, quantification and belief among the phenomena a model must handle. — [MultiNLI](https://www.arxiv-vanity.com/papers/1704.05426/)
- Epistemic modality ("is consistent with" vs "may be consistent with") becomes encoded in deeper LLM layers, according to clinical probing work. — [arXiv 2511.22402](https://arxiv.org/html/2511.22402v1)
- Minimal modality shifts (should → could) produce consistent differences in model generations. — [AAAI Controllable Epistemic Sensitivity](https://ojs.aaai.org/index.php/AAAI/article/view/42322)
- A 2026 preprint proposes screening for "epistemic-rhetorical miscalibration" (saying more than the evidence supports), which is close to over-promise detection. — [arXiv 2604.19768](https://arxiv.org/html/2604.19768)
- DynaGuard's error analysis: counting-related policies had a 53.4% error rate. — [DynaGuard arXiv 2509.02563](https://arxiv.org/html/2509.02563v3)

### Inferences (applicability, my own)
- Haiku should not be trusted to notice "usually" → "always" implicitly. The prompt or schema should force extraction of hedge and quantifier tokens from both the policy rule and the reply claim, then compare their strength on an ordinal scale (always/guaranteed > usually/typically > may/some branches/subject to availability). A hedge that is weaker in the policy than in the reply means over-promise and a fail.
- Hedge removal across languages (EN/DE/FR/ES/IT: "normalerweise", "généralement", "di solito", "normalmente") needs the same ordinal mapping. Asking the model to normalize hedges to English strength labels inside the JSON should handle translation.
- Deterministic hedge-lexicon checks are possible but brittle across 5 languages. A cheap pre-pass can flag strong universals in the reply ("always", "guaranteed", "immer", "toujours", "sempre", "siempre") as hints for the LLM, not as verdicts.

### Gaps
- I found no benchmark on frequency hedges ("usually") or availability hedges in entailment, and no multilingual hedge-NLI data.
- A search snippet claimed LLM evaluators are biased against responses that express uncertainty, but I could not tie it to a specific verified source.

## Q4. How well do LLMs check policy compliance and guideline adherence (customer-service policies, guardrails, policy-as-prompt)?

### Takeaway
"Policy as prompt" guardian models work. DynaGuard's DynaBench shows that free-form, user-written policies can be checked with about 73-80 F1 by an 8B model, and that chain-of-thought adds only about 1 point. Classic safety guardrails (LlamaGuard and similar) fail badly on custom policies. Multi-clause rules are the main weakness, and they match our "rule plus condition" structure.

### Cited Findings
- **DynaGuard** (ICLR 2026) takes user-defined policies (a set of rules) at runtime and judges whether a chatbot conversation complies. It has fast-classification and CoT modes. DynaBench contains 40K policies spanning regulatory compliance, user experience, transactions and other areas. — [DynaGuard arXiv 2509.02563](https://arxiv.org/html/2509.02563v3); [ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/8d2aad53fa148791ffd004a7c9cce5ad-Abstract-Conference.html)
- DynaBench F1: DynaGuard-8B (CoT) 73.1, GPT-4o-mini 70.1, base Qwen3-8B 60.7. Safety guardians: LlamaGuard3 13.1, WildGuard 20.9, NemoGuard 23.7, GuardReasoner-8B 22.0, ShieldGemma 38.2. — [DynaGuard](https://arxiv.org/html/2509.02563v3)
- CoT vs fast mode: DynaBench 73.1 vs 72.5, and all-task average 79.7 vs 78.4 ("only a difference of 1.3% in F1"). — [DynaGuard](https://arxiv.org/html/2509.02563v3)
- Error rates: "Multi-clause Rule Policies" 60.7% and "Factual Knowledge Policies" 73.4%. The authors note that policies should be well-formed and unambiguous. — [DynaGuard](https://arxiv.org/html/2509.02563v3)
- **τ-bench** (Sierra, ICLR 2025) tests customer-service agents that must follow domain policies (retail and airline). gpt-4o reached about 61% on retail and about 35% on airline (pass^1). The paper introduces pass^k to measure consistency across repeated trials. — [τ-bench arXiv 2406.12045](https://arxiv.org/pdf/2406.12045)
- A secondary source breaks down τ-bench failures as wrong arguments or info 55.5%, policy-violation decisions 25%, and partial resolution 22.2%. This is unverified against the paper. — [alphaxiv tau-bench](https://www.alphaxiv.org/benchmarks/sierra/tau-bench)

### Inferences (applicability, my own)
- Our judge is a narrow DynaGuard-style "policy-as-prompt" classifier. The DynaGuard weakness on multi-clause rules argues for having the LLM explicitly decompose each policy rule into (base entitlement, number, conditions, hedges) before judging, rather than judging the whole policy at once.
- The small CoT gain in DynaGuard and AbsenceBench (about 1-8 points) suggests that structured extraction (forcing the comparison) matters more than free-form reasoning length.
- τ-bench's pass^k idea is a reminder that LLM judges are stochastic. With 3 calls available, a 2-of-3 or "any-fail" vote could be considered, but spending calls on structured verification is probably the better use.

### Gaps
- I found no published benchmark for customer-support replies over-promising relative to a policy table (car rental or similar). No τ-bench numbers for Claude Haiku were checked.

## Q5. Do hybrid pipelines (deterministic checks before the LLM) improve precision?

### Takeaway
Evidence is thin and mostly practitioner-level. Number and unit matching is a common first stage and catches many numeric errors cheaply. Pure rule checks over-flag correct derived numbers, so the literature and practitioners suggest using rules as signals that feed an LLM decision.

### Cited Findings
- A clinical summary fact-checking module includes a numeric-consistency check (a value or unit mismatch for the same entity and attribute triggers NUMERICAL-FAIL). The module overall reports precision 0.8904, recall 0.8234 and F1 0.8556, but the numeric step is not isolated. — [arXiv 2512.16189](https://arxiv.org/pdf/2512.16189)
- Practitioner report: flagging any summary number not found verbatim in the source caught a high fraction of numeric errors. No precision figure is given. — [YLD blog](https://www.yld.com/blog/evaluating-llm-summaries-at-scale-what-we-tried-and-what-worked)
- Practitioner argument: a rule-based numeric flag is "an upper bound on hallucination, not a measurement," because correct derived numbers get flagged. The author recommends putting an LLM inside the guardrail for semantic context. — [Towards AI](https://pub.towardsai.net/why-my-llm-guardrail-flagged-the-right-answers-and-why-i-refused-to-fix-it-0db77efb0644)
- Multi-stage or hybrid numerical fact-checking pipelines appear in CLEF CheckThat! 2025, but I found no precision ablation for them. — [CEUR-WS Vol-4038 paper 55](https://ceur-ws.org/Vol-4038/paper_55.pdf)

### Inferences (applicability, my own)
- A cheap deterministic pre-pass fits well: extract all numbers, currencies, durations and percentages from the reply (handling locale formats such as "1.000,50 €" and "24 Stunden"), then flag any that don't match a policy value. Pass these flags to the LLM as hints ("number 48 not in policy; policy has 24"). Do not auto-fail, because a reply may legitimately say "1 day" for "24 hours" or compute a total.
- Directionality matters. A more generous number (a longer free-cancellation window, a lower fee) is a fail; a stricter one may be harmless or a different error. The LLM step should judge direction, since the policy table indicates which way is "generous."
- Translation-safe entity matching (branch types, car classes) is harder to do deterministically. Leave it to the LLM.

### Gaps
- I found no controlled study that measures the precision or recall gain from adding a deterministic number check before an LLM judge.

## Q6. Can claims be extracted and verified in a single structured JSON call instead of several calls, and how much quality is lost?

### Takeaway
Single-pass "extract + verify" is viable. VeriFastScore keeps a strong system-level correlation with the multi-call VeriScore pipeline, though claim-level agreement is moderate. MiniCheck shows that a separate decomposition step brings little accuracy gain for strong LLMs. For a short reply against a short policy, one structured call is probably close to a multi-call pipeline, and a second call works best as an independent recall or omission pass.

### Cited Findings
- **VeriFastScore** (2025) replaces VeriScore's multi-call pipeline (claim extraction, then per-claim verification) with one pass of fine-tuned Llama-3.1-8B over the response plus consolidated evidence (about 4K tokens). It outputs claims with Supported or Unsupported labels. — [VeriFastScore arXiv 2505.16973](https://arxiv.org/html/2505.16973v3)
- VeriFastScore's correlation with VeriScore: Pearson r = 0.80 per example and 0.94 at system level. Speed-up is about 6.6x overall (9.9x for modeling alone). — [VeriFastScore](https://arxiv.org/html/2505.16973v3)
- Quality loss: claim-level accuracy against VeriScore is about 66% with sentence-level evidence and 71.6% with claim-level evidence. Few-shot GPT-4o without fine-tuning reached only 0.33 correlation in the single-pass setting. Most verification errors were false positives (claims marked supported that weren't). — [VeriFastScore](https://arxiv.org/html/2505.16973v3)
- MiniCheck: decomposition adds 2-4x cost with gains of −3.3 to +1.2 points depending on the checker (+0.3 for GPT-4). — [MiniCheck](https://arxiv.org/html/2404.10774v2)
- FineSurE runs faithfulness (per-sentence fact-check) and completeness (keyfact alignment) as LLM prompts that return structured per-item outputs, an example of the "list of items with labels in one response" pattern. — [FineSurE](https://arxiv.org/html/2407.00908v3)
- DynaGuard: fast (no-CoT) classification is within about 1.3 F1 of CoT. — [DynaGuard](https://arxiv.org/html/2509.02563v3)

### Inferences (applicability, my own): a suggested 1-3 call design
- **Call 1 (extract + verify, precision direction):** one JSON response from Haiku. For each claim or promise in the reply, return `{reply_span, english_gloss, matched_policy_rule_id|null, reply_number, policy_number, number_direction: same|more_generous|stricter|n/a, reply_hedge_strength, policy_hedge_strength, label: supported|contradicted|unsupported_extra}`. Ignore openers and filler explicitly.
- **Call 2 (recall / omission direction, FineSurE-style):** given the set of matched_policy_rule_ids from call 1, list each rule's conditions and hedges, then check whether each one is preserved in the reply, contradicted, or dropped while the claim is stated unconditionally. Making the list explicit mimics AbsenceBench's placeholder trick. This could be merged into call 1 to save a call, but a separate pass lets the model "re-read" from the policy side.
- **Call 3 (optional):** an adjudicator that gets the call 1 and 2 JSON plus the criterion and deterministic number flags, and returns pass/fail with a rationale. Alternatively, spend it on a second sample of call 2 for an "any-confirmed-omission" vote, since omissions are the hardest case.
- Deterministic code (zero LLM calls) can do the final aggregation: fail if any label is contradicted, any number_direction is more_generous, the reply hedge is stronger than the policy's, or a condition is dropped on a matched rule. This removes the judge's freedom to rationalize. The VeriFastScore finding that errors skew to false "supported" suggests the aggregation should lean toward fail on explicit mismatches.
- Risk: false positives on harmless edits (reordering, translation, filler). Mitigate by having the LLM label filler as `no_policy_claim`, and by counting a condition as "dropped" only when the reply states the matched entitlement without it, not when the reply simply doesn't mention that rule.

### Gaps
- I found no evidence specific to Claude Haiku on single-call extract+verify quality. The VeriFastScore result is for a fine-tuned 8B model, and its few-shot GPT-4o baseline was weak, so prompt-only single-call quality for Haiku is unknown and should be measured on the hackathon dev set.
- I found no head-to-head study of one-call vs two-call (precision + recall) LLM judges for omission detection.
