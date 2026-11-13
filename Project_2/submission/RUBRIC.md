# Evidence against the official rubric

Source: repository `runbook/README.md`, section 6, and `runbook/handout.html`.
These are the jury's maximum points, not a self-awarded score.

| Criterion | Maximum | Evidence supplied |
|---|---:|---|
| Problem understanding | 15 | Delayed mileage, valuation/defleet use, measurement versus availability clocks, planned-return caveat in EDA.md |
| Quality of approach | 25 | Two baselines, rental-aware and robust candidates, earlier validation selection, separate calibration, future-field invariance tests |
| Results | 25 | Full development-sample evaluation on held-out vehicles and later periods; MAE/MAPE, bias, gap and lead-time groups; measured interval coverage; injected-error evidence |
| Business relevance and reusability | 15 | Daily fleet exports, explicit unsupported cases, local review queue, mileage-limit alerts, masked inference and shadow-mode adoption plan |
| Code and reproducibility | 10 | Minimal dependencies, Windows/Linux setup, public-data example, isolated-source smoke test, unit tests, source/result provenance |
| Presentation and demo | 10 | Five-slide PDF with measured charts, reproducible HTML, runnable synthetic demo, pitch/Q&A notes |

Project 2's stated results metric is error on held-out vehicles/periods versus a
naive baseline (MAE/MAPE); its README additionally asks that flags be plausible.
Finalists are selected by topic owners before the independent jury pitches.

Do not claim expert-confirmed precision, hidden-target accuracy or monetary savings.
Before publishing, resolve the existing tracked datasets and obtain push approval.
