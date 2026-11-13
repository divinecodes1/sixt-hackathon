"""Build two mock criteria from Project 3's dev pairs, to rehearse the surprise-criterion handoff.

Run from Project_3/starter_pack:  python3 <skill>/scripts/make_mocks.py [--pairs dev_pairs.jsonl] [--out ../mock_criteria]

For each mock it writes <out>/<name>/CRITERION.md, c2_dev_pairs.jsonl (a few labelled examples from 2 source replies,
like the organizers will hand out) and eval_pairs.jsonl (other source replies, at most 2 per edit type and language),
then prints the number-rule mode final_judge.prepare() picks. Labels are derived from how each pair was built, so
they are approximate. No LLM calls.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.getcwd())

NUMBERS = """# Mock criterion A: wrong numbers

Decide whether the reply states a number (fee, price, amount, deposit, age, time limit, duration) that differs from
the policy.

- `pass`: every number in the reply matches the policy, or the reply contains no number.
- `fail`: at least one number in the reply differs from the policy.

Missing conditions, hedges, scope, tone, length, politeness and language do not matter for this criterion.
"""

FILLER = """# Mock criterion B: unnecessary pleasantries or filler

Decide whether the reply contains unnecessary pleasantries or filler: a greeting or polite opener, or a sentence that
gives the customer no information (for example "We are always happy to help").

- `pass`: every sentence of the reply carries information that answers the question.
- `fail`: the reply contains at least one opener, pleasantry or filler sentence.

Whether the reply's facts match the policy does not matter for this criterion. Sentence order and language do not
matter either.
"""

# name -> (criterion text, edit types whose edited reply fails, filter for usable cases)
MOCKS = {
    "numbers": (NUMBERS, {"wrong_number"}, lambda c: True),
    # padding_removal originals contain padding, and padded harmful edits contain an opener/filler: both excluded
    "filler": (FILLER, {"polite_opener", "filler_padding"},
               lambda c: c["edit_type"] != "padding_removal" and not c.get("length_padding")),
}


def relabel(c: dict, failing: set[str]) -> dict:
    harmful = c["edit_type"] in failing
    return {**c, "edit_family": "harmful" if harmful else "harmless", "expected_verdict_change": harmful,
            "original_label": "pass", "edited_label": "fail" if harmful else "pass"}


def cap(cases: list[dict], key, n: int) -> list[dict]:
    seen: collections.Counter = collections.Counter()
    out = []
    for c in sorted(cases, key=lambda c: c["case_id"]):
        if seen[key(c)] < n:
            seen[key(c)] += 1
            out.append(c)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pairs", default="dev_pairs.jsonl")
    ap.add_argument("--policy", default="policy.md")
    ap.add_argument("--out", default="../mock_criteria")
    a = ap.parse_args()
    if not os.path.exists("final_judge.py"):
        sys.exit("run this from Project_3/starter_pack")
    import final_judge as fj

    cases = [json.loads(line) for line in open(a.pairs, encoding="utf-8") if line.strip()]
    policy = open(a.policy, encoding="utf-8").read()
    sources = sorted({c["source_id"] for c in cases})
    example_sources = set(sources[:2])
    for name, (text, failing, usable) in MOCKS.items():
        pool = [relabel(c, failing) for c in cases if usable(c)]
        examples = cap([c for c in pool if c["source_id"] in example_sources], lambda c: c["edit_type"], 2)
        evals = cap([c for c in pool if c["source_id"] not in example_sources],
                    lambda c: (c["edit_type"], c["lang"]), 2)
        d = os.path.join(a.out, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "CRITERION.md"), "w", encoding="utf-8") as f:
            f.write(text)
        for fname, rows in (("c2_dev_pairs.jsonl", examples), ("eval_pairs.jsonl", evals)):
            with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
                f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        fj.prepare(text, policy, examples)
        fam = collections.Counter(c["edit_family"] for c in evals)
        print(f"{name}: {len(examples)} examples, {len(evals)} eval cases ({dict(fam)}), "
              f"number rule = {fj.CONFIG['number_rule']}  -> {d}")


if __name__ == "__main__":
    main()
