"""Write a small stratified dev subset for screening variants (default: 30 cases -> starter_pack/dev_pairs_30.jsonl).

Stratified by edit type (half harmful, half harmless) and spread round-robin over source replies, deterministic.
Screen variants on it with the full dev set as the example pool, so only the scored cases shrink:

    cd Project_3/starter_pack
    python3 ../dev_tools/make_subset.py
    python3 ../dev_tools/experiments.py --variants base R_hint --pairs dev_pairs_30.jsonl

One case is 3.3 points of catch or keep here: use it to drop clear losers, confirm winners on dev_pairs.jsonl.
"""
import argparse
import json
import os
import random
from collections import defaultdict

STARTER = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "starter_pack"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--src", default=os.path.join(STARTER, "dev_pairs.jsonl"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cases = [json.loads(line) for line in open(a.src, encoding="utf-8")]
    rng = random.Random(a.seed)
    by_type: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        by_type[c["edit_type"]].append(c)
    # quota per edit type: half of n per family, split evenly over that family's types
    fam_types: dict[str, list[str]] = defaultdict(list)
    for t, cs in sorted(by_type.items()):
        fam_types[cs[0]["edit_family"]].append(t)
    quota: dict[str, int] = {}
    fams = sorted(fam_types)
    for i, fam in enumerate(fams):
        n_fam = a.n // len(fams) + (1 if i < a.n % len(fams) else 0)
        types = sorted(fam_types[fam], key=lambda t: -len(by_type[t]))
        for j, t in enumerate(types):
            quota[t] = min(len(by_type[t]), n_fam // len(types) + (1 if j < n_fam % len(types) else 0))
    # pick per type, preferring the least-used source reply so all sources stay covered
    used: dict[str, int] = defaultdict(int)
    picked: list[dict] = []
    for t in sorted(quota, key=lambda t: len(by_type[t])):
        pool = by_type[t][:]
        rng.shuffle(pool)
        for _ in range(quota[t]):
            best = min(pool, key=lambda c: used[c["source_id"]])
            pool.remove(best)
            used[best["source_id"]] += 1
            picked.append(best)
    picked.sort(key=lambda c: c["case_id"])
    out = a.out or os.path.join(STARTER, f"dev_pairs_{a.n}.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for c in picked:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"wrote {len(picked)} cases to {out}")
    print("edit types:", {t: q for t, q in sorted(quota.items())})
    print("sources:", dict(sorted(used.items())))


if __name__ == "__main__":
    main()
