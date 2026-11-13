"""Tests for mileage.py on synthetic data with known answers. Run: python -m unittest test_mileage -v"""
from __future__ import annotations

import random
import unittest
from datetime import date, timedelta

import mileage as M

START = date(2024, 1, 1)


def synth_rows(n_vehicles=12, days=200, km_rent=180.0, km_idle=5.0, seed=0, stale_onrent=True):
    """Each vehicle alternates rentals of 2-6 days and idle stretches of 1-4 days. A NotOnRent row at every return
    (true km). With stale_onrent, also an OnRent row at the return timestamp carrying the HANDOVER km, as in the data."""
    rng = random.Random(seed)
    rows = []
    for k in range(n_vehicles):
        vid, km, d = f"V{k:02d}", 1000.0 * k, 0
        while d < days:
            idle = rng.randint(1, 4)
            km += km_idle * idle
            d += idle
            h, length = d, rng.randint(2, 6)
            km_at_handover = km
            km += km_rent * (length + 1)            # rental days inclusive of handover and return day
            d += length
            base = {"vhcl_anon_id": vid, "vehicle_level": "Intermediate", "vhcl_max_mileage": "25000",
                    "uti_plan": "0.8", "repair_status": "NotOnRepair", "rental_product": "ShortTerm"}
            ts = (START + timedelta(days=d)).isoformat() + " 00:00:00.000"
            hd, rd = (START + timedelta(days=h)).isoformat(), (START + timedelta(days=d)).isoformat()
            rows.append({**base, "vhcl_fct_taken_datm": ts, "vhcl_current_mileage": f"{km:.0f}",
                         "on_rent_status": "NotOnRent", "rntl_handover_date": "", "rntl_return_date": ""})
            if stale_onrent:
                rows.append({**base, "vhcl_fct_taken_datm": ts, "vhcl_current_mileage": f"{km_at_handover:.0f}",
                             "on_rent_status": "OnRent", "rntl_handover_date": hd, "rntl_return_date": rd})
    return rows


class Data(unittest.TestCase):
    def test_stale_onrent_rows_do_not_look_like_decreases(self):
        rows = synth_rows()
        self.assertGreater(M.naive_flags(rows), 50)                      # raw timestamps: many false "decreases"
        fleet = M.build_fleet(rows)
        self.assertEqual([f for f in M.flags(fleet) if f["rule"] == "decrease"], [])

    def test_series_monotone_after_handover_timing(self):
        for v in M.build_fleet(synth_rows()).values():
            self.assertEqual(v.obs_km, sorted(v.obs_km))

    def test_rentals_merged_and_counted(self):
        v = M.Vehicle("x", rentals=M._merge([(1, 3), (3, 5), (8, 9)]))
        self.assertEqual(v.rentals, [(1, 5), (8, 9)])
        self.assertEqual(M.rental_days(v, 0, 10), 7.0)
        self.assertEqual(M.rental_days(v, 0, 10, known_by=5), 5.0)


class Models(unittest.TestCase):
    def test_rent_aware_recovers_rates_and_beats_baselines(self):
        fleet = M.build_fleet(synth_rows())
        m = M.RentAware().fit(fleet, set(fleet), 10**7)
        r_rent, r_idle = m.fleet_prior
        self.assertGreater(r_rent, 120)
        self.assertLess(r_idle, 60)
        res = M.backtest(fleet)
        now = res["nowcast"]["models"]
        self.assertLess(now["rent_aware"]["all"]["MAE_km"], now["mean_rate"]["all"]["MAE_km"])
        self.assertLess(now["mean_rate"]["all"]["MAE_km"], now["naive_last"]["all"]["MAE_km"])

    def test_no_leakage_after_cutoff(self):
        rows = synth_rows()
        fleet = M.build_fleet(rows)
        cutoff = M.global_cutoff(fleet)
        cut_iso = M.date.fromordinal(cutoff).isoformat()
        changed = [dict(r) for r in rows]
        for r in changed:   # rewrite everything first recorded after the cutoff
            if r["vhcl_fct_taken_datm"][:10] > cut_iso:
                r["vhcl_current_mileage"] = str(float(r["vhcl_current_mileage"]) * 3)
                r["uti_plan"] = "0.1"
        f2 = M.build_fleet(changed)
        for cls in M.MODELS:
            a = cls().fit(fleet, set(fleet), cutoff)
            b = cls().fit(f2, set(f2), cutoff)
            for vid in ("V01", "V07"):
                self.assertAlmostEqual(a.predict(fleet[vid], cutoff, cutoff + 30, nowcast=False),
                                       b.predict(f2[vid], cutoff, cutoff + 30, nowcast=False), places=6, msg=cls.name)

    def test_selection_and_intervals(self):
        res = M.backtest(M.build_fleet(synth_rows(n_vehicles=40)))
        self.assertLess(res["validation_cutoff"], res["cutoff"])
        self.assertIn(res["selected"]["nowcast"], M.MODEL_BY_NAME)
        cov = res["intervals"]["nowcast"]["rent_aware"]["all"]["coverage"]
        self.assertGreater(cov, 0.75)   # target 0.90; synthetic data is close to exchangeable

    def test_defleet_stops_planned_rentals(self):
        fleet = M.build_fleet(synth_rows())
        m = M.RentAware().fit(fleet, set(fleet), 10**7)
        v = fleet["V02"]
        self.assertGreater(m.utilisation(v, v.obs_day[-1]), 0)
        v.defleet_day = v.obs_day[-1]
        self.assertEqual(m.utilisation(v, v.obs_day[-1]), 0.0)

    def test_hierarchical_prior_falls_back(self):
        fleet = M.build_fleet(synth_rows())
        m = M.RentAware().fit(fleet, set(fleet), 10**7)
        v = M.Vehicle("new", product="ShortTerm", level="Unknown level")
        self.assertEqual(m.prior_for(v), m.prior[("ShortTerm",)])

    def test_vehicle_holdout_used_when_enough_vehicles(self):
        res = M.backtest(M.build_fleet(synth_rows(n_vehicles=40)))
        self.assertGreater(res["n_test_vehicles"], 0)
        self.assertLess(res["n_test_vehicles"], res["n_vehicles"])


def _flags_for(rows, vid):
    return [f for f in M.flags(M.build_fleet(rows)) if f["vhcl_anon_id"] == vid]


class Flags(unittest.TestCase):
    def test_one_off_typos_are_isolated_outliers_without_cascade(self):
        rows = synth_rows()
        v03 = [r for r in rows if r["vhcl_anon_id"] == "V03" and r["on_rent_status"] == "NotOnRent"]
        v03[10]["vhcl_current_mileage"] = str(float(v03[10]["vhcl_current_mileage"]) - 2000)   # one-off dip
        v03[20]["vhcl_current_mileage"] = str(float(v03[20]["vhcl_current_mileage"]) + 90000)  # extra-digit spike
        fl = _flags_for(rows, "V03")
        dates = {r["vhcl_fct_taken_datm"][:10] for r in (v03[10], v03[20])}
        self.assertEqual({f["date"] for f in fl if f["rule"] == "isolated_outlier"}, dates)
        self.assertLessEqual(len(fl), 3)   # before the fix, every reading after the spike was a "decrease"

    def test_persistent_rollback_is_a_decrease(self):
        rows = synth_rows()
        v03 = sorted((r for r in rows if r["vhcl_anon_id"] == "V03"), key=lambda r: r["vhcl_fct_taken_datm"])
        start = v03[20]["vhcl_fct_taken_datm"]
        for r in v03:
            if r["vhcl_fct_taken_datm"] >= start:      # every reading from here on is 5,000 km lower
                r["vhcl_current_mileage"] = str(float(r["vhcl_current_mileage"]) - 5000)
        rules = {f["rule"] for f in _flags_for(rows, "V03")}
        self.assertIn("decrease", rules)

    def test_implausible_jump_at_the_end_is_flagged(self):
        rows = synth_rows()
        last = max((r for r in rows if r["vhcl_anon_id"] == "V05" and r["on_rent_status"] == "NotOnRent"),
                   key=lambda r: r["vhcl_fct_taken_datm"])
        last["vhcl_current_mileage"] = str(float(last["vhcl_current_mileage"]) + 90000)
        rules = {f["rule"] for f in _flags_for(rows, "V05")}
        self.assertIn("implausible_rate", rules)
        self.assertIn("residual_outlier", rules)

    def test_clean_fleet_has_few_flags(self):
        fleet = M.build_fleet(synth_rows())
        n = sum(len(v.obs_day) for v in fleet.values())
        self.assertLess(len(M.flags(fleet)), 0.02 * n)


class FleetScale(unittest.TestCase):
    """The realistic synthetic fleet (synth_fleet.py) and the injected-error benchmark (flag_benchmark.py)."""

    @classmethod
    def setUpClass(cls):
        import synth_fleet
        cls.rows = synth_fleet.generate(n_vehicles=80, days=200, seed=3)

    def test_synthetic_fleet_has_no_false_decreases(self):
        fleet = M.build_fleet(self.rows)
        self.assertGreater(M.naive_flags(self.rows), 20)          # the stale-OnRent pattern is reproduced
        self.assertEqual([f for f in M.flags(fleet) if f["rule"] == "decrease"], [])

    def test_benchmark_recall_and_false_flags(self):
        import flag_benchmark
        r = flag_benchmark.run(self.rows, rate=0.05, seed=0)
        self.assertGreaterEqual(sum(r["caught"].values()) / sum(r["injected"].values()), 0.8)
        self.assertLess(r["flagged_untouched"] / r["untouched"], 0.01)

    def test_nowcast_table_interval_contains_estimate(self):
        fleet = M.build_fleet(self.rows)
        asof = max(d for v in fleet.values() for d in v.obs_day) - 10
        table = M.nowcast_table(fleet, asof)
        self.assertTrue(table)
        for t in table:
            if t["low_km"] is not None:
                self.assertLessEqual(t["low_km"], t["nowcast_km"])
                self.assertLessEqual(t["nowcast_km"], t["high_km"])
                self.assertGreaterEqual(t["low_km"], t["last_km"])


if __name__ == "__main__":
    unittest.main()
