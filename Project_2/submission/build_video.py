"""Create narrated showcase videos from measured results and the offline mock demo.

Video-only dependencies: pillow, imageio-ffmpeg. Windows narration uses an
installed System.Speech voice. No API, organizer vehicle records or network.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK = HERE / '.video-work'
W, H = 1920, 1080
INK, MUTED, ORANGE = '#14232d', '#617380', '#f55c00'


def read(name):
    return json.loads((ROOT / 'results' / name).read_text(encoding='utf-8'))


def font(size, bold=False):
    path = Path('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf')
    return ImageFont.truetype(str(path), size)


def wrapped(draw, text, xy, width, size=36, fill=INK, bold=False, spacing=13):
    f = font(size, bold)
    lines, line = [], ''
    for word in text.split():
        candidate = (line + ' ' + word).strip()
        if draw.textlength(candidate, font=f) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=f, fill=fill)
        y += size + spacing
    return y


def plan():
    m, b, inf = read('metrics.json'), read('flag_benchmark.json'), read('test_inference_summary.json')
    n = m['nowcast']['models'][m['selected']['nowcast']]['all']
    f = m['forecast']['models'][m['selected']['forecast']]['all']
    recall = sum(b['caught'].values()) / sum(b['injected'].values())
    detailed = [
        dict(id='welcome', title="Where is that car's odometer right now?", subtitle='Divinecodes · Project 2 · SIXT Hackathon',
             points=['Estimate current mileage', 'Forecast future mileage', 'Find reports worth reviewing'],
             narration="This is team Divinecodes, presenting Project Two: mileage forecasting and erroneous mileage detection. We built a local pipeline and an interactive demonstration to estimate a rental car's current mileage, forecast future mileage, and identify reports that deserve a closer look."),
        dict(id='problem', title='The problem: readings arrive late', subtitle='Why this matters to SIXT',
             points=['A car can stay with a customer for weeks', 'The recorded odometer becomes outdated', 'Valuation and defleet decisions still need an estimate'],
             narration="During a long rental, the latest recorded odometer may be weeks out of date. SIXT still needs to value the car and decide when to remove it from the rental fleet. A nowcast estimates mileage today. A forecast estimates mileage on a future date. Suspicious reading detection helps analysts find possible entry mistakes or unusual usage."),
        dict(id='data', title='We connected the supplied Parquet data', subtitle='Development evidence and separate inference targets',
             stats=[(f"{m['input_rows']:,}", 'development status rows'), (f"{m['n_vehicles']:,}", 'development vehicles'), (f"{inf['masked_targets']:,}", 'missing-mileage targets')],
             points=['Use development data for evaluation', 'Keep masked targets separate from tuning', 'Empty organizer prediction columns are not model features'],
             narration="The development sample contains nearly two point seven million status rows across twenty seven thousand, six hundred and thirty vehicles. We added Parquet support and streaming fleet loading. The separate inference file has one hundred and sixty three thousand, forty seven missing mileage targets. We keep those targets separate from model tuning and do not use the empty organizer prediction or error columns as features."),
        dict(id='timing', title='The key insight: two different clocks', subtitle='Measurement date is different from availability date',
             points=['An OnRent value may be an older handover reading', 'Retiming a value must not make it available earlier', 'Rental metadata and changing categories obey the same boundary', 'The pattern is not universal: verify the source semantics'],
             narration="Our main insight is that the date a mileage value belongs to can differ from the date the system first knows it. Some On Rent rows contain older handover mileage. We retime those values, but never reveal them before their row was recorded. We apply the same availability boundary to rental metadata and changing vehicle categories. The fleet pattern is not universal, so we document the assumption rather than treating every row as certain truth."),
        dict(id='method', title='Compare methods, then evaluate honestly', subtitle='Choose before looking at held-out outcomes',
             points=['Last-reading and average-rate baselines', 'Rental-aware rates, recent rates, a blend and a robust candidate', 'Separate model selection from interval calibration', 'Test on later periods and held-out vehicles'],
             narration="We compared the last recorded reading, an average daily rate, rental aware models, a recent usage variant, a blend, and a robust rate candidate. Earlier validation chooses the model separately for each task. A different later period calibrates the prediction ranges. Final evaluation uses later readings on held out vehicles. Future field mutation tests check that changing future rows cannot change earlier predictions."),
        dict(id='dashboard', title='Live walkthrough: estimate the current mileage', subtitle='All dashboard vehicles and readings are synthetic',
             shot='overview', points=['Choose a vehicle', 'Compare last reading with the current estimate', 'Read the age and uncertainty range'],
             narration="Here is the working dashboard. Every vehicle in this demonstration is made up. Select a car on the left. The first card shows its last recorded mileage and the age of that reading. The orange card shows the model's current estimate and a prediction range. The timeline connects the known history to the estimate, making the gap visible instead of hiding the uncertainty."),
        dict(id='forecast', title='Change the planning horizon', subtitle='Precomputed Python model outputs · not an invented browser calculation',
             shot='forecast', points=['Switch between 7, 30, 60 and 90 days', 'Inspect the future estimate and its range', 'Export the selected result to CSV'],
             narration="Next, change the forecast horizon from thirty days to ninety days. The future estimate and its range update using outputs precomputed by the Python models. Longer horizons can require much wider ranges. The page also supports searching, filtering, and exporting the selected estimate as a CSV. The demo works offline and needs no API key."),
        dict(id='review', title='Make suspicious reports explainable', subtitle='A review signal is not proof of fraud',
             shot='review', points=['An invented mileage spike is flagged', 'Each signal includes a date, reason and context', 'Transfers, delayed data and unusual usage can also trigger flags'],
             narration="The review queue includes an intentionally invented mileage spike. Each signal shows the report date, the reading, and a reason for investigation. Our rules cover isolated spikes or dips, decreases, implausible rates, movement without recorded rentals, unchanged readings during rental days, and model residual outliers. A flag is a request for review. It is not proof of fraud, and real precision still requires domain expert labels."),
        dict(id='results', title='Measured results on held-out data', subtitle='Average absolute error in kilometres · lower is better',
             results=True,
             narration="On held out development readings, current mileage error falls from five hundred and sixty one kilometres for the last reading baseline to four hundred and fifteen. Forecast error falls from seven thousand, three hundred and seventy six kilometres to two thousand, seven hundred and thirty four. Those are reductions of twenty six percent and sixty two point nine percent. The selected models also beat the stronger average rate baseline. These are fleet evaluation results, separate from the synthetic dashboard."),
        dict(id='flags', title='Measure detection, report its limits', subtitle='Known injected mistakes provide a controlled check',
             stats=[(f'{recall:.1%}', 'injected-error episode recall'), ('93.9%', 'exact corrupted-reading recall'), ('Unknown', 'real-world flag precision')],
             points=['Episode recall can credit a rollback neighbour', 'Untouched flags can include pre-existing problems', 'Do not turn review signals into accusations'],
             narration="In a controlled development benchmark, the detector caught four hundred and fifty one of four hundred and seventy nine injected mistakes: ninety four point two percent episode recall. Exact corrupted reading recall was ninety three point nine percent. Episode recall can also credit the reading immediately before a rollback. This does not establish real world precision. Untouched readings may already contain errors, and some flags may reflect missing or stale operational data."),
        dict(id='inference', title='The missing-mileage output is complete', subtitle='Original table preserved · unsupported certainty avoided',
             stats=[(f"{inf['predicted']:,}", 'prediction values written'), (f"{inf['with_interval']:,}", 'history-based estimates with ranges'), (f"{inf['fleet_prior_predictions']:,}", 'flagged cohort-prior fallbacks')],
             points=['Future targets use the forecast recipe', 'No own history: clearly mark the cohort fallback', 'Leave sixt_error unchanged when truth is missing'],
             narration="We filled all one hundred and sixty three thousand, forty seven missing mileage targets and preserved the original table. Most use the vehicle's own earlier history with a range. Three thousand, seven hundred and forty five have no usable own history, so they receive an explicitly flagged fleet cohort fallback. Those fallbacks have no calibrated range and need review. The error column stays unchanged because the masked ground truth is unavailable."),
        dict(id='delivery', title='A reproducible project, ready for review', subtitle='Code · evaluation evidence · visual demo · presentation',
             points=['31 automated tests pass', 'Public example runs without organizer data', 'Self-contained offline dashboard and five-slide PDF', 'Next: expert labels, long-term validation and a shadow-mode pilot'],
             narration="The project includes reproducible commands, measured aggregate evidence, thirty one passing tests, an offline dashboard, and a five slide presentation. A clean source copy runs the public example without organizer data. The next step is a shadow mode pilot: confirm measurement semantics, label representative flags, and validate long term rentals and range coverage. We demonstrate a working decision aid, not proven fraud detection, guaranteed savings, or production readiness.")
    ]
    short = [
        dict(detailed[0], narration="We are Divinecodes. Our project estimates current rental car mileage, forecasts future mileage, and flags suspicious reports."),
        dict(detailed[3], narration="The key insight is timing: an old handover value must not become available before its status row was recorded."),
        dict(detailed[5], narration="Our offline dashboard shows the last reading, current estimate, uncertainty range, and selectable future forecasts. All demo vehicles are synthetic."),
        dict(detailed[8], narration="On held out fleet readings, current mileage error drops from five hundred sixty one to four hundred fifteen kilometres. Forecast error drops from seven thousand three hundred seventy six to two thousand seven hundred thirty four."),
        dict(detailed[10], narration="We filled every missing mileage target. Vehicles without history receive clearly flagged cohort fallbacks, not false certainty."),
        dict(detailed[11], narration="Thirty one tests pass. Next: expert flag review and a shadow mode pilot. Full details are in our submission.")
    ]
    return {'walkthrough': detailed, 'demo': short}


SPEECH = r"""
Add-Type -AssemblyName System.Speech
$plan = Get-Content -LiteralPath $env:P2_VIDEO_PLAN -Raw | ConvertFrom-Json
$folder = $env:P2_VIDEO_AUDIO
foreach ($video in $plan.PSObject.Properties) {
  $i = 0
  foreach ($scene in $video.Value) {
    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $s.SelectVoice('Microsoft Zira Desktop')
    $s.Rate = 0
    $name = $video.Name + '_' + $i
    $identifier = 'p2video_' + $name
    $subscription = Register-ObjectEvent -InputObject $s -EventName SpeakProgress -SourceIdentifier $identifier
    $s.SetOutputToWaveFile((Join-Path $folder ($name + '.wav')))
    $s.Speak([string]$scene.narration)
    $s.SetOutputToNull()
    $events = @(Get-Event -SourceIdentifier $identifier -ErrorAction SilentlyContinue | ForEach-Object {
      @{start=$_.SourceEventArgs.AudioPosition.TotalSeconds; offset=$_.SourceEventArgs.CharacterPosition; length=$_.SourceEventArgs.CharacterCount}
    })
    ConvertTo-Json -InputObject $events -Depth 4 | Set-Content -LiteralPath (Join-Path $folder ($name + '.json')) -Encoding UTF8
    Unregister-Event -SourceIdentifier $identifier
    Get-Event -SourceIdentifier $identifier -ErrorAction SilentlyContinue | Remove-Event
    $s.Dispose()
    $i++
  }
}
"""


def narrate(story):
    path = WORK / 'plan.json'
    path.write_text(json.dumps(story, indent=2), encoding='utf-8')
    env = dict(os.environ, P2_VIDEO_PLAN=str(path), P2_VIDEO_AUDIO=str(WORK))
    result = subprocess.run(['powershell', '-NoProfile', '-Command', SPEECH], env=env,
                            capture_output=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-3000:])
    for name, scenes in story.items():
        for i in range(len(scenes)):
            if not (WORK / f'{name}_{i}.wav').exists():
                raise RuntimeError('Windows speech did not create narration audio')


def screenshots():
    source = (HERE / 'demo.html').read_text(encoding='utf-8')
    browser = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
    common = [browser, '--headless', '--disable-gpu', '--no-first-run', '--hide-scrollbars',
              '--disable-background-networking', '--window-size=1600,1000', '--virtual-time-budget=1000',
              '--user-data-dir=' + str(WORK / 'chrome')]
    actions = {
        'overview': "document.querySelector('.detail').scrollIntoView({block:'start'});window.scrollTo(0,180);",
        'forecast': "$('horizon').value='90';$('horizon').dispatchEvent(new Event('change'));window.scrollTo(0,180);",
        'review': "$('review').scrollIntoView({block:'center'});"
    }
    for name, action in actions.items():
        page = WORK / (name + '.html')
        page.write_text(source.replace('</body>', '<script>' + action + '</script></body>'), encoding='utf-8')
        result = subprocess.run(common + ['--screenshot=' + str(WORK / (name + '.png')), page.as_uri()],
                                capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError('Browser capture failed: ' + result.stderr.decode(errors='replace')[-1000:])


def scene_frame(scene, number, count):
    img = Image.new('RGB', (W, H), '#f3f5f5')
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 15), fill=ORANGE)
    d.text((80, 48), 'DIVINECODES  /  PROJECT 2', font=font(25, True), fill=ORANGE)
    d.text((W-340, 48), 'SIXT HACKATHON 2026', font=font(23), fill=MUTED)
    wrapped(d, scene['title'], (80, 105), 1760, 58, bold=True)
    d.text((82, 185), scene['subtitle'], font=font(27), fill=MUTED)
    points = scene.get('points', [])
    if scene.get('shot'):
        shot = Image.open(WORK / (scene['shot'] + '.png')).convert('RGB')
        # Focus on the actual dashboard controls and cards while keeping its
        # synthetic-data context explicit in the surrounding video.
        shot.thumbnail((1220, 675), Image.Resampling.LANCZOS)
        img.paste(shot, (65, 250))
        y = 280
        for point in points:
            d.rounded_rectangle((1320, y+7, 1333, y+20), radius=4, fill=ORANGE)
            y = wrapped(d, point, (1355, y), 470, 34, spacing=13) + 55
        d.text((80, 913), 'Dashboard footage: entirely synthetic vehicles and readings', font=font(23), fill=MUTED)
    elif scene.get('results'):
        m = read('metrics.json')
        for j, task in enumerate(('nowcast', 'forecast')):
            x, y = 95 + j * 920, 285
            d.text((x, y), 'CURRENT MILEAGE' if task == 'nowcast' else 'FUTURE MILEAGE', font=font(29, True), fill=INK)
            names = list(dict.fromkeys(['naive_last', 'mean_rate', m['selected'][task]]))
            vals = [m[task]['models'][name]['all']['MAE_km'] for name in names]
            labels = ['Last reading', 'Average rate', 'Selected model']
            for k, (name, value) in enumerate(zip(names, vals)):
                yy = y + 90 + k * 140
                d.text((x, yy), labels[k], font=font(28), fill=MUTED)
                width = int(620 * value / max(vals))
                color = ORANGE if name == m['selected'][task] else '#8899a5'
                d.rounded_rectangle((x, yy+45, x+width, yy+85), radius=6, fill=color)
                d.text((x+width+15, yy+43), f'{value:,.0f} km', font=font(32, True), fill=INK)
            metric = m[task]['models'][m['selected'][task]]['all']
            d.text((x, 808), f"{metric['skill_vs_naive']:.1%} lower MAE", font=font(36, True), fill=ORANGE)
            d.text((x, 862), 'versus the last-reading baseline', font=font(25), fill=MUTED)
        d.text((95, 905), 'Held-out development readings. Model choice used earlier validation; lower error is better.', font=font(25), fill=MUTED)
    else:
        y = 290
        stats = scene.get('stats', [])
        if stats:
            for j, (value, label) in enumerate(stats):
                x = 80 + j * 600
                d.rounded_rectangle((x, 280, x+560, 490), radius=18, fill='white')
                d.text((x+28, 312), value, font=font(57, True), fill=ORANGE)
                wrapped(d, label, (x+28, 398), 510, 29, fill=MUTED)
            y = 560
        for point in points:
            d.rounded_rectangle((90, y+8, 107, y+25), radius=5, fill=ORANGE)
            y = wrapped(d, point, (140, y), 1640, 40, spacing=16) + 47
    d.text((80, 1034), 'Narration: synthesized voice · Public examples are synthetic · Results are measured aggregates',
           font=font(20), fill='#94a1a9')
    d.text((W-165, 1030), f'{number} / {count}', font=font(23), fill='#94a1a9')
    return img


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'


def encode(name, scenes):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subtitle, elapsed, transcript = [], 0.0, []
    clips = []
    for i, scene in enumerate(scenes):
        audio = WORK / f'{name}_{i}.wav'
        with wave.open(str(audio), 'rb') as wav:
            duration = wav.getnframes() / wav.getframerate()
        frame = scene_frame(scene, i+1, len(scenes))
        frame_path = WORK / f'{name}_{i}.png'
        frame.save(frame_path)
        events = json.loads((WORK / f'{name}_{i}.json').read_text(encoding='utf-8-sig'))
        if isinstance(events, dict):
            events = [events]
        if not events:
            words = list(re.finditer(r'\S+', scene['narration']))
            events = [{'start': duration*j/len(words), 'offset': w.start(), 'length': len(w.group())} for j, w in enumerate(words)]
        # Word events provide real audio timestamps; group them into readable captions.
        cues = []
        for j in range(0, len(events), 15):
            group = events[j:j+15]
            start = max(0, group[0]['start'])
            end = events[j+15]['start'] if j+15 < len(events) else duration
            a, z = group[0]['offset'], group[-1]['offset'] + group[-1]['length']
            caption = scene['narration'][a:z]
            cues.append((start, max(end, start+.1), caption))
        # Burn captions into the video using transparent PNGs, avoiding any
        # font/filter dependency in the encoder.
        caption_list = []
        last = 0.0
        for j, (start, end, caption) in enumerate(cues):
            if start > last:
                caption_list.append((frame_path, start-last))
            canvas = frame.copy()
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((0, 942, W, 1025), fill='#11232d')
            wrapped(draw, caption, (85, 955), 1750, 29, fill='white', spacing=6)
            path = WORK / f'{name}_{i}_caption_{j}.png'
            canvas.save(path)
            caption_list.append((path, end-start))
            subtitle.append(f'{len(subtitle)+1}\n{timestamp(elapsed+start)} --> {timestamp(elapsed+end)}\n{caption}\n')
            last = end
        if last < duration+.35:
            caption_list.append((frame_path, duration+.35-last))
        listing = WORK / f'{name}_{i}_frames.txt'
        listing.write_text(''.join("file '"+str(p).replace('\\','/')+"'\nduration "+str(max(t,.02))+"\n" for p,t in caption_list)
                           + "file '"+str(caption_list[-1][0]).replace('\\','/')+"'\n", encoding='utf-8')
        clip = WORK / f'{name}_{i}.mp4'
        args = [ffmpeg, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing), '-i', str(audio),
                '-vf', 'fps=24,format=yuv420p', '-af', 'apad=pad_dur=0.35', '-t', str(duration+.35),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '24', '-c:a', 'aac', '-b:a', '128k', str(clip)]
        subprocess.run(args, check=True, capture_output=True)
        clips.append(clip)
        transcript.append(f"## {scene['title']}\n\n{scene['narration']}\n")
        elapsed += duration+.35
        print(f'{name}: chapter {i+1}/{len(scenes)} encoded', flush=True)
    concat = WORK / f'{name}_clips.txt'
    concat.write_text(''.join("file '"+str(p).replace('\\','/')+"'\n" for p in clips), encoding='utf-8')
    target = HERE / ('demo.mp4' if name == 'demo' else 'walkthrough.mp4')
    subprocess.run([ffmpeg, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-c', 'copy', '-movflags', '+faststart', str(target)], check=True, capture_output=True)
    if name == 'demo' and elapsed > 59:
        # Keep the official deliverable below one minute without cutting content.
        ratio = elapsed / 58.5
        adjusted = WORK / 'demo-adjusted.mp4'
        subprocess.run([ffmpeg, '-y', '-v', 'error', '-i', str(target), '-vf', f'setpts=PTS/{ratio}',
                        '-af', f'atempo={ratio}', '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
                        '-c:a', 'aac', '-movflags', '+faststart', str(adjusted)], check=True, capture_output=True)
        target.write_bytes(adjusted.read_bytes())
        # Align the sidecar subtitles to the final playback speed.
        scaled = []
        for item in subtitle:
            lines = item.splitlines()
            def parse(s):
                hh, mm, ss = s.replace(',', '.').split(':')
                return int(hh)*3600+int(mm)*60+float(ss)
            a, z = lines[1].split(' --> ')
            lines[1] = timestamp(parse(a)/ratio) + ' --> ' + timestamp(parse(z)/ratio)
            scaled.append('\n'.join(lines)+'\n')
        subtitle, elapsed = scaled, elapsed/ratio
    (HERE / f'{name}.srt').write_text('\n'.join(subtitle), encoding='utf-8')
    (HERE / f'{name}_narration.md').write_text('# Video narration\n\nVoice: synthesized Microsoft Zira Desktop.\n\n'+'\n'.join(transcript), encoding='utf-8')
    if name == 'demo' and target.stat().st_size >= 50_000_000:
        raise RuntimeError('Submission video exceeds 50 MB')
    # Decode the complete result to catch corrupt streams, not just inspect the container.
    subprocess.run([ffmpeg, '-v', 'error', '-i', str(target), '-f', 'null', '-'], check=True, capture_output=True)
    probe = subprocess.run([ffmpeg, '-i', str(target)], capture_output=True, text=True)
    match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', probe.stderr)
    if not match or 'Audio: aac' not in probe.stderr or 'Video: h264' not in probe.stderr:
        raise RuntimeError('Expected playable H.264 video and AAC narration streams')
    hh, mm, ss = match.groups()
    measured_duration = int(hh)*3600 + int(mm)*60 + float(ss)
    if name == 'demo' and measured_duration > 60:
        raise RuntimeError('Measured submission video exceeds one minute')
    return {'file': target.name, 'duration_seconds': measured_duration, 'bytes': target.stat().st_size,
            'resolution': [W,H], 'audio': 'synthesized English narration', 'captions': 'burned in + SRT',
            'full_decode_check': 'passed'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare-only', action='store_true')
    ap.add_argument('--reuse-audio', action='store_true')
    args = ap.parse_args()
    WORK.mkdir(exist_ok=True)
    story = plan()
    (HERE / 'video_storyboard.json').write_text(json.dumps(story, indent=2), encoding='utf-8')
    if args.prepare_only:
        return
    if not args.reuse_audio:
        narrate(story)
    screenshots()
    report = {name: encode(name, scenes) for name, scenes in story.items()}
    (HERE / 'video_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
