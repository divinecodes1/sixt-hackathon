# Interactive demonstration

## Narrated videos

- **walkthrough.mp4**: detailed explanation of the problem, data, timing insight,
  evaluation, dashboard, forecasts, flags, results, prediction output and limits.
- **demo.mp4**: the short submission cut, verified below the one-minute limit.
- **walkthrough.srt / demo.srt**: sidecar captions; captions are also burned into both videos.
- **walkthrough_narration.md / demo_narration.md**: full scripts for rehearsal or recording your own voice.

Narration uses an explicitly disclosed synthesized English voice. Dashboard
scenes show made-up vehicles; performance charts use measured aggregate results.
Video durations, file sizes and decode checks are in video_report.json.

To rebuild on Windows with Chrome and installed Windows speech voices:

    .venv/Scripts/python.exe -m pip install -r submission/requirements-video.txt
    .venv/Scripts/python.exe submission/build_video.py

The builder creates temporary audio and frames in ignored .video-work/.
The detailed walkthrough is for explanation; use the short demo.mp4 if submitting
a video under the hackathon limit.

## Interactive page

Open **demo.html** in Chrome, Edge, Firefox or Safari. The page is self-contained
and works offline. It uses synthetic vehicles and model-generated outputs only.

Click **Start guided demo** for the three-step walkthrough:

1. Compare the last reading with the estimated current mileage and its range.
2. Change the forecast horizon to see the future estimate and uncertainty.
3. Review the invented mileage spike, its explanation and report date.

You can also search/filter vehicles, select another car, show the isolated typo
on the chart, and export the selected estimate as a CSV.

## Rebuild

From Project_2:

    .venv/Scripts/python.exe submission/build_demo.py

On Linux/macOS use .venv/bin/python instead. The builder runs the actual Python
models, embeds their outputs and writes demo.html. Horizon changes select those
precomputed outputs; the browser does not retrain a model.

## Suggested recording

Introduce the delayed-mileage problem, show the current estimate, switch from
the default forecast horizon to the longest one, then show the flagged typo.
Close with the analyst workflow: an estimate and a prioritized review queue.
Keep the synthetic-data label visible. A recording is optional because the
required five-slide PDF is already supplied separately.
