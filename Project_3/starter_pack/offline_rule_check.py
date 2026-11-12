"""Offline evidence for the code rule, no LLM needed.

1. Self-validation, exactly as final_judge.prepare() does it, per cross-validation fold.
2. Rule precision/recall on every dev reply.
3. "Baseline + rule": the precomputed baseline verdicts with the rule overriding to FAIL where it fires, scored.

    python3 offline_rule_check.py
"""
from __future__ import annotations

import collections
import csv
import io
import contextlib

import final_judge as fj
import run_judge
import score
from crossval import folds_by_source

pairs = run_judge._jsonl("dev_pairs.jsonl")
policy = open("policy.md", encoding="utf-8").read()
policy_numbers = frozenset(v for _, v in fj.numbers_in(policy))

print("1. Self-validation per fold (rule mode chosen from the OTHER folds' labelled examples):")
for i, fold in enumerate(folds_by_source(pairs, 3)):
    examples = [c for c in pairs if c not in fold]
    print(f"   fold {i + 1}: mode = {fj._validate_number_rule(policy_numbers, examples)}")

print("\n2. Rule fires on dev replies, by side and edit type:")
fires = collections.Counter()
for c in pairs:
    fires[("original", "all")] += bool(fj.unknown_numbers(c["original"], policy_numbers))
    fires[(c["edit_family"], c["edit_type"])] += bool(fj.unknown_numbers(c["edited"], policy_numbers))
totals = collections.Counter((c["edit_family"], c["edit_type"]) for c in pairs)
totals[("original", "all")] = len(pairs)
for k in sorted(totals):
    print(f"   {k[0]:<9} {k[1]:<22} fires on {fires[k]:>3} of {totals[k]:>3}")

print("\n3. Baseline verdicts, with the rule overriding the edited (and original) side to FAIL where it fires:")
base = score.read_verdicts("baseline_dev_verdicts.csv")
combo = {}
for c in pairs:
    o, e = base[c["case_id"]]
    o = "fail" if fj.unknown_numbers(c["original"], policy_numbers) else o
    e = "fail" if fj.unknown_numbers(c["edited"], policy_numbers) else e
    combo[c["case_id"]] = (o, e)
with open("../results/baseline_plus_rule_dev_verdicts.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["case_id", "original", "edited"])
    for cid in sorted(combo):
        w.writerow([cid, *combo[cid]])
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    score.main(["../results/baseline_plus_rule_dev_verdicts.csv", "dev_pairs.jsonl", "--baseline", "baseline_dev_verdicts.csv"])
print("\n".join("   " + line for line in buf.getvalue().splitlines()[:6]))
