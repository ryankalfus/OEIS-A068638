# Conjecture Evidence

## Main Outcome

- Observed odd terms: `[1, 25]`
- Any odd term larger than `25`: `false`
- Exhaustively tested odd composite candidates in the run range: `119288`
- Every tested odd composite `m > 25` had a recorded prime witness: `true`

## Least-Witness Function

- Maximum least witness: `712` at `m = 226591`
- Number of least-witness record setters: `21`
- First five least-witness record rows: `[[27, 14, None, None, 3], [49, 24, 14, 10, 1], [91, 90, 24, 66, 1], [145, 94, 90, 4, 2], [235, 118, 94, 24, 3]]`

## Sparse Odd-Composite Cases

- Witness count `= 1`: `[49, 55, 85, 91, 115]`
- Witness count `<= 2`: `[49, 55, 85, 91, 115, 145]`
- Witness count `<= 5`: `25` cases
- Witness count `<= 10`: `53` cases

## Even Tail

- Accepted even terms beyond `25` agree with the `e+1` and `e+25` composite rule in every recorded case: `true`
- Final term `a(100000) = 288834` satisfies `e+1` and `e+25` composite checks.

## Interpretation

The 100000-term run supports the working picture from `RESEARCH.md`: after the early odd transient `{1, 25}`, every later odd composite is blocked by at least one accepted even witness, while the even tail is completely governed by the `+1` and `+25` composite conditions throughout the tested range.
