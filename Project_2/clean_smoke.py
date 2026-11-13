"""Run public commands from an isolated source copy, without local data/results."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='p2-repro-') as tmp:
        target = Path(tmp)
        for name in ('mileage.py', 'run_baseline.py', 'synth_fleet.py', 'flag_benchmark.py',
                     'test_mileage.py', 'example_file.csv', 'demo.py', 'predict_missing.py'):
            shutil.copy2(root / name, target / name)
        for args in (['-m', 'unittest', 'test_mileage', '-q'],
                     ['run_baseline.py', 'example_file.csv', '--out', 'results/example'],
                     ['demo.py']):
            subprocess.run([sys.executable, *args], cwd=target, check=True)
        print('PASS: isolated source copy works without organizer data or prior result files.')
