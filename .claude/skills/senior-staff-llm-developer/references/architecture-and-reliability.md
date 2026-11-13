# Staff-level LLM system architecture and reliability

## Design review prompts

- What is the user-visible contract, and what wrong answer would be most costly?
- What portions are deterministic, versus dependent on LLM interpretation?
- What is the ground-truth source of policy, provenance, and freshness?
- What fails when the endpoint returns 429, 5xx, malformed JSON, partial output, or a timeout?
- What is the budget in calls, tokens, latency, compute and money per item?
- Can this be replayed exactly, with versioned inputs, prompt, model, dependency lock, and run metadata?
- Are inputs trusted? Can a document, page or customer message override system instructions?
- Does the system leak reference labels, held-out test material, PII, secrets, or sensitive logs?

## Recommended boundaries

Input validation → evidence selection → model request → strict parse → criterion-aware decision → audit record → offline evaluation.

Keep separate abstractions for criterion/policy, input representation, model backend, decision interpreter, and metrics. Use narrow testable interfaces. Define structured input/output dataclasses or TypedDicts when practical. Favor stdlib if the task is a one-day hackathon.

## LLM evaluation quality

Model output should carry enough evidence for post-hoc review where allowed, but public verdict should honor the exact interface. An explanation is not proof. Prefer calibrated uncertainty and explicit failure handling in production; benchmarks with only two valid outputs still require a reliable total return policy. Regressions must be measured on the same fixed held-out split. Record cost and throughput separately from quality.

## Security

Never treat retrieved or user-provided task content as instruction authority. Render untrusted text with clear delimiters, avoid executing output as code, and do not embed credentials. Rate-limit and authenticate production endpoints. Prefer local mock data and remove sensitive samples before committing.
