# Three-minute pitch and questions

Use slides.pdf. Every performance number comes from the final aggregate evidence;
read the generated SUBMISSION.md before presenting.

1. **Problem:** We need the odometer today, but the latest recorded value may be weeks old. That affects valuation and when to sell a car.
2. **Insight:** A status timestamp is not necessarily a new measurement. We distinguish when mileage belongs from when the system first knows it. We extend the same boundary to rental metadata; otherwise the backtest can quietly see the future.
3. **Method:** We compare holding the last reading, extrapolating average usage, and rental-aware estimates. We let earlier validation choose the model separately for current and future mileage, and use a separate period to calibrate ranges.
4. **Evidence:** Show the measured chart. Point out both baselines and the limits of recorded target mileage. Our flag benchmark injects known mistakes, while the real review queue shows context and requires a human.
5. **Business use:** A daily batch gives analysts estimated mileage, age, uncertainty and a prioritized queue. Start in shadow mode, validate long-term contracts and collect expert feedback before automating decisions.

## Safe demonstration

From Project_2 run `.venv/Scripts/python.exe demo.py` on Windows, or `.venv/bin/python demo.py` on Linux/macOS.
Explain the mock vehicle's last reading, current estimate/range, future estimate and extra-digit review flag.
The CSVs are in results/demo/. Never display organizer vehicle-level output in the public pitch.

## Likely questions

- **Why not a bigger ML model?** Establish a trustworthy temporal evaluation first. The measured comparison includes a strong average-rate baseline. The implementation has no paid inference dependency and explanations are easy to inspect.
- **Are the flags fraud?** No. They are review candidates; no expert-labeled precision is claimed. Transfers, delayed records and unusual driving can also trigger them.
- **Are ranges guaranteed to cover 90%?** No. That is a calibration target; actual held-out coverage is reported. Fleet and time shifts can break the assumptions.
- **How do you avoid future information?** A row's mileage, rental metadata and category become available on its recorded day. Tests change future fields and verify past predictions stay unchanged. Model selection and calibration precede held-out evaluation.
- **What about the missing-mileage file?** It is used for inference after the recipe is fixed. We use past readings and earlier development priors, report unsupported cases, and do not claim accuracy where truth is missing.
- **How much money does it save?** We have not measured a currency benefit. The next step is a valuation/defleet pilot with SIXT's decision costs and domain labels.
- **What remains before production?** Confirm measurement/return semantics, label representative flags, validate direct current-mileage truth and long-term rentals, then monitor coverage and review workload in shadow mode.
