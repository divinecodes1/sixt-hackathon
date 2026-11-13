"""Read-only Project 2 deliverable audit. Never pushes or prints secret values."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    checks = []
    doc = (ROOT / 'SUBMISSION.md').read_text(encoding='utf-8')
    checks.append(('Submission contains no unfinished placeholders', not re.search(r'\bTBD\b|to be added', doc, re.I)))
    for heading in ('Authors', 'Problem and approach', 'Models and why', 'Results', 'How to run', 'Demo', 'Next steps'):
        checks.append((f'Submission section: {heading}', heading.lower() in doc.lower()))
    pdf = ROOT / 'submission/slides.pdf'
    pages = len(re.findall(rb'/Type\s*/Page\b', pdf.read_bytes())) if pdf.exists() else 0
    checks.append(('Required PDF deck exists and has 1–5 pages', 1 <= pages <= 5))
    metrics = json.loads((ROOT / 'results/metrics.json').read_text())
    checks.append(('Fleet evaluation uses supplied development sample', metrics.get('n_vehicles', 0) > 10 and metrics.get('input') == 'data_30_percent_sample.parquet'))
    checks.append(('Separate selection/calibration/test cutoffs', metrics.get('validation_cutoff', '') < metrics.get('calibration_start', '') < metrics.get('cutoff', '')))
    for task in ('nowcast', 'forecast'):
        checks.append((f'Held-out targets exist: {task}', metrics[task]['n'] > 0))
    inference = ROOT / 'results/test_inference_summary.json'
    checks.append(('Masked-file inference has an aggregate report', inference.exists()))
    if inference.exists():
        inf = json.loads(inference.read_text())
        checks.append(('Every masked target has an estimate or explicit unsupported status', inf['predicted'] + inf.get('unsupported', inf['without_past_reading']) == inf['masked_targets']))
    tracked = subprocess.run(['git', 'ls-files', 'Project_2/data'], cwd=ROOT.parent, capture_output=True, text=True, check=True).stdout.splitlines()
    checks.append(('No supplied dataset files tracked in git (permission unresolved)', not tracked))
    secret_files = []
    for name in subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', 'Project_2'], cwd=ROOT.parent, capture_output=True, text=True, check=True).stdout.splitlines():
        p = ROOT.parent / name
        if p.suffix.lower() in ('.md', '.py', '.txt', '.json', '.html') and p.exists():
            if re.search(rb'sk-[A-Za-z0-9]{20,}|JUDGE_LLM_API_KEY\s*=\s*[^\s"\']{10,}', p.read_bytes()):
                secret_files.append(name)
    checks.append(('No credential patterns in Project 2 submission-source text', not secret_files))
    for label, ok in checks:
        print(('PASS' if ok else 'ACTION') + ': ' + label)
    print('No commit or push performed. Human flag review and organizer data permission remain external checks.')
    result = {'checks': [{'check': label, 'pass': ok} for label, ok in checks], 'pdf_pages': pages,
              'tracked_data_paths': tracked, 'secret_pattern_file_count': len(secret_files)}
    (ROOT / 'results/readiness.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
