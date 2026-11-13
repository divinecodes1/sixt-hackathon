# Pre-merge and pre-submission review checklist

- [ ] Correct repository, branch, and scope; no unrelated changes.
- [ ] Every stated constraint documented and implemented.
- [ ] API signatures and output schema match runner exactly.
- [ ] One-reply isolation preserved; no label, edit-type, paired-text leakage.
- [ ] Model ID and call budget enforced, not merely described.
- [ ] Criterion-specific facts are runtime inputs, not hardcoded.
- [ ] Policy facts scoped to customer question and response; no naive global number matching.
- [ ] Input replies cannot inject instructions into the judging logic.
- [ ] Parsing tolerates formatting variations and rejects truncated outputs transparently.
- [ ] Rate limit, timeout, concurrency, and retry failure modes tested or disclosed.
- [ ] No secret keys, `.env`, private data, or enormous generated assets committed.
- [ ] Baseline and new run compared on same dataset; per-language and per-edit results inspected.
- [ ] Repeat consistency tested without result caching when required.
- [ ] All reported metrics directly supported by saved run outputs.
- [ ] Reproducible instructions and dependency versions provided.
- [ ] Frozen commit hash recorded before deadline; subsequent runs use frozen code.
- [ ] Submission filenames, deadline, and evidence artifacts checked against latest repository README.
