# Project 2: Mileage Forecasting & Erroneous Mileage Detection

**Team: Divinecodes**

SIXT needs a car's mileage today even when the latest report is weeks old. This project estimates current and future mileage and flags reports that look inconsistent with the car's usage.

Read [SUBMISSION.md](SUBMISSION.md) for the approach, model comparison, held-out results and limitations. Open [submission/slides.pdf](submission/slides.pdf) for the five-slide pitch.

## Open the demo

Double-click [submission/demo.html](submission/demo.html) to open it in a browser. It works offline. Select a car, compare its last reading with its estimated mileage, change the forecast horizon, and review a suspicious report. Demo vehicles are synthetic; they are not organizer records.

## Data in plain language

Each row is a vehicle status update. It contains an anonymized vehicle ID, a timestamp, mileage, rental status/dates, vehicle characteristics and planned utilisation. A status update does not necessarily contain a fresh mileage reading. The public `example_file.csv` contains 57 rows for one vehicle.

The measured development results use `data_30_percent_sample.parquet`. The separate `test_data.parquet` contains missing-mileage targets to fill; their true mileage is not supplied. Neither file is needed for the public example. Keep organizer data and vehicle-level outputs local.

## Run the public example

Use Python 3.11+; no API key or environment variables are required. Dependencies are NumPy and DuckDB, listed in `requirements.txt`.

From the repository root on Windows:

```powershell
cd Project_2
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest test_mileage -v
.\.venv\Scripts\python.exe run_baseline.py example_file.csv --out results/example
```

Linux/macOS:

```sh
cd Project_2
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest test_mileage -v
.venv/bin/python run_baseline.py example_file.csv --out results/example
```

The example writes `results/example/metrics.json` and `results/example/flags.csv`. Its single vehicle is a smoke check, not the source of the reported fleet performance. Always pass a separate `--out` directory for example runs; the default output directory is `results/`.

## Reproduce the supplied-data analysis

Create `Project_2/data/` and provide these organizer files locally:

```text
data/data_30_percent_sample.parquet
data/test_data.parquet
```

From `Project_2`, after installing dependencies, run the following on Windows. On Linux/macOS replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

```powershell
.\.venv\Scripts\python.exe profile_data.py data/data_30_percent_sample.parquet
.\.venv\Scripts\python.exe run_baseline.py data/data_30_percent_sample.parquet --out results
.\.venv\Scripts\python.exe flag_benchmark.py data/data_30_percent_sample.parquet --max-vehicles 1000 --training-only --before 2025-02-01 --rate 0.02 --seeds 3 --out results/flag_benchmark.json
.\.venv\Scripts\python.exe predict_missing.py --development data/data_30_percent_sample.parquet --input data/test_data.parquet
```

These regenerate the data profile, held-out model comparisons, flag benchmark and missing-mileage predictions. The inference runner reads the selected recipes and calibration information from `results/metrics.json`, so run evaluation first. Runtime depends on the machine; do not interpret public-example scores as fleet scores.

### Generate current and future mileage tables

For an explicitly chosen historical origin and future date:

```powershell
.\.venv\Scripts\python.exe run_baseline.py example_file.csv --out results/example --asof 2024-08-01 --forecast-date 2024-08-31
```

The runner exports `nowcast_2024-08-01.csv` and `forecast_2024-08-31.csv` in the output directory. Replace the input and dates for a supplied-data run. The export selects models using validation before the origin; insufficient calibration is reported explicitly.

## Outputs and evidence

| File | What it contains |
|---|---|
| `results/metrics.json` | Fleet model comparisons, selected models, interval coverage and flag counts |
| `results/data_profile.json` | Input sizes, schema and data-quality checks |
| `results/flag_benchmark.json` | Detection results for injected errors |
| `results/test_inference_summary.json` | Counts and recipes for missing-mileage predictions |
| `results/inference_validation.json` | Recorded completed-file preservation and validity checks |
| `results/test_schema.json`, `results/test_target_dates.json` | Supplied inference-file metadata |
| `results/provenance.json` | Source/evidence checksums and recorded dependency versions |
| `results/local/flags.csv` | Locally generated flagged reports, reasons and scores |
| `results/local/test_predictions.csv` | Locally generated estimates, model, uncertainty and review status |
| `results/local/test_completed.parquet` | Original inference table with missing prediction values filled |

Vehicle-level output files are generated when the supplied-data commands run and are ignored by git. The completed inference file fills `sixt_predicted_mileage_interp` and preserves `sixt_error`; no error labels are invented. Schema/date summaries and the completed-file validation report are retained audit evidence; the commands above do not regenerate every audit file.

## Code map

| File | Responsibility |
|---|---|
| `mileage.py` | Data preparation, statistical models, evaluation, uncertainty and flags |
| `run_baseline.py` | Command-line evaluation and mileage-table exports |
| `predict_missing.py` | Fill missing-mileage targets and preserve the original table |
| `profile_data.py` | Audit supplied Parquet data |
| `flag_benchmark.py` | Inject known errors and measure detection |
| `test_mileage.py`, `synth_fleet.py` | Correctness tests and synthetic test fixtures |

The organizer's requested submission is code, `SUBMISSION.md`, evaluation evidence, and a video or a PDF of at most five slides. This package uses the PDF; the HTML demo is supplementary. See the publication-status note in `SUBMISSION.md` before publishing the repository.
