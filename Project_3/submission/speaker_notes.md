# Speaker notes: Judge the Judge (Team Divinecodes, Project 3)

Target: about 4 minutes, 5 slides (roughly 45 s each, the demo slide longer). Every number below is on the slides and comes
from the score.py reports in `results/` and `starter_pack/baseline_report.txt`.

## 1 · Problem (≈ 40 s)
- A customer asks: "Can I keep the car a few days longer?"
- Reply A gives the policy: usually possible, *as long as the car is not reserved for another customer*.
- Reply B drops that condition. It reads fine, but it commits SIXT to something the policy does not guarantee.
- The starting judge passes both. On dev it catches only 7% of dropped conditions. A release gate built on that judge
  lets these replies ship.

## 2 · Insight (≈ 40 s)
- A judge that reads one reply cannot see what is *missing*. You can't flag an absence you never look for.
- So we make the absence explicit: for each claim, call 1 lists the conditions the **policy** attaches and marks each one
  kept, dropped or not applicable. A dropped condition becomes a field, not a gap.
- Result: dropped-condition catch goes from 0.067 to 0.667.
- Everything else is generic: certainty 0–3 ("usually" vs "always"), scope, numbers checked in code. Nothing about the
  criterion is hard-coded.

## 3 · Architecture (≈ 50 s)
- Read the diagram left to right. The number rule is code, no LLM. `prepare()` turns it on only if it never fires on a
  pass example of the current criterion.
- Call 1 checks claim by claim. No violation: PASS in one call.
- If call 1 suspects a violation, call 2 verifies it in a fresh context. It must quote the reply's exact words (checked in
  code) and name a concrete case where a customer is misled. Proven: FAIL. Nothing proven: PASS.
- Call 3 is only a fallback when an answer is unreadable. At most three calls, one reply per call, no state, Haiku 4.5.
- The verdict is always computed in code, never taken from free text.

## 4 · Results (≈ 50 s)
- Criterion 1: combined 0.845 vs baseline 0.697. Catch 0.762 vs 0.592, keep 0.949 vs 0.847.
- The surprise criterion 2, same code: 0.883 vs 0.652.
- Two runs give the same verdict every time (repeat 1.000).
- Be honest about it: both call-2 changes were designed on dev errors, so dev gains are an upper bound. The 14:05 change
  costs some criterion-1 catch on dropped conditions.

## 5 · Live demo and use at SIXT (≈ 60 s)
- Open divinecodes-judge-the-judge.vercel.app (or point at the screenshot).
- Partner question: "usually" became "always". The original passes in one call, the edit fails after call 2 confirms it.
  Every call and reason is shown.
- At SIXT: run every chatbot version against the policy before release, block replies that drop a condition or
  raise certainty, and give the reviewer the quoted words and the policy clause.
- A new criterion needs only the criterion text and a few labelled examples.
- Next: win back dropped-condition catch on criterion 1 (0.800 before the 14:05 change, 0.667 now), and retrieve the
  closest examples per reply.

**Backup if the live site is slow:** the screenshot on slide 5 shows the same run (PASS then FAIL, case J1D-0001).
