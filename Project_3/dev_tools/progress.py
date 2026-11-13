#!/usr/bin/env python3
"""One-line progress bars for the running Project 3 evaluations (used as the Claude Code status line).

Reads only local logs: the newest results/dev_eval_*.log (run_dev.sh, 2 passes x 3 folds) and the newest
results/exp_fast_*.log (experiments.py, N variants; finished variants are the rows logged in experiments.md).
"""
import glob
import os
import re
import sys

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")


def bar(frac: float, width: int = 12) -> str:
    frac = max(0.0, min(1.0, frac))
    full = int(round(frac * width))
    return "█" * full + "░" * (width - full)


def newest(pattern: str):
    files = glob.glob(os.path.join(RES, pattern))
    return max(files, key=os.path.getmtime) if files else None


def dev_progress():
    path = newest("dev_eval_*.log")
    if not path:
        return None
    text = open(path, encoding="utf-8", errors="replace").read()
    passes = 2
    # Each "fold k/3" line starts a fold; "judged a/b" lines report progress inside it.
    done = 0.0
    current = 0.0
    for chunk in re.split(r"(?=fold \d/3:)", text)[1:]:
        judged = re.findall(r"judged (\d+)/(\d+)", chunk)
        total = int(judged[-1][1]) if judged else None
        if judged and judged[-1][0] == judged[-1][1]:
            done += 1
            current = 0.0
        else:
            current = int(judged[-1][0]) / total if judged else 0.0
    finished = "COMBINED" in text  # score.py's report is tee'd into the same log at the end
    frac = 1.0 if finished else (done + current) / (3 * passes)
    pass_no = min(passes, int(done // 3) + 1)
    label = "done" if finished else f"pass {pass_no}/{passes}"
    return f"dev CV {bar(frac)} {frac*100:3.0f}% {label}"


def exp_progress():
    path = newest("exp_*_*.log")
    if not path:
        return None
    text = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"(\d+) variant\(s\)", text)
    total = int(m.group(1)) if m else 0
    if not total:
        return None
    done = len(re.findall(r"^\| \d\d-\d\d \d\d:\d\d \|", text, flags=re.M))
    running = [v for v in re.findall(r"_variant_(\w+)\.py", _ps()) if v]
    cur = f" now {running[0]}" if running and done < total else ""
    return f"variants {bar(done / total)} {done}/{total}{cur}"


def _ps() -> str:
    try:
        return os.popen("ps -eo args 2>/dev/null").read()
    except Exception:
        return ""


def main():
    sys.stdin.read() if not sys.stdin.isatty() else None  # Claude Code sends session JSON; not needed
    parts = [p for p in (dev_progress(), exp_progress()) if p]
    print("  │  ".join(parts) if parts else "no Project 3 runs found")


if __name__ == "__main__":
    main()
