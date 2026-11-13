"""Measure the judge's recipe settings, one variant at a time, with the same grouped cross-validation as run_dev.sh.

Each variant is a temporary copy of final_judge.py (starter_pack/_variant_<name>.py, git-ignored, deleted after
the run) with one or more settings changed. final_judge.py itself is never edited by this script. Results are
appended to results/experiments.md; pick a winner there, then set it in final_judge.py by hand and rerun run_dev.sh.

    cd Project_3/starter_pack
    python3 ../dev_tools/experiments.py --dry                                  # list variants, count replies
    python3 ../dev_tools/experiments.py --variants base R_hint E_contrast      # 113-case screen (default)
    python3 ../dev_tools/experiments.py --variants base P_prefill --pairs dev_pairs.jsonl --repeat
    python3 ../dev_tools/experiments.py --variants base R_hint --stress        # also the stress set

Read results next to the noise floor: 9 source replies, so one case moves a type by 3-7 points.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STARTER = os.path.normpath(os.path.join(HERE, "..", "starter_pack"))
RESULTS = os.path.normpath(os.path.join(HERE, "..", "results"))
STRESS = os.path.normpath(os.path.join(HERE, "..", "stress", "stress_pairs.jsonl"))

# name -> (settings to change, hypothesis). Values are Python source, written into the copy as they are.
VARIANTS = {
    "base": ({}, "current final_judge.py"),
    "R_hint": ({"NUMBER_RULE_MAX": '"hint"'}, "rule as hint only: fewer false fails on stricter numbers"),
    "E_contrast": ({"EXAMPLE_STYLE": '"contrast"'}, "minimal-pair examples make the pass/fail boundary visible"),
    "P_prefill": ({"PREFILL": "True"}, "prefilled <json> removes preambles and parse failures"),
    "T_think1k": ({"THINKING_BUDGET": "1024"}, "extended thinking on call 1; costs temperature 0"),
    "T_think3k": ({"THINKING_BUDGET": "3072"}, "more thinking on call 1"),
    "PE": ({"PREFILL": "True", "EXAMPLE_STYLE": '"contrast"'}, "prefill + contrast examples"),
    "PER": ({"PREFILL": "True", "EXAMPLE_STYLE": '"contrast"', "NUMBER_RULE_MAX": '"hint"'}, "all three"),
    "S_second_look": ({"SECOND_LOOK": "True"}, "call 2 re-checks passes whose own fields show a policy difference"),
    "J_adjudicate": ({"ADJUDICATE": "True"}, "call 3 weighs both reviewers' arguments instead of judging afresh"),
    "SJ": ({"SECOND_LOOK": "True", "ADJUDICATE": "True"}, "second look + adjudication"),
    "C_evidence": ({"CONDITION_EVIDENCE": "True"}, "kept conditions must quote the reply; unproven ones go to call 2"),
    "K_clauses": ({"CLAUSE_IDS": "True"}, "numbered policy clauses; cited clause text checked in code"),
    "H_hedge": ({"HEDGE_FROM_QUOTE": "True"}, "certainty from the original words; quantities to scope; gloss last"),
    "V_deanchor": ({"VERIFY_DEANCHOR": "True"}, "call 2 sees where to look, not the first reviewer's conclusion"),
    "X_verify_examples": ({"VERIFY_EXAMPLES": "True"}, "call 2 sees the labelled examples: fewer false confirms on good replies"),
    "W_witness": ({"VERIFY_WITNESS": "True"}, "call 2 confirms only with the reply's exact words + a concrete case: "
                  "fewer false confirms on correct originals"),
    "WX": ({"VERIFY_WITNESS": "True", "VERIFY_EXAMPLES": "True"}, "witness + labelled examples in call 2"),
    "Q_scoped_verify": ({"VERIFY_SCOPED": "True"}, "call 2: limitation stated anywhere counts; condition matters only for the promise it limits"),
    "CKHV": ({"CONDITION_EVIDENCE": "True", "CLAUSE_IDS": "True", "HEDGE_FROM_QUOTE": "True",
              "VERIFY_DEANCHOR": "True"}, "all four evidence switches"),
}


def make_variant(name: str, settings: dict) -> str:
    src = open(os.path.join(STARTER, "final_judge.py"), encoding="utf-8").read()
    for key, value in settings.items():
        src, n = re.subn(rf"^{key} = [^#\n]*", f"{key} = {value}  ", src, count=1, flags=re.M)
        if n != 1:
            sys.exit(f"setting {key} not found in final_judge.py")
    path = os.path.join(STARTER, f"_variant_{name}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    return path


def score(verdicts: str, pairs: str, repeat: str | None) -> dict:
    cmd = [sys.executable, "score.py", verdicts, pairs]
    if os.path.basename(pairs).startswith("dev_pairs"):
        cmd += ["--baseline", "baseline_dev_verdicts.csv"]
    if repeat:
        cmd += ["--repeat", repeat]
    out = subprocess.run(cmd, cwd=STARTER, capture_output=True, text=True, check=True).stdout
    get = lambda pat: (re.search(pat, out) or [None, "n/a"])[1]  # noqa: E731
    return {"combined": get(r"COMBINED \(the score\)\s+([\d.]+)"), "catch": get(r"macro catch\s+([\d.]+)"),
            "keep": get(r"macro keep\s+([\d.]+)"), "kappa": get(r"kappa vs construction\s+(-?[\d.]+)"),
            "same": get(r"same verdict ([\d.]+)"), "report": out}


def run_one(judge: str, pairs: str, out: str, workers: int, stress: bool,
            examples: str | None = None) -> tuple[float, str]:
    if stress:
        cmd = [sys.executable, "run_judge.py", "--judge", judge, "--pairs", pairs, "--criterion",
               "JUDGE1_CRITERION.md", "--policy", "policy.md", "--dev", "dev_pairs.jsonl", "--out", out,
               "--workers", str(workers)]
    else:
        cmd = [sys.executable, "crossval.py", "--judge", judge, "--pairs", pairs, "--criterion", "JUDGE1_CRITERION.md",
               "--policy", "policy.md", "--out", out, "--workers", str(workers)]
        if examples and os.path.abspath(examples) != os.path.abspath(pairs):
            cmd += ["--examples", examples]
    env = {k: v for k, v in os.environ.items() if k != "JUDGE_LLM_CACHE"}
    p = subprocess.run(cmd, cwd=STARTER, capture_output=True, text=True, env=env)
    if p.returncode:
        sys.exit(f"run failed:\n{p.stderr[-2000:]}")
    calls = re.search(r"LLM calls (\d+)", p.stderr)
    return (int(calls[1]) if calls else -1), p.stderr


def replies(pairs: str) -> int:
    rows = [json.loads(l) for l in open(pairs, encoding="utf-8")]
    return len({(r["orig_lang"], r["question_original"], r["original"]) for r in rows} |
               {(r["lang"], r["question"], r["edited"]) for r in rows})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variants", nargs="+", default=["base"], choices=sorted(VARIANTS))
    ap.add_argument("--pairs", default="dev_pairs_113.jsonl",
                    help="scored cases (default: 113-case stratified screen, see make_subset.py)")
    ap.add_argument("--examples", default="dev_pairs.jsonl",
                    help="example pool for cross-validation (held-out sources removed per fold)")
    ap.add_argument("--stress", action="store_true", help="also score each variant on the stress set")
    ap.add_argument("--repeat", action="store_true", help="run twice to measure consistency")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--results", default=RESULTS, help="output folder (default Project_3/results)")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--combine", nargs="+", metavar="VARIANT",
                    help="also run one variant that merges these variants' settings (named combo_<a>+<b>...)")
    a = ap.parse_args()
    if a.combine:
        merged: dict = {}
        for v in a.combine:
            for key, value in VARIANTS[v][0].items():
                if merged.get(key, value) != value:
                    sys.exit(f"--combine: {v} sets {key}={value}, another variant sets {merged[key]}")
                merged[key] = value
        name = "combo_" + "+".join(a.combine)
        VARIANTS[name] = (merged, "combined: " + ", ".join(f"{k}={v}" for k, v in merged.items()))
        a.variants = [v for v in a.variants if v != name] + [name]
    pairs = os.path.join(STARTER, a.pairs) if not os.path.isabs(a.pairs) else a.pairs
    sets = [("dev", pairs, False)] + ([("stress", STRESS, True)] if a.stress else [])
    n_runs = 2 if a.repeat else 1
    total = sum(replies(p) for _, p, _ in sets) * n_runs * len(a.variants)
    print(f"{len(a.variants)} variant(s) x {n_runs} run(s): {total} replies to judge, 1-3 LLM calls each")
    for v in a.variants:
        print(f"  {v:11} {VARIANTS[v][1]}")
    if a.dry:
        return

    res_dir = os.path.abspath(a.results)
    os.makedirs(res_dir, exist_ok=True)
    log = os.path.join(res_dir, "experiments.md")
    prefix = "exp_"
    if not os.path.exists(log):
        with open(log, "w", encoding="utf-8") as f:
            f.write("# Experiments log (final_judge.py settings)\n\nEvery number below is produced by score.py.\n\n"
                    "| time | variant | set | combined | catch | keep | kappa | same verdict | calls/reply | note |\n"
                    "|---|---|---|---|---|---|---|---|---|---|\n")
    for v in a.variants:
        settings, note = VARIANTS[v]
        judge = make_variant(v, settings)
        try:
            for set_name, set_path, is_stress in sets:
                outs, calls = [], 0
                for run in range(1, n_runs + 1):
                    out = os.path.join(res_dir, f"{prefix}{v}_{set_name}_{os.path.basename(set_path)[:-6]}_run{run}.csv")
                    c, _ = run_one(os.path.basename(judge), set_path, out, a.workers, is_stress,
                                   os.path.join(STARTER, a.examples))
                    calls += c
                    outs.append(out)
                m = score(outs[0], set_path, outs[1] if len(outs) > 1 else None)
                per = f"{calls / (replies(set_path) * n_runs):.2f}" if calls >= 0 else "n/a"
                report = os.path.join(res_dir, f"{prefix}{v}_{set_name}_{os.path.basename(set_path)[:-6]}_report.txt")
                open(report, "w", encoding="utf-8").write(m["report"])
                row = (f"| {dt.datetime.now():%m-%d %H:%M} | {v} | {set_name} ({os.path.basename(set_path)}) | "
                       f"{m['combined']} | {m['catch']} | {m['keep']} | {m['kappa']} | "
                       f"{m['same'] if a.repeat else 'n/a'} | {per} | {note} |")
                with open(log, "a", encoding="utf-8") as f:
                    f.write(row + "\n")
                print(row, flush=True)
        finally:
            os.remove(judge)


if __name__ == "__main__":
    main()
