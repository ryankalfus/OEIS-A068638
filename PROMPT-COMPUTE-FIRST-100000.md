# Formal Prompt for Codex: Compute the First 100,000 Terms of OEIS A068638

## Objective

Compute the first `100000` terms of OEIS `A068638` directly from the defining greedy rule, without relying on previously published term lists.

The sequence is defined by:

- `a(1) = 1`
- for `n >= 2`, `a(n)` is the smallest new composite integer `m` such that `m + a(k)` is composite for every `1 <= k <= n`

Equivalently, after `a(1) = 1`, each new term is the least unused composite integer whose sum with every earlier term is composite.

## Required Reading

Before starting work, read these files in the repository:

- `CODEX.md`
- `LOG.md`
- `OEIS-A068638.md`
- `RESEARCH.md`
- `RUNTIME-TRACKING.md`
- `MATHEMATICAL-OUTPUTS.md`

## Primary Deliverables

Produce the following outputs from a fresh computation:

1. A plain text term file with one term per line and explicit indices.
2. A machine-readable table of the first `100000` terms.
3. Checkpoint files so a long run can resume safely.
4. A computation report that summarizes correctness checks, runtime behavior, and mathematically relevant patterns.
5. Supporting datasets focused on the conjecture that `25` is the largest odd term.

## Required Output Files

Create these files unless the repo already contains better-named equivalents:

- `data/a068638_first_100000.txt`
- `data/a068638_first_100000.csv`
- `data/checkpoints/`
- `analysis/run-summary.md`
- `analysis/odd-composite-witnesses.csv`
- `analysis/least-witness-records.csv`
- `analysis/even-admissible-statistics.csv`
- `analysis/residue-class-notes.md`
- `analysis/conjecture-evidence.md`

## Implementation Requirements

Implement the computation from the definition, not by downloading or copying existing terms.

Your program should:

1. Maintain the accepted term list in increasing order.
2. Test candidate composite integers in increasing order.
3. Reject a candidate immediately when some earlier term produces a prime sum.
4. Accept the first candidate that survives all required composite checks.
5. Continue until exactly `100000` terms have been generated.

The implementation should also:

- support restarting from checkpoints
- avoid recomputing primality information unnecessarily
- record enough metadata to audit difficult cases later
- keep correctness checks separate from performance optimizations

## Mathematical Data to Collect During the Run

For each accepted term, keep track of:

- its index `n`
- its value `a(n)`
- whether it is odd or even
- the smallest previous term tested last before acceptance, if useful for debugging

For each rejected candidate `m`, keep track of at least one blocking witness:

- a previous term `a(k)` such that `m + a(k)` is prime
- the prime value `m + a(k)`
- whether `m` is odd or even

For odd composite candidates `m > 25`, collect stronger data:

- the full witness count `|W(m)|`, where `W(m) = { e : e is an earlier term and m + e is prime }`
- the least witness `w(m) = min W(m)`
- whether the least witness sets a new record

For even accepted terms `e > 25`, record whether they satisfy the equivalent tail conditions:

- `e + 1` is composite
- `e + 25` is composite

## Conjecture-Focused Analysis

Use the run to gather evidence relevant to:

> Conjecture: `25` is the largest odd term of the sequence.

In particular, analyze:

1. Whether any odd term larger than `25` appears among the first `100000` terms.
2. For every odd composite candidate examined beyond `25`, the existence of a prime witness.
3. The least-witness function `w(m)` for odd composites `m > 25`.
4. Record values where `w(m)` exceeds all previous least witnesses.
5. The density of admissible even terms satisfying the `+1` and `+25` composite conditions.
6. Residue-class patterns of witnesses and failures modulo small moduli such as `6`, `30`, and `210`.

## Verification Requirements

Verify all of the following:

1. The initial terms match the sequence prefix in `OEIS-A068638.md`.
2. Every accepted term is composite.
3. Every accepted term is distinct.
4. Every sum of two terms required by the greedy rule is composite.
5. Every skipped candidate has a recorded prime witness or an equivalent rejection explanation.

Include explicit spot checks in the report for early terms and for unusual later cases.

## Efficiency Expectations

The task is large enough that a naive implementation may become too slow.

You should therefore:

- design the primality layer carefully
- use checkpointing
- measure time per accepted term or per candidate block
- report bottlenecks honestly
- prefer correctness first, then optimize the hot path

If the full `100000`-term target is not completed in one pass, leave the computation resumable and document the exact current progress.

## Final Report Expectations

In `analysis/run-summary.md`, summarize:

- whether the first `100000` terms were completed
- the largest computed index and value
- total runtime
- memory-related observations if available
- the odd terms encountered
- the strongest evidence relevant to the `25` conjecture
- the most informative rare or difficult cases

In `analysis/conjecture-evidence.md`, emphasize the mathematically useful outputs rather than only runtime facts.

## Working Style

Be formal, explicit, and reproducible.

Treat this as both a computation task and a research-support task. The output should help a later proof attempt, not merely confirm a long prefix.
