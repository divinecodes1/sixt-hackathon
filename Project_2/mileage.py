"""Mileage nowcast/forecast and erroneous-mileage flags. Python 3.11+, numpy + standard library only.

Data fact this module is built around (see EDA.md): a row with on_rent_status == "OnRent" carries a STALE odometer
value (the reading from before or at the rental's handover), stamped with a later timestamp. Read naively, the series
"goes down" whenever an OnRent row follows a return reading. We therefore time OnRent readings at their handover date
and treat them as "known by then", not as a measurement at vhcl_fct_taken_datm.

Pieces:
- load_rows / build_fleet: CSV -> per-vehicle observations (date, km), rental intervals, utilisation plan, attributes.
- Models (all share predict(vehicle, cutoff_day, target_day) -> km):
    NaiveLast      last known reading (no growth)
    MeanRate       last + vehicle's average km/day so far (the starter's baseline)
    RentAware      last + r_rent * rental days + r_idle * idle days. Rental days in the gap come from known rentals
                   (nowcast) or from the utilisation plan (forecast). r_rent, r_idle per vehicle, shrunk towards a
                   vehicle-level prior fitted on training data (empirical Bayes), so short histories still work.
- backtest: held-out period (global time cutoff) and, with enough vehicles, held-out vehicles.
- flags: rule flags (decrease, implausible rate, movement with no rental) + residual outliers vs RentAware.
"""
from __future__ import annotations

import csv
import hashlib
import math
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import numpy as np

MAX_KM_PER_DAY = 1500.0      # physically implausible above this (about 62 km/h for 24 h)
DECREASE_TOL_KM = 10.0       # odometer may be typed with small slips; below this we do not flag a decrease
IDLE_MOVE_KM = 300.0         # km gained over a stretch with no known rental
RESIDUAL_Z = 4.0             # robust z-score above which a residual is flagged
PRIOR_STRENGTH_DAYS = 30.0   # empirical-Bayes shrinkage: a vehicle with 30 observed days counts as much as the prior


# ================================================================================================ loading
def _day(s: str) -> int | None:
    s = (s or "").strip()
    if not s:
        return None
    return date.fromisoformat(s[:10]).toordinal()


def _float(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class Vehicle:
    vid: str
    obs_day: list[int] = field(default_factory=list)       # sorted measurement days
    obs_km: list[float] = field(default_factory=list)
    obs_src: list[str] = field(default_factory=list)       # "return" (not on rent) or "handover" (OnRent, stale)
    rentals: list[tuple[int, int]] = field(default_factory=list)   # (handover_day, return_day), merged
    uti: list[tuple[int, float]] = field(default_factory=list)     # (day, planned utilisation)
    level: str = "?"
    max_mileage: float | None = None

    def known_before(self, day: int) -> int:
        """Number of observations measured strictly before `day`."""
        return bisect_right(self.obs_day, day - 1)


def build_fleet(rows: list[dict]) -> dict[str, Vehicle]:
    raw: dict[str, list[tuple[int, float, str]]] = defaultdict(list)
    rent: dict[str, set[tuple[int, int]]] = defaultdict(set)
    fleet: dict[str, Vehicle] = {}
    for r in rows:
        vid = r.get("vhcl_anon_id", "")
        km = _float(r.get("vhcl_current_mileage"))
        taken = _day(r.get("vhcl_fct_taken_datm"))
        if not vid or km is None or taken is None:
            continue
        v = fleet.setdefault(vid, Vehicle(vid))
        v.level = r.get("vehicle_level") or v.level
        v.max_mileage = _float(r.get("vhcl_max_mileage")) or v.max_mileage
        u = _float(r.get("uti_plan"))
        if u is not None:
            v.uti.append((taken, u))
        h, ret = _day(r.get("rntl_handover_date")), _day(r.get("rntl_return_date"))
        on_rent = (r.get("on_rent_status") or "").strip() == "OnRent"
        if h is not None and ret is not None and ret >= h:
            rent[vid].add((h, ret))
        if on_rent and h is not None:
            raw[vid].append((min(h, taken), km, "handover"))   # stale reading: known at handover
        else:
            raw[vid].append((taken, km, "return"))
    for vid, v in fleet.items():
        seen = set()
        for d, km, src in sorted(raw[vid], key=lambda x: (x[0], x[1])):
            if (d, km) in seen:
                continue
            seen.add((d, km))
            v.obs_day.append(d)
            v.obs_km.append(km)
            v.obs_src.append(src)
        v.rentals = _merge(sorted(rent[vid]))
        v.uti.sort()
    return fleet


def _merge(iv: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def rental_days(v: Vehicle, start: int, end: int, known_by: int | None = None) -> float:
    """Days in (start, end] the vehicle was on rent, using only rentals handed over by `known_by`."""
    total = 0
    for a, b in v.rentals:
        if known_by is not None and a > known_by:
            break
        lo, hi = max(a, start + 1), min(b, end)
        if hi >= lo:
            total += hi - lo + 1
    return float(total)


def planned_utilisation(v: Vehicle, day: int, default: float) -> float:
    i = bisect_right([d for d, _ in v.uti], day) - 1
    return v.uti[i][1] if i >= 0 else default


# ================================================================================================ models
class NaiveLast:
    name = "naive_last"

    def fit(self, fleet: dict[str, Vehicle], train_ids: set[str], cutoff: int) -> "NaiveLast":
        return self

    def predict(self, v: Vehicle, cutoff: int, target: int, nowcast: bool = True) -> float | None:
        n = v.known_before(cutoff + 1)
        return v.obs_km[n - 1] if n else None


class MeanRate(NaiveLast):
    """The starter's baseline: previous reading + the vehicle's average daily rate so far."""
    name = "mean_rate"

    def predict(self, v: Vehicle, cutoff: int, target: int, nowcast: bool = True) -> float | None:
        n = v.known_before(cutoff + 1)
        if n == 0:
            return None
        last_d, last_km = v.obs_day[n - 1], v.obs_km[n - 1]
        span = last_d - v.obs_day[0]
        rate = (last_km - v.obs_km[0]) / span if n > 1 and span > 0 else 0.0
        return last_km + max(rate, 0.0) * (target - last_d)


def _intervals(v: Vehicle, upto: int) -> list[tuple[float, float, float]]:
    """(rental days, idle days, km) for consecutive observations measured up to `upto`."""
    n = v.known_before(upto + 1)
    out = []
    for i in range(1, n):
        d0, d1 = v.obs_day[i - 1], v.obs_day[i]
        dk = v.obs_km[i] - v.obs_km[i - 1]
        if d1 <= d0 or dk < 0 or dk / (d1 - d0) > MAX_KM_PER_DAY:
            continue                        # unusable or itself suspicious: keep it out of the rate estimate
        rd = rental_days(v, d0, d1)
        out.append((rd, (d1 - d0) - rd, dk))
    return out


def _fit_rates(ints: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """Non-negative least squares for km = r_rent * rent_days + r_idle * idle_days. Returns (r_rent, r_idle, days)."""
    if not ints:
        return 0.0, 0.0, 0.0
    a = np.array([[r, i] for r, i, _ in ints], dtype=float)
    y = np.array([k for _, _, k in ints], dtype=float)
    days = float(a.sum())
    if a[:, 0].sum() == 0:                  # never on rent in the history: one idle rate
        return 0.0, float(y.sum() / max(a[:, 1].sum(), 1.0)), days
    coef, *_ = np.linalg.lstsq(a, y, rcond=None)
    r_rent, r_idle = float(coef[0]), float(coef[1])
    if r_idle < 0 or r_rent < 0:            # refit with the negative one fixed at 0
        if r_idle < 0:
            r_rent, r_idle = float(y.sum() / max(a[:, 0].sum(), 1.0)), 0.0
        else:
            r_rent, r_idle = 0.0, float(y.sum() / max(a[:, 1].sum(), 1.0))
    return r_rent, r_idle, days


class RentAware(NaiveLast):
    """last + r_rent * rental days + r_idle * idle days, with vehicle rates shrunk towards a vehicle-level prior."""
    name = "rent_aware"

    def fit(self, fleet: dict[str, Vehicle], train_ids: set[str], cutoff: int) -> "RentAware":
        by_level: dict[str, list] = defaultdict(list)
        allints, util_num, util_den = [], 0.0, 0.0
        for vid in train_ids:
            v = fleet[vid]
            ints = _intervals(v, cutoff)
            by_level[v.level] += ints
            allints += ints
            for r, i, _ in ints:
                util_num, util_den = util_num + r, util_den + r + i
        self.fleet_prior = _fit_rates(allints)[:2]
        self.level_prior = {lv: _fit_rates(ints)[:2] if len(ints) >= 20 else self.fleet_prior
                            for lv, ints in by_level.items()}
        self.fleet_util = util_num / util_den if util_den else 0.5
        return self

    def rates(self, v: Vehicle, cutoff: int) -> tuple[float, float]:
        pr = self.level_prior.get(v.level, self.fleet_prior)
        r_rent, r_idle, days = _fit_rates(_intervals(v, cutoff))
        w = days / (days + PRIOR_STRENGTH_DAYS)
        return w * r_rent + (1 - w) * pr[0], w * r_idle + (1 - w) * pr[1]

    def predict(self, v: Vehicle, cutoff: int, target: int, nowcast: bool = True) -> float | None:
        n = v.known_before(cutoff + 1)
        if n == 0:
            return None
        last_d, last_km = v.obs_day[n - 1], v.obs_km[n - 1]
        r_rent, r_idle = self.rates(v, cutoff)
        gap = max(target - last_d, 0)
        if nowcast:   # rentals handed over by the target day are known (the car left the branch)
            rd = rental_days(v, last_d, target, known_by=target)
        else:         # forecast: only rentals known at the cutoff; the rest from the utilisation plan
            known = rental_days(v, last_d, min(target, cutoff), known_by=cutoff)
            rest = max(target - max(last_d, cutoff), 0)
            rd = known + rest * planned_utilisation(v, cutoff, self.fleet_util)
        rd = min(rd, gap)
        return last_km + r_rent * rd + r_idle * (gap - rd)


MODELS = (NaiveLast, MeanRate, RentAware)


# ================================================================================================ evaluation
def split_vehicles(fleet: dict[str, Vehicle], test_share: float = 0.2) -> tuple[set[str], set[str]]:
    """Held-out vehicles by hash. With fewer than 10 vehicles there is nothing to hold out: all are used for both."""
    ids = set(fleet)
    if len(ids) < 10:
        return ids, ids
    test = {v for v in ids if int(hashlib.sha256(v.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < test_share}
    return ids - test, test


def global_cutoff(fleet: dict[str, Vehicle], q: float = 0.8) -> int:
    days = sorted(d for v in fleet.values() for d in v.obs_day)
    return days[int(q * (len(days) - 1))]


HORIZONS = ((1, 7), (8, 14), (15, 30), (31, 60), (61, 10_000))


def _bucket(h: int) -> str:
    for lo, hi in HORIZONS:
        if lo <= h <= hi:
            return f"{lo}-{hi}d" if hi < 10_000 else f">{lo - 1}d"
    return "0d"


def backtest(fleet: dict[str, Vehicle], cutoff: int | None = None) -> dict:
    """Nowcast (rolling origin: predict each post-cutoff reading from everything measured before its day) and
    forecast (fixed origin at the cutoff: predict every later reading). Priors are fitted before the cutoff on the
    training vehicles only; errors are reported on the held-out vehicles (all vehicles if there are fewer than 10)."""
    cutoff = cutoff if cutoff is not None else global_cutoff(fleet)
    train, test = split_vehicles(fleet)
    models = [m().fit(fleet, train, cutoff) for m in MODELS]
    res: dict = {"cutoff": date.fromordinal(cutoff).isoformat(), "n_vehicles": len(fleet),
                 "n_train_vehicles": len(train), "n_test_vehicles": len(test), "nowcast": {}, "forecast": {}}
    for task in ("nowcast", "forecast"):
        rows = []
        for vid in sorted(test):
            v = fleet[vid]
            for j, (d, km) in enumerate(zip(v.obs_day, v.obs_km)):
                if d <= cutoff or v.obs_src[j] != "return":   # targets: real (fresh) readings after the cutoff
                    continue
                origin = d - 1 if task == "nowcast" else cutoff
                n = v.known_before(origin + 1)
                if n == 0:
                    continue
                last_km = v.obs_km[n - 1]
                preds = {m.name: m.predict(v, origin, d, nowcast=(task == "nowcast")) for m in models}
                rows.append((d - v.obs_day[n - 1], km, km - last_km, preds))
        res[task] = _metrics(rows, [m.name for m in models])
    return res


def _metrics(rows: list, names: list[str]) -> dict:
    out = {"n": len(rows), "models": {}}
    for name in names:
        groups: dict[str, list] = defaultdict(list)
        for gap, km, inc, p in rows:
            if p[name] is not None:
                groups["all"].append((p[name] - km, km, inc))
                groups[_bucket(gap)].append((p[name] - km, km, inc))
        out["models"][name] = {g: _summ(v) for g, v in sorted(groups.items())}
    return out


def _summ(v: list) -> dict:
    err = np.array([e for e, _, _ in v])
    km = np.array([k for _, k, _ in v])
    inc = np.array([i for _, _, i in v])
    return {"n": int(len(v)), "MAE_km": float(np.abs(err).mean()),
            "MAPE_odometer": float((np.abs(err) / np.maximum(km, 1)).mean()),
            "WAPE_distance": float(np.abs(err).sum() / max(np.abs(inc).sum(), 1.0))}


# ================================================================================================ flags
def _robust_z(x: np.ndarray) -> np.ndarray:
    med = np.median(x)
    mad = np.median(np.abs(x - med)) * 1.4826
    return (x - med) / mad if mad > 0 else np.zeros_like(x)


def flags(fleet: dict[str, Vehicle], model: RentAware | None = None) -> list[dict]:
    """One row per suspicious reading: vehicle, day, km, rule, detail, score. Residual flags use the model's nowcast
    from everything measured before that day, scaled by sqrt(gap) so long gaps are not flagged for being long."""
    model = model or RentAware().fit(fleet, set(fleet), max(d for v in fleet.values() for d in v.obs_day))
    out, resid = [], []
    for vid in sorted(fleet):
        v = fleet[vid]
        peak = -math.inf
        for j in range(len(v.obs_day)):
            d, km = v.obs_day[j], v.obs_km[j]
            row = {"vhcl_anon_id": vid, "date": date.fromordinal(d).isoformat(), "km": km, "source": v.obs_src[j]}
            if km < peak - DECREASE_TOL_KM:
                out.append({**row, "rule": "decrease", "detail": f"{peak - km:.0f} km below an earlier reading",
                            "score": float(peak - km)})
            peak = max(peak, km)
            if j == 0:
                continue
            d0, k0 = v.obs_day[j - 1], v.obs_km[j - 1]
            gap = max(d - d0, 1)
            if (km - k0) / gap > MAX_KM_PER_DAY:
                out.append({**row, "rule": "implausible_rate", "detail": f"{(km - k0) / gap:.0f} km/day",
                            "score": float((km - k0) / gap)})
            if km - k0 > IDLE_MOVE_KM and rental_days(v, d0, d) == 0:
                out.append({**row, "rule": "moved_without_rental",
                            "detail": f"+{km - k0:.0f} km with no known rental", "score": float(km - k0)})
            if v.obs_src[j] == "return":
                p = model.predict(v, d - 1, d, nowcast=True)
                if p is not None:
                    resid.append((row, (km - p) / math.sqrt(gap), km - p))
    if resid:
        z = _robust_z(np.array([s for _, s, _ in resid]))
        for (row, _, e), zi in zip(resid, z):
            if abs(zi) > RESIDUAL_Z:
                out.append({**row, "rule": "residual_outlier",
                            "detail": f"{e:+.0f} km vs nowcast (robust z {zi:+.1f})", "score": float(abs(zi))})
    return out


def naive_flags(rows: list[dict]) -> int:
    """The starter's flags on the raw rows (timestamp order): mileage going down or > 1000 km/day."""
    by: dict[str, list] = defaultdict(list)
    for i, r in enumerate(rows):
        km, d = _float(r.get("vhcl_current_mileage")), r.get("vhcl_fct_taken_datm", "")
        if km is not None and d:
            by[r["vhcl_anon_id"]].append((d, i, km))
    n = 0
    for xs in by.values():
        xs.sort()
        for (d0, _, k0), (d1, _, k1) in zip(xs, xs[1:]):
            days = (date.fromisoformat(d1[:10]) - date.fromisoformat(d0[:10])).days
            n += k1 < k0 or (days > 0 and (k1 - k0) / days > 1000)
    return n
