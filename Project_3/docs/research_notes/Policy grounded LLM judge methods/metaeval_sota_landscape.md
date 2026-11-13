# Meta-evaluation of LLM judges, generalisation to unseen criteria, and the state of the art in policy/grounding checks (as of 13 Nov 2026)

Scope note: this file **extends** `docs/research_report.md` and `docs/research_notes/failure_modes.md`. Those files already summarise the four organiser papers (2608.24419, 2606.19544 [withdrawn], Observe.AI 2602.14970, 2609.02942), FBI's numbers (Remove Fact detected 6% → 48% with a reference), AbsenceBench and MiniCheck/LLM-AggreFact basics. Those findings are only restated in one line each here. Tags used below: **[fetched]** means read this session from a primary or official page. **[snippet]** means seen only as a search-result summary. **[prior knowledge, not fetched]** means a well-known result that was not re-read today, so verify it before quoting.

## (a) What meta-evaluation says judges fail at, and what fixed it

### Takeaway
Every perturbation benchmark finds the same thing. Judges are **invariant but insensitive**: they ignore surface edits but miss small edits that change the meaning, worst of all omissions, dropped conditions and hedge removal. The fixes with measured gains share one move. They give the judge an explicit thing to check against: a reference answer, rules or a checklist, or both answer orders. Asking it to "think harder" is not one of them. In 2026 the newest failure mode measured in policy settings is **"scope mis-attribution"**: the judge matches the reply to the wrong (compliant) rule. That failure, not a lack of reasoning, explains most missed violations.

### Cited Findings
- **Organiser papers, restated in one line each (details in failure_modes.md).**
  - 2608.24419: across 7 judges, invariance S≈0.945 but sensitivity R≈0.319. claude-haiku-4.5 had the highest R (0.561, S 0.917). Hedge removal (0.210) and condition removal (0.379) are among the hardest edits. — [arXiv 2608.24419](https://arxiv.org/html/2608.24419)
  - Observe.AI: style-only counterfactuals flip 6.9–7.9% of QA verdicts, and fairness instructions help only −2.5 to −4.2 points. — [arXiv 2602.14970](https://arxiv.org/html/2602.14970v1)
  - 2609.02942: rubric text alone predicts the judge's labels, and when the response is reversed the judge flips correctly only 37.7% of the time. — [arXiv 2609.02942](https://arxiv.org/html/2609.02942)
  - 2606.19544 was **withdrawn by arXiv admins**. — [arXiv 2606.19544](https://arxiv.org/abs/2606.19544)
- **FBI (EMNLP 2024)**: with a reference, single-answer GPT-4-turbo's detection of "Remove Fact" rose from 6% to 48% (already covered in research_report.md). — [arXiv 2406.13439](https://arxiv.org/html/2406.13439)
- **LLMBar (Zeng et al., ICLR 2024)** [snippet + repo] has 419 pairs with Natural and Adversarial splits (Neighbor, GPTInst, GPTOut, Manual).
  - Three prompt strategies were tested. **Rules** states evaluation priorities that favour faithful execution of the instruction. **Metrics** has the judge first write instruction-specific questions, then apply them. **Swap** judges both answer orders and reconciles them.
  - The best combination, Rules+Metrics+Reference, adds roughly 10 points for GPT-4 on the Adversarial split. GPT-4 reached about 82.8% on Adversarial vs 95% for human experts (a secondary summary says 85.4%, so check the tables).
  - Swap raises positional agreement without hurting accuracy.
  - Sources: [arXiv 2310.07641](https://arxiv.org/pdf/2310.07641), [GitHub princeton-nlp/LLMBar](https://github.com/princeton-nlp/LLMBar)
- **JudgeBench (ICLR 2025)** [snippet]: on hard pairs with objective correctness, GPT-4o with the Arena-Hard prompt scored 56.57% and vanilla GPT-4o 50.86% (chance is 50%). Claude-3.5-Sonnet was the best general model at 64.29%. The lesson is that judges are near chance once the difference is about correctness rather than style. — [ICLR 2025 proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/9e720fce64f91114c49cfd640d821da3-Abstract-Conference.html), [themoonlight review](https://www.themoonlight.io/review/judgebench-a-benchmark-for-evaluating-llm-based-judges)
- **CompliBench (UCSB + Cresta, arXiv 2604.12312, 14 Apr 2026)** [fetched abstract page]. This is the closest published analogue to our task: per-turn guideline-violation detection in airline, healthcare and insurance dialogues, with judges asked to name the governing guideline plus give a binary label. — [alphaXiv 2604.12312](https://www.alphaxiv.org/abs/2604.12312)
  - **How the violations are made.** An adversarial judge-and-refine loop builds them, and a variant is kept only if it changes behaviour and the adversarial judge *misses* it. These are hard, minimal violations, similar to our meaning-changing edits.
  - **Gemini-3-pro had the highest violation-detection accuracy (VDA)**, above 90% in all domains. Base Qwen3-8B had conversation-level accuracy below 2%.
  - **Failure modes.** Many judges had high accuracy on compliant turns but low VDA, meaning they say "compliant" too often. **For GPT-5, scope mis-attribution caused over 70% of missed violations**: the judge maps the non-compliant action to a different, compliant rule. Other errors were over-strict reading of acceptable paraphrase (false fails), missed required actions (omissions) and invented dependencies between steps. Reward models labelled everything one way.
  - **What fixed it.** Fine-tuning Qwen3-8B on the synthetic data, with chain-of-thought distilled from larger models, gave 51.47% conversation-level accuracy on airline, the best reported, matching or beating GPT-5 and Gemini-3-pro. It also transferred to unseen domains (healthcare, insurance).
- **Language-switching invariance (Yin, arXiv 2606.14278, Jun 2026)** [fetched PDF, parsed locally]. This includes **Claude Haiku 4.5 (claude-haiku-4-5-20251001)** on LLMBar's 419 items in English, Chinese and code-switched EN/ZH, with both answer orders. — [arXiv 2606.14278](https://arxiv.org/pdf/2606.14278)
  - Haiku accuracy: EN 78.9%, ZH 74.3%, language-switched 74.4%.
  - **Haiku's judgment-flip rate vs English: 14.2% for EN–ZH and 12.3% for EN–LS.** Correctness-flip rates are nearly the same (14.1% and 12.0%), so the flips are real errors and not harmless swaps. McNemar p < 0.001.
  - Across all judges flip rates ran 10.7–14.4%, and every judge was most accurate in English.
  - On translation-equivalent tie probes Haiku answered "tie" 82.3% of the time.
  - Haiku's position inconsistency rose from 13.6% (EN) to 18.4% (language-switched).
  - Chinese is not one of our languages; no DE/FR/ES/IT numbers were found.
- **READ (AIES paper)** [snippet only; the PDF was blocked by a bot-wall]: a judge can reach the right verdict by leaning on a learned safety prior rather than the supplied policy. The authors propose perturbing the *policy* text to test whether verdicts depend on it. — [AAAI/AIES](https://ojs.aaai.org/index.php/AIES/article/download/43237/50797/47343)
- **Rubrics as an attack surface (arXiv 2602.13576)** [snippet]: refining a rubric until it passes a benchmark can cause systematic preference drift on the target domain. Rubric tuning on dev may therefore not transfer. — [alphaXiv 2602.13576](https://www.alphaxiv.org/abs/2602.13576.md)
- **"Judging the Judges" (Thakur et al. 2024)** [prior knowledge, not fetched]: percent agreement hides judge differences, Cohen's kappa separates judges better, and judges are lenient (they over-accept). — [arXiv 2406.12624](https://arxiv.org/abs/2406.12624)

### Inferences
- CompliBench's "scope mis-attribution" is the policy-checking form of our dropped-condition miss. When "free cancellation" loses its "up to 48h before pickup", the judge finds *some* rule that permits free cancellation and passes the reply. The fix that follows is to make the judge **quote the exact governing policy clause and list every condition in that clause** before deciding, rather than ask "is this consistent with the policy?". That is the extract-then-check design already in ARCHITECTURE.md, and this evidence supports it. One addition: require the clause quote to be **verbatim** and check it in code. RULERS does the same with its evidence check (section b).
- The 2606.14278 numbers suggest that translation alone may cost Haiku 10–14% flips on *hard* items. The hidden set's translated-harmless items are probably easier than LLMBar's adversarial ones, but a translation-flip cost of a few percent should be budgeted for. Mitigation: reason in English while quoting the source-language span (already in the design), and make the number rule normalise locale formats (1.000,50 vs 1,000.50).
- Swap and order invariance from LLMBar do not apply directly (we judge single answers), but the principle does: **present the same content two ways and require agreement before failing**. That is a cheap guard for reorder and translation types.

### Gaps
- No numbers found for EvalBiasBench/OffsetBias or for CheckList-style judge tests from 2025–2026 in this session.
- No DE/FR/ES/IT language-invariance numbers for Haiku 4.5.
- CompliBench's per-model F1 and per-violation-type numbers were not on the abstract page. The full PDF was not read.
- The READ paper's numbers could not be retrieved because of the bot-wall.

## (b) Generalising to unseen criteria and unseen edit types

### Takeaway
Fine-tuned "custom-rubric" judges (Prometheus 1/2) generalise to new rubrics inside their own domain but weakly outside it. For a fixed prompt-only model, the best-evidenced recipe for a new criterion is: **compile the criterion once into a locked, explicit checklist; score each item with verbatim evidence checked in code; calibrate a single global threshold on the few labelled examples.** Generated rubrics transfer well for style or linguistic quality and badly for factual or specialised checks. That is a warning against auto-generating long rubrics for a policy criterion.

### Cited Findings
- **RULERS (arXiv 2601.08654v3, 9 Sep 2026; no venue listed)** [fetched]. It treats judging as "criteria transfer" to a frozen LLM in three phases. — [arXiv 2601.08654](https://arxiv.org/html/2601.08654)
  - **Phase I** compiles the rubric into a *locked* bundle of checklist items, anchors and evidence rules, hashed and reused for every item.
  - **Phase II** scores each item 0/1/2 with **evidence quotes that are checked against the source text**.
  - **Phase III** calibrates with ridge regression plus quantile mapping, fit on N=200 labels and then frozen.
  - **Results (QWK).** RULERS was best in 13 of 16 dataset×backbone cells. With GPT-4o-mini: ASAP 0.708 vs best baseline 0.557, DREsS 0.529 vs 0.294, WebNLG 0.614 vs 0.572, SummHF 0.398 vs 0.328. It also worked on Llama-3.1-8B, except on SummHF.
  - **Ablations (GPT-4o-mini).** Removing calibration cost the most (ASAP 0.708→0.657, WebNLG 0.614→0.504). Removing locked compilation cost 0.03–0.07, and removing evidence anchoring cost 0.02–0.05.
  - QWK was "relatively stable" under reversed or paraphrased rubric wording (figure only, no numbers).
  - Giving baselines the same calibration did not close the gap (ASAP 0.541 vs 0.708).
- **GER-Eval / "Learning to Judge" (arXiv 2602.08672)** [snippet]: LLMs generating and applying their own rubrics, zero-shot and few-shot. Rubrics transfer well for open-domain linguistic quality. For factual or specialised data such as SumPubMed, one reported correlation is **below 0.3**. — [arXiv 2602.08672](https://arxiv.org/html/2602.08672v1)
- **GenRubric (arXiv 2608.29856)** [snippet]: a self-evolving rubric generator whose gains "extend to held-out domains not observed during training". It needs training, so it is not reproducible with prompts only. — [HF papers 2608.29856](https://huggingface.co/papers/2608.29856.md)
- **Prometheus / Prometheus 2** [snippet]. Prometheus-13B reached Pearson 0.897 with humans on 45 customised unseen rubrics (GPT-4 0.882). Prometheus 2 (EMNLP 2024) supports custom criteria in direct and pairwise modes and was the best *open* evaluator on 4+4 benchmarks. — [arXiv 2310.08491](https://arxiv.org/html/2310.08491v2), [arXiv 2405.01535](https://arxiv.org/abs/2405.01535v2)
  - Our earlier notes record that fine-tuned rubric judges "failed to generalize" out of domain and scored below random on LLMBar fairness (rubric_prompting_methods.md, via Eugene Yan).
- **CompliBench transfer** [fetched]: a judge trained only on airline guidelines generalised to healthcare and insurance. Policy-violation *skills* (find the governing rule, check its conditions) transfer across policy documents when the data teaches the procedure rather than the domain. — [alphaXiv 2604.12312](https://www.alphaxiv.org/abs/2604.12312)
- **LLMBar "Metrics"** [snippet]: having the judge write instance-specific check questions before judging helped GPT-4 on adversarial pairs, as part of the roughly +10 point combination. — [arXiv 2310.07641](https://arxiv.org/pdf/2310.07641)
- **Edit types not in dev.** The 2608.24419 taxonomy (scope: domain extension, population widening, quantifier strengthening, tense/modality shift; strength: condition removal, hedge removal, intensifier addition) is the most complete public list of meaning-changing minimal edits. — [arXiv 2608.24419](https://arxiv.org/html/2608.24419)
  - Of these, **population widening, domain extension, intensifier addition and tense/modality shift** are probably absent from our dev set and are plausible hidden types. Examples: "all customers" instead of "Gold members"; "at all branches" instead of "at airport branches"; "guaranteed" added; "will be refunded" instead of "may be refunded".
  - CompliBench adds **missing required action** and **invented step dependency**.

### Inferences
- **Prompt-only RULERS fits the 3-call budget.** Phase I (compile the criterion into a checklist) can be done in `prepare()` deterministically: parse the criterion text and policy into atomic items. If it uses an LLM, it must not be per-reply state; safer to keep it as text in the prompt. Phase II is our extract-and-check call with verbatim quotes checked in code. Phase III is a single global threshold or vote rule chosen on dev, never per criterion.
  - Only RULERS' calibration needs data, and with 5–10 surprise examples it can only choose between 2–3 preset operating points, not fit a regressor. This is inference, not tested.
- **Generalise across edit types by checking the meaning dimension, not the edit.** Instead of "did they drop a condition?", ask per commitment: *who* it applies to (population), *where/what* (domain), *how much* (number/quantity), *how sure* (modality/hedge/intensifier), *under what conditions*, *when* (tense/deadline), and *what the customer must do* (required action). Each dimension maps to one or more items in the 2608.24419 + CompliBench taxonomies, so unseen edit types still land in a known slot.
- **Use the few labelled examples for the surprise criterion as calibration and in-context contrast pairs, not as a source for rubric generation.** GER-Eval shows auto-rubrics transfer poorly on factual criteria, and the attack-surface paper shows rubric tuning drifts. Keep the criterion text verbatim and show 2–4 examples as pass/fail pairs with one-line reasons.

### Gaps
- No paper found that measures few-shot (≤10 labelled examples) adaptation of a *prompt-only* judge to a brand-new binary criterion, with held-out edit types.
- RULERS' perturbation-robustness numbers appear only in a figure. It is a September 2026 v3 preprint without peer review.

## (c) Best systems available now for policy and grounding compliance checking

### Takeaway
The leaders split into three families:
1. **Small fine-tuned NLI-style checkers** (MiniCheck/Bespoke, FactCG, Granite Guardian, Lynx, HHEM, Luna). They score each sentence or claim for support against the context.
2. **LLM judges with structured claim-level output** (Vertex Check Grounding, Azure groundedness with reasoning).
3. **Neuro-symbolic policy checkers** (AWS Bedrock Automated Reasoning). An LLM translates the policy and the Q/A into logic, then a solver proves VALID/INVALID.

The best LLM-AggreFact scores are around 79.5 balanced accuracy, and nobody is near human level. Most vendor accuracy figures are self-reported.

### Cited Findings
- **LLM-AggreFact leaderboard** [fetched; no update date shown]: nimble-v4-max (27B) 79.5, Clef (27B) 79.0, Decider v1.2 (27B) 78.7, Jev 1.13.0 78.7, d1-ultra 78.5, nimble-v4 (9B) 77.8, **Bespoke-MiniCheck-7B 77.4**, Claude-3.5 Sonnet 77.2, Clef Flash 76.6, Drex v1.5 76.5, **Granite Guardian 3.3 (8B) 76.5**, Mistral-Large 2 76.5, gpt-4o 75.9, **FactCG-DeBERTa-L (0.4B) 75.6**. **No Claude 4.x or Haiku entry.** — [llm-aggrefact.github.io](https://llm-aggrefact.github.io/)
  - A mirror imported on 2026-05-29 shows a different ordering (Bespoke first at ~77.5). Treat the rankings as approximate. — [benchmarklist mirror](https://benchmarklist.com/benchmarks/llm_aggrefact/)
- **Google FACTS Grounding** (a different task: does the model's *own* answer stay grounded?) [snippet]: Gemini 3 Pro about 69.0%, GPT-5 69.6%, Claude 4.5 Opus 62.1%, with a 62–74% spread. — [arXiv 2512.10791](https://arxiv.org/html/2512.10791v1), [Hacks/Hackers](https://www.hackshackers.com/googles-new-benchmark-reveals-wide-gaps-in-ai-factual-accuracy-and-shows-search-tools-help)
- **AWS Bedrock Automated Reasoning checks** (GA Aug 2025) [fetched AWS blog]. — [AWS News Blog](https://aws.amazon.com/blogs/aws/minimize-ai-hallucinations-and-deliver-up-to-99-verification-accuracy-with-automated-reasoning-checks-now-available)
  - **How it works.** A policy document (up to 122,880 tokens, about 100 pages) is compiled into **variables, rules (each with an ID) and custom types**. Users refine it with test cases (expected VALID/INVALID/SATISFIABLE), auto-generated scenarios and a translation confidence threshold. At runtime the Q/A is translated into logic and checked, and findings cite the rule IDs that cause a contradiction.
  - **The "up to 99% verification accuracy" claim is AWS's own** and, per a later AWS post, applies only to *unambiguous* natural-language-to-logic translations. No independent benchmark was found.
  - Later additions: auto-generation of test Q&A (Nov 2025). Two automated policy-refinement workflows (Jun 2026) were reported only on an AWS-hosted mirror and are unconfirmed.
  - Sources: [AWS what's new Nov 2025](https://aws.amazon.com/about-aws/whats-new/2025/11/automated-reasoning-checks-include-natural-language), [AWS policy refinement blog](https://aws.amazon.com/blogs/machine-learning/automated-reasoning-policy-refinement-in-amazon-bedrock)
  - It does not defend against prompt injection. — [dev.to](https://dev.to/aws-builders/amazon-bedrock-automated-reasoning-checks-eliminate-hallucinations-with-ai-1i42)
- **Azure AI Content Safety groundedness detection** [snippet of MS Learn]. It flags ungrounded segments, has an optional **reasoning** mode (explanations, recommended for development) and a **correction** preview that rewrites flagged text from sources. The example corrects a 5% rate to the 4.5% in the source, which is exactly our wrong_number case. It is **English-only (optimised)**. — [MS Learn groundedness](https://learn.microsoft.com/en-gb/azure/ai-services/content-safety/concepts/groundedness), [MS Tech Community](https://techcommunity.microsoft.com/blog/azure-ai-services-blog/correction-capability-helps-revise-ungrounded-content-and-hallucinations/4253281)
- **Google Vertex AI Check Grounding API** [snippet of docs]. It returns an overall **support score from 0 to 1** and optional **claim-level support scores** with citations to fact chunks. A citation threshold filters responses. Latency is claimed below 500 ms (vendor). — [Google Cloud docs](https://docs.cloud.google.com/generative-ai-app-builder/docs/check-grounding?authuser=0)
- **Patronus Lynx** (open, 2024) [snippet of vendor docs/paper]. HaluBench has 15k items with hard negatives built by **semantic perturbation** of answers. Vendor-reported HaluBench accuracy: Lynx-8B 84.3%, Lynx-70B 87.4%, Llama-3-70B-Instruct 80.1%. — [Patronus docs](https://docs.patronus.ai/docs/hallucination-detection), [arXiv 2407.08488](https://arxiv.org/html/2407.08488v2)
- **Galileo Luna** (DeBERTa-large encoder) [vendor blog]. It beats RAGAS and GPT-3.5 on RAGTruth QA and summarisation, reporting P/R/F1 with per-task tuned thresholds. It was trained only on QA RAG. — [Galileo blog](https://galileo.ai/blog/galileo-luna-breakthrough-in-llm-evaluation-beating-gpt-3-5-and-ragas)
- **Vectara HHEM-2.1-open** [snippet]: powers Vectara's hallucination leaderboard and was trained partly on RAGTruth, so RAGTruth is not a held-out test for it. — [arXiv 2505.04847](https://arxiv.org/html/2505.04847v2)
- **Policy violation detection on tau-bench-style data (arXiv 2512.03994)** [fetched].
  - On DynaBench, F1: **GPT-4o-mini as judge 70.1**, Qwen3-8B judge 60.7, LlamaGuard-3 20.9, DynaGuard-8B 73.1, and activation-whitening on Qwen2.5-7B 86.0 (a white-box method that needs hidden states, so it is not usable with the Haiku API).
  - On 25+25 real tau-bench airline trajectories, **GPT-4o-mini as judge had the best F1 at the default operating point**; whitening AUC was 0.87.
  - Takeaway: general-purpose guard models built for safety (LlamaGuard) are poor at *custom-policy* compliance. Prompted LLM judges are competitive.
  - Source: [arXiv 2512.03994](https://arxiv.org/html/2512.03994v3)
- **Policy violations in agent benchmarks** [snippet]. IBM's Near-Miss estimates about a quarter of tau2-bench airline failures are policy violations and that outcome-only grading misses violations that leave the final state unchanged. "Reason Less, Verify More" finds that deterministic pre-execution gates beat relying on the model to apply every rule. — [arXiv 2603.29665](https://arxiv.org/pdf/2603.29665), [HF 2607.07405](https://huggingface.co/papers/2607.07405.md)
- **Glider (Patronus, 3.8B general judge), NVIDIA NeMo Guardrails fact-checking, HHEM-2.x numeric scores**: not retrieved this session (see Gaps).

### Inferences
**What the leaders do, and what Haiku can reproduce with prompts:**

| Leader idea | Reproducible prompt-only on Haiku 4.5? | How |
|---|---|---|
| Claim/sentence-level support scores (MiniCheck, Vertex claim scores, Azure segments) | Yes | One structured call: list each commitment, quote the supporting policy clause verbatim (or "NONE"), and label it supported, contradicted or unsupported. Code fails the reply if any is contradicted or unsupported and material. |
| Hard negatives from semantic perturbation (Lynx, CompliBench) | Partly, offline only | Use the 2608.24419 taxonomy to write *synthetic* stress pairs from the public policy for dev testing (never from hidden data). |
| Policy compiled into variables + rules with IDs (AWS AR) | Yes, as text | In `prepare()`, segment the policy into numbered clauses deterministically, so the judge cites a clause ID and code can check that the ID and quote exist. A full SMT solver is overkill and rule-risky. |
| Translation-ambiguity flag (AWS TRANSLATION_AMBIGUOUS) | Yes | Let call 1 output "AMBIGUOUS". Route those to verify instead of deciding. |
| Correction / rewrite (Azure) | Not needed | It is a useful *verify* idea, though: "what would the policy-correct sentence say?" A diff against that rewrite exposes dropped conditions. This is the "show what changed" idea, untested. |
| Calibrated threshold (RULERS, Vertex citation threshold) | Yes | One global vote/threshold knob chosen on dev. |
| Fine-tuned small judge (CompliBench Qwen3-8B, DynaGuard) | No | Model is fixed to claude-haiku-4.5. |

- None of these systems is benchmarked on *meaning-changing minimal edits in multilingual customer-service replies*. Vendor numbers such as 99%, 84–87% and 79.5 BAcc are not comparable with our harmonic-mean metric.

### Gaps
- No public LLM-AggreFact, CompliBench or FACTS numbers for claude-haiku-4.5 as a grounding checker.
- Glider's FLASK and BigGen numbers, Galileo Luna-2, HHEM-2.x balanced accuracy and NeMo Guardrails fact-check accuracy were not found this session. Search returned nothing usable.
- No independent evaluation of AWS Automated Reasoning checks was found.

---

### Validity vs reliability (cross-cutting; folded in here because of the three-section format)
- Kappa is lower than raw agreement, and agreement can hide poor discrimination. The source for this is the withdrawn 2606.19544 [fetched earlier] plus "Judging the Judges" [prior knowledge, not fetched]. Report **Cohen's kappa against the gold labels per edit type and per language**, plus **run-to-run agreement**, separately. — [arXiv 2606.19544](https://arxiv.org/abs/2606.19544), [arXiv 2406.12624](https://arxiv.org/abs/2406.12624)
- 2608.24419 recommends reporting sensitivity *at matched invariance*, a surface-only baseline (55–67% of public labels are predictable from surface features alone) and a label-permutation null. — [arXiv 2608.24419](https://arxiv.org/html/2608.24419)
- Risk: a judge that always answers "pass" has perfect consistency and perfect invariance with zero sensitivity. CompliBench's high accuracy on compliant turns with low VDA, and the reward models that labelled everything one way, are real cases of this. — [alphaXiv 2604.12312](https://www.alphaxiv.org/abs/2604.12312)

### What the best solution available right now looks like for this setup (inference, synthesised from the above)
1. **Deterministic layer first.** A number/entity rule that checks digits, amounts, durations and percentages against the policy, normalised for EN/DE/FR/ES/IT formats. It validates itself on the labelled examples and switches off automatically if the criterion does not concern facts. This mirrors Azure's correction example and the "deterministic gates" result.
2. **Call 1: compile, extract and check (RULERS Phase I+II, MiniCheck/Vertex claim-level, AWS rule IDs).** The policy is pre-segmented into numbered clauses in `prepare()`. Haiku lists every commitment in the reply. For each one it gives:
   - the verbatim span,
   - the governing clause ID and a verbatim quote, to counter CompliBench's scope mis-attribution,
   - each condition, qualifier and hedge in that clause, marked present or absent in the reply,
   - checks along the dimensions population, scope, quantity, modality, conditions, time and required action, which cover unseen edit types,
   - a label: supported, contradicted, unsupported or ambiguous.

   Code verifies that the quotes exist and computes the verdict.
3. **Call 2: verify, only on candidate fails or ambiguous items**, in fresh context. Ask "write the policy-correct version of this sentence, then compare" (a "know what changed" diff, untested) and apply the invariance principle (language, order, opener and filler matter only if the criterion says so).
4. **Call 3: tie-break.** A second verify using the presentation-swap idea (for example, the reply sentence quoted in English gloss vs the original language), since LLMBar's Swap reduced order bias.
5. **One global calibration knob** (votes needed to fail), chosen on dev by the harmonic mean, with leave-one-edit-type-out. For the surprise criterion: the criterion text stays verbatim, and the 2–4 labelled examples go in as contrast pairs.
6. **Report like 2608.24419**: sensitivity per meaning edit at the measured invariance per harmless edit, per-language flip rates, run-to-run agreement, and a surface-only baseline. No response cache.

Expected weak spots, given the evidence: hedge and intensifier edits (the lowest sensitivity in 2608.24419), translation flips (Haiku flips 12–14% on hard LLMBar items across languages), and over-strict false fails on acceptable paraphrase (CompliBench).
