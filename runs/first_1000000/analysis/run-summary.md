# Run Summary

- Completed first `1000000` terms: true
- Largest computed index: `1000000`
- Largest computed value: `2713574`
- Total runtime: `389.298 s`
- Peak resident memory: `207.72 MiB`
- Prime sieve limit used: `8000000`
- Prime lookups: `7745583`
- Odd bitset witness queries: `1159221`
- Odd terms encountered: `[1, 25]`

## Correctness Checks

- Prefix check against `OEIS-A068638.md`: `True`
- First `100000` terms agree with baseline: `True`
- All accepted terms distinct: `True`
- All accepted terms beyond `a(1)` composite: `True`
- Rejected candidates with recorded witness rows: `1516008`

## Spot Checks

- `a(6) = 25` survived because `25 + 1 = 26`, `25 + 8 = 33`, `25 + 14 = 39`, `25 + 20 = 45`, and `25 + 24 = 49` are all composite.
- Final accepted term `a(1000000) = 2713574` is even, with `2713575` and `2713599` both composite.
- Largest least witness in the tested odd-composite range is `1056` at `m = 2282305` with witness count `73254`.

## Runtime Behavior

- Composite candidates tested: `2516007`
- Accepted candidates: `1000000`
- Rejected odd composites: `1159220`
- Rejected even composites: `356788`
- Checkpoint files written: `10`

## Conjecture-Focused Highlights

- No odd term larger than `25` was accepted: `True`
- Odd composite candidates above `25` tested: `1159217`
- Minimum / median / mean / maximum witness counts: `1` / `67457.0` / `68093.313` / `147115`
- Maximum least witness: `1056`
- Unique-witness odd composites: `5`
- Odd composites with at most 2 witnesses: `6`
- Odd composites with at most 5 witnesses: `25`
- Odd composites with at most 10 witnesses: `53`

## Milestones

| accepted terms | largest term | elapsed seconds | checkpoint | max least witness | count = 1 | count <= 2 | count <= 5 | count <= 10 | accepted-even density |
| ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 100000 | 288834 | 5.787937 | checkpoint_n0100000.json.gz | 712 | 5 | 6 | 25 | 53 | 0.692430 |
| 250000 | 702482 | 27.983245 | checkpoint_n0200000.json.gz | 712 | 5 | 6 | 25 | 53 | 0.711758 |
| 500000 | 1379592 | 102.538640 | checkpoint_n0500000.json.gz | 816 | 5 | 6 | 25 | 53 | 0.724850 |
| 750000 | 2048962 | 228.819145 | checkpoint_n0700000.json.gz | 816 | 5 | 6 | 25 | 53 | 0.732077 |
| 1000000 | 2713574 | 389.297707 | checkpoint_n1000000.json.gz | 1056 | 5 | 6 | 25 | 53 | 0.737034 |

## Even-Tail Density Snapshots

| bound | even composite candidates | accepted evens | accepted density | E-rule candidates | E-rule density |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 49 | 19 | 0.387755 | 19 | 0.387755 |
| 1000 | 499 | 249 | 0.498998 | 249 | 0.498998 |
| 10000 | 4999 | 2954 | 0.590918 | 2954 | 0.590918 |
| 2713574 | 1356786 | 999998 | 0.737034 | 999998 | 0.737034 |
