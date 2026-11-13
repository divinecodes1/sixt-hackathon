# Video narration

Voice: synthesized Microsoft Zira Desktop.

## Where is that car's odometer right now?

We are Divinecodes. Our project estimates current rental car mileage, forecasts future mileage, and flags suspicious reports.

## The key insight: two different clocks

The key insight is timing: an old handover value must not become available before its status row was recorded.

## Live walkthrough: estimate the current mileage

Our offline dashboard shows the last reading, current estimate, uncertainty range, and selectable future forecasts. All demo vehicles are synthetic.

## Measured results on held-out data

On held out fleet readings, current mileage error drops from five hundred sixty one to four hundred fifteen kilometres. Forecast error drops from seven thousand three hundred seventy six to two thousand seven hundred thirty four.

## The missing-mileage output is complete

We filled every missing mileage target. Vehicles without history receive clearly flagged cohort fallbacks, not false certainty.

## A reproducible project, ready for review

Thirty one tests pass. Next: expert flag review and a shadow mode pilot. Full details are in our submission.
