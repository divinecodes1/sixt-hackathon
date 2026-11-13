"""Browser smoke checks and screenshots for the generated offline demo."""
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CHECKS = """
<script>
try {
  const assert=(ok,label)=>{if(!ok)throw Error(label)};
  assert(document.querySelectorAll('#fleetlist button').length===40,'fleet loaded');
  assert(document.querySelector('#carname').textContent,'vehicle selected');
  const old=document.querySelector('#future').textContent;
  document.querySelector('#horizon').value='90';
  document.querySelector('#horizon').dispatchEvent(new Event('change'));
  assert(document.querySelector('#futurelabel').textContent.includes('90'),'horizon changes');
  assert(document.querySelector('#future').textContent!==old,'forecast changes');
  document.querySelector('#search').value='no-such-vehicle';
  document.querySelector('#search').dispatchEvent(new Event('input'));
  assert(document.querySelector('#fleetlist').textContent.includes('No matching'),'empty search');
  document.querySelector('#search').value='';
  document.querySelector('#filter').value='review';
  document.querySelector('#filter').dispatchEvent(new Event('change'));
  assert(document.querySelectorAll('#fleetlist button').length===DATA.vehicles.filter(v=>v.flags.length).length,'review filter');
  document.querySelector('#filter').value='all';
  document.querySelector('#filter').dispatchEvent(new Event('change'));
  document.querySelector('#fleetlist button').click();
  assert(document.querySelector('#carname').textContent==='Demo car 01','vehicle selection');
  let downloaded='';
  const originalClick=HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click=function(){downloaded=this.download};
  document.querySelector('#export').click();
  HTMLAnchorElement.prototype.click=originalClick;
  assert(downloaded.endsWith('-estimate.csv'),'CSV export');
  document.querySelector('#tourstart').click();
  document.querySelector('#tournext').click();
  assert(document.querySelector('#horizon').value==='90','guided forecast');
  document.querySelector('#tournext').click();
  document.querySelector('#tournext').click();
  assert(!document.querySelector('#tour').classList.contains('open'),'guided tour completes');
  assert(DATA.vehicles.every(v=>v.history.every(p=>p.date<=DATA.asof)),'no future history');
  assert(DATA.flags.every(f=>f.date<=DATA.asof),'no future review records');
  assert(document.documentElement.scrollWidth<=innerWidth,'no horizontal overflow');
  document.body.dataset.demoChecks='passed';
} catch(error) {document.body.dataset.demoChecks='failed: '+error.message;}
</script>
"""


def main():
    browser = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
    profile = ROOT / '.chrome-profile'
    profile.mkdir(exist_ok=True)
    qa = profile / 'demo-check.html'
    qa.write_text((HERE / 'demo.html').read_text(encoding='utf-8').replace('</body>', CHECKS + '</body>'), encoding='utf-8')
    common = [browser, '--headless', '--disable-gpu', '--no-first-run',
              '--disable-background-networking', '--hide-scrollbars',
              '--user-data-dir=' + str(profile / 'demo-browser')]
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    for size in ('1600,1100', '500,900'):
        result = subprocess.run(common + ['--window-size=' + size, '--virtual-time-budget=1500', '--dump-dom', qa.as_uri()],
                                capture_output=True, timeout=60, **options)
        content = result.stdout.decode(errors='replace')
        if result.returncode or 'data-demo-checks="passed"' not in content:
            (profile / 'demo-check-output.html').write_text(content, encoding='utf-8')
            raise RuntimeError('Browser demo checks failed; inspect .chrome-profile/demo-check-output.html')
        target = profile / ('demo-desktop.png' if size.startswith('1600') else 'demo-mobile.png')
        result = subprocess.run(common + ['--window-size=' + size, '--virtual-time-budget=1000',
                                '--screenshot=' + str(target), (HERE / 'demo.html').as_uri()],
                                capture_output=True, timeout=60, **options)
        if result.returncode or not target.exists():
            raise RuntimeError('Screenshot failed')
        print('PASS: browser interactions and layout at ' + size)


if __name__ == '__main__':
    main()
