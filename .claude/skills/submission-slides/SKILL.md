---
name: submission-slides
description: Build the hackathon deliverable submission/slides.pdf (max 5 slides, 16:9) for Project 2 or Project 3 from the measured results, as a self-contained HTML deck with inline SVG charts printed to PDF by headless Chrome. Use when asked for slides, a deck, a pitch, a demo deliverable or slides.pdf.
---

# Submission slides (≤ 5 pages PDF)

The deck is judged with the demo criterion (10 pts) and is what the jury sees first. Numbers must come from the repo's results files; no number that isn't measured. No real data: show aggregates and synthetic or truncated examples only.

## Story (one slide each)
1. **Problem** - the business pain in one sentence and one concrete example (P3: the dropped "as long as the car isn't reserved"; P2: the 4-week odometer blind spot).
2. **Insight** - the one non-obvious finding (P3: a judge can't see an absence, so make the policy's conditions a checklist; P2: OnRent rows carry a stale odometer, 12 false decreases on the example).
3. **Method** - a small pipeline diagram (P3: rule → call 1 → verify → tiebreak, verdict in code, ≤3 calls; P2: re-timing → rent-aware model + intervals → flags).
4. **Results vs baseline** - one bar chart and one table: P3 combined / catch / keep / consistency, ours vs baseline, criterion 1 and 2; P2 MAE nowcast and forecast vs naive_last and mean_rate, plus flag numbers. Say what didn't work.
5. **How SIXT uses it + next steps** - the release gate / daily nowcast job, and 2–3 next steps.
Team name, project number and repo link in the footer of slide 1.

## Build
Source: `Project_N/submission/slides.html` (commit it, so the deck is reproducible). Self-contained: no external fonts or scripts.
```html
<style>
@page { size: 13.333in 7.5in; margin: 0; }
body { margin: 0; font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; }
section { width: 13.333in; height: 7.5in; box-sizing: border-box; padding: 0.6in 0.8in;
          break-after: page; page-break-after: always; overflow: hidden; }
section:last-child { break-after: auto; page-break-after: auto; }
h1 { font-size: 34pt; margin: 0 0 0.25in; } p, li { font-size: 18pt; line-height: 1.35; }
.accent { color: #ff5f00; }  /* SIXT orange, as in the repo handout */
</style>
```
Charts: generate inline `<svg>` with a short stdlib Python script that reads `Project_3/results/*_report.txt` or `Project_2/results/metrics.json` and writes the bars (rect + text labels with the value on each bar; 2 colours: ours = #ff5f00, baseline = grey). Keep the generator next to the HTML (`submission/make_slides.py`) so slides update when numbers change.

Print:
```bash
cd Project_N/submission
google-chrome --headless --no-pdf-header-footer --print-to-pdf="$PWD/slides.pdf" "file://$PWD/slides.html"
python3 -c 'import re,sys; print(len(re.findall(rb"/Type\s*/Page[^s]", open(sys.argv[1],"rb").read())), "pages")' slides.pdf
```
Must print ≤ 5 pages. Open the PDF and look at every page: text must not overflow or be cut at the bottom (`overflow: hidden` hides it silently).

## Demo alternative
A video (`submission/demo.mp4`, ≤ 1 min, < 50 MB) is optional instead of slides; ffmpeg is not installed here, so prefer slides unless the user records the video themselves.
