"""Print the offline deck with installed Chrome/Edge; optional visual previews."""
import argparse
import os
import shutil
import subprocess
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--previews', action='store_true')
    a = ap.parse_args()
    here = Path(__file__).resolve().parent
    candidates = [shutil.which(n) for n in ('google-chrome', 'chromium', 'chromium-browser')]
    candidates += ['C:/Program Files/Google/Chrome/Application/chrome.exe',
                   'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe']
    browser = next((str(p) for p in candidates if p and Path(p).exists()), None)
    if not browser:
        raise SystemExit('Install Chrome/Chromium/Edge to print the offline deck.')
    profile = here.parent / '.chrome-profile'
    profile.mkdir(exist_ok=True)
    common = [browser, '--headless', '--disable-gpu', '--no-first-run',
              '--disable-background-networking', '--no-pdf-header-footer',
              '--user-data-dir=' + str(profile / 'browser')]
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    def run(args):
        result = subprocess.run(common + args, capture_output=True, timeout=60, **options)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace')[-2000:])
    source = (here / 'slides.html').as_uri()
    pdf = here / 'slides.pdf'
    run(['--print-to-pdf=' + str(pdf), source])
    if not pdf.exists():
        raise RuntimeError('Browser did not create the PDF.')
    if a.previews:
        for page in range(1, 6):
            target = profile / f'slide-{page}.png'
            run(['--window-size=1280,720', '--hide-scrollbars', '--screenshot=' + str(target), source + f'#{page}'])
    print(pdf)


if __name__ == '__main__':
    main()
