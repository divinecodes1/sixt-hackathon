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

# (label, report path). First = the shipped judge (run_dev.sh, VERIFY_WITNESS on, 12:33); second = the same recipe
# before the witness check (run A, 11:23), to show what the fix bought.
BASELINE = os.path.join(P3, "starter_pack", "baseline_report.txt")
OURS = [("Ours, shipped", os.path.join(RES, "dev_pairs_report.txt")),
        ("Ours, before witness check", os.path.join(RES, "exp_base_dev_dev_pairs_report.txt"))]
C2_OURS = os.path.join(RES, "c2_dev_pairs_report.txt")            # written by run_dev.sh on the surprise criterion
C2_BASE = os.path.join(RES, "c2_vs_baseline_report.txt")          # score.py ... --baseline (optional)
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
                     ("base_combined", r"COMBINED \(the score\)\s+[\d.]+\s+\(baseline ([\d.]+)")]:
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


PIPELINE = f"""<svg viewBox="0 0 1150 250" width="1150" height="250" font-family="Arial" role="img">
<defs><marker id="a" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">
<path d="M0,0 L10,5 L0,10 z" fill="{DARK}"/></marker></defs>
<g font-size="17" text-anchor="middle">
<rect x="0" y="70" width="190" height="100" rx="10" fill="#fff" stroke="{GREY}" stroke-width="2"/>
<text x="95" y="105" font-weight="bold">prepare()</text><text x="95" y="130">examples + rule mode</text>
<text x="95" y="152">from labelled pairs</text>
<rect x="240" y="70" width="190" height="100" rx="10" fill="#fff" stroke="{DARK}" stroke-width="2"/>
<text x="335" y="105" font-weight="bold">Number rule</text><text x="335" y="130">code, 0 calls</text>
<text x="335" y="152">self-validated</text>
<rect x="480" y="70" width="210" height="100" rx="10" fill="{ORANGE}"/>
<text x="585" y="100" font-weight="bold" fill="#fff">Call 1</text>
<text x="585" y="125" fill="#fff">claim by claim:</text><text x="585" y="147" fill="#fff">conditions kept /</text>
<text x="585" y="167" fill="#fff">dropped (JSON)</text>
<rect x="740" y="70" width="180" height="100" rx="10" fill="{ORANGE}" opacity="0.85"/>
<text x="830" y="105" font-weight="bold" fill="#fff">Call 2</text><text x="830" y="130" fill="#fff">verify suspected</text>
<text x="830" y="152" fill="#fff">fails only</text>
<rect x="970" y="70" width="180" height="100" rx="10" fill="{ORANGE}" opacity="0.65"/>
<text x="1060" y="105" font-weight="bold" fill="#fff">Call 3</text><text x="1060" y="130" fill="#fff">tie-break only</text>
<text x="1060" y="152" fill="#fff">if 1 and 2 disagree</text>
</g>
<g stroke="{DARK}" stroke-width="2" marker-end="url(#a)">
<line x1="190" y1="120" x2="236" y2="120"/><line x1="430" y1="120" x2="476" y2="120"/>
<line x1="690" y1="120" x2="736" y2="120"/><line x1="920" y1="120" x2="966" y2="120"/></g>
<g font-size="16" fill="{DARK}" text-anchor="middle">
<text x="335" y="205">unknown number → FAIL</text><text x="585" y="205">no finding → PASS (1 call)</text>
<text x="830" y="205">confirmed → FAIL</text><text x="1060" y="205">verdict decided</text></g>
<text x="575" y="30" font-size="18" text-anchor="middle" fill="{DARK}">verdict computed in code · one reply per call ·
no state · ≤ 3 calls · claude-haiku-4.5, temperature 0</text>
</svg>"""


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
        c2_base = c2b.get("base_combined") if c2b else None
        trs += (f"<tr><td>2</td><td>Baseline</td><td>{f3(c2_base)}</td><td colspan=4>"
                f"{'' if c2_base is not None else 'pending'}</td></tr>"
                f"<tr><td>2</td><td>Ours, unchanged</td><td>{f3(c2['combined'])}</td><td>{f3(c2.get('catch'))}"
                f"</td><td>{f3(c2.get('keep'))}</td><td>{f3(c2.get('kappa'))}</td><td>{f3(c2.get('same'))}</td></tr>")
    else:
        trs += '<tr class="pending"><td>2</td><td colspan=6>runs on the new criterion at 14:30, code unchanged</td></tr>'

    cond_base = base["types"].get("condition_removal", {}).get("catch", "n/a")
    shipped = runs[0][1]
    cond_ours = shipped["types"].get("condition_removal", {}).get("catch", "n/a")
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
table {{ border-collapse: collapse; font-size: 13pt; white-space: nowrap; }} td, th {{ padding: 4px 7px; border-bottom: 1px solid #ddd; text-align: left; }}
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
<div class="kicker">METHOD</div>
<h1>Code for facts, the LLM for meaning, <span class="accent">code for the verdict</span></h1>
{PIPELINE}
<ul>
<li><b>Self-validating rule:</b> a number not in the policy fails the reply, only if <code>prepare()</code> sees it never fire on a pass example of the current criterion; otherwise hint or off.</li>
<li><b>Verify only suspected fails</b> in a fresh context. Call 2 may confirm a fail only by quoting the reply's exact words (checked in code) and naming a concrete misleading case; a third call only when calls 1 and 2 disagree.</li>
<li>Same code for the surprise criterion: only <code>--criterion</code> and <code>--dev</code> change.</li>
</ul>
<div class="foot">starter_pack/final_judge.py · recipe: starter_pack/RECIPE.md</div>
</section>

<section>
<div class="kicker">RESULTS · DEV, GROUPED CROSS-VALIDATION, claude-haiku-4.5</div>
<h1>More bad replies caught, <span class="accent">and more good replies kept</span></h1>
<div class="cols"><div>{chart}</div>
<div style="flex:1"><table><tr><th>crit.</th><th>judge</th><th>combined</th><th>catch</th><th>keep</th><th>kappa</th><th>repeat</th></tr>{trs}</table>
<p style="font-size:13pt"><b>What fixed keep:</b> before the witness check, call 2 confirmed false alarms on correct
replies (correct original passed {orig_pass}, baseline {f3(base.get('orig_pass'))}); each failed original costs every
pair built from it. <b>What did not work:</b> evidence-quoting variants in call 1 scored lower on subsets.
<b>Caveat:</b> the witness prompt was designed on dev errors, so the dev gain is an upper bound. “repeat” = same verdict on two runs.</p></div></div>
<div class="foot">Sources: starter_pack/baseline_report.txt, results/dev_pairs_report.txt (shipped), results/exp_base_dev_dev_pairs_report.txt{', results/c2_dev_pairs_report.txt' if c2 else ''}</div>
</section>

<section>
<div class="kicker">FOR SIXT</div>
<h1>A release gate for chatbot changes, <span class="accent">with the reason attached</span></h1>
<ul>
<li>Run every candidate chatbot version against the policy before release; a reply that drops a condition or raises
certainty is blocked.</li>
<li>Each fail carries the quoted reply words and the policy clause, so a reviewer decides in seconds.</li>
<li>The recipe takes any new criterion plus a few labelled examples, with no code change (shown live on the surprise criterion).</li>
</ul>
<h2>Next steps</h2>
<ul>
<li>Close the gap on wrong numbers and wrong policy details, where the baseline still catches slightly more.</li>
<li>Retrieve the closest labelled examples per reply instead of a fixed set.</li>
<li>Measure transfer on edit types not in dev (leave-one-edit-type-out).</li>
</ul>
<div class="foot">Team Divinecodes · {REPO}</div>
</section>
</body></html>"""
    with open(os.path.join(HERE, "slides.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote slides.html:", ", ".join(f"{lbl} {r['combined']:.3f}" for lbl, r in runs),
          "| criterion 2:", "yes" if c2 else "pending")


if __name__ == "__main__":
    main()
