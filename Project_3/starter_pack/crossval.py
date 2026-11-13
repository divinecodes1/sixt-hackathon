"""Honest dev numbers for a judge that learns from labelled examples: grouped cross-validation by source reply.

Each source_id goes to one of K folds (sorted ids, round robin). For every fold the judge's prepare() only sees the
OTHER folds as examples, and is scored on this fold. The merged verdicts cover every case exactly once, so they can be
scored with score.py like any other verdicts file.

    python3 crossval.py --judge final_judge.py --pairs dev_pairs.jsonl --criterion JUDGE1_CRITERION.md \\
        --policy policy.md --out cv_run1.csv [--folds 3] [--workers 8]
    python3 score.py cv_run1.csv dev_pairs.jsonl --baseline baseline_dev_verdicts.csv [--repeat cv_run2.csv]
"""
from __future__ import annotations

import argparse
import csv
import sys

import run_judge


def folds_by_source(cases: list[dict], k: int) -> list[list[dict]]:
    ids = sorted({c["source_id"] for c in cases})
    fold_of = {sid: i % k for i, sid in enumerate(ids)}
    out: list[list[dict]] = [[] for _ in range(k)]
    for c in cases:
        out[fold_of[c["source_id"]]].append(c)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--criterion", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    criterion = open(a.criterion, encoding="utf-8").read()
    policy = open(a.policy, encoding="utf-8").read()
    cases = run_judge._jsonl(a.pairs)
    folds = folds_by_source(cases, a.folds)
    verdicts: dict[str, tuple[str, str]] = {}
    for i, fold in enumerate(folds):
        examples = [c for j, f in enumerate(folds) if j != i for c in f]
        print(f"fold {i + 1}/{len(folds)}: {len(fold)} cases scored, {len(examples)} example cases", file=sys.stderr)
        verdicts.update(run_judge.run(a.judge, fold, criterion, policy, examples, workers=a.workers, progress=True))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "original", "edited"])
        for cid in sorted(verdicts):
            w.writerow([cid, *verdicts[cid]])
    print(f"wrote {len(verdicts)} verdict rows to {a.out}")
    mod = sys.modules.get("contestant_judge")
    if mod is not None and hasattr(mod, "STATS"):
        s = mod.STATS
        print(f"LLM calls {s['calls']}, parse failures {s['parse_failures']}, rule fails {s['rule_fail']}, "
              f"models reported by the endpoint: {sorted(s['models'])}", file=sys.stderr)
        if s.get("temperature_dropped"):
            print(f"WARNING: the endpoint rejected temperature {s['temperature_dropped']} times; those calls were "
                  "resent without it (default sampling). Set JUDGE_LLM_OMIT_TEMPERATURE=1 to skip the rejected "
                  "attempt; check run-to-run consistency.", file=sys.stderr)


if __name__ == "__main__":
    main()
