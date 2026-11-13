"""Mileage nowcast/forecast and erroneous-mileage flags. Python 3.11+, numpy + standard library only.

OnRent rows often carry stale handover mileage. We place those readings at handover,
but make the reading, rental metadata and changing vehicle attributes available only
from the row's recorded day. This avoids assuming an unprovided live handover feed.
The fleet sample contains planned returns later than the row timestamp, so a row
must not automatically be interpreted as a completed rental. See SUBMISSION.md for limits.

Pieces:
- load_rows / build_fleet: CSV -> per-vehicle observations (day, km), rental intervals, utilisation plan, segment
  (level, vehicle type, rental product as known at each date; region is kept for display only) and the first
  defleet day (status >= 3).
- Models (all share fit(fleet, train_ids, cutoff) and predict(vehicle, cutoff_day, target_day, nowcast) -> km):
    NaiveLast        last known reading (no growth)
    MeanRate         last + vehicle's average km/day so far (the starter's baseline)
    RentAware        last + r_rent * rental days + r_idle * idle days. Rental days in the gap come from known rentals
                     (nowcast) or from the utilisation plan, corrected by its historical bias (forecast). Vehicle rates
                     are shrunk towards a hierarchical prior (product > level > vehicle type, empirical Bayes).
    RentAwareRecent  RentAware with time-decayed vehicle rates (recent behaviour counts more).
    Blend            mean of MeanRate and RentAware.
- backtest: held-out period (time cutoff) and, with enough vehicles, held-out vehicles. Model choice per task and the
  conformal interval width are both decided on a validation cutoff BEFORE the test cutoff, on training vehicles only.
- flags: isolated outliers (one-off typos), decrease below the running maximum, implausible rate, movement without a
  rental, no movement while on rent (copied / under-reported reading), residual outliers vs RentAware. Outliers are removed before the other rules and the model see the series.
"""
from __future__ import annotations

import csv
import hashlib
import math
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

import numpy as np

MAX_KM_PER_DAY = 1500.0      # physically implausible above this (about 62 km/h for 24 h)
DECREASE_TOL_KM = 10.0       # odometer may be typed with small slips; below this we do not flag a decrease
IDLE_MOVE_KM = 300.0         # km gained over a stretch with no known rental
RESIDUAL_Z = 8.0             # robust z-score above which a residual is flagged ...
RESIDUAL_MIN_KM = 1000.0     # ... and only if the reading is also at least this far from the nowcast. Chosen with
                             # flag_benchmark.py on synthetic data (z 4 -> 8: recall 94.5% -> 93.7%, untouched flags
                             # 10.9 -> 2.1 per 1,000). Re-check on the real data.
STUCK_RENTAL_DAYS = 3        # a reading that has not moved although the car was on rent this many days is flagged
PRIOR_STRENGTH_DAYS = 30.0   # empirical-Bayes shrinkage: a vehicle with 30 observed days counts as much as the prior
PRIOR_MIN_INTERVALS = 20     # a segment prior needs at least this many training intervals, else use its parent
HALF_LIFE_DAYS = 60.0        # RentAwareRecent: weight of an interval halves every 60 days back from the cutoff
ALPHA = 0.1                  # prediction intervals: 90% target coverage
INTERVAL_BY_HORIZON = True   # calibrate the interval width per horizon bucket (gap since the last known reading);
                             # buckets longer than any validated one use the longest validated bucket's width
PLAN_WINDOW = 30             # utilisation plan calibration: window length (days) ...
PLAN_LOOKBACK = 120          # ... and how far back before the cutoff the window origins go


# ================================================================================================ loading
def _day(s: str | None) -> int | None:
    s = (s or "").strip()
    if not s:
        return None
    return date.fromisoformat(s[:10]).toordinal()


def _float(s: str | None) -> float | None:
    try:
        value = float(s)  # type: ignore[arg-type]
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def load_rows(path: str, max_vehicles: int | None = None) -> list[dict]:
    """Read CSV/Parquet; optionally select vehicles by stable SHA256 order.

    Organizer prediction/error columns are excluded, never used as features.
    """
    required = {'vhcl_anon_id', 'vhcl_fct_taken_datm', 'vhcl_current_mileage', 'on_rent_status'}
    if Path(path).suffix.lower() == '.parquet':
        import duckdb
        con = duckdb.connect()
        try:
            con.read_parquet(path).create_view('input_rows')
            columns = [r[0] for r in con.execute('DESCRIBE input_rows').fetchall()]
            if missing := required - set(columns):
                raise ValueError(f'Missing required columns: {sorted(missing)}')
            columns = [c for c in columns if not c.startswith('sixt_')]
            selected = ', '.join('"' + c.replace('"', '""') + '"' for c in columns)
            where = ''
            if max_vehicles is not None:
                if max_vehicles < 1:
                    raise ValueError('max_vehicles must be positive')
                where = (' WHERE vhcl_anon_id IN (SELECT DISTINCT vhcl_anon_id FROM input_rows '
                         f"ORDER BY sha256('development:' || vhcl_anon_id) LIMIT {int(max_vehicles)})")
            cur = con.execute(f'SELECT {selected} FROM input_rows{where} ORDER BY vhcl_anon_id, vhcl_fct_taken_datm, vhcl_current_mileage, on_rent_status, rntl_handover_date')
            rows = []
            while batch := cur.fetchmany(10000):
                rows.extend(dict(zip(columns, ('' if x is None else str(x) for x in row))) for row in batch)
            return rows
        finally:
            con.close()
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if missing := required - set(reader.fieldnames or []):
            raise ValueError(f'Missing required columns: {sorted(missing)}')
        rows = list(reader)
    if max_vehicles is not None:
        ids = sorted({r['vhcl_anon_id'] for r in rows}, key=lambda s: hashlib.sha256(('development:' + s).encode()).hexdigest())
        keep = set(ids[:max_vehicles])
        rows = [r for r in rows if r['vhcl_anon_id'] in keep]
    return rows


def load_fleet(path: str, max_vehicles: int | None = None) -> tuple[dict, int, int]:
    """Stream a Parquet fleet one vehicle at a time, keeping raw rows out of RAM."""
    if Path(path).suffix.lower() != '.parquet' or max_vehicles is not None:
        rows = load_rows(path, max_vehicles)
        return build_fleet(rows), len(rows), naive_flags(rows)
    import duckdb
    con = duckdb.connect()
    con.read_parquet(path).create_view('input_rows')
    columns = [r[0] for r in con.execute('DESCRIBE input_rows').fetchall() if not r[0].startswith('sixt_')]
    selected = ', '.join('"' + c.replace('"', '""') + '"' for c in columns)
    cur = con.execute(f'SELECT {selected} FROM input_rows ORDER BY vhcl_anon_id, vhcl_fct_taken_datm, vhcl_current_mileage, on_rent_status, rntl_handover_date')
    fleet, count, starter = {}, 0, 0
    group, previous = [], None
    while batch := cur.fetchmany(10000):
        for values in batch:
            row = dict(zip(columns, ('' if x is None else str(x) for x in values)))
            vid = row['vhcl_anon_id']
            if previous is not None and previous != vid:
                fleet.update(build_fleet(group))
                starter += naive_flags(group)
                group = []
            group.append(row)
            previous = vid
            count += 1
    if group:
        fleet.update(build_fleet(group))
        starter += naive_flags(group)
    con.close()
    return fleet, count, starter


@dataclass
class Vehicle:
    vid: str
    obs_day: list[int] = field(default_factory=list)       # sorted measurement days
    obs_km: list[float] = field(default_factory=list)
    obs_src: list[str] = field(default_factory=list)       # "return" (not on rent) or "handover" (OnRent, stale)
    obs_known: list[int] = field(default_factory=list)     # day each reading became available (row timestamp)
    rentals: list[tuple[int, int]] = field(default_factory=list)   # (handover_day, return_day), merged
    rental_records: list[tuple[int, int, int]] = field(default_factory=list)  # handover, return/plan, row-known day
    attributes: list[tuple[int, str, str, str, float | None]] = field(default_factory=list)
    latest_recorded_day: int | None = None
    uti: list[tuple[int, float]] = field(default_factory=list)     # (day, planned utilisation)
    level: str = "?"
    vtype: str = "?"
    product: str = "?"                                     # most frequent rental_product over all rows (display)
    products: list[tuple[int, str]] = field(default_factory=list)  # (known_day, rental_product), sorted
    region: str = "?"
    max_mileage: float | None = None
    defleet_day: int | None = None                         # first day with status_code >= 3 (defleet / sold)

    def known_before(self, day: int) -> int:
        """Number of observations measured strictly before `day` (call it on a view() to respect availability)."""
        return bisect_right(self.obs_day, day - 1)

    def view(self, day: int) -> "Vehicle":
        """The vehicle as seen on `day`: only readings whose row was written by then."""
        latest = self.latest_recorded_day if self.latest_recorded_day is not None else max(self.obs_known, default=0)
        if latest <= day:
            return self
        keep = [j for j, k in enumerate(self.obs_known) if k <= day]
        attrs = [a for a in self.attributes if a[0] <= day]
        level, vtype, region, limit = attrs[-1][1:] if attrs else ('?', '?', '?', None)
        return replace(self, obs_day=[self.obs_day[j] for j in keep], obs_km=[self.obs_km[j] for j in keep],
                       obs_src=[self.obs_src[j] for j in keep], obs_known=[self.obs_known[j] for j in keep],
                       rentals=_merge(sorted({(a, b) for a, b, k in self.rental_records if k <= day}))
                               if self.rental_records else self.rentals,
                       rental_records=[r for r in self.rental_records if r[2] <= day],
                       attributes=attrs, latest_recorded_day=day,
                       products=[p for p in self.products if p[0] <= day],
                       level=level if self.attributes else self.level,
                       vtype=vtype if self.attributes else self.vtype,
                       region=region if self.attributes else self.region,
                       max_mileage=limit if self.attributes else self.max_mileage)


def obs_day_of(row: dict) -> int | None:
    """The day a row's odometer value was measured: the handover for OnRent rows, else the status timestamp."""
    taken = _day(row.get("vhcl_fct_taken_datm"))
    h = _day(row.get("rntl_handover_date"))
    if taken is None:
        return None
    if (row.get("on_rent_status") or "").strip() == "OnRent" and h is not None:
        return min(h, taken)
    return taken


def build_fleet(rows: list[dict]) -> dict[str, Vehicle]:
    raw: dict[str, list[tuple[int, float, str, int]]] = defaultdict(list)
    rent: dict[str, set[tuple[int, int]]] = defaultdict(set)
    products: dict[str, Counter] = defaultdict(Counter)
    fleet: dict[str, Vehicle] = {}
    for r in rows:
        vid = r.get("vhcl_anon_id", "")
        km = _float(r.get("vhcl_current_mileage"))
        taken = _day(r.get("vhcl_fct_taken_datm"))
        if not vid or km is None or taken is None:
            continue
        v = fleet.setdefault(vid, Vehicle(vid))
        v.latest_recorded_day = max(v.latest_recorded_day or taken, taken)
        v.level = r.get("vehicle_level") or v.level
        v.vtype = r.get("vehicle_type") or v.vtype
        v.region = r.get("brnc_region_code") or v.region
        v.max_mileage = _float(r.get("vhcl_max_mileage")) or v.max_mileage
        v.attributes.append((taken, v.level, v.vtype, v.region, v.max_mileage))
        status = _float(r.get("status_code_anonymized"))
        if status is not None and status >= 3:
            v.defleet_day = taken if v.defleet_day is None else min(v.defleet_day, taken)
        u = _float(r.get("uti_plan"))
        if u is not None:
            v.uti.append((taken, u))
        h, ret = _day(r.get("rntl_handover_date")), _day(r.get("rntl_return_date"))
        if h is not None and ret is not None and ret >= h:
            rent[vid].add((h, ret))
            v.rental_records.append((h, ret, taken))
            if r.get("rental_product"):
                products[vid][r["rental_product"]] += 1
                v.products.append((taken, r["rental_product"]))
        on_rent = (r.get("on_rent_status") or "").strip() == "OnRent"
        raw[vid].append((obs_day_of(r), km, "handover" if on_rent and h is not None else "return", taken))  # type: ignore
    for vid, v in fleet.items():
        seen = set()
        for d, km, src, known in sorted(raw[vid], key=lambda x: (x[0], x[1], x[3], x[2] == 'handover')):
            if (d, km) in seen:          # same reading twice: keep the earliest-known copy
                continue
            seen.add((d, km))
            v.obs_day.append(d)
            v.obs_km.append(km)
            v.obs_src.append(src)
            v.obs_known.append(known)
        v.rentals = _merge(sorted(rent[vid]))
        v.uti.sort()
        v.attributes.sort(key=lambda a: a[0])
        v.rental_records = sorted(set(v.rental_records))
        v.products = sorted(set(v.products))
        if products[vid]:
            v.product = products[vid].most_common(1)[0][0]
    return fleet


def _merge(iv: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def product_at(v: Vehicle, day: int) -> str:
    """Most frequent rental product recorded by `day` ("?" if none): no look-ahead."""
    seen = Counter(p for h, p in v.products if h <= day)
    return seen.most_common(1)[0][0] if seen else "?"


def rental_days(v: Vehicle, start: int, end: int, known_by: int | None = None) -> float:
    """Rental-covered days in (start,end], optionally restricted to rows recorded by known_by.

    Without recorded availability metadata (manually constructed Vehicles), fall
    back to handover-based availability. Future return dates may be plans.
    """
    total = 0
    intervals = (_merge(sorted({(a, b) for a, b, k in v.rental_records if k <= known_by}))
                 if known_by is not None and v.rental_records else v.rentals)
    for a, b in intervals:
        if known_by is not None and a > known_by:
            break
        lo, hi = max(a, start + 1), min(b, end)
        if hi >= lo:
            total += hi - lo + 1
    return float(total)


def planned_utilisation(v: Vehicle, day: int, default: float | None) -> float | None:
    """The latest utilisation plan recorded on or before `day` (plans are only known once recorded)."""
    i = bisect_right([d for d, _ in v.uti], day) - 1
    return v.uti[i][1] if i >= 0 else default


# ================================================================================================ models
class NaiveLast:
    name = "naive_last"

    def fit(self, fleet: dict[str, Vehicle], train_ids: set[str], cutoff: int) -> "NaiveLast":
        return self

    def predict(self, v: Vehicle, cutoff: int, target: int, nowcast: bool = True) -> float | None:
        v = v.view(cutoff)
        n = v.known_before(cutoff + 1)
        return v.obs_km[n - 1] if n else None


class MeanRate(NaiveLast):
    """The starter's baseline: previous reading + the vehicle's average daily rate so far."""
    name = "mean_rate"

    def predict(self, v: Vehicle, cutoff: int, target: int, nowcast: bool = True) -> float | None:
        v = v.view(cutoff)
        n = v.known_before(cutoff + 1)
        if n == 0:
            return None
        last_d, last_km = v.obs_day[n - 1], v.obs_km[n - 1]
        span = last_d - v.obs_day[0]
        rate = (last_km - v.obs_km[0]) / span if n > 1 and span > 0 else 0.0
        return last_km + max(rate, 0.0) * (target - last_d)


Interval = tuple[float, float, float, int, int]   # (rental days, idle days, km, start day, end day)


def _intervals(v: Vehicle, upto: int) -> list[Interval]:
    """Consecutive observations known by `upto`, as (rental days, idle days, km, d0, d1)."""
    v = v.view(upto)
    n = v.known_before(upto + 1)
    out = []
    for i in range(1, n):
        d0, d1 = v.obs_day[i - 1], v.obs_day[i]
        dk = v.obs_km[i] - v.obs_km[i - 1]
        if d1 <= d0 or dk < 0 or dk / (d1 - d0) > MAX_KM_PER_DAY:
            continue                        # unusable or itself suspicious: keep it out of the rate estimate
        rd = rental_days(v, d0, d1)
        out.append((rd, (d1 - d0) - rd, dk, d0, d1))
    return out


def _fit_rates(ints: list[Interval], weights: list[float] | None = None) -> tuple[float, float, float]:
    """Non-negative (weighted) least squares for km = r_rent * rent_days + r_idle * idle_days.
    Returns (r_rent, r_idle, effective observed days)."""
    if not ints:
        return 0.0, 0.0, 0.0
    w = np.ones(len(ints)) if weights is None else np.asarray(weights, dtype=float)
    a = np.array([[r, i] for r, i, *_ in ints], dtype=float)
    y = np.array([k for _, _, k, *_ in ints], dtype=float)
    days = float((a.sum(axis=1) * w).sum())
    rent_days, idle_days = float((a[:, 0] * w).sum()), float((a[:, 1] * w).sum())
    if rent_days == 0:                      # never on rent in the history: one idle rate
        return 0.0, float((y * w).sum() / max(idle_days, 1.0)), days
    sw = np.sqrt(w)
    coef, *_ = np.linalg.lstsq(a * sw[:, None], y * sw, rcond=None)
    r_rent, r_idle = float(coef[0]), float(coef[1])
    if r_idle < 0 or r_rent < 0:            # refit with the negative one fixed at 0
        if r_idle < 0:
            r_rent, r_idle = float((y * w).sum() / max(rent_days, 1.0)), 0.0
        else:
            r_rent, r_idle = 0.0, float((y * w).sum() / max(idle_days, 1.0))
    return r_rent, r_idle, days


class RentAware(NaiveLast):
    """last + r_rent * rental days + r_idle * idle days, with vehicle rates shrunk towards a hierarchical prior."""
    name = "rent_aware"
    half_life: float | None = None

    @staticmethod
    def _keys(v: Vehicle, day: int) -> list[tuple]:
        """Prior keys from coarse to fine: fleet, rental product (as known on `day`), + vehicle level, + vehicle type."""
        p = product_at(v, day)
        return [(), (p,), (p, v.level), (p, v.level, v.vtype)]

    def fit(self, fleet: dict[str, Vehicle], train_ids: set[str], cutoff: int) -> "RentAware":
        groups: dict[tuple, list[Interval]] = defaultdict(list)
        util_num = util_den = 0.0
        for vid in sorted(train_ids):
            v = fleet[vid].view(cutoff)
            ints = _intervals(v, cutoff)
            for key in self._keys(v, cutoff):
                groups[key] += ints
            for r, i, *_ in ints:
                util_num, util_den = util_num + r, util_den + r + i
        self.prior = {k: _fit_rates(ints)[:2] for k, ints in groups.items()
                      if k == () or len(ints) >= PRIOR_MIN_INTERVALS}
        self.prior.setdefault((), (0.0, 0.0))
        self.fleet_prior = self.prior[()]
        self.fleet_util = util_num / util_den if util_den else 0.5
        self.util_ratio = 1.0
        # durations (inclusive days) of rentals completed by the cutoff, per rental product and overall
        self.durations: dict[str | None, list[int]] = defaultdict(list)
        for vid in sorted(train_ids):
            v = fleet[vid].view(cutoff)
            for a, b in v.rentals:
                if b <= cutoff:
                    self.durations[product_at(v, a)].append(b - a + 1)
                    self.durations[None].append(b - a + 1)
        # sorted durations + prefix sums: expected_on_rent in O(log n) instead of a scan of every rental per call
        self._dur = {}
        for k, ds in self.durations.items():
            ds = sorted(ds)
            pre = [0]
            for d in ds:
                pre.append(pre[-1] + d)
            self._dur[k] = (ds, pre)
        self.util_ratio = self._plan_ratio(fleet, train_ids, cutoff)
        return self

    def _plan_ratio(self, fleet: dict[str, Vehicle], train_ids: set[str], cutoff: int) -> float:
        """Bias of the utilisation plan, calibrated on the quantity the forecast predicts: rental days in
        PLAN_WINDOW-day windows that end by the cutoff (origins every 7 days), for training vehicles active over the
        window. ratio = sum(realised - expected running-rental days) / sum(plan * remaining days)."""
        num = den = 0.0
        for o in range(cutoff - PLAN_WINDOW, cutoff - PLAN_WINDOW - PLAN_LOOKBACK, -7):
            for vid in sorted(train_ids):
                full = fleet[vid]
                v = full.view(o)
                plan = planned_utilisation(v, o, None)
                if plan is None or not v.obs_day or v.obs_day[0] > o or \
                        (v.defleet_day is not None and v.defleet_day <= o + PLAN_WINDOW):
                    continue
                running = [a for a, b in v.rentals if a <= o < b]
                on = self.expected_on_rent(product_at(v, o), o - running[-1] + 1, PLAN_WINDOW) if running else 0.0
                num += rental_days(full, o, o + PLAN_WINDOW, known_by=o + PLAN_WINDOW) - on
                den += plan * (PLAN_WINDOW - on)
        return min(max(num / den, 0.5), 2.0) if den > 0 else 1.0

    def expected_on_rent(self, product: str, elapsed: int, horizon: int) -> float:
        """Expected days still on rent within the next `horizon` days, for a rental already running `elapsed` days:
        mean of min(duration - elapsed, horizon) over completed training rentals longer than `elapsed`."""
        key = product if len(self.durations.get(product, [])) >= 20 else None
        ds, pre = self._dur.get(key, ([], [0]))
        i = bisect_right(ds, elapsed)               # rentals longer than `elapsed`
        if i == len(ds):    # running longer than any rental we have seen: assume it continues
            return float(horizon)
        j = bisect_right(ds, elapsed + horizon)     # ... of which these end within the horizon
        total = (pre[j] - pre[i]) - elapsed * (j - i) + horizon * (len(ds) - j)
        return float(total / (len(ds) - i))

    def prior_for(self, v: Vehicle, day: int) -> tuple[float, float]:
        for key in reversed(self._keys(v, day)):
            if key in self.prior:
                return self.prior[key]
        return self.fleet_prior

    def rates(self, v: Vehicle, cutoff: int) -> tuple[float, float]:
        pr = self.prior_for(v, cutoff)
        ints = _intervals(v, cutoff)
        weights = None if self.half_life is None else [0.5 ** ((cutoff - d1) / self.half_life) for *_, d1 in ints]
        r_rent, r_idle, days = _fit_rates(ints, weights)
        w = days / (days + PRIOR_STRENGTH_DAYS)
        return w * r_rent + (1 - w) * pr[0], w * r_idle + (1 - w) * pr[1]

    def utilisation(self, v: Vehicle, cutoff: int) -> float:
        """Expected share of future days on rent, as known at the cutoff."""
        if v.defleet_day is not None and v.defleet_day <= cutoff:
            return 0.0                                  # in defleet: no new rentals planned
        plan = planned_utilisation(v, cutoff, None)
        return self.fleet_util if plan is None else min(plan * self.util_ratio, 1.0)

    def predict(self, v: Vehicle, cutoff: int, target: int, nowcast: bool = True) -> float | None:
        v = v.view(cutoff)
        n = v.known_before(cutoff + 1)
        if n == 0:
            return None
        last_d, last_km = v.obs_day[n - 1], v.obs_km[n - 1]
        r_rent, r_idle = self.rates(v, cutoff)
        gap = max(target - last_d, 0)
        if nowcast:   # only rental rows already recorded at the prediction origin
            rd = rental_days(v, last_d, target, known_by=cutoff)
            # After the latest recorded status, absence of a rental row does not
            # mean the car is idle. Fill only that unobserved suffix from the plan.
            latest_status = max(v.obs_known) if v.obs_known else cutoff
            unknown_start = max(last_d, latest_status)
            unobserved = max(0, target - unknown_start) - rental_days(v, unknown_start, target, known_by=cutoff)
            rd += max(0, unobserved) * self.utilisation(v, cutoff)
        else:         # forecast: rental days up to the cutoff are known; after it, the (bias-corrected) plan.
            # The actual return date of a rental still running at the cutoff is only written when it ends, so it is
            # not used (that would be leakage).
            # A car on rent at the cutoff is known to be out (operational status), so its expected remaining rental
            # days come from the duration distribution of completed rentals, given the days it has already run.
            known = rental_days(v, last_d, min(target, cutoff), known_by=cutoff)
            latest_status = max(v.obs_known) if v.obs_known else cutoff
            unknown_start = max(last_d, latest_status)
            unobserved = max(0, min(target, cutoff) - unknown_start) - rental_days(v, unknown_start, min(target, cutoff), known_by=cutoff)
            known += max(0, unobserved) * self.utilisation(v, cutoff)
            rest = max(target - max(last_d, cutoff), 0)
            running = [a for a, b in v.rentals if a <= cutoff < b]
            on = self.expected_on_rent(product_at(v, cutoff), cutoff - running[-1] + 1, rest) if running and rest \
                else 0.0
            rd = known + on + (rest - on) * self.utilisation(v, cutoff)
        rd = min(rd, gap)
        return last_km + r_rent * rd + r_idle * (gap - rd)


class RentAwareRecent(RentAware):
    """RentAware with time-decayed vehicle rates: an interval's weight halves every HALF_LIFE_DAYS before the cutoff."""
    name = "rent_aware_recent"
    half_life = HALF_LIFE_DAYS


class Blend(NaiveLast):
    """Mean of MeanRate and RentAware: two different error sources, so averaging usually helps."""
    name = "blend"

    def fit(self, fleet: dict[str, Vehicle], train_ids: set[str], cutoff: int) -> "Blend":
        self.parts = [MeanRate().fit(fleet, train_ids, cutoff), RentAware().fit(fleet, train_ids, cutoff)]
        return self

    def predict(self, v: Vehicle, cutoff: int, target: int, nowcast: bool = True) -> float | None:
        ps = [m.predict(v, cutoff, target, nowcast) for m in self.parts]
        return None if any(p is None for p in ps) else float(sum(ps) / len(ps))  # type: ignore[arg-type]


class RobustRate(NaiveLast):
    """Causal typo cleaning and winsorised calendar-day rate; no rental availability assumption.

    Clean only observations already available at the origin. A typo at the latest
    reading cannot be identified using a future neighbour. Rates are clipped at
    the vehicle's 10th/90th percentiles before exposure-weighted averaging.
    """
    name = 'robust_rate'

    def predict(self, v: Vehicle, cutoff: int, target: int, nowcast: bool = True) -> float | None:
        seen = v.view(cutoff)
        seen = without(seen, isolated_outliers(seen))
        n = seen.known_before(cutoff + 1)
        if not n:
            return None
        rates, days = [], []
        for i in range(1, n):
            gap = seen.obs_day[i] - seen.obs_day[i - 1]
            gain = seen.obs_km[i] - seen.obs_km[i - 1]
            if gap > 0 and 0 <= gain / gap <= MAX_KM_PER_DAY:
                rates.append(gain / gap)
                days.append(gap)
        rate = 0.0
        if rates:
            lo, hi = np.quantile(rates, [0.1, 0.9])
            rate = float(np.average(np.clip(rates, lo, hi), weights=days))
        return seen.obs_km[n - 1] + rate * max(0, target - seen.obs_day[n - 1])


MODELS = (NaiveLast, MeanRate, RentAware, RentAwareRecent, Blend, RobustRate)
MODEL_BY_NAME = {m.name: m for m in MODELS}


# ================================================================================================ evaluation
def split_vehicles(fleet: dict[str, Vehicle], test_share: float = 0.2) -> tuple[set[str], set[str]]:
    """Held-out vehicles by hash. With fewer than 10 vehicles there is nothing to hold out: all are used for both."""
    ids = set(fleet)
    if len(ids) < 10:
        return ids, ids
    test = {v for v in ids if int(hashlib.sha256(v.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < test_share}
    if not test or test == ids:
        ordered = sorted(ids, key=lambda s: hashlib.sha256(s.encode()).hexdigest())
        test = set(ordered[:max(1, round(len(ids) * test_share))])
    return ids - test, test


def global_cutoff(fleet: dict[str, Vehicle], q: float = 0.8) -> int:
    days = sorted(d for v in fleet.values() for d in v.obs_day)
    if not days:
        raise ValueError('No usable mileage readings were found in the input.')
    return days[int(q * (len(days) - 1))]


def validation_cutoff(fleet: dict[str, Vehicle], cutoff: int, q: float = 0.75) -> int:
    """A cutoff before the test cutoff, at the q-quantile of the reading days up to it."""
    days = sorted(d for v in fleet.values() for d in v.obs_day if d <= cutoff)
    if not days:
        raise ValueError('The cutoff is earlier than every available reading.')
    return min(days[int(q * (len(days) - 1))], cutoff - 1)


HORIZONS = ((1, 7), (8, 14), (15, 30), (31, 60), (61, 10_000))


def _bucket_order(name: str) -> int:
    """'all' first, then buckets by horizon."""
    labels = ["all"] + [f"{lo}-{hi}d" if hi < 10_000 else f">{lo - 1}d" for lo, hi in HORIZONS] + ["0d"]
    return labels.index(name) if name in labels else len(labels)


def _bucket(h: int) -> str:
    for lo, hi in HORIZONS:
        if lo <= h <= hi:
            return f"{lo}-{hi}d" if hi < 10_000 else f">{lo - 1}d"
    return "0d"


Row = tuple[int, float, float, dict]   # (gap days since the last known reading, actual km, km driven, predictions)


def predictions(fleet: dict[str, Vehicle], ids: set[str], cutoff: int, task: str, models: list,
                upto: int | None = None, target_after: int | None = None,
                segments: dict | None = None) -> list[Row]:
    """Targets: fresh return readings with cutoff < day <= upto. Nowcast origin = the day before each target
    (rolling); forecast origin = the cutoff (fixed)."""
    rows = []
    for vid in sorted(ids):
        v = fleet[vid]
        for j, (d, km) in enumerate(zip(v.obs_day, v.obs_km)):
            if d <= cutoff or (upto is not None and d > upto) or v.obs_src[j] != "return":
                continue
            if target_after is not None and d <= target_after:
                continue
            origin = d - 1 if task == "nowcast" else cutoff
            seen = v.view(origin)
            n = seen.known_before(origin + 1)
            if n == 0:
                continue
            preds = {m.name: m.predict(seen, origin, d, nowcast=(task == "nowcast")) for m in models}
            row = (d - seen.obs_day[n - 1], km, km - seen.obs_km[n - 1], preds)
            rows.append(row)
            if segments is not None:
                segments.setdefault('product:' + product_at(v, origin), []).append(row)
                if task == 'forecast':
                    segments.setdefault('lead_time:' + _bucket(d - origin), []).append(row)
    return rows


def _conformal_q(scores: list[float], alpha: float) -> float | None:
    """Split-conformal quantile: the ceil((n+1)(1-alpha))-th smallest score (None if too few scores)."""
    n = len(scores)
    k = math.ceil((n + 1) * (1 - alpha))
    return sorted(scores)[k - 1] if n and k <= n else None


def _scale(gap: int) -> float:
    return math.sqrt(max(gap, 1))


_BUCKETS = ["0d"] + [f"{lo}-{hi}d" if hi < 10_000 else f">{lo - 1}d" for lo, hi in HORIZONS]   # ascending


def interval_q(rows: list[Row], name: str, alpha: float = ALPHA) -> dict[str, float]:
    """Conformal widths (km per sqrt(day)) from calibration rows: overall ("all") and per horizon bucket (buckets with
    too few rows for the (1 - alpha) quantile are left out)."""
    scores: dict[str, list[float]] = defaultdict(list)
    for gap, km, _, p in rows:
        if p[name] is not None:
            sc = abs(p[name] - km) / _scale(gap)
            scores["all"].append(sc)
            scores[_bucket(gap)].append(sc)
    qs = {b: _conformal_q(v, alpha) for b, v in scores.items()}
    return {b: q for b, q in qs.items() if q is not None}


def q_for(qs: dict[str, float], gap: int) -> float | None:
    """Width for one prediction: its horizon bucket's; beyond the validated buckets, the longest validated bucket's,
    never narrower than the overall width; the overall width when INTERVAL_BY_HORIZON is off."""
    if not INTERVAL_BY_HORIZON or not qs:
        return qs.get("all")
    b = _bucket(gap)
    if b in qs:
        return qs[b]
    shorter = [qs[x] for x in _BUCKETS[:_BUCKETS.index(b)] if x in qs]
    cands = [x for x in (shorter[-1] if shorter else None, qs.get("all")) if x is not None]
    return max(cands) if cands else None


def backtest(fleet: dict[str, Vehicle], cutoff: int | None = None, alpha: float = ALPHA,
             evaluate_test: bool = True) -> dict:
    """Nowcast and forecast backtest. Leakage-free protocol:
    1. validation: models fitted at a validation cutoff on training vehicles, scored on their readings up to the test
       cutoff -> choose the model per task (lowest MAE) and calibrate the interval width (conformal, |error|/sqrt(gap));
    2. test: models fitted at the test cutoff on training vehicles, scored on held-out vehicles after it.
    With fewer than 10 vehicles the same vehicles are used for both (earlier vs later period)."""
    cutoff = cutoff if cutoff is not None else global_cutoff(fleet)
    train, test = split_vehicles(fleet)
    val_cut = validation_cutoff(fleet, cutoff)
    cal_cut = val_cut + (cutoff - val_cut) // 2
    val_models = [m().fit(fleet, train, val_cut) for m in MODELS]
    models = [m().fit(fleet, train, cutoff) for m in MODELS] if evaluate_test else []
    names = [m.name for m in val_models]
    res: dict = {"cutoff": date.fromordinal(cutoff).isoformat(),
                 "validation_cutoff": date.fromordinal(val_cut).isoformat(),
                 "calibration_start": date.fromordinal(cal_cut).isoformat(),
                 "n_vehicles": len(fleet), "n_train_vehicles": len(train), "n_test_vehicles": len(test),
                 "alpha": alpha, "selected": {}, "validation": {}, "nowcast": {}, "forecast": {}, "intervals": {}}
    for task in ("nowcast", "forecast"):
        val_rows = predictions(fleet, train, val_cut, task, val_models, upto=cal_cut)
        cal_rows = predictions(fleet, train, val_cut, task, val_models, upto=cutoff, target_after=cal_cut)
        val = _metrics(val_rows, names)
        res["validation"][task] = val
        scored = {n: g["all"]["MAE_km"] for n, g in val["models"].items() if "all" in g}
        res["selected"][task] = min(scored, key=scored.get) if scored else "rent_aware"  # type: ignore[arg-type]
        if not evaluate_test:
            continue
        segments = {}
        rows = predictions(fleet, test, cutoff, task, models, segments=segments)
        res[task] = _metrics(rows, names)
        res[task]['by_segment'] = {key: _metrics(xs, names) for key, xs in segments.items()}
        res[task]['calibration_targets'] = len(cal_rows)
        res["intervals"][task] = {}
        for name in names:
            res["intervals"][task][name] = _coverage(rows, name, interval_q(cal_rows, name, alpha))
    return res


def _coverage(rows: list[Row], name: str, qs: dict[str, float]) -> dict:
    out: dict = {"q_km_per_sqrt_day": qs.get("all"), "q_by_horizon": {b: qs[b] for b in _BUCKETS if b in qs}}
    groups: dict[str, list] = defaultdict(list)
    for gap, km, _, p in rows:
        q = q_for(qs, gap)
        if p[name] is not None and q is not None:
            hit = abs(p[name] - km) <= q * _scale(gap)
            groups["all"].append((hit, 2 * q * _scale(gap)))
            groups[_bucket(gap)].append((hit, 2 * q * _scale(gap)))
    for g, xs in sorted(groups.items(), key=lambda kv: _bucket_order(kv[0])):
        out[g] = {"n": len(xs), "coverage": sum(h for h, _ in xs) / len(xs), "mean_width_km": sum(w for _, w in xs) / len(xs)}
    return out


def _metrics(rows: list[Row], names: list[str]) -> dict:
    out: dict = {"n": len(rows), "models": {}}
    for name in names:
        groups: dict[str, list] = defaultdict(list)
        for gap, km, inc, p in rows:
            if p[name] is not None:
                groups["all"].append((p[name] - km, km, inc))
                groups[_bucket(gap)].append((p[name] - km, km, inc))
        out["models"][name] = {g: _summ(v) for g, v in sorted(groups.items(), key=lambda kv: _bucket_order(kv[0]))}
    naive = out["models"].get("naive_last", {})
    for name, groups in out["models"].items():          # skill vs the naive forecast on the same targets
        for g, s in groups.items():
            base = naive.get(g, {}).get("MAE_km")
            s["skill_vs_naive"] = 1 - s["MAE_km"] / base if base else None
    return out


def _summ(v: list) -> dict:
    err = np.array([e for e, _, _ in v])
    km = np.array([k for _, k, _ in v])
    inc = np.array([i for _, _, i in v])
    return {"n": int(len(v)), "MAE_km": float(np.abs(err).mean()), "bias_km": float(err.mean()),
            "zero_odometer_targets": int((km == 0).sum()),
            "MAPE_odometer": float((np.abs(err) / np.maximum(km, 1)).mean()),
            "WAPE_distance": float(np.abs(err).sum() / max(np.abs(inc).sum(), 1.0))}


def nowcast_table(fleet: dict[str, Vehicle], asof: int, model_name: str = "rent_aware", alpha: float = ALPHA,
                  target: int | None = None) -> list[dict]:
    """Today's estimate per vehicle: the product output. Model fitted on all vehicles with data up to `asof`; interval
    width calibrated on nowcasts of the 60 days before `asof`."""
    cls = MODEL_BY_NAME[model_name]
    target = asof if target is None else target
    if target < asof:
        raise ValueError('Forecast target cannot be before the as-of date')
    task = 'nowcast' if target == asof else 'forecast'
    ids = set(fleet)
    cal_cut = asof - 60
    cal = cls().fit(fleet, ids, cal_cut)
    qs = interval_q(predictions(fleet, ids, cal_cut, task, [cal], upto=asof), cal.name, alpha)
    m = cls().fit(fleet, ids, asof)
    out = []
    for vid in sorted(fleet):
        full = fleet[vid]
        v = full.view(asof)
        n = v.known_before(asof + 1)
        if n == 0:
            continue
        pred = m.predict(full, asof, target, nowcast=task == 'nowcast')
        gap = target - v.obs_day[n - 1]
        q = q_for(qs, gap)
        half = None if q is None or pred is None else q * _scale(gap)
        out.append({"vhcl_anon_id": vid, "asof": date.fromordinal(asof).isoformat(),
                    'target_date': date.fromordinal(target).isoformat(), 'model': model_name,
                    "last_reading_date": date.fromordinal(v.obs_day[n - 1]).isoformat(), "last_km": v.obs_km[n - 1],
                    "gap_days": gap, "rental_days_in_gap": rental_days(v, v.obs_day[n - 1], asof, known_by=asof),
                    "nowcast_km": round(pred, 0) if pred is not None else None,
                    "low_km": None if half is None else round(max(pred - half, v.obs_km[n - 1]), 0),
                    "high_km": None if half is None else round(pred + half, 0),
                    "in_defleet": full.defleet_day is not None and v.defleet_day <= asof})
        out[-1]['quality_status'] = ('insufficient_calibration' if half is None else
                                     'stale_over_30_days' if asof - v.obs_day[n - 1] > 30 else 'estimated')
        out[-1]['mileage_limit_alert'] = (v.max_mileage is not None and pred is not None and pred > v.max_mileage)
        if task == 'forecast':
            out[-1]['forecast_km'] = out[-1].pop('nowcast_km')
    return out


# ================================================================================================ flags
def _robust_z(x: np.ndarray) -> np.ndarray:
    med = np.median(x)
    mad = np.median(np.abs(x - med)) * 1.4826
    return (x - med) / mad if mad > 0 else np.zeros_like(x)


def isolated_outliers(v: Vehicle) -> dict[int, str]:
    """Readings that break an otherwise consistent series once: the neighbours agree with each other (next >= previous)
    but this reading is above the next one ("spike", e.g. an extra digit) or below the previous one ("dip", e.g. a
    missing digit). A rollback is different: every later reading stays low, so it is not isolated."""
    out = {}
    km = v.obs_km
    for j in range(1, len(km) - 1):
        kp, k, kn = km[j - 1], km[j], km[j + 1]
        if kn < kp - DECREASE_TOL_KM:
            continue
        if k > kn + DECREASE_TOL_KM:
            out[j] = "spike"
        elif k < kp - DECREASE_TOL_KM:
            out[j] = "dip"
    return out


def without(v: Vehicle, drop: set[int] | dict[int, str]) -> Vehicle:
    keep = [j for j in range(len(v.obs_day)) if j not in drop]
    return replace(v, obs_day=[v.obs_day[j] for j in keep], obs_km=[v.obs_km[j] for j in keep],
                   obs_src=[v.obs_src[j] for j in keep], obs_known=[v.obs_known[j] for j in keep])


MIN_Z_GROUP = 30   # residuals needed before a rental product gets its own robust z scale (else the pooled scale)


def flags(fleet: dict[str, Vehicle], model: RentAware | None = None) -> list[dict]:
    """One row per suspicious reading: vehicle, day, km, rule, detail, score. Isolated outliers are flagged first and
    removed; the other rules and the model then see the cleaned series, so one typo does not flag every later reading.
    Residual flags use the model's nowcast from everything measured before that day, scaled by sqrt(gap), and a robust
    z computed per rental product (long-term cars vary differently from short-term ones).

    score = the estimated km the reading is off by, for every rule, so one sorted list is a review queue:
    isolated_outlier |reading - mean of neighbours|; decrease km below the running maximum; implausible_rate km beyond
    MAX_KM_PER_DAY; moved_without_rental km gained; no_movement_on_rent km the model expected over the rental days;
    residual_outlier |reading - nowcast|. A decrease is flagged once per episode (when the series first drops below
    its maximum, or drops further), not on every later reading that is still below the old maximum."""
    outliers = {vid: isolated_outliers(v) for vid, v in fleet.items()}
    clean = {vid: without(v, outliers[vid]) for vid, v in fleet.items()}
    model = model or RentAware().fit(clean, set(clean), max(d for v in clean.values() for d in v.obs_day))
    out, resid = [], []
    for vid in sorted(fleet):
        v, cv = fleet[vid], clean[vid]
        for j, kind in sorted(outliers[vid].items()):
            kp, k, kn = v.obs_km[j - 1], v.obs_km[j], v.obs_km[j + 1]
            out.append({"vhcl_anon_id": vid, "date": date.fromordinal(v.obs_day[j]).isoformat(), "km": k,
                        "source": v.obs_src[j], "rule": "isolated_outlier",
                        "detail": f"{kind}: {k:.0f} km between {kp:.0f} and {kn:.0f}",
                        "score": float(abs(k - (kp + kn) / 2))})
        peak, low = -math.inf, None   # low: lowest reading of the current decrease episode (None: not in one)
        for j in range(len(cv.obs_day)):
            d, km = cv.obs_day[j], cv.obs_km[j]
            row = {"vhcl_anon_id": vid, "date": date.fromordinal(d).isoformat(), "km": km, "source": cv.obs_src[j]}
            if km < peak - DECREASE_TOL_KM:
                if low is None or km < low - DECREASE_TOL_KM:     # a new episode, or a further drop within one
                    out.append({**row, "rule": "decrease", "detail": f"{peak - km:.0f} km below an earlier reading",
                                "score": float(peak - km)})
                low = km if low is None else min(low, km)
            else:
                low = None
            peak = max(peak, km)
            if j == 0:
                continue
            d0, k0 = cv.obs_day[j - 1], cv.obs_km[j - 1]
            gap = max(d - d0, 1)
            if (km - k0) / gap > MAX_KM_PER_DAY:
                out.append({**row, "rule": "implausible_rate", "detail": f"{(km - k0) / gap:.0f} km/day",
                            "score": float(km - k0 - MAX_KM_PER_DAY * gap)})
            rd = rental_days(cv, d0, d)
            if km - k0 > IDLE_MOVE_KM and rd == 0:
                out.append({**row, "rule": "moved_without_rental",
                            "detail": f"+{km - k0:.0f} km with no known rental", "score": float(km - k0)})
            if cv.obs_src[j] == 'return' and abs(km - k0) <= DECREASE_TOL_KM and rd >= STUCK_RENTAL_DAYS:
                expected = model.rates(cv.view(d), d0)[0] * rd
                out.append({**row, "rule": "no_movement_on_rent",
                            "detail": f"{km - k0:+.0f} km over {rd:.0f} rental days (about {expected:.0f} expected)",
                            "score": float(expected)})
            if cv.obs_src[j] == "return":
                p = model.predict(cv, d - 1, d, nowcast=True)
                if p is not None:
                    resid.append((row, (km - p) / math.sqrt(gap), km - p, product_at(cv, d)))
    if resid:
        z = np.empty(len(resid))
        pooled = np.array([s for _, s, _, _ in resid])
        z_all = _robust_z(pooled)
        groups: dict[str, list[int]] = defaultdict(list)
        for i, (*_, prod) in enumerate(resid):
            groups[prod].append(i)
        for idx in groups.values():
            z[idx] = _robust_z(pooled[idx]) if len(idx) >= MIN_Z_GROUP else z_all[idx]
        for (row, _, e, _), zi in zip(resid, z):
            if abs(zi) > RESIDUAL_Z and abs(e) >= RESIDUAL_MIN_KM:
                out.append({**row, "rule": "residual_outlier",
                            "detail": f"{e:+.0f} km vs nowcast (robust z {zi:+.1f})", "score": float(abs(e))})
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
