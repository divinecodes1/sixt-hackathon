# Surprise task

A new criterion for the same replies and the same policy. Run your recipe on it **unchanged**: only the inputs change
(this criterion and these examples), not your code.

| File | What |
|---|---|
| `CRITERION.md` | The new criterion. Pass it to your judge exactly as you passed `JUDGE1_CRITERION.md`. |
| `dev_pairs.jsonl` | 73 labelled example pairs, same format as the starter pack's `dev_pairs.jsonl`. |

These files are in `Project_3/starter_pack/surprise/`. Pull them into your fork, then from `Project_3/starter_pack/`:

```bash
git pull https://github.com/sixt-hackathon-2026/sixt-hackathon-2026.git main
```


```bash
python3 run_judge.py --judge final_judge.py --pairs surprise/dev_pairs.jsonl --criterion surprise/CRITERION.md \
    --policy policy.md --dev surprise/dev_pairs.jsonl --out surprise_dev.csv
python3 score.py surprise_dev.csv surprise/dev_pairs.jsonl
```

(Scoring a judge on the same examples it was given with `--dev` flatters it: hold some back if you want an honest number.)

At 16:00 you get the test cases for both criteria, with instructions. Code freeze stays at 16:00.
