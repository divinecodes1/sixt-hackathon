# Failure modes of LLM-as-a-judge: sensitivity to meaning-changing edits vs invariance to harmless surface edits

Research date: 2026-11-12. Sources are tagged [fetched] when this session read the page, and [prior knowledge] when the citation comes from the researcher's background knowledge and was not re-opened in this session. Check [prior knowledge] items before quoting exact numbers.

## Q1. Do the four papers named in the hackathon brief exist, and what do they find?

### Takeaway
All four exist. "A Judge Should Know What Changed" is the most relevant: it evaluates claude-haiku-4.5 among 7 judges, and it finds that judges almost never flip on surface edits but often miss condition removal and hedge removal. "Reliability without Validity" exists but has been **withdrawn by arXiv administrators** for not meeting quality standards, so treat it with care. The Observe.AI paper appears under a longer title: "Counterfactual Fairness Evaluation of LLM-Based Contact Center Agent Quality Assurance System".

### Cited Findings
**A Judge Should Know What Changed: Construct Validity for LLM-as-a-Judge Evaluation** (Chen, Chen, Lin, Vong; arXiv 2608.24419, submitted 25 Aug 2026) [fetched] — [abs](https://arxiv.org/abs/2608.24419), [html](https://arxiv.org/html/2608.24419)
- The paper proposes a two-axis profile. **Invariance (S)** asks whether the verdict stays the same under edits that preserve the construct. **Sensitivity (R)** asks whether the verdict changes under minimal edits that alter the construct. Across 7 judges and 4 domains, judges were highly invariant (S≈0.945) but only weakly sensitive (R≈0.319) at matched invariance (S≥0.90). — [html](https://arxiv.org/html/2608.24419)
- The judges were claude-haiku-4.5, nemotron-3-nano-30b-a3b, gemini-2.5-flash-lite, mistral-small-3.2-24b, deepseek-v4-flash, glm-4.7-flash and llama-4-scout. **claude-haiku-4.5 had the highest sensitivity (R=0.561, S=0.917)** and llama-4-scout the lowest (R=0.093, S=0.979). The other R values were nemotron 0.447, gemini-flash-lite 0.408, mistral 0.309, deepseek 0.245 and glm 0.168. — [html](https://arxiv.org/html/2608.24419)
- The edit taxonomy maps directly onto the hackathon:
  - **Scope edits (should flip):** domain extension, population widening, quantifier strengthening, tense/modality shift.
  - **Strength edits (should flip):** **condition removal**, **hedge removal**, intensifier addition.
  - **Control edits (should not flip):** format shift, register shift, reordering, verbosity padding, elaboration.

  Padding and elaboration were dropped as controls because human annotators did not agree on them (0.689 and 0.404). — [html](https://arxiv.org/html/2608.24419)
- Mean sensitivity by edit type, across judges:

  | Edit type | Mean sensitivity |
  |---|---|
  | Quantifier strengthening | 0.445 |
  | Domain extension | 0.445 |
  | Condition removal | 0.379 |
  | Tense/modality shift | 0.358 |
  | Population widening | 0.299 |
  | Intensifier addition | 0.235 |
  | **Hedge removal** | **0.210** (lowest) |

  — [html](https://arxiv.org/html/2608.24419)
- Judges are more sensitive to scope edits (0.383) than to strength edits (0.262). The gap of +0.121 holds for all 7 judges, with a bootstrap 95% CI of +0.052 to +0.189 and permutation p<0.002. Length does not explain it, and the authors treat the gap as a lower bound. — [html](https://arxiv.org/html/2608.24419)
- Control edits rarely flip verdicts: format shift 0.029, register shift 0.053, **reordering 0.084**. — [html](https://arxiv.org/html/2608.24419)
- Public validation sets are weak tests of judges. A predictor that reads only surface form reproduces 55–67% of labels across five public label sets, including 67.4% of MT-Bench human votes in paired mode. On RewardBench, "prefer the shorter response" is right on 59.7% of pairs. — [html](https://arxiv.org/html/2608.24419)
- The authors recommend the following:
  - Report R only together with S, and compare judges at matched invariance or across the whole threshold frontier, not at default thresholds.
  - Get labels for the direction of a change from humans.
  - Report a surface-only baseline, a human ceiling and a label-permutation null.
  - Probe in both directions, with construct-changing edits and with surface-only edits.

  — [html](https://arxiv.org/html/2608.24419)
- The parts of the paper this session could read do not test chain-of-thought, reference-based prompting or "show the diff" prompting as mitigations. Ensembling and self-consistency are predicted to raise S without moving R, but one table marks those runs as not yet done.

**Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models Across Agreement, Consistency, and Bias** (Norman, Rivera, Hughes; arXiv 2606.19544; v1 17 Jun 2026, v2 3 Nov 2026) [fetched] — [abs](https://arxiv.org/abs/2606.19544)
- **The listing shows it was withdrawn by arXiv administrators for not meeting research-quality standards.** The claims below should not be treated as established.
- It studies 21 judges from 9 providers on MT-Bench, JudgeBench and RewardBench, with about 541k judgments. It reports that kappa is consistently lower than exact-match agreement, and that exact match overstates how well judges discriminate. Judge rankings change across benchmarks. Some production judges pair high test-retest reliability with severe position bias. Verbosity bias is small under one pairwise rubric. The authors propose a "Minimum Viable Validation Protocol". — [abs](https://arxiv.org/abs/2606.19544)

**Counterfactual Fairness Evaluation of LLM-Based Contact Center Agent Quality Assurance System** (Observe.AI; arXiv 2602.14970, Feb 2026; ACL Findings 2026, 2026.findings-acl.1890) [fetched] — [arXiv html](https://arxiv.org/html/2602.14970v1), [ACL preview](https://preview.aclanthology.org/ingest-acl/2026.findings-acl.1890/)
- It covers 18 LLMs, 3,000 real contact-center transcripts and 13 counterfactual dimensions grouped as Identity, Context and Behavioral Style. The metrics are the Counterfactual Flip Rate (CFR, how often a binary verdict reverses) and the Mean Absolute Score Difference. — [html](https://arxiv.org/html/2602.14970v1)
- **Changes to behavioral style alone still flip verdicts.** The average CFRs were:

  | Dimension | Average CFR |
  |---|---|
  | Politeness | 6.93% |
  | Formality | 7.07% |
  | Communicative style | 7.63% |
  | Emotional labor | 7.85% |
  | Contextual metadata | 10.08% |
  | Priming from coaching notes | **16.44%** (highest) |

  — [html](https://arxiv.org/html/2602.14970v1)
- CFR ranges from Claude-4-Sonnet at 5.41% (best) to Llama-3.2-3B at about 12.95%. Larger models generally do better, but not monotonically: Nova-Premier 6.93% vs Nova-Lite 10.77%. Fairness does not track accuracy. — [html](https://arxiv.org/html/2602.14970v1)
- Explicit fairness instructions give only modest and uneven gains: −2.5 to −4.2 points for most models, and Claude-3.5-Haiku got slightly worse (+0.26). — [html](https://arxiv.org/html/2602.14970v1)

**Judging LLM-as-a-Judge: Concerning Rubric Artifacts in LLM-based Automated Text Generation Evaluation** (Bagaria, Sundaram, Krishnan, Ravindran; arXiv 2609.02942, 31 Aug 2026; listed as EMNLP 2026) [fetched] — [abs](https://arxiv.org/abs/2609.02942), [html](https://arxiv.org/html/2609.02942)
- A PubMedBERT classifier that sees only the **rubric text, with no response**, predicts the judge's (Qwen2.5-7B) labels with 5-fold CV balanced accuracy of 0.80–0.88 on HealthBench. The majority-class baselines are also high (around 88–89%), so read this signal with caution. — [html](https://arxiv.org/html/2609.02942)
- When the response is reversed, the judge flips in the expected direction only **37.7%** of the time. In 39.6% of cases it does not move ("sticky"), and in 17.8% it flips the wrong way. When the rubric criterion is reversed, it flips correctly only 16.8–32.2% of the time. — [html](https://arxiv.org/html/2609.02942)
- Limitations: a single 7B judge, binary labels, no causal claims, and some tables are internally inconsistent. — [html](https://arxiv.org/html/2609.02942)

### Inferences
- The brief's baseline numbers fit this profile. Wrong numbers and wrong policy details are content substitutions, like "scope" or factual edits, and they are caught 80–100% of the time. Dropped conditions (7%) and hedge removals (50%) are "strength" edits, which 2608.24419 finds hardest. Note that claude-haiku-4.5 was already the most sensitive judge in that study, so the remaining weakness is not simply down to model choice.
- The baseline in the brief flips about 27% of reordered replies. That is far above the 8.4% reordering flip rate in 2608.24419, which suggests something specific to this prompt or data. One example would be reordering a condition so it sits apart from the promise it qualifies. This is inference, not tested.

### Gaps
- This session could not read the per-judge, per-edit table in 2608.24419 (claude-haiku-4.5's own numbers for condition removal and hedge removal), or which four domains were used. The html beyond about 200k characters and the table sections were not fully parsed.
- No session source tested whether showing the judge "what changed" (a diff against a reference) closes the strength-edit gap.

## Q2. Evidence that judges and NLI models under-detect omissions, dropped conditions or qualifiers, negation and hedge/modality changes

### Takeaway
Omissions and weakened qualifiers are consistently the hardest edits to catch. Changes to stated content (opposite facts, wrong numbers, wrong entities) are caught much more often, especially when the judge has a reference. This matches the hackathon baseline.

### Cited Findings
**FBI: Finding Blind Spots in Evaluator LLMs with Interpretable Checklists** (Doddapaneni et al., EMNLP 2024, Outstanding Paper) [fetched] — [arXiv html](https://arxiv.org/html/2406.13439), [ACL](https://aclanthology.org/2024.emnlp-main.911)
- The benchmark has 2,400 perturbed answers across 22 categories, including Remove Fact, Do Less, Opposite Fact, Number Errors and Entity, plus 516 "score-invariant" controls. Evaluators missed the quality drop in more than 50% of cases on average. — [html](https://arxiv.org/html/2406.13439)
- **Omissions are the blind spot.** GPT-4-turbo's detection rates were:

  | Category | Single-answer, score only | Reference-guided |
  |---|---|---|
  | Remove Fact | **6%** | 48% |
  | Opposite Fact | 43% | 100% |
  | Number Errors | 30% | 92% |
  | Entity | 33% | 91% |

  — [html](https://arxiv.org/html/2406.13439)
- Reference-guided evaluation does best. The share of perturbed factual answers left unpenalized was 0.11 with a reference vs 0.54–0.76 in single-answer modes. — [html](https://arxiv.org/html/2406.13439)
- **Rubrics and axis prompts made single-answer judging worse.** Rubric prompting left factual misses at 0.73 vs 0.54 for vanilla prompting. Asking for an explanation helped a little (vanilla 0.54 vs score-only 0.67). Explanations sometimes named the error but did not lower the score. — [html](https://arxiv.org/html/2406.13439)
- Llama-3-70B with a reference was over-strict. It gave a perfect score to only 13% of score-invariant answers, which shows the trade-off between sensitivity and false failures. — [html](https://arxiv.org/html/2406.13439)

**2608.24419** (see Q1): hedge removal (0.210) and condition removal (0.379) have low sensitivity across all 7 judges. — [html](https://arxiv.org/html/2608.24419)

**SummEdits** (Laban et al., EMNLP 2023) [search-snippet level]
- On factual-inconsistency detection, most LLMs score near chance. GPT-4 is about 8 points below estimated human performance. — [ACL](https://aclanthology.org/2023.emnlp-main.600), [arXiv](https://arxiv.org/abs/2305.14540)

**NLI literature on negation, quantifiers and monotonicity** [search-snippet level]
- Transformer NLI models do poorly on negation and several quantifier types, and fine-tuning does not significantly fix it. — [ACL 2023.nlrse-1.12](https://aclanthology.org/2023.nlrse-1.12.pdf)
- Monotonicity information is weakly represented in high-scoring NLI models. — [arXiv 2112.08289](https://arxiv.org/abs/2112.08289)
- MoNLI: models trained on general NLI fail systematically on negation. — [arXiv 2004.14623](https://arxiv.org/pdf/2004.14623v4.pdf)
- Semantic fragments probe quantifiers and monotonicity. — [arXiv 1909.07521](https://arxiv.org/pdf/1909.07521)

### Inferences
- Omitted content leaves no surface signal in the reply under review. A reference-free judge has to rebuild the missing condition from the policy and notice that it is absent. FBI shows that providing the reference (here, the policy clause with its conditions) is the single most effective lever, and that generic rubrics can backfire.
- A practical prompt design follows from this, though it is not directly tested: make the judge first list every condition, limit and hedge in the relevant policy clause, then check each one against the reply.

### Gaps
- This session found no dedicated benchmark for hedge or epistemic-modality changes ("usually" → "always") in NLI or judge evaluation, other than 2608.24419's hedge-removal slot.
- This session did not verify EvalBiasBench/OffsetBias numbers. [prior knowledge] Park et al. 2024, "OffsetBias", arXiv 2407.06551, introduces EvalBiasBench with bias categories such as length, concreteness, empty reference and content continuation — [arXiv](https://arxiv.org/abs/2407.06551).

## Q3. Known biases: verbosity, position, self-preference, politeness/tone, order sensitivity, prompt and rubric wording, over-strictness

### Takeaway
Many biases are documented. For single-reply pass/fail grading, the ones that matter are tone and politeness, rubric-wording priors, and over-strictness (false fails). Position bias mostly affects pairwise setups.

### Cited Findings
- **Zheng et al. 2023 (MT-Bench, NeurIPS 2023 D&B):** GPT-4 judges agree with human preferences more than 80% of the time, about the same as human-human agreement. The paper names position, verbosity and self-enhancement biases and limited reasoning ability. — [arXiv 2306.05685](https://arxiv.org/abs/2306.05685) [search-snippet]
- **CALM, "Justice or Prejudice?" (Ye et al., ICLR 2025):** 12 bias types are injected automatically through principle-guided edits. Significant biases persist on specific tasks even in advanced models. — [arXiv 2410.02736](https://arxiv.org/abs/2410.02736) [search-snippet]
- **Politeness and style:** Changing only politeness, formality or communicative style flips binary QA verdicts 6.9–7.9% of the time. Fairness prompting helps only modestly. — [arXiv 2602.14970](https://arxiv.org/html/2602.14970v1) [fetched]
- **Reordering and format:** In 2608.24419, reordering flips verdicts 8.4% of the time and register shift 5.3%. Padding and elaboration could not even get consistent human labels. — [html](https://arxiv.org/html/2608.24419) [fetched]
- **Rubric wording carries the score:** Judge labels can be partly predicted from rubric text alone. Reversing the criterion produces the correct flip only 17–32% of the time. — [arXiv 2609.02942](https://arxiv.org/html/2609.02942) [fetched]
- **Rubric prompts can lower sensitivity:** see FBI in Q2. — [html](https://arxiv.org/html/2406.13439)
- **Over-strictness:** Llama-3-70B with a reference gave full marks to only 13% of perturbations that should not change the score. — [html](https://arxiv.org/html/2406.13439)
- [prior knowledge] **Position bias:** Wang et al. 2023, "Large Language Models are not Fair Evaluators", show that swapping answer order can reverse verdicts, and propose balanced position calibration. — [arXiv 2305.17926](https://arxiv.org/abs/2305.17926)
- [prior knowledge] **Self-preference:** Panickssery et al. 2024, "LLM Evaluators Recognize and Favor Their Own Generations". — [arXiv 2404.13076](https://arxiv.org/abs/2404.13076)
- [prior knowledge] **Surveys:** Gu et al. 2024, "A Survey on LLM-as-a-Judge" — [arXiv 2411.15594](https://arxiv.org/abs/2411.15594). Li et al. 2024, "LLMs-as-Judges: A Comprehensive Survey" — [arXiv 2412.05579](https://arxiv.org/abs/2412.05579).

### Inferences
- The baseline's 14% false fails on correct originals and 27% on reordered replies are likely over-strictness triggered by rubric wording. A criterion like "over-promise?" may prime the judge to find something to fail. FBI and 2609.02942 both show that rubric framing shifts verdicts independently of the content.
- Possible fixes, none tested here: tell the judge explicitly that a reply passes when every commitment it makes is supported by the policy, and calibrate the threshold on harmless-edit controls.

### Gaps
- This session did not verify the exact magnitudes of position, verbosity and self-preference bias. Those are [prior knowledge] citations.
- No source was found that measures sentence-order sensitivity in single-response pass/fail grading, other than 2608.24419.

## Q4. Reliability vs validity: high agreement or kappa without correctness, and how to measure consistency

### Takeaway
A judge can be stable across runs and invariant to surface edits and still be invalid. The validity check is whether the verdict changes when the meaning changes. Measure invariance and sensitivity together on paired minimal edits, use chance-corrected agreement, and compare against surface-only baselines.

### Cited Findings
- High invariance (S≈0.945) coexists with low sensitivity (R≈0.319). Single agreement numbers hide this. — [html](https://arxiv.org/html/2608.24419)
- Surface-only predictors reproduce 55–67% of public validation labels, so agreement with such sets is weak evidence of validity. — [html](https://arxiv.org/html/2608.24419)
- 2608.24419 recommends reporting the (S, R) profile, the best surface-only baseline, the human ceiling, a permutation null, and the source of every label. — [html](https://arxiv.org/html/2608.24419)
- Kappa is consistently below exact-match agreement. Test-retest reliability can coexist with severe position bias (**withdrawn paper**). — [arXiv 2606.19544](https://arxiv.org/abs/2606.19544)
- The Counterfactual Flip Rate on paired counterfactuals is a simple measure of invariance, and fairness does not track accuracy. — [html](https://arxiv.org/html/2602.14970v1)
- In FBI, explanations sometimes named the error but the score did not change. Rationales are therefore not reliable evidence that the judge actually detected something. — [html](https://arxiv.org/html/2406.13439)

### Inferences
- For the hackathon, report a per-edit-type detection rate (sensitivity) and a per-harmless-type false-flip rate (invariance) side by side, plus the false-fail rate on originals. Also report repeat-run agreement, with Cohen's or Fleiss' kappa rather than raw agreement. A "reliable" judge with 7% detection of dropped conditions is reliable but not valid.

### Gaps
- This session found no peer-reviewed, non-withdrawn large-scale study of test-retest reliability vs validity specifically for binary judges.

## Q5. Multilingual judging: do judges degrade outside English, and does translating to English help?

### Takeaway
Yes, judges are less consistent across languages, with an average Fleiss' kappa of about 0.3 on parallel data, and they may drift towards higher scores in non-English text. Translating to English is a common design choice, but this session found no controlled evidence that it helps, and judges may favour machine-translated text.

### Cited Findings
- Fu & Liu, "How Reliable is Multilingual LLM-as-a-Judge?" (Findings of EMNLP 2025): 5 models, 5 tasks, 25 languages. Cross-language consistency averages Fleiss' kappa ≈0.3 and is worst for low-resource languages. Neither scale nor multilingual training reliably improves it. The authors propose an ensemble of judges. — [arXiv 2505.12201](https://arxiv.org/abs/2505.12201v1) [search-snippet]
- Hada et al. (Findings of EACL 2024): GPT-4 evaluators were compared with about 20k human judgments across 8 languages. They may be biased towards higher scores and should be calibrated against native-speaker judgments, especially for low-resource and non-Latin-script languages. — [arXiv 2309.07462](https://arxiv.org/abs/2309.07462v2) [search-snippet]
- CE-Judge (GlobalNLP 2025) translates the instruction and response into English to generate its checklist, on the reasoning that English is more reliable. The snippets did not show an ablation of translating vs judging natively. — [arXiv 2507.06774](https://arxiv.org/html/2507.06774v2) [search-snippet]
- Multilingual judges favour machine-translated content over human-written text even when the translation is semantically flawed. Pivoting through English can therefore add its own bias. — [arXiv 2603.10351](https://arxiv.org/pdf/2603.10351) [search-snippet]
- Breaking judgments into shared, language-agnostic criteria enables cross-lingual transfer with few English labels. — [arXiv 2603.18557](https://arxiv.org/pdf/2603.18557v1) [search-snippet]

### Inferences
- EN, DE, FR, ES and IT are high-resource languages, so degradation should be smaller than the low-resource numbers above. However, translated replies can change hedge words ("in der Regel", "généralement"), and the policy may stay in English while the reply is not.
- One option, untested here: have the judge extract the reply's commitments into normalized English before checking them against the policy. Validate this on the translation controls, because of the translationese bias above.

### Gaps
- This session found no controlled study of claude-haiku-4.5 specifically on multilingual judging, and no head-to-head comparison of translating to English vs judging natively.
