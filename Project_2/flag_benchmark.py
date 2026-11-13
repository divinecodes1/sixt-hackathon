"""Measure the mileage flags with injected errors (known answers).

    python flag_benchmark.py [file.csv] [--rate 0.01] [--seeds 3]
Default input: first CSV in data/ (organizer data), else synthetic/fleet.csv, else example_file.csv.

For each seed: copy the rows, inject errors into a random sample of fresh return readings (NotOnRent rows, typed at
return), run mileage.flags() and report per error type how many injected readings were caught, and the flag rate on
untouched readings. On real data the untouched readings may contain real errors, so that rate is an upper bound on the
false-flag rate. Error types (what manual entry and manipulation look like):
  extra_digit     one digit typed twice or appended  (12345 -> 123455)
  missing_digit   one digit dropped                  (12345 -> 1235)
  transposed      two adjacent digits swapped        (12345 -> 12435), only if the change is >= 100 km
  rollback        the odometer is set back 2,000-8,000 km and every later reading stays lower (manipulation)
  stuck           the previous reading is reported again although the car was driven (copied / under-reported)
A rollback counts as caught if its first lowered reading or the reading just before it is flagged.
"""
from __future__ import annotations

import argparse
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import mileage as M

HERE = Path(__file__).resolve().parent
TYPES = ("extra_digit", "missing_digit", "transposed", "rollback", "stuck")


def _digits(km: float, kind: str, rng: random.Random) -> float | None:
    s = str(int(round(km)))
    if len(s) < 3:
        return None
    i = rng.randrange(len(s))
    if kind == "extra_digit":
        new = s[:i] + s[i] + s[i:]
    elif kind == "missing_digit":
        new = s[:i] + s[i + 1:]
    else:
        pairs = [j for j in range(len(s) - 1) if s[j] != s[j + 1]]
        if not pairs:
            return None
        j = rng.choice(pairs)
        new = s[:j] + s[j + 1] + s[j] + s[j + 2:]
    out = float(new)
    return out if abs(out - km) >= 100 else None


def inject(rows: list[dict], rate: float, seed: int) -> tuple[list[dict], list[dict], set]:
    """Returns (rows with errors, injected records, keys of later readings changed by a rollback)."""
    rng = random.Random(seed)
    rows = [dict(r) for r in rows]
    by_vid: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_vid[r.get("vhcl_anon_id", "")].append(i)
    candidates = [i for i, r in enumerate(rows)
                  if r.get("on_rent_status") == "NotOnRent" and M._float(r.get("vhcl_current_mileage")) is not None]
    chosen = rng.sample(candidates, max(1, int(rate * len(candidates))))
    injected, rolled_later, used_vids = [], set(), set()
    for n, i in enumerate(chosen):
        r = rows[i]
        vid, kind = r["vhcl_anon_id"], TYPES[n % len(TYPES)]
        if vid in used_vids:                      # one error per vehicle keeps the attribution unambiguous
            continue
        km = float(r["vhcl_current_mileage"])
        d0 = M.obs_day_of(r)
        if kind == "rollback":
            delta = rng.uniform(2000, 8000)
            for j in by_vid[vid]:                 # this reading and every reading measured after it
                dj = M.obs_day_of(rows[j])
                if dj is not None and dj >= d0 and (dj > d0 or j == i):
                    new_km = float(rows[j]["vhcl_current_mileage"]) - delta
                    rows[j]["vhcl_current_mileage"] = f"{new_km:.0f}"
                    if j != i:
                        rolled_later.add((vid, dj, round(new_km)))
            new = km - delta
        elif kind == "stuck":
            before = [(M.obs_day_of(rows[j]), float(rows[j]["vhcl_current_mileage"])) for j in by_vid[vid]
                      if M.obs_day_of(rows[j]) is not None and M.obs_day_of(rows[j]) < d0]
            if not before or km - max(before)[1] < 100:
                continue
            new = max(before)[1]
            r["vhcl_current_mileage"] = f"{new:.0f}"
        else:
            new = _digits(km, kind, rng)
            if new is None:
                continue
            r["vhcl_current_mileage"] = f"{new:.0f}"
        used_vids.add(vid)
        injected.append({"vid": vid, "type": kind, "day": d0, "km": round(new), "true_km": km})
    return rows, injected, rolled_later


def run(rows: list[dict], rate: float, seed: int) -> dict:
    bad_rows, injected, rolled_later = inject(rows, rate, seed)
    fleet = M.build_fleet(bad_rows)
    fl = M.flags(fleet)
    flagged = defaultdict(set)
    for f in fl:
        flagged[(f["vhcl_anon_id"], M._day(f["date"]), round(f["km"]))].add(f["rule"])
    caught = Counter()
    by_rule = defaultdict(Counter)
    for e in injected:
        v = fleet[e["vid"]]
        keys = [(e["vid"], e["day"], e["km"])]
        if e["type"] == "rollback":               # also the reading just before it
            idx = [j for j in range(len(v.obs_day)) if v.obs_day[j] == e["day"] and round(v.obs_km[j]) == e["km"]]
            if idx and idx[0] > 0:
                keys.append((e["vid"], v.obs_day[idx[0] - 1], round(v.obs_km[idx[0] - 1])))
        rules = set().union(*(flagged.get(k, set()) for k in keys))
        caught[e["type"]] += bool(rules)
        for rule in rules:
            by_rule[e["type"]][rule] += 1
    injected_keys = {(e["vid"], e["day"], e["km"]) for e in injected}
    untouched = [(vid, d, round(km)) for vid, v in fleet.items() for d, km in zip(v.obs_day, v.obs_km)
                 if (vid, d, round(km)) not in injected_keys and (vid, d, round(km)) not in rolled_later]
    false = [k for k in untouched if k in flagged]
    return {"injected": Counter(e["type"] for e in injected), "caught": caught, "by_rule": by_rule,
            "untouched": len(untouched), "flagged_untouched": len(false),
            "false_rules": Counter(r for k in false for r in flagged[k])}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--rate", type=float, default=0.01, help="share of return readings to corrupt (default 0.01)")
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    found = sorted((HERE / "data").glob("*.csv")) or [p for p in (HERE / "synthetic" / "fleet.csv",) if p.exists()] \
        or [HERE / "example_file.csv"]
    path = Path(a.csv) if a.csv else found[0]
    rows = M.load_rows(str(path))
    tot: dict = {"injected": Counter(), "caught": Counter(), "untouched": 0, "flagged_untouched": 0,
                 "false_rules": Counter(), "by_rule": defaultdict(Counter)}
    for seed in range(a.seeds):
        r = run(rows, a.rate, seed)
        for k in ("injected", "caught", "false_rules"):
            tot[k] += r[k]
        tot["untouched"] += r["untouched"]
        tot["flagged_untouched"] += r["flagged_untouched"]
        for t, c in r["by_rule"].items():
            tot["by_rule"][t] += c
    print(f"{path.name}: {a.seeds} seeds, {a.rate:.1%} of return readings corrupted per seed")
    print(f"\n{'error type':<15}{'injected':>9}{'caught':>8}{'recall':>8}   rules that fired")
    for t in TYPES:
        n, c = tot["injected"][t], tot["caught"][t]
        rules = ", ".join(f"{k} {v}" for k, v in tot["by_rule"][t].most_common())
        print(f"{t:<15}{n:>9}{c:>8}{(c / n if n else float('nan')):>8.0%}   {rules}")
    n_all, c_all = sum(tot["injected"].values()), sum(tot["caught"].values())
    rate = tot["flagged_untouched"] / max(tot["untouched"], 1)
    print(f"{'all':<15}{n_all:>9}{c_all:>8}{c_all / max(n_all, 1):>8.0%}")
    print(f"\nuntouched readings flagged: {tot['flagged_untouched']} of {tot['untouched']} "
          f"({1000 * rate:.1f} per 1,000; upper bound on false flags) by rule: {dict(tot['false_rules'])}")


if __name__ == "__main__":
    main()
