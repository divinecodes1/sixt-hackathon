"""Stability check: backtest on several independently generated synthetic fleets (synth_fleet.py).

    python synth_eval.py [--seeds 5] [--vehicles 300] [--out results/synthetic/seeds.json]
Prints mean ± sd of MAE per model and task, which model the validation step chose, and the interval coverage of the
chosen model. Synthetic data only: it shows the method is stable and leakage-free, not how it does on SIXT's fleet.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import mileage as M
import synth_fleet

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--vehicles", type=int, default=300)
    ap.add_argument("--out", default=str(HERE / "results" / "synthetic" / "seeds.json"))
    a = ap.parse_args()
    names = [m.name for m in M.MODELS]
    out: dict = {"seeds": list(range(1, a.seeds + 1)), "vehicles": a.vehicles, "tasks": {}}
    runs = [M.backtest(M.build_fleet(synth_fleet.generate(a.vehicles, 240, s))) for s in out["seeds"]]
    for task in ("nowcast", "forecast"):
        mae = {n: [r[task]["models"][n]["all"]["MAE_km"] for r in runs] for n in names}
        sel = [r["selected"][task] for r in runs]
        mae["chosen_on_validation"] = [r[task]["models"][s]["all"]["MAE_km"] for r, s in zip(runs, sel)]
        cov = [r["intervals"][task][s]["all"]["coverage"] for r, s in zip(runs, sel)]
        out["tasks"][task] = {"MAE_km": {n: {"mean": float(np.mean(v)), "sd": float(np.std(v))} for n, v in mae.items()},
                              "chosen": sel, "coverage_of_chosen": cov}
        print(f"{task.upper()}  MAE km over {a.seeds} synthetic fleets of {a.vehicles} vehicles")
        for n, v in mae.items():
            print(f"  {n:<22} {np.mean(v):>7.0f} ± {np.std(v):.0f}")
        print(f"  chosen: {sel}; 90% interval coverage of the chosen model: {[round(c, 2) for c in cov]}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
