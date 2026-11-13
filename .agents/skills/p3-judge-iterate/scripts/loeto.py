"""Leave-one-edit-type-out evaluation for a Project 3 judge.

For every edit type, the judge's prepare() sees labelled examples from all OTHER edit types only, and the judge is
scored on that type. This estimates how the recipe handles edit types it has never seen (the hidden set has some).
Examples may come from the same source replies as the scored type: this tests unseen edit types, not unseen sources
(use crossval.py for that).

Run from Project_3/starter_pack with the .env loaded (needs the LLM key unless --dry):
    python3 <skill>/scripts/loeto.py [--pairs dev_pairs_fast.jsonl] [--criterion JUDGE1_CRITERION.md]
        [--judge final_judge.py] [--out ../results/loeto.csv] [--workers 8] [--dry]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.getcwd())  # run_judge.py and score.py live in starter_pack/
import run_judge  # noqa: E402
import score  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pairs", default="dev_pairs_fast.jsonl")
    ap.add_argument("--criterion", default="JUDGE1_CRITERION.md")
    ap.add_argument("--policy", default="policy.md")
    ap.add_argument("--judge", default="final_judge.py")
    ap.add_argument("--out", default="../results/loeto.csv")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry", action="store_true", help="only print the split sizes, no LLM calls")
    a = ap.parse_args()
    if not os.path.exists("run_judge.py"):
        sys.exit("run this from Project_3/starter_pack")
    if os.environ.get("JUDGE_LLM_CACHE") and not a.dry:
        print("warning: JUDGE_LLM_CACHE is set; these numbers are not valid for reporting", file=sys.stderr)

    crit = open(a.criterion, encoding="utf-8").read()
    pol = open(a.policy, encoding="utf-8").read()
    cases = run_judge._jsonl(a.pairs)
    types = sorted({c["edit_type"] for c in cases})
    verdicts: dict[str, tuple[str, str]] = {}
    print(f"{'held-out edit type':<24}{'family':<10}{'n':>4}{'examples':>10}   catch   keep")
    for t in types:
        test = [c for c in cases if c["edit_type"] == t]
        examples = [c for c in cases if c["edit_type"] != t]
        fam = test[0]["edit_family"]
        if a.dry:
            print(f"{t:<24}{fam:<10}{len(test):>4}{len(examples):>10}")
            continue
        v = run_judge.run(a.judge, test, crit, pol, examples, workers=a.workers)
        verdicts.update(v)
        r = score.score(test, v)["per_edit_type"][t]
        print(f"{t:<24}{fam:<10}{len(test):>4}{len(examples):>10}   {score.fmt(r['catch'])}  {score.fmt(r['keep'])}",
              flush=True)
    if a.dry:
        return
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "original", "edited"])
        for cid in sorted(verdicts):
            w.writerow([cid, *verdicts[cid]])
    print("\nOverall (every type scored while held out):")
    print(score.report(score.score(cases, verdicts)))
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
