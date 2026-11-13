#!/usr/bin/env python3
"""Build submission/slides.html (5 slides) from the score.py reports in the repo. Standard library only.

Every number on the slides is read from a report file; nothing is typed in by hand. Rerun after new results:
    python3 make_slides.py && google-chrome --headless --no-pdf-header-footer \
        --print-to-pdf="$PWD/slides.pdf" "file://$PWD/slides.html"
"""
import html
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
P3 = os.path.dirname(HERE)
RES = os.path.join(P3, "results")

# (label, report path). First = the shipped judge (run_dev.sh: VERIFY_WITNESS + TRUST_VERIFY_REJECT, 14:05); second = the
# same recipe before both call-2 changes (run A, 11:23), to show what they bought.
BASELINE = os.path.join(P3, "starter_pack", "baseline_report.txt")
OURS = [("Ours, shipped", os.path.join(RES, "dev_pairs_report.txt")),
        ("Ours, before 12:25", os.path.join(RES, "exp_base_dev_dev_pairs_report.txt"))]
C2_OURS = os.path.join(RES, "c2_dev_pairs_report.txt")            # written by run_dev.sh on the surprise criterion
C2_BASE = os.path.join(RES, "c2_vs_baseline_report.txt")          # score.py ... --baseline (optional)
C2_UNCHANGED = os.path.join(RES, "c2_unchanged_vs_baseline_report.txt")  # the judge before 14:05, run on criterion 2
WITNESS = os.path.join(RES, "exp_W_witness_dev_dev_pairs_report.txt")  # call 2 with witness, before TRUST_VERIFY_REJECT
REPEATS = [os.path.join(RES, "guard_c1_report.txt"), os.path.join(RES, "guard_c2_report.txt")]  # same judge, 14:21
REPO = "github.com/divinecodes1/sixt-hackathon"

ORANGE, GREY, DARK = "#ff5f00", "#9a9a9a", "#1a1a1a"


def parse(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    out: dict = {"types": {}}
    for key, pat in [("combined", r"COMBINED \(the score\)\s+([\d.]+)"), ("catch", r"macro catch\s+([\d.]+)"),
                     ("keep", r"macro keep\s+([\d.]+)"), ("kappa", r"kappa vs construction\s+([\d.]+)"),
                     ("same", r"same verdict ([\d.]+)"), ("orig_pass", r"original pass ([\d.]+)"),
                     ("base_combined", r"COMBINED \(the score\)\s+[\d.]+\s+\(baseline ([\d.]+)"),
                     ("base_catch", r"macro catch\s+[\d.]+\s+\(baseline ([\d.]+)"),
                     ("base_keep", r"macro keep\s+[\d.]+\s+\(baseline ([\d.]+)"),
                     ("base_kappa", r"kappa vs construction\s+[\d.]+\s+\(baseline ([\d.]+)")]:
        m = re.search(pat, text)
        if m:
            out[key] = float(m.group(1))
    for m in re.finditer(r"^\s+([a-z_]+)\s+(\d+)\s+([\d.]+|n/a)\s+([\d.]+|n/a)", text, flags=re.M):
        out["types"][m.group(1)] = {"catch": m.group(3), "keep": m.group(4)}
    return out if "combined" in out else None


def f3(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def bars(groups: list[str], series: list[tuple[str, str, list[float]]], w=560, h=330) -> str:
    """Grouped vertical bars with the value on each bar. series: (label, colour, values per group)."""
    pad_l, pad_b, pad_t = 40, 46, 30
    gw = (w - pad_l) / len(groups)
    bw = min(56, (gw - 30) / len(series))
    s = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" font-family="Arial">']
    base_y = h - pad_b
    s.append(f'<line x1="{pad_l}" y1="{base_y}" x2="{w}" y2="{base_y}" stroke="#ccc"/>')
    for gi, g in enumerate(groups):
        x0 = pad_l + gi * gw + (gw - bw * len(series)) / 2
        for si, (_, col, vals) in enumerate(series):
            v = vals[gi]
            bh = (base_y - pad_t) * v
            x = x0 + si * bw
            s.append(f'<rect x="{x:.1f}" y="{base_y - bh:.1f}" width="{bw - 6:.1f}" height="{bh:.1f}" fill="{col}"/>')
            s.append(f'<text x="{x + (bw - 6) / 2:.1f}" y="{base_y - bh - 6:.1f}" font-size="15" '
                     f'text-anchor="middle" fill="{DARK}">{v:.2f}</text>')
        s.append(f'<text x="{pad_l + gi * gw + gw / 2:.1f}" y="{h - 16}" font-size="18" text-anchor="middle" '
                 f'fill="{DARK}">{html.escape(g)}</text>')
    lx = pad_l
    for label, col, _ in series:
        s.append(f'<rect x="{lx}" y="2" width="14" height="14" fill="{col}"/>'
                 f'<text x="{lx + 20}" y="14" font-size="15" fill="{DARK}">{html.escape(label)}</text>')
        lx += 30 + 8.5 * len(label)
    s.append("</svg>")
    return "".join(s)


def _box(x, y, w, h, lines, fill, stroke, color, bold_first=True, size=16, rx=10, dash=""):
    """A rounded box with centred lines of text (first line bold)."""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"'
           f'{f" stroke-dasharray={chr(34)}{dash}{chr(34)}" if dash else ""}/>']
    top = y + h / 2 - (len(lines) - 1) * (size + 4) / 2 + size * 0.35
    for i, t in enumerate(lines):
        wt = ' font-weight="bold"' if bold_first and i == 0 else ""
        out.append(f'<text x="{x + w / 2}" y="{top + i * (size + 4):.1f}" font-size="{size}"{wt} fill="{color}" '
                   f'text-anchor="middle">{html.escape(t)}</text>')
    return "".join(out)


PASS_BG, PASS_LINE, FAIL_BG, FAIL_LINE, CODE_BG = "#e6f4ea", "#188038", "#fdecea", "#d93025", "#f1f3f4"


def arch_svg() -> str:
    """Decision paths of the shipped judge (TRUST_VERIFY_REJECT on, off-switches left out). Mirrors docs/ARCHITECTURE.md."""
    s = [f'<svg viewBox="0 0 1180 400" width="1120" height="370" font-family="Arial" role="img">'
         f'<defs><marker id="a" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{DARK}"/></marker></defs>']
    s.append(_box(0, 0, 380, 46, ["prepare(): examples + rule mode, from the labelled pairs"], "#fff", GREY, DARK,
                  bold_first=False, size=15, dash="6 4"))
    s.append(_box(0, 110, 150, 110, ["One reply", "+ criterion", "+ policy"], CODE_BG, "#5f6368", DARK))
    s.append(_box(190, 110, 160, 110, ["Number rule", "code · 0 calls", "self-validated"], CODE_BG, "#5f6368", DARK))
    s.append(_box(390, 110, 220, 110, ["Call 1", "claim by claim (JSON):", "conditions kept / dropped,", "certainty · scope"],
                  ORANGE, ORANGE, "#fff", size=15))
    s.append(_box(680, 110, 220, 110, ["Call 2 · verify", "fresh context: exact", "reply quote + concrete", "misleading case"],
                  ORANGE, ORANGE, "#fff", size=15))
    s.append(_box(970, 110, 210, 110, ["Call 3 · fallback", "holistic, with examples", "rarely needed"],
                  "#ffa366", "#ffa366", "#fff", size=15))
    s.append(f'<g stroke="{DARK}" stroke-width="2" fill="none" marker-end="url(#a)">'
             f'<line x1="270" y1="46" x2="270" y2="106"/>'
             f'<line x1="150" y1="165" x2="186" y2="165"/><line x1="350" y1="165" x2="386" y2="165"/>'
             f'<line x1="610" y1="165" x2="676" y2="165"/><line x1="900" y1="165" x2="966" y2="165"/>'
             f'<path d="M500,110 C500,60 1075,60 1075,106"/>'
             f'<line x1="445" y1="220" x2="445" y2="276"/><line x1="565" y1="220" x2="565" y2="276"/>'
             f'<line x1="735" y1="220" x2="735" y2="276"/><line x1="855" y1="220" x2="855" y2="276"/>'
             f'<line x1="1075" y1="220" x2="1075" y2="276"/></g>')
    s.append(f'<g font-size="13" fill="{DARK}" text-anchor="middle"><text x="790" y="66">call 1 unreadable</text>'
             f'<text x="643" y="155">violation</text><text x="935" y="155">unclear</text></g>')
    s.append(_box(385, 280, 120, 72, ["FAIL · 1 call", "unknown number", "not cleared"], FAIL_BG, FAIL_LINE, DARK, size=14))
    s.append(_box(515, 280, 100, 72, ["PASS · 1 call", "no claim", "violates"], PASS_BG, PASS_LINE, DARK, size=14))
    s.append(_box(675, 280, 120, 72, ["FAIL · 2 calls", "confirmed, quote", "found in reply"], FAIL_BG, FAIL_LINE, DARK, size=14))
    s.append(_box(805, 280, 100, 72, ["PASS · 2 calls", "all answered,", "none proven"], PASS_BG, PASS_LINE, DARK, size=14))
    s.append(_box(970, 280, 210, 72, ["PASS / FAIL · 3 calls", "decided by call 3"], CODE_BG, "#5f6368", DARK, size=14))
    s.append(f'<text x="590" y="390" font-size="16" text-anchor="middle" fill="{DARK}">verdict computed in code · '
             f'one reply per call · no state between calls · at most 3 calls · claude-haiku-4.5, temperature 0</text>')
    s.append("</svg>")
    return "".join(s)


DEMO_URL = "divinecodes-judge-the-judge.vercel.app"
DEMO_IMG = "demo_screenshot.png"  # made by make_demo_screenshot.mjs from the live site


def main() -> None:
    base = parse(BASELINE)
    runs = [(lbl, parse(p)) for lbl, p in OURS]
    runs = [(lbl, r) for lbl, r in runs if r]
    if not base or not runs:
        raise SystemExit("missing report files: run score.py / run_dev.sh first")
    c2, c2b = parse(C2_OURS), parse(C2_BASE)

    chart = bars(["combined", "macro catch", "macro keep"],
                 [("Baseline", GREY, [base["combined"], base["catch"], base["keep"]])]
                 + [(lbl, ORANGE if i == 0 else "#ffa366", [r["combined"], r["catch"], r["keep"]])
                    for i, (lbl, r) in enumerate(runs)])

    rows = [("1", "Baseline", base)] + [("1", lbl, r) for lbl, r in runs]
    trs = "".join(f"<tr><td>{c}</td><td>{html.escape(j)}</td><td>{f3(r.get('combined'))}</td><td>{f3(r.get('catch'))}"
                  f"</td><td>{f3(r.get('keep'))}</td><td>{f3(r.get('kappa'))}</td><td>{f3(r.get('same'))}</td></tr>"
                  for c, j, r in rows)
    if c2:
        b = c2b or {}
        trs += (f"<tr><td>2</td><td>Baseline</td><td>{f3(b.get('base_combined'))}</td><td>{f3(b.get('base_catch'))}"
                f"</td><td>{f3(b.get('base_keep'))}</td><td>{f3(b.get('base_kappa'))}</td><td>n/a</td></tr>")
        un = parse(C2_UNCHANGED)
        if un:
            trs += (f"<tr><td>2</td><td>Ours, before 14:05</td><td>{f3(un['combined'])}</td>"
                    f"<td>{f3(un.get('catch'))}</td><td>{f3(un.get('keep'))}</td><td>{f3(un.get('kappa'))}</td>"
                    f"<td>n/a</td></tr>")
        trs += (f"<tr><td>2</td><td>Ours, shipped</td><td>{f3(c2['combined'])}</td><td>{f3(c2.get('catch'))}"
                f"</td><td>{f3(c2.get('keep'))}</td><td>{f3(c2.get('kappa'))}</td><td>{f3(c2.get('same'))}</td></tr>")
    else:
        trs += '<tr class="pending"><td>2</td><td colspan=6>runs on the new criterion at 14:30, code unchanged</td></tr>'

    rep = [parse(p) for p in REPEATS]
    repeat_note = ""
    if c2 and all(rep):
        c1_lo, c1_hi = sorted([runs[0][1]["combined"], rep[0]["combined"]])
        c2_lo, c2_hi = sorted([c2["combined"], rep[1]["combined"]])
        repeat_note = (f" <b>Noise:</b> a second pair of runs of the shipped judge gave criterion 1 {f3(c1_lo)}–{f3(c1_hi)},"
                       f" criterion 2 {f3(c2_lo)}–{f3(c2_hi)}.")
    cond_base = base["types"].get("condition_removal", {}).get("catch", "n/a")
    shipped = runs[0][1]
    cond_ours = shipped["types"].get("condition_removal", {}).get("catch", "n/a")
    w = parse(WITNESS) or {"types": {}}
    cond_before = w["types"].get("condition_removal", {}).get("catch", "n/a")
    orig_pass = " → ".join(f3(r.get("orig_pass")) for _, r in reversed(runs))

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Judge the Judge · Divinecodes</title>
<style>
@page {{ size: 13.333in 7.5in; margin: 0; }}
body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: {DARK}; }}
section {{ width: 13.333in; height: 7.5in; box-sizing: border-box; padding: 0.55in 0.8in; position: relative;
          break-after: page; page-break-after: always; overflow: hidden; }}
section:last-child {{ break-after: auto; page-break-after: auto; }}
h1 {{ font-size: 34pt; margin: 0 0 0.2in; }} h2 {{ font-size: 20pt; margin: 0 0 0.1in; color: #555; font-weight: normal; }}
p, li {{ font-size: 18pt; line-height: 1.35; }} li {{ margin-bottom: 6px; }}
.accent {{ color: {ORANGE}; }} .kicker {{ font-size: 13pt; letter-spacing: 2px; color: {ORANGE}; font-weight: bold; }}
.bubble {{ border-left: 6px solid {GREY}; padding: 8px 16px; margin: 10px 0; font-size: 17pt; background: #f6f6f6; }}
.bubble.bad {{ border-color: {ORANGE}; }} .strike {{ text-decoration: line-through; color: {ORANGE}; }}
.foot {{ position: absolute; bottom: 0.35in; left: 0.8in; right: 0.8in; font-size: 12pt; color: #777;
        border-top: 1px solid #ddd; padding-top: 6px; }}
.big {{ font-size: 54pt; font-weight: bold; color: {ORANGE}; }}
table {{ border-collapse: collapse; font-size: 12pt; white-space: nowrap; }} td, th {{ padding: 3px 5px; border-bottom: 1px solid #ddd; text-align: left; }}
th {{ color: #555; font-weight: normal; }} tr.pending td {{ color: #999; font-style: italic; }}
.cols {{ display: flex; gap: 0.4in; align-items: flex-start; }}
</style></head><body>

<section>
<div class="kicker">PROJECT 3 · JUDGE THE JUDGE</div>
<h1>AI judges wave through replies that <span class="accent">promise too much</span></h1>
<p>Customer: “Can I keep the car a few days longer?”</p>
<div class="bubble">A: You can usually extend your rental in the app or by phone,
<b>as long as the car is not reserved for another customer.</b></div>
<div class="bubble bad">B: You can usually extend your rental in the app or by phone. <span class="strike">[condition dropped]</span></div>
<p>The starting judge passes both. B commits SIXT to something the policy does not guarantee, and the judge
catches only <b>{float(cond_base):.0%}</b> of dropped conditions on dev. A release gate built on it lets these replies ship.</p>
<div class="foot">Team Divinecodes · Project 3 · {REPO} · all data synthetic (starter pack)</div>
</section>

<section>
<div class="kicker">INSIGHT</div>
<h1>A judge that reads one reply cannot see what is missing.<br><span class="accent">So we make the absence explicit.</span></h1>
<p>For every claim, call 1 lists the conditions and hedges the <b>policy</b> attaches to it and marks each one
<i>kept</i>, <i>dropped</i> or <i>not applicable</i>. A dropped condition becomes a visible field instead of a gap.</p>
<div class="cols"><div><div class="big">{cond_base} → {cond_ours}</div>
<p>dropped-condition catch rate, baseline → ours (dev, grouped 3-fold CV, shipped judge)</p></div></div>
<p>The rest is generic: certainty on a 0–3 scale (“usually” vs “always”), scope (some vs all branches), and numbers
checked in code. Nothing about the criterion is hard-coded; examples and rule mode come from the labelled pairs.</p>
<div class="foot">Numbers from score.py reports: starter_pack/baseline_report.txt, results/*_report.txt</div>
</section>

<section>
<div class="kicker">ARCHITECTURE</div>
<h1>LLM for meaning, <span class="accent">code for the verdict</span></h1>
{arch_svg()}
<ul style="margin-top:4px">
<li style="font-size:15pt"><b>Self-validating rule:</b> an unknown number fails a reply only if <code>prepare()</code> sees the rule never fire on a pass example of the current criterion.</li>
<li style="font-size:15pt"><b>Verify suspected fails only:</b> call 2 must quote the reply's exact words (checked in code). No proof → PASS. Same code for any criterion: only <code>--criterion</code> and <code>--dev</code> change.</li>
</ul>
<div class="foot">starter_pack/final_judge.py · recipe: starter_pack/RECIPE.md · full diagram: docs/ARCHITECTURE.md</div>
</section>

<section>
<div class="kicker">RESULTS · DEV, GROUPED CROSS-VALIDATION, claude-haiku-4.5</div>
<h1>More bad replies caught, <span class="accent">and more good replies kept</span></h1>
<div class="cols"><div>{chart}</div>
<div style="flex:1"><table><tr><th>crit.</th><th>judge</th><th>combined</th><th>catch</th><th>keep</th><th>kappa</th><th>repeat</th></tr>{trs}</table>
<p style="font-size:13pt"><b>What fixed keep:</b> call 2 must prove a violation with the reply's own words, and an
unproven finding passes (correct original passed {orig_pass}, baseline {f3(base.get('orig_pass'))}).
<b>Trade-off:</b> the 14:05 change (an unproven finding passes, no call 3) came from the criterion-2 error analysis and
was measured on both criteria; it costs some criterion-1 catch on dropped conditions. <b>Caveat:</b> both call-2 changes were designed
on dev errors, so dev gains are an upper bound. “repeat” = same verdict on two runs.{repeat_note}</p></div></div>
<div class="foot">Sources: starter_pack/baseline_report.txt, results/dev_pairs_report.txt (shipped), results/exp_base_dev_dev_pairs_report.txt{', results/c2_dev_pairs_report.txt' if c2 else ''}</div>
</section>

<section>
<div class="kicker">LIVE DEMO · FOR SIXT</div>
<h1>A release gate, <span class="accent">with the reason attached</span></h1>
<div class="cols">
<div><img src="{DEMO_IMG}" alt="Live demo: the original reply passes, the 'always' edit fails" style="height:5.15in;border:1px solid #ddd;border-radius:8px"></div>
<div style="flex:1">
<p style="font-size:15pt;margin:0 0 6px"><b>Live:</b> {DEMO_URL}. Real claude-haiku-4.5, every call shown. Here “usually” → “always”: original PASS, edit FAIL.</p>
<ul style="padding-left:22px;margin:0">
<li style="font-size:15pt">Run each chatbot version against the policy before release; replies that drop a condition or raise certainty are blocked.</li>
<li style="font-size:15pt">Every fail quotes the reply and the policy clause, so a reviewer decides in seconds.</li>
<li style="font-size:15pt">New criterion = new <code>--criterion</code> + a few labelled examples, no new code.</li></ul>
<h2 style="font-size:16pt;margin-top:10px">Next steps</h2>
<ul style="padding-left:22px;margin:0">
<li style="font-size:14pt">Win back dropped-condition catch on criterion 1 ({cond_before} before the 14:05 change, {cond_ours} now).</li>
<li style="font-size:14pt">Retrieve the closest labelled examples per reply; measure leave-one-edit-type-out.</li></ul>
</div></div>
<div class="foot">Team Divinecodes · {REPO} · demo: {DEMO_URL}</div>
</section>
</body></html>"""
    with open(os.path.join(HERE, "slides.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote slides.html:", ", ".join(f"{lbl} {r['combined']:.3f}" for lbl, r in runs),
          "| criterion 2:", "yes" if c2 else "pending")


if __name__ == "__main__":
    main()
