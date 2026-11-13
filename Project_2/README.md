# Project 2  Divinecodes

Mileage nowcasting, forecasting and suspicious-reading detection for the SIXT Hackathon.

Read [SUBMISSION.md](SUBMISSION.md) for the method, measured results, limitations and full reproduction commands.
Open [submission/slides.pdf](submission/slides.pdf) for the five-slide presentation.

## Run the public example

Python 3.11+; no API key or organizer data required.

```sh
python -m pip install -r requirements.txt
python -m unittest test_mileage -v
python run_baseline.py example_file.csv --out results/example
```

Run these commands from `Project_2`. Use a virtual environment as described in `SUBMISSION.md`.

`mileage.py` implements the models and flags. `run_baseline.py` evaluates them;
`predict_missing.py` fills missing mileage; `profile_data.py` audits input data;
`flag_benchmark.py` measures injected-error detection. `synth_fleet.py` supplies public test fixtures.
Aggregate evidence is retained in `results/`. The supplied organizer data and vehicle-level outputs
are excluded from the submission. To reproduce the full analysis, create `data/` and provide
`data_30_percent_sample.parquet` and `test_data.parquet` locally.

Pass `--out results/example` for example runs to preserve the measured fleet evidence in `results/metrics.json`.
