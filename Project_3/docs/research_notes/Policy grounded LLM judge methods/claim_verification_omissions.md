# Claim verification against a reference, and detection of omissions, hedge strengthening and scope widening (extension notes, 13 Nov 2026)

Scope: these notes add to `research_report.md`, `research_notes/decomposition_verification.md` and `research_notes/failure_modes.md` and do not repeat them. Already covered there: FActScore, SAFE, RefChecker, MiniCheck/AlignScore costs, the MiniCheck decomposition ablation, Claimify, DnDScore, AbsenceBench, MED-OMIT, FineSurE, EQUATE, generalized quantifiers, DynaGuard, VeriFastScore, and the four brief papers.

Sources are marked **[fetched]** when this session read the page, or **[search]** when the claim comes only from a search-engine summary. Treat [search] numbers as unverified until someone opens the paper. "Inferences" are my own reasoning about our judge, not findings from the sources.

## Q1. Which decomposition-verification methods work best, and what do ablations say about granularity and about decompose-then-verify vs. a single pass?

### Takeaway
New 2026 evidence (arXiv 2603.28005) shows that a **holistic single-call judge beats a single-call "decompose the candidate into atomic claims" judge at detecting *incompleteness***, by +14.5 to +33 points. The cause is that candidate-side decomposition has no list of what is missing. The atomic judge is slightly better only at catching contradicted or unsupported content. Our call 1 already avoids this failure because it lists **reference-side** conditions per claim. The finding supports keeping that design and making the reference-side list more central, rather than adding more claim splitting.

### Cited Findings
- **"Rethinking Atomic Decomposition for LLM Judges: A Prompt-Controlled Study of Reference-Grounded QA Evaluation"** (X. Zhang, arXiv 2603.28005, 30 Mar 2026). It compares two designs, both one call each, on ASQA, QAMPARI and TruthfulQA with 400 rows per cell. **C** is candidate-side atomic decomposition, which splits the answer, checks each claim against the reference and returns JSON. **H** is a holistic rubric judge covering correctness, completeness and unsupported detail. The judges were Claude Opus-4.6, Claude Sonnet-4.6, GPT-4.1 and Gemini Flash Lite. No Haiku was tested. — [arXiv html](https://arxiv.org/html/2603.28005) [fetched]
  - ASQA accuracy, C vs. H: Opus 0.778 vs. 0.850, Sonnet-4.6 0.715 vs. 0.810, GPT-4.1 0.565 vs. 0.720, Gemini Flash Lite 0.550 vs. 0.698. On TruthfulQA, C was equal or better for every judge (e.g. Sonnet-4.6 0.975 vs. 0.945). — [arXiv html](https://arxiv.org/html/2603.28005) [fetched]
  - **On the "partially supported / incomplete" class**, C vs. H was: Opus .555 vs. .700, Sonnet .430 vs. .620, GPT-4.1 .160 vs. .465, Gemini Flash Lite .125 vs. .455. **The weakest models suffer most from candidate-side decomposition when the error is an omission.** — [arXiv html](https://arxiv.org/html/2603.28005) [fetched]
  - The authors explain that with candidate-side decomposition "nothing in its structure lists what the candidate leaves out." A C-v2 prompt that also asked for "completeness" still trailed H, so the gap is not only a wording effect. — [arXiv html](https://arxiv.org/html/2603.28005) [fetched]
  - Caveats: three QA benchmarks of 200 examples each, and labels built by construction. On a 60-row check labelled by the author alone, the ranking reversed: C beat H for every judge, e.g. 54 vs. 52 for Opus. Multi-stage pipelines and externally supplied decompositions were not tested. — [arXiv html](https://arxiv.org/html/2603.28005) [fetched]
- **Counter-evidence from another task type:** structured, decomposed verification of math reasoning reportedly reached 65.2% F1 on OlympiadBench versus 35.9% for holistic verification. That is error finding in reasoning chains, not reference grounding. — [alphaxiv summary of arXiv 2506.12509](https://www.alphaxiv.org/overview/2506.12509v3) [search]
- **VeriScore** (Song, Kim and Iyyer, Findings of EMNLP 2024) extracts only *verifiable* claims and skips hypotheticals and opinions, unlike FActScore and SAFE, which decompose everything. Human annotators reportedly preferred its extraction over SAFE's about 93% of the time. GPT-4o was the best of the 16 models scored. — [arXiv 2406.19276](https://arxiv.org/abs/2406.19276v1); [ACL Anthology](https://aclanthology.org/2024.findings-emnlp.552.pdf) [search; the 93% figure is from a summary, not checked in the paper]
- **The LLM-AggreFact leaderboard (current page, no update date shown)** is now topped by fine-tuned 9B-27B checkers: nimble-v4-max 79.5, Clef 79.0, Decider v1.2 78.7, Bespoke-MiniCheck-7B 77.4. Claude-3.5 Sonnet sits at 77.2 and MiniCheck-Flan-T5-L at 75.0. **No Claude Haiku, 3.7 or 4.x row is listed.** — [llm-aggrefact.github.io](https://llm-aggrefact.github.io/) [fetched]

### Inferences
- The decompose vs. holistic question is a false choice for us. What matters is **which side gets decomposed**. Decomposing the candidate catches additions and contradictions, such as wrong_number and wrong_policy_detail. Listing the reference catches omissions, such as condition_removal and hedge_removal. Call 1 already does both, through claims plus `policy_conditions`. Per 2603.28005, the omission recall comes from the reference list, so the prompt should make Haiku **copy the policy rule's conditions verbatim before it looks at the reply wording**. Today the reply claim is extracted first and conditions are attached to it.
- One gap remains. If the reply never makes a claim that maps to a rule (for example, the claim is paraphrased so loosely that Haiku attaches `policy_rule: null`), no conditions are listed and the omission is invisible. A cheap safeguard: when `policy_rule` is null but the claim contains an entitlement or promise verb, treat it as "unsupported promise" for the second look.
- The leaderboard gives no Haiku-class number, so we cannot cite an external accuracy for Haiku-4.5 as a checker. Only our own dev runs can supply that (per AGENTS.md, only numbers from `score.py`).

### Gaps
- No 2025-2026 study measures reference-side vs. candidate-side decomposition on *conditional* statements, or on a Haiku-class model.
- 2603.28005 is a single-author preprint whose labels reverse under a small human check. Treat the direction as suggestive, not settled.

## Q2. Which methods detect omissions and missing conditions specifically, and with what numbers?

### Takeaway
The best-supported recipe is still an **explicit inventory in the reference-to-response direction** (QuestEval recall, FineSurE keyfacts, MED-OMIT facts, and the "placeholder" effect in AbsenceBench, already covered). New evidence adds two points: holistic or inventory prompts beat claim-splitting on incompleteness (Q1), and precision-only metrics reward texts with too much removed. I found no method or dataset aimed at dropped *conditions or qualifiers* as opposed to dropped facts.

### Cited Findings
- **QuestEval** (EMNLP 2021, older) combines precision (questions generated from the summary, answered on the source) with recall (questions generated from the source, answered on the summary). A learned "question weighter" decides which source questions matter and applies only to recall. On SummEval the unified metric reached an average Pearson of 33.5, against 28.4 for precision-only and 27.5 for recall-only. — [arXiv 2103.12693](https://arxiv.org/pdf/2103.12693) [search]
- Recall-only QA "does not take into account possible model hallucinations," because the summary could answer a question wrongly. Both directions are needed. — [arXiv 2103.12693](https://arxiv.org/pdf/2103.12693) [search]
- A document-simplification study warns that "precision-oriented metrics will skew in favour of very short and concise simplifications even when too much information has been removed." It uses QAFactEval's recall-oriented variant, with questions from the source, to compensate. — [arXiv 2404.03278](https://arxiv.org/pdf/2404.03278) [search]
- **EmbedKDECheck** (TALN 2025 / EMNLP 2025 Industry) detects omissions in medical summaries without a reference, using small-model embeddings and density-based anomaly detection. It is compared against SelfCheckGPT, ChainPoll, G-Eval and GPTScore. — [TALN 2025](https://aclanthology.org/2025.jeptalnrecital-taln.15.pdf); [EMNLP 2025 talk](https://underline.io/lecture/131700-detecting-omissions-in-llm-generated-medical-summaries) [search; numbers not checked]
- AbsenceBench was accepted at NeurIPS 2025 (Datasets and Benchmarks); its numbers are already in decomposition_verification.md. — [NeurIPS 2025 poster](https://neurips.cc/virtual/2025/poster/121453) [search]

### Inferences
- With our Haiku budget, the QuestEval idea becomes "**questions from the policy rule, answered on the reply**." For each condition C of a matched rule, ask: "Does the reply say or imply C (any language)? Quote it or say NONE." Requiring a quote for "kept" is the key change. It turns absence into a verifiable claim: no quote means dropped. Today `status: kept` needs no evidence, so Haiku can mark a condition kept without pointing at text. **Concrete, cheap change: add `"evidence_quote"` to each `policy_conditions` item and have code treat `kept` with an empty quote, or a quote not found in the reply (a stdlib substring check after whitespace and case normalisation), as `dropped`.** This is the code-verifiable version of the AbsenceBench placeholder effect. It must be measured on dev, because paraphrased or translated conditions may not match a verbatim substring. Use a fuzzy `difflib.SequenceMatcher` ratio, or only require the quote to come from the reply.
- The precision-skew warning matches our failure case directly. A reply that drops a condition contains *fewer* claims, so precision-style checking (is every reply claim supported?) passes it. Only the recall direction catches it.
- Relevance gating (already noted in earlier notes) is what keeps the recall direction from failing harmless padding removal. Conditions only count for rules the reply actually asserts.

### Gaps
- I found no benchmark with labels for "dropped condition or exception" in policy or legal QA. The closest are CONFER (Q3) and the distortion datasets (Q3). No published numbers exist for quote-required inventory checks vs. plain status labels.

## Q3. Detection of hedge/certainty strengthening, quantifier/scope widening, negation flips and added commitments

### Takeaway
Three 2024-2026 findings matter. (1) **claude-haiku-4.5 itself raises expressed certainty when it rewrites text**: 20% of medical examples after one paraphrase, 40% after five (EMNLP 2026). The `gloss_en` step in our call 1 is therefore a place where "usually" can quietly become "always." (2) LLM judges penalise *weakeners* on correct answers (GPT-4o accuracy 92.7 → 73.7). That bias works against our "stricter or hedged reply is fine" rule. (3) Comparing certainty and generality between paired texts is hard for small models (macro F1 0.22-0.33 for 7B-scale LLMs in 2024). An explicit ordinal comparison is needed, not an implicit judgement.

### Cited Findings
- **"From 'May' to 'Is': Certainty Distortion in Language Model Rewriting"** (Belem, Wu, Yao, Steyvers, Singh, Smyth; arXiv 2606.07951; v2 15 Sep 2026; EMNLP 2026 Main) [fetched — abstract page]:
  - Certainty distortion, meaning a meaningful change in expressed certainty during a meaning-preserving rewrite, affects "up to 75% of LM outputs."
  - Distortion is asymmetric: most LMs are "1.5-2x more likely to increase the expressed certainty than to decrease it."
  - **claude-haiku-4.5 increases certainty in 20% of medical-domain examples after one paraphrasing iteration, and 40% after five.**
  - Prompt-based interventions reduce distortion but do not remove it (no figure on the abstract page). The paper proposes an LM-based certainty metric "consistent with population-level judgments of certainty"; its accuracy is not given on the abstract page.
  — [arXiv abs 2606.07951](https://arxiv.org/abs/2606.07951)
- **EMBER** ("Are LLM-Judges Robust to Expressions of Uncertainty?", Lee et al., NAACL 2025). Correct answers judged with no marker (N), a strengthener (S) or a weakener (W) [fetched]:
  - GPT-4o accuracy was 92.7 (N), 91.2 (S) and **73.7 (W)**, with a weakener verdict-switch rate of 19.8%.
  - Llama-3-8B fell from 95.0 to 47.8. GPT-4-turbo was robust, at 86.5 and 88.5.
  - Humans showed no bias: 87.3, 87.3 and 87.0.
  - In pairwise judging, adding weakeners to the stronger output flipped Llama-3-70B's preference from 58.6/41.4 to 22.8/77.2.
  — [arXiv html 2410.20774v2](https://arxiv.org/html/2410.20774v2); [NAACL 2025](https://aclanthology.org/2025.naacl-long.452)
- **Fine-grained distortions in reports of scientific findings** (Wührl, Wright, Klinger, Augenstein; arXiv 2402.12431, Feb 2024). The task compares a paper finding with a reported finding on certainty (4 levels) and generality ("which is more general?"); there are about 1,600 annotated instances, though the paper's counts are inconsistent. Results [fetched]:
  - Certainty, macro F1: RoBERTa 0.59, SciBERT 0.53; few-shot LLaMa-2 0.30, Mistral-7B 0.30, Mixtral-8x7B 0.22.
  - Generality, macro F1: SciBERT 0.47, RoBERTa 0.40; LLaMa-2 0.22, Mistral-7B 0.33, Mixtral 0.30.
  - The authors write that "all LLMs struggle to make meaningful predictions." No chain-of-thought was tested, and the models are older, small open ones.
  — [arXiv html 2402.12431](https://arxiv.org/html/2402.12431v1)
- **Generalization bias in LLM summaries** (Peters and Chin-Yee, arXiv 2504.00025; Royal Society Open Science). Over 4,900 summaries from 10 models, LLM summaries contained broad generalisations about 5x as often as expert human summaries (OR 4.85). Asking for accuracy *increased* overgeneralisation (about 2x). Claude reportedly had the best generalization accuracy, and lower temperature reportedly helped. — [arXiv 2504.00025](https://arxiv.org/abs/2504.00025v1); [Utrecht University press release](https://www.uu.nl/en/news/most-leading-chatbots-routinely-exaggerate-science-findings) [search; this concerns generation, not detection]
- **RIGOURATE** (arXiv 2601.04350, Jan 2026) scores overstatement, meaning claim strength beyond the evidence, on a continuous 0-1 scale using LLM annotators plus a fine-tuned retriever. — [arXiv 2601.04350](https://arxiv.org/html/2601.04350v1) [search; no numbers checked]
- **CONFER** (arXiv 2506.06133, Jun 2025) is an NLI dataset on presupposition in conditionals ("If A, then B"). Standard NLI models "consistently fail," fine-tuning on existing NLI data does not help, and LLMs (GPT-4o, LLaMA, Gemma, DeepSeek-R1) are better but "still exhibit substantial limitations." — [arXiv 2506.06133](https://arxiv.org/html/2506.06133v1) [search]
- **Epistemic markers vs. confidence:** LLM-generated markers are unreliable confidence signals (arXiv 2505.24778), and the marker-to-confidence mapping shifts across domains (arXiv 2605.28778). These are background evidence that hedge words have no stable meaning to models. — [arXiv 2505.24778](https://arxiv.org/html/2505.24778v2); [arXiv 2605.28778](https://arxiv.org/pdf/2605.28778v1) [search]

### Inferences
- **The gloss_en risk.** Call 1 asks Haiku to write `gloss_en` and then rate `certainty_reply`. If the rating is taken from Haiku's own gloss, the Belem et al. effect (Haiku raises certainty in 20% of single rewrites) can make a correctly hedged German or Italian reply look stronger than the policy, which produces false FAILs on translations. Mitigations that fit inside call 1: (a) instruct "rate certainty from the original-language `quote`, not from your gloss"; (b) add a field `hedge_words_reply` that holds the **verbatim** hedge or quantifier tokens from the quote (e.g. "in der Regel", "di solito"; empty if none). Code can then refuse a "certainty raised" finding when the reply's verbatim hedge list is non-empty and the policy's hedge is the same class. This must be measured; do not assume it helps.
- **EMBER bias works against our asymmetry.** Judges penalise hedged but correct answers. Our criterion explicitly allows replies that are stricter or more hedged. The prompt sentence "Being stricter or less generous than the policy, or saying less, is not a violation" is the right counter. The `_differences()` second look is symmetric by design (criterion-agnostic) and also sends "less certain" and "narrower" differences to the verifier, where this bias could turn them into false FAILs. Watch dev false FAILs on those paths; a lower false-fail rate there would support an asymmetric aggregation.
- **The 0-3 certainty scale mixes three dimensions.** It combines possibility modality ("may / will"), frequency ("usually / always") and quantification ("some / all"). The literature treats these as separate phenomena: quantifiers in the generalized-quantifier and EQUATE work, modality in EMBER and Belem et al., and generality in Wührl et al. "Some branches" → "all branches" belongs in `scope`, but the scale's 0 = "some" and 3 = "all" overlap with it, so Haiku may count one edit in two fields or in neither. The cheap fix is to remove "some/all/any" from the certainty anchors and leave quantifiers to `scope`. Measure it with leave-one-edit-type-out.
- **Negation flips and added commitments** are the easy case. They are contradictions or unsupported content, where candidate-side checking does best (TruthfulQA results, Q1). The current per-claim `policy_rule` plus `violates_criterion` design covers them. An added commitment with `policy_rule: null` should be a finding under criterion 1. The schema allows this, but code only acts on `violates_criterion`.
- Paired comparison is hard for small models (F1 around 0.3). Asking Haiku for a single holistic "is it over-promising?" judgement is the weakest design. Separate ordinal ratings for policy and reply, compared **in code** (`certainty_reply > certainty_policy`), is the stronger design and is what we already have.

### Gaps
- I found no dataset or result for "usually → always" or "may → will" detection by a modern LLM judge on short paired texts, and no multilingual hedge-strength dataset.
- I did not read the Belem et al. full text, so how its LM certainty metric was validated, and how well prompt interventions worked, are unknown.

## Q4. Multilingual verification (DE/FR/ES/IT): does verifying in English or in the native language matter?

### Takeaway
The evidence is mixed and comes mostly from fact-checking or claim-matching tasks, not from entailment against an English reference. Translating to English generally helped mid-sized LLMs, but **the strongest multilingual model did better on original-language input**, and machine translation is known to distort nuance. For hedges, which are what we care about, the Belem et al. certainty-drift result (Q3) argues against relying on an LLM-written English gloss as the basis for verification.

### Cited Findings
- On claim matching against previously fact-checked claims (20 languages, 7 LLMs; Vykopal et al., Findings of EMNLP 2025), English translation "generally enhanced LLM performance across most scenarios." The strongest multilingual model did better on original-language inputs, and chain-of-thought combined with translation gave "only marginal improvements." — [arXiv 2503.02737](https://arxiv.org/pdf/2503.02737) [search]
- A 15-language cross-language claim-verification study compares direct inference, self-translation and pre-translation. — [arXiv 2410.10303](https://www.arxiv.org/pdf/2410.10303) [search; final numbers not checked]
- XFEVER (2023, older, pre-LLM) found that performance in non-English languages is "somewhat inferior to the English case," varying by language. — [arXiv 2310.16278](https://arxiv.org/pdf/2310.16278) [search]
- A 2025 English-Telugu study saw back-translation BLEU of only 0.255, a reminder that translation loses content. — [arXiv 2509.26415](https://arxiv.org/html/2509.26415v1) [search]

### Inferences
- DE, FR, ES and IT are high-resource languages, and Haiku 4.5 is a strong multilingual model. The "strongest model does better in the original language" finding is the closest analogue. Keep the reply in its original language in the prompt (we do) and compare it **directly** against the English policy. Treat `gloss_en` as a reasoning aid only, never as the object the certainty and condition fields are scored on.
- A stdlib-only aid: a small multilingual hedge and universal lexicon (e.g. immer/toujours/sempre/siempre; normalerweise, in der Regel, généralement, di solito, normalmente, por lo general; "nach Verfügbarkeit", "sous réserve", "salvo disponibilità", "sujeto a disponibilidad") passed to call 1 as *hints* only. Earlier notes proposed this too. New support: the gloss can drift, while a verbatim lexicon match cannot.

### Gaps
- No study compares native vs. English verification of hedged or conditional claims against an English reference document. Our own dev split by language is the only evidence available today.

## Q5. Asymmetry: "stricter than policy" (harmless) vs. "looser than policy" (harmful), and directional or one-sided entailment

### Takeaway
"Looser than policy" is a **one-directional entailment** test: the policy must entail the reply's commitment, but the reply need not entail the policy. LMs are known to be poor at learning directionality, and LLMs show an "attestation bias" toward affirming plausible hypotheses, which produces false-positive entailment. I found no method built for over-promise detection. The practical answer is to let the LLM extract ordinal fields and have code apply the direction.

### Cited Findings
- "Language Models Are Poor Learners of Directional Inference" (Li et al., Findings of EMNLP 2022, older): LMs show "limited ability to learn such directional inference," and existing datasets rarely test it. — [arXiv 2210.04695](https://arxiv.org/pdf/2210.04695) [search]
- "Sources of Hallucination by LLMs on Inference Tasks" (McKenna et al., 2023, older): LLMs are biased toward affirming hypotheses attested in their training text, which leads to false-positive entailment. Under adversarial labels they degrade toward near-random. — [arXiv 2305.14552](https://arxiv.org/pdf/2305.14552v1.pdf) [search]
- Directional entailment graphs, which use the asymmetry of NLI probabilities between response pairs, are used for uncertainty quantification (arXiv 2407.00994). They show that bidirectional NLI scores carry real asymmetric signal. — [arXiv 2407.00994](https://arxiv.org/html/2407.00994v2) [search]
- A 2026 civic fact-checking paper notes that entailment labels are fooled by entity swaps, negation, asymmetric phrasing and unsupported extra detail. — [ICNLSP 2026](https://aclanthology.org/2026.icnlsp-1.5.pdf) [search]

### Inferences
- In our domain, attestation bias predicts that Haiku will accept "free cancellation up to 24 h" as policy-supported when the policy says 48 h, simply because the phrase sounds like real rental policy. The deterministic number rule plus `number_vs_policy` handles this for numbers. For non-numeric commitments, the "quote the policy rule" requirement is the protection.
- Concrete direction-aware fields already exist: `certainty_policy` and `certainty_reply`, `scope` (wider/narrower), `number_vs_policy` (more or less favourable) and `policy_conditions` (dropped). The research supports **keeping the direction decision in code or in the criterion text, not in a free-text LLM verdict**. Where the criterion says "must not promise more," code could treat only the "looser" direction as a candidate for FAIL. That would hard-code a direction, though, and the rule forbids criterion-specific code. The current symmetric `_differences()` with the criterion text deciding is the rule-compliant choice. Leave it as is, but note in the write-up that EMBER-style bias is the expected source of false FAILs on hedged or stricter replies.

### Gaps
- I found no published "over-claim vs. under-claim" classifier or dataset for policy compliance, and no LLM-judge study that measures directional errors on conditional promises.

## Q6. Do the arXiv IDs cited in the repo exist, and what do they report?

### Takeaway
2608.24419, 2606.19544 and 2609.02942 were already checked in `failure_modes.md` (fetched 2026-11-12). I did not re-fetch them, to stay within the call budget. One new citation, 2606.07951, is verified here and is the most Haiku-specific result found in this pass. The repo cites 2608.05228 (TriQua) and 2602.21857 without them having been re-opened in these notes.

### Cited Findings
- 2608.24419 "A Judge Should Know What Changed": exists. claude-haiku-4.5 had the highest sensitivity among the 7 judges (R=0.561, S=0.917). Hedge removal was the least detected edit, at 0.210 mean sensitivity. — per [failure_modes.md](../failure_modes.md), source [arXiv html](https://arxiv.org/html/2608.24419) [fetched there, not re-fetched here]
- 2606.19544 "Reliability without Validity": exists, but was **withdrawn by arXiv administrators**. — [arXiv abs](https://arxiv.org/abs/2606.19544) [fetched there]
- 2609.02942 "Judging LLM-as-a-Judge: Rubric Artifacts": exists, listed as EMNLP 2026, with a single 7B judge. — [arXiv abs](https://arxiv.org/abs/2609.02942) [fetched there]
- 2606.07951 "From 'May' to 'Is'": exists, EMNLP 2026 Main, and measures claude-haiku-4.5 certainty inflation (Q3). — [arXiv abs](https://arxiv.org/abs/2606.07951) [fetched]
- 2603.28005 "Rethinking Atomic Decomposition for LLM Judges": exists (Q1). — [arXiv html](https://arxiv.org/html/2603.28005) [fetched]

### Inferences
- Ranked changes that fit the 3-call budget, each behind a default-off switch, measured with CV plus leave-one-edit-type-out:
  1. `evidence_quote` per policy condition, with code demoting "kept but no quote found" to "dropped" (Q2). Targets condition_removal.
  2. Rate certainty from the verbatim quote, and add `hedge_words_reply` to call 1 (Q3/Q4). Targets hedge_removal recall and false FAILs on translations.
  3. Remove some/all from the certainty anchors and leave quantifiers to `scope` (Q3). Targets scope edits, which are likely in the hidden set as "quantifier strengthening" or "population widening."
  4. Make call 1 list policy-rule conditions before judging the reply wording (Q1).
- None of these adds an LLM call, and all of them are criterion-agnostic.

### Gaps
- TriQua (2608.05228) and 2602.21857 were not re-verified in this pass. Re-open them before quoting them in SUBMISSION.md.
