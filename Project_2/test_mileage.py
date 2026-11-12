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

    def test_vehicle_holdout_used_when_enough_vehicles(self):
        res = M.backtest(M.build_fleet(synth_rows(n_vehicles=40)))
        self.assertGreater(res["n_test_vehicles"], 0)
        self.assertLess(res["n_test_vehicles"], res["n_vehicles"])


class Flags(unittest.TestCase):
    def test_injected_errors_are_flagged(self):
        rows = synth_rows(stale_onrent=False)
        returns = [r for r in rows if r["vhcl_anon_id"] == "V03"]
        returns[10]["vhcl_current_mileage"] = str(float(returns[10]["vhcl_current_mileage"]) - 2000)  # rollback
        returns[20]["vhcl_current_mileage"] = str(float(returns[20]["vhcl_current_mileage"]) + 90000)  # typo
        rules = {(f["vhcl_anon_id"], f["rule"]) for f in M.flags(M.build_fleet(rows))}
        self.assertIn(("V03", "decrease"), rules)
        self.assertIn(("V03", "implausible_rate"), rules)
        self.assertIn(("V03", "residual_outlier"), rules)

    def test_clean_fleet_has_few_flags(self):
        fleet = M.build_fleet(synth_rows())
        n = sum(len(v.obs_day) for v in fleet.values())
        self.assertLess(len(M.flags(fleet)), 0.02 * n)


if __name__ == "__main__":
    unittest.main()
