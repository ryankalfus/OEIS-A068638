# Run Summary

- Completed first `100000` terms: true
- Largest computed index: `100000`
- Largest computed value: `288834`
- Total runtime: `5.019 s`
- Peak resident memory: `195.47 MiB`
- Prime sieve limit used: `1000000`
- Prime lookups: `816245`
- Odd bitset witness queries: `119292`
- Odd terms encountered: `[1, 25]`

## Correctness Checks

- Prefix check against `OEIS-A068638.md`: `True`
- All accepted terms distinct: `True`
- All accepted terms beyond `a(1)` composite: `True`
- Rejected candidates with recorded witness rows: `163709`

## Spot Checks

- `a(6) = 25` survived because `25 + 1 = 26`, `25 + 8 = 33`, `25 + 14 = 39`, `25 + 20 = 45`, and `25 + 24 = 49` are all composite.
- Final accepted term `a(100000) = 288834` is even, with `288835` and `288859` both composite.
- Largest least witness in the tested odd-composite range is `712` at `m = 226591` with witness count `7838`.

## Runtime Behavior

- Composite candidates tested: `263708`
- Accepted candidates: `100000`
- Rejected odd composites: `119291`
- Rejected even composites: `44418`
- Checkpoint files written: `10`

## Conjecture-Focused Highlights

- No odd term larger than `25` was accepted: `True`
- Odd composite candidates above `25` tested: `119288`
- Minimum / median / mean / maximum witness counts: `1` / `7888.0` / `8037.017` / `17665`
- Maximum least witness: `712`
- Unique-witness odd composites: `5`
- Odd composites with at most 2 witnesses: `6`
- Odd composites with at most 5 witnesses: `25`
- Odd composites with at most 10 witnesses: `53`

## Even-Tail Density Snapshots

| bound | even composite candidates | accepted evens | accepted density | E-rule candidates | E-rule density |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 49 | 19 | 0.387755 | 19 | 0.387755 |
| 1000 | 499 | 249 | 0.498998 | 249 | 0.498998 |
| 10000 | 4999 | 2954 | 0.590918 | 2954 | 0.590918 |
| 288834 | 144416 | 99998 | 0.692430 | 99998 | 0.692430 |
