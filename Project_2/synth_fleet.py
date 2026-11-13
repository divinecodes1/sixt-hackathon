"""Synthetic fleet in the organizers' schema and data model, to test the pipeline at fleet scale before (and besides)
the real data. Everything here is made up; numbers measured on it are NOT evidence about SIXT's fleet.

The row pattern copies example_file.csv (EDA.md):
- every rental close writes an OnRent row stamped at the return date that carries the odometer at HANDOVER;
- some returns also write a NotOnRent row with the fresh return reading (more often for LongTerm);
- defleet: status 3 and uti_plan 0 from a random day, one last one-way rental, then no more rows.
What varies: segment (level, type, km per rental day), ShortTerm (1-13 days) vs LongTerm (28-120 days, lower daily
km), per-vehicle and per-rental intensity, idle transfers, and a monthly plan that is biased against realised use.

    python synth_fleet.py [--vehicles 300] [--days 240] [--seed 0] [--out synthetic/fleet.csv]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import random
from datetime import date, timedelta

COLUMNS = ["vhcl_anon_id", "acriss_code_anonymized", "vehicle_level", "vehicle_type", "model_year", "driven_wheels",
           "power_ps", "cubic_capacity_liter", "status_code_anonymized", "vhcl_fct_taken_datm",
           "vhcl_current_mileage", "repair_status", "on_rent_status", "rental_product", "one_way_flg",
           "rntl_handover_date", "rntl_return_date", "vhcl_max_mileage", "brnc_code", "brnc_pool_code",
           "brnc_region_code", "brnc_state_code", "uti_plan"]

# level, vehicle type, mean km per rental day (ShortTerm), acriss code
SEGMENTS = [("Compact", "Limousine", 160.0, "1"), ("Intermediate", "Off Road", 210.0, "2"),
            ("Full Size", "Wagon", 250.0, "3"), ("Premium", "Limousine", 230.0, "4")]
START = date(2024, 1, 1)


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest().upper()


def generate(n_vehicles: int = 300, days: int = 240, seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    branches = [_h(f"branch{i}-{seed}") for i in range(12)]
    regions = [_h(f"region{i}-{seed}") for i in range(3)]
    months = (days // 30) + 2
    plan = {(s[0], m): rng.uniform(0.6, 0.9) for s in SEGMENTS for m in range(months)}   # segment-month plan
    rows: list[dict] = []
    for k in range(n_vehicles):
        level, vtype, base, acriss = rng.choice(SEGMENTS)
        long_term = rng.random() < 0.15
        r_rent = base * rng.lognormvariate(0, 0.25) * (0.45 if long_term else 1.0)
        r_idle = rng.uniform(0.0, 6.0)                     # transfers between branches, shuttling
        plan_bias = rng.gauss(1.05, 0.12)                  # realised utilisation vs plan, per vehicle
        p_return_row = 0.6 if long_term else 0.4
        defleet = rng.randint(int(days * 0.5), days) if rng.random() < 0.3 else None
        vid, branch, region = _h(f"veh{k}-{seed}"), rng.choice(branches), rng.choice(regions)
        static = {"vhcl_anon_id": vid, "acriss_code_anonymized": acriss, "vehicle_level": level, "vehicle_type": vtype,
                  "model_year": "2024", "driven_wheels": rng.choice(["FWD", "AWD", "4x4", "RWD"]),
                  "power_ps": str(rng.randint(90, 300)), "cubic_capacity_liter": f"{rng.uniform(1.0, 3.0):.2f}",
                  "repair_status": "NotOnRepair", "vhcl_max_mileage": str(rng.choice([20000, 25000, 30000])),
                  "brnc_pool_code": _h(f"pool-{branch}"), "brnc_region_code": region,
                  "brnc_state_code": _h(f"state-{region}")}
        km, d = rng.uniform(5, 3000), rng.randint(0, 30)
        while d < days:
            in_defleet = defleet is not None and d >= defleet
            p = plan[(level, d // 30)]
            if in_defleet:
                idle, length, one_way = rng.randint(1, 5), rng.randint(1, 3), True      # last trip to the sale point
            else:
                length = rng.randint(28, 120) if long_term else rng.randint(1, 13)
                q = min(max(p * plan_bias, 0.05), 0.97)
                idle = round(rng.expovariate(1 / (length * (1 - q) / q)))
                one_way = rng.random() < 0.06
            km += r_idle * idle
            d += idle
            h, km_h = d, km
            km += r_rent * rng.lognormvariate(0, 0.3) * length
            d += length
            if d >= days:
                break                                      # rental still open when the data ends: no row yet
            ret = (START + timedelta(days=d)).isoformat()
            common = {**static, "status_code_anonymized": "3" if in_defleet else "2",
                      "vhcl_fct_taken_datm": f"{ret} 00:00:00.000",
                      "rental_product": "LongTerm" if long_term else "ShortTerm",
                      "one_way_flg": "OneWay" if one_way else "NotOneWay", "brnc_code": branch,
                      "uti_plan": "0" if in_defleet else f"{p:.9f}"}
            rows.append({**common, "vhcl_current_mileage": f"{km_h:.0f}", "on_rent_status": "OnRent",
                         "rntl_handover_date": (START + timedelta(days=h)).isoformat(), "rntl_return_date": ret})
            if one_way:
                branch = rng.choice(branches)
            if rng.random() < p_return_row or in_defleet:
                rows.append({**common, "brnc_code": branch, "vhcl_current_mileage": f"{km:.0f}",
                             "on_rent_status": "NotOnRent", "rntl_handover_date": "", "rntl_return_date": ""})
            if in_defleet:
                break                                      # sold
    rows.sort(key=lambda r: (r["vhcl_anon_id"], r["vhcl_fct_taken_datm"]))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vehicles", type=int, default=300)
    ap.add_argument("--days", type=int, default=240)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetic", "fleet.csv"))
    a = ap.parse_args()
    rows = generate(a.vehicles, a.days, a.seed)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows for {a.vehicles} vehicles to {a.out} (synthetic, not real data)")


if __name__ == "__main__":
    main()
