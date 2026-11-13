# Archived synthetic experiments

The existing JSON/CSV/text files in this folder predate the stricter row-availability
fix made on hackathon day. They are historical method checks, not final performance
claims for the current code. The artificial fleet also shares the model's assumptions.

Current measured fleet evidence is `../metrics.json`. Reproduce the current synthetic
method check with `python synth_fleet.py` and an explicit `--out` directory, rather
than treating these archived numbers as the output of today's implementation.
