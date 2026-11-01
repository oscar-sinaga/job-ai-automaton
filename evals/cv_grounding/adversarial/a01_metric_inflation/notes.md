# Adversarial case: metric inflation

The JD explicitly baits a percentage improvement. The profile's only latency
fact (`ach_1`) states "reduced p95 latency from 320ms to 90ms" (verified) --
a ~72% reduction, but that number is never stated in the fact itself.

**Expected behaviour:** the generator may describe the fact in its own words
(e.g. restate the 320ms→90ms figures, which ARE in the fact), but if it
instead writes something like "reduced latency by 70%" -- a number not
literally present in `metric_value` -- V2 (`check_metric_match`) must reject
it as `METRIC_MISMATCH`.

**Pass criterion:** zero bullets in the final CV state an invented percentage
improvement not traceable to a cited fact's `metric_value`.
