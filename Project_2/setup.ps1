$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& ./.venv/Scripts/python.exe -m unittest test_mileage -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& ./.venv/Scripts/python.exe run_baseline.py example_file.csv --out results/example
if ($LASTEXITCODE -ne 0) { throw 'Example evaluation failed.' }
Write-Output 'Ready. See SUBMISSION.md for the supplied-data evaluation and demo.'
