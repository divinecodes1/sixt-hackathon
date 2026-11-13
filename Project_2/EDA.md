# EDA: what the mileage data really says

Data so far: `example_file.csv`, 57 rows, 1 vehicle (Intermediate, Off Road, 4x4, model year 2024), 20 Mar to
30 Aug 2024. The full data arrives on the day; rerun `python run_baseline.py` on it and update the numbers here.

## Finding 1: OnRent rows carry a stale odometer value
Rows come as status snapshots. On the day a rental ends, there are usually **two** rows:

| vhcl_fct_taken_datm | on_rent_status | rental (handover → return) | vhcl_current_mileage |
|---|---|---|---|
| 2024-04-13 | NotOnRent | – | **1351** (the real reading at return) |
| 2024-04-13 | OnRent | 2024-04-03 → 2024-04-13 | **1025** (= the reading at the 29 Mar return, before this rental) |

- In all **15 of 15** same-day OnRent/NotOnRent pairs, the OnRent row has the lower mileage.
- Read by timestamp (as `starter.py` does), the series "goes down" **12 times** in 57 rows. The starter's rule flags
  all 12, and every one of them is an artifact.
- If OnRent readings are timed at their **handover date** instead, the false decreases drop from 12 to 1. The
  remaining same-day tie is resolved by ordering by km.

Consequences:
- **For flagging:** "mileage decreased" is only meaningful after this correction. Otherwise the error detector mostly
  detects the data model.
- **For nowcasting:** a reading recorded during or at the end of a rental is *not* new information. The latest true
  reading is the last return (NotOnRent) reading. This is exactly the business problem: long rentals hide the odometer.

## Finding 1b: a handover reading becomes known only when its rental ends
The OnRent row that carries the handover odometer is written at the rental's **return** (`vhcl_fct_taken_datm`), so
the reading is *measured* at the handover but *known* only at the return. In the example the lag is 3 days median and
13 days at most (41 OnRent rows). Of 45 distinct readings, 29 are such handover readings and only 16 are fresh return
readings (16 NotOnRent rows for 38 rentals). For a long-term rental the lag is the whole rental: this is the blind spot
the project is about.

Consequence: `mileage.py` keeps both days for every reading (`obs_day` measured, `obs_known` written) and every model,
backtest and nowcast only sees readings known by its origin date. An earlier version of our backtest ignored this and
let models see handover readings before their row existed; fixing it moved the example's naive nowcast MAE from 269 to
419 km on 5 targets (`results/metrics.json`). `test_mileage.py::test_no_leakage_after_cutoff` guards it: rewriting
every row written after the cutoff must not change any prediction made at the cutoff. What *is* known at once is that
a car is on rent (the handover happens at the counter), so nowcasts use the current rental status, as the README asks.

## Finding 2: rental days drive the mileage
Over the example's 5 months the car gains about 11,500 km, almost all of it while on rent (ShortTerm rentals of 1–13
days). This motivates the `rent_aware` model: km = r_rent × rental days + r_idle × idle days. The rental days in a
gap are known for nowcasting (the handover is recorded when the car leaves) and come from `uti_plan` for
forecasting.

## Finding 3: other fields
- `status_code_anonymized` goes from 2 (active) to 3 (defleet) on 25 Aug; `uti_plan` drops to 0 at the same time.
  A forecast should use the plan, which then expects no further mileage.
- `vhcl_max_mileage` changes from 25000 to 24000 in June: it is a contract or plan limit, not a reading.
- `repair_status` = OnRepair appears once (24 Jun), with no mileage jump.
- Branch codes change with one-way rentals (`one_way_flg` = OneWay).

## Finding 4: evaluating at return readings favours on-rent days
Fresh readings only exist at returns, so every backtest target is a day on which a rental just ended. A forecast for
an arbitrary day should expect fewer rental days than the days just before a return actually had. On the synthetic
fleet, the utilisation plan is nearly unbiased on fixed 30-day windows (calibration ratio 1.03), yet forecasts at
return readings under-predict (bias −1,212 km for `rent_aware`, `results/synthetic/run_baseline.txt`). We keep the
calibration that is right for the business question ("mileage on day X") and report the bias instead of tuning the
model to the evaluation's quirk. Model choice per task happens on a validation period, so whichever model handles this
best on the data at hand is picked.

## Open questions for the full data
- Does the stale-OnRent pattern hold across the fleet? (`run_baseline.py` prints the starter's raw-timestamp flag
  count next to ours.)
- LongTerm `rental_product`: how long are the gaps between readings, and how does the error grow with the gap
  (MAE by horizon bucket in `results/metrics.json`)?
- Per segment (vehicle_level, vehicle_type, rental product): km per rental day. The priors are now hierarchical
  (product > level > type, each used once it has 20+ training intervals); check which levels the real data fills.
- How often does a reading not move although the car was on rent (`no_movement_on_rent`)? On real monthly
  self-reporting this may be common and a sign of copied values.
- Rerun `python flag_benchmark.py` on the real data: thresholds were chosen on synthetic data.
