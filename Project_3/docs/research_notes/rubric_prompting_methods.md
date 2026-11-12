# Criterion-agnostic techniques for improving LLM judges (checklists, few-shot, CoT, voting, calibration)

Context: claude-haiku-4.5 as the judge, at most 3 calls per reply, a binary pass/fail verdict, and a surprise criterion that arrives with a few labelled examples. The score is the harmonic mean of catch and keep, macro-averaged over edit types, plus Cohen's kappa and run-to-run consistency. Notes compiled 2026-11-12.

## 1. Checklist / rubric-as-questions methods (CheckEval, TICK, RocketEval, InFoBench DRFR, rubric generation)

### Takeaway
Breaking a criterion into binary YES/NO sub-questions reliably makes judges agree more with each other and with themselves. CheckEval cut score variance by roughly 5x. Gains in agreement with humans are moderate: TICK added +5.8 pts exact agreement, and CheckEval added about +0.10 correlation on average. Checklists help most for small or weak judges and in pairwise settings. A 2025 EMNLP study found they do not always help direct scoring, and about 40% of auto-generated items can be "harmful" (though the overall effect of those items was small).

### Cited Findings
- **CheckEval method.** Evaluation is broken into Boolean questions, one per component. The score is the proportion of "yes" answers. Questions are batched by sub-dimension in one prompt, and the authors saw "no noticeable difference" from single-question prompting in pilot tests (no numbers given). — [CheckEval arXiv 2403.18771v2](https://arxiv.org/html/2403.18771v2)
- **CheckEval inter-evaluator agreement (12 evaluator models).** Krippendorff's α on SummEval rose from 0.09 (G-Eval) to 0.48. On Topical-Chat it rose from 0.06 to 0.45. Among the top 3 models it rose from 0.07 to 0.65 (SummEval). The abstract headline is "+0.45 average agreement". The tables show α gains of about 0.39 and κ gains of 0.29 / 0.11, so the headline number is not obviously reproduced. — [CheckEval](https://arxiv.org/html/2403.18771v2)
- **CheckEval correlation with humans.** GPT-4o on SummEval went from ρ 0.32 (G-Eval) to 0.50. Llama3.1-8B on Topical-Chat went from 0.11 to 0.46, a much bigger gain for the weaker model. There are exceptions where G-Eval wins (Qwen2.5-72B and Mistral-Small on Topical-Chat). The variance of correlation across models dropped from 0.0100 to 0.0019 (SummEval Spearman). — [CheckEval](https://arxiv.org/html/2403.18771v2)
- **CheckEval checklist construction.** It starts from human seed questions (15 to 18), then uses GPT-4o for diversification and elaboration, which grew the lists to more than 100 questions. Filtering out bad questions improved results only marginally (ρ 0.4790 to 0.4816). — [CheckEval](https://arxiv.org/html/2403.18771v2)
- **TICK.** An LLM generates instruction-specific YES/NO checklists (2 to 8 questions, few-shot prompt, covering explicit and implicit criteria). The judge answers each item, and the pass rate is the sum of yes answers divided by n. With GPT-4o as judge, exact agreement with human preferences was 0.464 for direct scoring, 0.487 for Check-then-Score, and 0.522 for TICK. — [TICK arXiv 2410.03608](https://arxiv.org/html/2410.03608v1)
- **TICK generated vs human checklists.** GPT-4o-generated checklists were about as close to the human reference as alternative human checklists were (ROUGE-L 0.593 vs 0.583; question-count MAE 1.410 vs 2.158). Pass-rate correlation with human-checklist pass rates was 0.772 (Internal) and 0.853 (InFoBench). — [TICK](https://arxiv.org/html/2410.03608v1)
- **TICK item-level accuracy and CoT.** Item-answer accuracy against the human majority was 0.826 for GPT-4o and 0.778 for Llama3.1-70B. The authors say CoT "substantially improves" item accuracy and that maj@k over CoT samples improves it further (shown in a figure only; no numbers in the text). — [TICK](https://arxiv.org/html/2410.03608v1)
- **Checklists help human raters too.** Showing generated checklists to human raters raised inter-annotator Krippendorff's α from 0.194 to 0.256. — [TICK](https://arxiv.org/html/2410.03608v1)
- **DRFR (InFoBench)** is the aggregate fraction of checklist items satisfied across a dataset: the sum of all a_ij divided by the sum of all n_i. — [TICK (describing InFoBench DRFR)](https://arxiv.org/html/2410.03608v1)
- **RocketEval (ICLR 2025).** Lightweight judges answer checklist items independently to "minimize interaction noise", and item weights are then fit to human annotations. The authors argue the weakness of small judges comes from uncertainty and positional bias and "is not easily enhanced through techniques such as chain-of-thought". They report 0.965 correlation with human preferences using Gemma-2-2B (author claim). — [RocketEval ICLR 2025](https://www.iclr.cc/virtual/2025/poster/27674); [themoonlight summary](https://www.themoonlight.io/review/rocketeval-efficient-automated-llm-evaluation-via-grading-checklist)
- **Counter-evidence: "Are Checklists Really Useful?" (EMNLP 2025).**
  - Pairwise (LLMBar): selective checklist use often beat both "none" and "all". "None" was the lowest setting for 6 of 8 models.
  - Direct scoring (InFoBench): no policy produced a statistically significant difference across 8 models.
  - No checklist-generation method won consistently.
  - About 42% (LLMBar) and 41% (InFoBench) of checklist items were classified as harmful to alignment, but the authors say their impact is "generally small".
  - Conclusion: "checklists do not always improve evaluations."
  - [Furuhashi et al. arXiv 2508.15218](https://arxiv.org/html/2508.15218v1)
- **Specific criteria agree with humans more than general ones.** Kim et al. (EvalLM) found specific criteria had the highest human agreement. Gao et al. found scoring one dimension per prompt usually beats multi-dimension prompts. Doddapaneni et al. ("Blind Spots") found simple direct scoring with CoT beat more complex rubric-based strategies. — all as summarized by [Eugene Yan, LLM-evaluators](https://eugeneyan.com/writing/llm-evaluators/)
- **Fine-tuned rubric judges (Prometheus)** reached Pearson 0.897 vs GPT-4's 0.882 on Feedback Bench. However, fine-tuned judges "failed to generalize" out of domain (Huang et al.), scoring below random on LLMBar fairness. — [Eugene Yan](https://eugeneyan.com/writing/llm-evaluators/)
- **Rubric detail.** Removing evaluation criteria lowered human correlation from 0.666 to 0.591 (GPT-4o) and from 0.641 to 0.555 (Llama3.1-70B) on BIGGEN-Bench. Score descriptions for only the endpoints (1 and 5) performed about as well as describing all 5 levels. — [Yamauchi et al. arXiv 2506.13639](https://arxiv.org/html/2506.13639v1)

### Inferences
- (Inference) Under a 3-call budget, the most transferable pattern is a TICK-style "generate checklist from criterion + policy" step. It needs no criterion-specific code, because the checklist is derived at runtime from the criterion text.
  - Because the checklist depends only on the criterion and not on each reply, it can be generated once per criterion and cached. That makes it effectively free per reply, leaving all 3 per-reply calls for judging and voting.
  - Freezing the checklist across both scoring runs also removes one source of run-to-run variance. CheckEval's variance reduction suggests fixed questions are a large stabilizer.
- (Inference) Haiku 4.5 is a "lightweight" judge relative to GPT-4o-class judges. CheckEval and RocketEval show the largest checklist gains for weaker judges, so decomposition is more likely to help here than with a frontier judge.
- (Inference) Because our task is direct scoring (not pairwise), the EMNLP 2025 null result is the most relevant caution. Validate on dev that checklist-based judging beats the plain holistic prompt before committing.
- (Inference) Auto-generated checklists contain about 40% weak or harmful items. Prefer a short list (TICK's 2 to 8 items), and ask the generator to tie each item to a specific policy clause. That limits invented requirements, which would cause false "fail" verdicts and lower keep.

### Gaps
- LLM-Rubric (Hashemi et al. 2024) and Prometheus rubric format were not fetched in primary form. No numbers here.
- No study found that measures checklist judging specifically for detecting *meaning-changing edits* in customer-support text, or with Claude Haiku as judge.
- CheckEval reports no direct binary-vs-Likert ablation.

## 2. Few-shot / in-context examples for judges

### Takeaway
Evidence is mixed. Few-shot examples can raise consistency (one report: up to +28%), and many-shot with rationales beat many-shot without them. But few-shot judge performance is unstable to label balance, order, and count. Practitioners recommend a small, balanced, contrastive set (clear pass, clear fail, borderline) drawn only from training data, while avoiding copying surface keywords.

### Cited Findings
- **Few-shot is unstable.** Luo et al. (ChatGPT as factual-inconsistency evaluator) found few-shot performance unstable when label, example order, or example count changed. — [Eugene Yan](https://eugeneyan.com/writing/llm-evaluators/)
- **Many-shot ICL for evaluators (COLING 2025).** Evaluation quality and consistency improve as the number of examples grows. With GPT-4o, the template with model-generated rationales (MSwR) beat the template without them (MSoR). MSwR mitigates positional bias, and the authors also identify a "symbol bias". This is described as a preliminary study. — [Song et al. arXiv 2406.11629](https://arxiv.org/html/2406.11629v6)
- **Consistency gain.** Few-shot demonstrations of consistent scores raised LLM-evaluator consistency by up to 28% (KDD 2024 GenAI eval workshop paper, via search summary; not verified in full text). — [KDD2024 paper 17](https://genai-evaluation-kdd2024.github.io/genai-evalution-kdd2024/assets/papers/GenAI_Evaluation_KDD2024_paper_17.pdf)
- **Label bias persists.** Majority-label, recency, and feature biases in ICL are documented (Zhao et al. 2021). A study of 10 LLMs on 279 tasks found demonstrations and scale reduce label bias, but "ample bias persists". — [Beyond Performance arXiv 2405.02743](https://arxiv.org/html/2405.02743v1)
- **Some LLMs resist majority label bias.** Certain LLMs were about 90% robust to in-context majority label bias, with robustness linked to model size and richer instructions. — [arXiv 2312.16549 via fugumt](https://fugumt.com/fugumt/paper_check/2312.16549v1_enmode)
- **Label-preserving example sampling.** The EMNLP 2025 industry paper DPFS uses only human-written examples and samples them to preserve the training label distribution, aligning evaluation criteria with human labels. It reportedly outperforms DeepEval and APO methods "by a large margin". — [EMNLP 2025 industry.82](https://aclanthology.org/anthology-files/pdf/emnlp/2025.emnlp-industry.82.pdf)
- **Practitioner guidance (Hamel Husain's evals-skills, "write-judge-prompt").**
  - Include at least one clear Pass, one clear Fail, and one borderline example; borderline examples are "most valuable".
  - Put the critique before the verdict.
  - Never use dev/test examples as few-shot (leakage).
  - Recommends at least 20 Pass and 20 Fail labels to validate the judge.
  - [skills.sh hamelsmu/evals-skills](https://skills.sh/hamelsmu/evals-skills/write-judge-prompt)
- **Use expert critiques as few-shot material.** Critiques should be detailed enough to serve as few-shot material ("Critique Shadowing"). — [tianpan.co summary](https://tianpan.co/blog/2025/10/04/llm-as-judge-evaluation)
- **Don't copy example wording into the prompt.** Dropbox Dash (DSPy judge optimization) warned the optimizer: "avoid overfitting to specific example(s). Do not include exact examples or keywords from them in the prompt." — [Dropbox tech blog](https://dropbox.tech/machine-learning/optimizing-dropbox-dash-relevance-judge-with-dspy)

### Inferences
- (Inference) With only "a few labelled examples" for the surprise criterion, include all of them, balanced pass/fail. Present each with a short rationale explaining *why* it passes or fails relative to the criterion, following the MSwR result.
  - Frame them as illustrations of the principle, not as patterns to match. This guards against surface-cue overfitting, which matters because hidden test cases include unseen edit types.
- (Inference) Contrastive pairs work best: the same reply with a harmless edit (pass) and a harmful edit (fail). They teach the judge that the edit's *effect on meaning or policy* decides the verdict, not the presence of an edit. That directly supports both catch and keep.
- (Inference) Unbalanced examples (e.g., mostly fails) risk majority-label bias toward "fail", which lowers keep. Balance the example set or re-order it to alternate labels.

### Gaps
- No study found that compares nearest-neighbour vs fixed example selection for binary LLM judges on unseen error types.
- Original Hamel Husain blog posts were not fetched directly; the guidance above comes via his skill file and secondary summaries.

## 3. Chain-of-thought vs direct verdict; reasoning-first vs verdict-first

### Takeaway
CoT gives little gain when the criteria and references are detailed. It helps more when they are missing or vague (EvalBiasBench without references: α 0.647 direct vs 0.869 CoT). For lightweight judges, structured decomposition beats free-form CoT. Evidence on ordering is thin and conflicting: reasoning-first is the practitioner default, but post-hoc rationalization and inflated scores are documented risks.

### Cited Findings
- **Yamauchi et al. 2025 (GPT-4o, BIGGEN-Bench).** With full criteria and references, direct and CoT were nearly identical (α 0.912 vs 0.908; correlation 0.664 vs 0.666). Without criteria, CoT helped a lot (α 0.818 to 0.909). Without references on EvalBiasBench, α went from 0.647 (direct) to 0.869 (CoT). Conclusion: "CoT reasoning provides diminishing returns when detailed evaluation criteria are present." — [arXiv 2506.13639](https://arxiv.org/html/2506.13639v1)
- **ICLR 2026 (math grading).** CoT and multi-step pipelines can improve agreement, but G-Eval-style multi-step methods underperform simpler strategies. — [ICLR 2026 "Rethinking LLM Judges"](https://iclr.cc/virtual/2026/10017403)
- **Reasoning presence sways judges.** A 2026 ACL paper found weak judges are easily swayed by fluent reasoning and accept incorrect answers that come with it. Strong judges are more selective but can still be misled. — [ACL 2026 long.2082](https://aclanthology.org/2026.acl-long.2082.pdf)
- **CoT doesn't fix small judges.** RocketEval argues that lightweight judges' gap "is not easily enhanced through techniques such as chain-of-thought"; checklists work instead. — [RocketEval](https://www.iclr.cc/virtual/2025/poster/27674)
- **CoT plus voting helps checklist items.** In TICK, CoT substantially improves checklist-item accuracy, and maj@k over CoT samples improves it further. — [TICK](https://arxiv.org/html/2410.03608v1)
- **Ordering.**
  - One 2026 study found *score-first* gave higher agreement with humans than explanation-first. — [arXiv 2606.12234](https://arxiv.org/pdf/2606.12234)
  - Arize reports little measured accuracy difference between orderings but recommends explanation-first for grounding. — [Arize](https://arize.com/blog/evidence-based-prompting-strategies-for-llm-as-a-judge-explanations-and-chain-of-thought/)
  - A 2026 rationalization-bias paper argues post-decision explanations drift toward the label. It proposes "Proof-Before-Preference": lock criterion-wise evidence first, then decide. — [arXiv 2605.23970](https://www.alphaxiv.org/abs/2605.23970)
  - Hamel's skill mandates critique-before-verdict. — [skills.sh](https://skills.sh/hamelsmu/evals-skills/write-judge-prompt)
- **Verbosity of reasoning.** Adding "don't overthink" to GPT-4 in PoLL raised its performance, though it stayed below Command-R and Haiku. — [Eugene Yan summarizing PoLL](https://eugeneyan.com/writing/llm-evaluators/)

### Inferences
- (Inference) For this task the judge must first *locate* the edit and *determine its effect*, which is a multi-step operation. A short structured evidence step (quote the changed span, name the policy clause, say what changed) before the verdict fits the "Proof-Before-Preference" idea better than open-ended CoT.
- (Inference) Keep the reasoning short and structured, for example in JSON fields, with the verdict as the last field. This reduces the "talk itself into fail" risk and makes parsing deterministic.

### Gaps
- No primary study with Claude Haiku 4.5 specifically. No study isolating CoT for detecting edits in support replies.
- Extended thinking / reasoning-judge papers (JudgeLRM etc.) were not fetched in this pass.

## 4. Self-consistency / majority voting / panels; temperature-0 determinism

### Takeaway
Sampling plus aggregation beats greedy decoding on human correlation (GPT-4o 0.635 to 0.666 with mean over 5 samples). Greedy decoding gives zero variance but lower validity. Panels of diverse models (PoLL) beat a single GPT-4 judge, but our model is fixed, so only same-model voting or prompt-variant voting applies. Temperature 0 on Claude is reportedly not fully deterministic. Agreement between runs is a weak signal of correctness.

### Cited Findings
- **Sampling vs greedy (Yamauchi et al.; GPT-4o, BIGGEN-Bench; T=1.0, 5 seeds).**
  - Default setting correlation: greedy 0.635, majority 0.647, median 0.648, mean 0.666.
  - Llama3.1 default: greedy 0.593 vs mean 0.641.
  - "Greedy decoding ensures zero score variance, but it tends to show lower correlation with human judgments."
  - [arXiv 2506.13639](https://arxiv.org/html/2506.13639v1)
- **PoLL.** A panel of Command R, Claude 3 Haiku, and GPT-3.5 beat a single GPT-4 judge in correlation with humans across 3 settings and 6 datasets. It reduced self-preference bias and cost more than 7x less. Binary QA used max (majority) voting. — [Verga et al. arXiv 2404.18796](https://arxiv.org/html/2404.18796v2)
- **Majority vote has trade-offs.** It sometimes beat the best single run on balanced accuracy, but there is a trade-off between self-reliability and performance. — [Rating Roulette arXiv 2510.27106](https://arxiv.org/pdf/2510.27106) (full-text numbers not extracted)
- **Consistency is not validity.** Self-consistency is a positive but *weak* predictor of correctness, and agreement can reflect shared bias. — [arXiv 2607.08065](https://arxiv.org/pdf/2607.08065). See also "Reliability without Validity", which defines run-to-run self-consistency as how often each run matches the majority verdict. — [arXiv 2606.19544](https://arxiv.org/html/2606.19544)
- **A bare majority hides margin.** It cannot distinguish a 5-4 split from 9-0; the paper proposes modelling the vote distribution. — [arXiv 2512.03019](https://arxiv.org/html/2512.03019v1)
- **Multi-judge binary voting.** Majority voting of binary True/False verdicts from several judges improved alignment with humans. — [arXiv 2408.09235](https://arxiv.org/pdf/2408.09235v3)
- **Temperature 0 on Claude.**
  - Secondary sources report Anthropic's docs say temperature 0 results are "not fully deterministic". — [claudearchitectcertification.com](https://claudearchitectcertification.com/concepts/llm-fundamentals-tokens-and-sampling); [unstract](https://unstract.com/blog/understanding-why-deterministic-output-from-llms-is-nearly-impossible/)
  - Some secondary sources claim newer Claude models reject non-default temperature. This is unverified and the claim concerns Opus-class models, not Haiku 4.5. — [digitalapplied](https://www.digitalapplied.com/blog/which-ai-models-still-accept-temperature)

### Inferences
- (Inference) Run-to-run consistency is scored here, so variance directly costs points. Use temperature 0 (if Haiku 4.5 accepts it) plus a deterministic prompt and fixed example order.
  - If budget allows 3 calls, a 3-vote majority over *different prompt framings* at T=0 (e.g., checklist judge, holistic judge, adversarial "find a harmful change" judge) gives diversity like PoLL while staying near-deterministic.
  - 3 samples of one prompt at T>0 also gain accuracy but add run-to-run variance.
- (Inference) Odd panel size (3) avoids ties for binary verdicts.

### Gaps
- Could not extract Rating Roulette's numeric intra-rater reliability results (PDF not parsed).
- Could not confirm from Anthropic's primary docs whether Haiku 4.5 accepts temperature=0 or how deterministic it is.

## 5. Asymmetric decision rules and calibration (any-fail vs verify; precision/recall control)

### Takeaway
Binary judges tend to have asymmetric errors: high sensitivity on clean items and poor sensitivity on defective ones (Luo et al.: >95% vs 30-60%). The choice of aggregation rule over sub-checks or votes acts as a threshold knob that trades catch against keep. Because the metric is a harmonic mean, both sides must stay balanced. Calibrate the threshold on the labelled examples and track precision and recall separately rather than raw agreement.

### Cited Findings
- **Asymmetric errors.** In binary entailment judging, sensitivity was >95% on consistent summaries but only 30-60% on inconsistent ones (Luo et al.). — [Eugene Yan](https://eugeneyan.com/writing/llm-evaluators/)
- **Defect recall vs false failures.** EvalGen achieved defect recall 0.73 vs 0.49 for SPADE, with false-failure rates of 0.10 (medical) and 0.39 (product). — [Eugene Yan](https://eugeneyan.com/writing/llm-evaluators/)
- **Follow-up questions raise recall.** In Cohen et al. (LM vs LM), removing the follow-up questions cut recall by 6-10%. A verification or interrogation step mainly boosts recall. — [Eugene Yan](https://eugeneyan.com/writing/llm-evaluators/)
- **Partial defects are hardest.** SelfCheckGPT PR-AUC was 0.93 for obvious hallucinations but 0.53 for partial ones. — [Eugene Yan](https://eugeneyan.com/writing/llm-evaluators/)
- **Use classification metrics.** Track precision and recall separately because raw agreement misleads when classes are imbalanced. Use Cohen's κ rather than correlation, since correlation ignores chance agreement. — [tianpan.co](https://tianpan.co/blog/2025/10/04/llm-as-judge-evaluation); [Eugene Yan](https://eugeneyan.com/writing/llm-evaluators/)
- **Pass-rate thresholds.** Checklist pass rate (the fraction of yes answers) is a continuous score that can be thresholded. TICK and CheckEval aggregate by proportion. — [TICK](https://arxiv.org/html/2410.03608v1); [CheckEval](https://arxiv.org/html/2403.18771v2)
- **Label-based calibration.** Estimating bias from the model's predictions on the demonstrations themselves is one proposed calibration approach. — [arXiv 2405.02743](https://arxiv.org/html/2405.02743v1)
- **Binary over scales.** Practitioners prefer binary pass/fail because Likert scales can't be calibrated (annotators disagree on 3 vs 4). — [Eugene Yan, product evals](https://eugeneyan.com/writing/product-evals/); [skills.sh](https://skills.sh/hamelsmu/evals-skills/write-judge-prompt)

### Inferences
- (Inference) "Fail if any sub-check fails" maximizes catch but hurts keep. Auto-generated checklists contain about 40% weak items, so each spurious item becomes a potential false alarm.
  - A two-stage rule balances this: call 1 flags candidate violations, and a second call verifies only flagged items ("is this change actually a violation of the policy as written, or a harmless paraphrase?").
  - The verify step uses the budget only on suspected fails, which recovers keep without lowering catch much.
- (Inference) Expose one generic tunable scalar (e.g., the votes needed to fail out of 3, or a pass-rate threshold). Pick it on the dev labelled examples to maximize harmonic(catch, keep), never hand-tuned per criterion.
  - With very few examples, prefer the middle setting (majority) unless dev shows strong asymmetry.

### Gaps
- No published study directly compares "any-fail" vs "fail-then-verify" aggregation for binary LLM judges, measured in catch and keep.

## 6. Meta-evaluation with paired/counterfactual data; prompt optimization from few labelled examples

### Takeaway
Automatic prompt optimization (DSPy/MIPRO/GEPA) can help judges. Dropbox cut NMSE by 45%, and another study saw +3.8% precision with 250 labels. But it needs substantial labelled data, and early experiments showed overfitting. With only a few examples for a surprise criterion, prompt optimization at runtime is high-risk. Use the labels for validation and few-shot, not optimization.

### Cited Findings
- **Dropbox Dash relevance judge (DSPy).** NMSE fell 45% (8.83 to 4.86) vs the manual prompt. The team "encountered important challenges with overfitting during early experiments". — [Dropbox tech](https://dropbox.tech/machine-learning/optimizing-dropbox-dash-relevance-judge-with-dspy)
- **Weak verifiers paper.** Judge prompt optimization with 250 labelled examples gave on average +3.8% precision over the CoT baseline, with "no clear scaling relationships". — [arXiv 2506.18203](https://arxiv.org/pdf/2506.18203)
- **DSPy teleprompters overfit.** They "require significant amount of labeled data, and may sometimes lead to over-fitting". — [arXiv 2412.15298](https://arxiv.org/html/2412.15298v1)
- **Keep a held-out split.** Split SME-labelled judge data into train (prompt-building) and test (overfitting check). — [Towards Data Science](https://towardsdatascience.com/systematic-llm-prompt-engineering-using-dspy-optimization/)
- **Tool minimum is not a recommendation.** NeMo's MIPROv2 requires as few as 2 labelled examples to run, but that is a tooling floor. — [NVIDIA NeMo docs](https://docs.nvidia.com/nemo/microservices/latest/evaluate/flows/prompt-optimization.html)
- **Label budget for validation.** At least 20 Pass and 20 Fail labelled examples are recommended to validate a judge. — [skills.sh](https://skills.sh/hamelsmu/evals-skills/write-judge-prompt)

### Inferences
- (Inference) Do the prompt optimization *offline on dev across several criteria* (to learn a generic recipe), not per criterion at runtime.
  - Judge the recipe by its leave-one-criterion-out and leave-one-edit-type-out performance, which mimics the hidden surprise criterion and the unseen edit types.
- (Inference) Paired counterfactual data (same reply, harmless edit vs harmful edit) is the right meta-evaluation unit for the catch/keep metric. Building synthetic pairs for dev criteria lets you measure keep and catch per edit type without new human labels.

### Gaps
- No study found on prompt optimization with fewer than about 10 labels for judges, or on cross-criterion transfer of an optimized judge prompt.

## 7. Practical synthesis: fitting into ≤3 calls (all inference, built from the findings above)
- **Option A, decompose and verify.**
  1. Call 1 (cacheable per criterion): generate 3 to 7 YES/NO checks from the criterion and policy (TICK-style), each tied to a policy clause.
  2. Call 2: answer each check for the reply with short quoted evidence, then give a verdict.
  3. Call 3 (only if call 2 says fail): a verifier asks whether the flagged issue is a real violation or a harmless rewording.
  - This targets keep without losing catch.
- **Option B, voting.**
  - Make 3 T=0 calls with different framings (checklist, holistic with few-shot rationales, adversarial "find a harmful change"), then take the majority.
  - This is PoLL-like diversity within one model and near-deterministic for run-to-run consistency.
- **For both options:**
  - Include all provided labelled examples, balanced, with rationales.
  - Keep reasoning short, structured, and evidence-first, with the verdict last.
  - Use binary output parsed from JSON.
  - Pick the single fail-threshold knob on dev by harmonic(catch, keep) using leave-one-edit-type-out.
