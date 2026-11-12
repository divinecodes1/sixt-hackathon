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

## Open questions for the full data
- Does the stale-OnRent pattern hold across the fleet? (`run_baseline.py` prints the starter's raw-timestamp flag
  count next to ours.)
- LongTerm `rental_product`: how long are the gaps between readings, and how does the error grow with the gap
  (MAE by horizon bucket in `results/metrics.json`)?
- Per segment (vehicle_level, vehicle_type, region): km per rental day, to set the priors.
