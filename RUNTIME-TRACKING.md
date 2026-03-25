# Runtime Tracking Guide for Computing OEIS A068638

This file explains what information is most valuable to record while a program computes the first `100000` terms of OEIS `A068638`.

The point is not only to finish the computation, but also to preserve the evidence that is most useful for understanding and eventually proving the apparent structure of the sequence.

## Highest-Value Information to Track

If storage or implementation time is limited, prioritize these items first.

### 1. The odd composite witness data

For each odd composite integer `m > 25` that is tested, record:

- whether `m` is rejected
- at least one witness `e` already in the sequence with `m + e` prime
- the least such witness `w(m)`
- the total number of witnesses `|W(m)|`, if feasible

This is the single most useful dataset for the conjecture.

Reason:

- the conjecture says `25` is the largest odd term
- that is equivalent to saying every odd composite `m > 25` is blocked by at least one earlier witness
- the least witness and total witness count show which odd composites are genuinely difficult cases

### 2. Record-breakers for the least witness function

Track every time the least witness function sets a new record:

- `w(m) > max_{t < m} w(t)`

For each such record-breaking `m`, store:

- `m`
- `w(m)`
- all witnesses up to a reasonable cap, or the full list if practical
- nearby odd composites and their witness counts

These record-breakers are especially important because they identify the rare cases where the conjecture comes closest to failure.

### 3. The actual accepted term list with checkpoints

Track:

- index `n`
- value `a(n)`
- parity
- checkpoint snapshots every fixed number of terms

The accepted-term list is the core output and the foundation for every other analysis.

### 4. Why each candidate fails

For rejected candidates, store a compact reason:

- the first previous term that blocks the candidate
- the corresponding prime sum

This matters because it turns each rejection into auditable evidence instead of a black-box decision.

### 5. Even-tail admissibility data

For each accepted even term `e > 25`, record:

- whether `e+1` is composite
- whether `e+25` is composite

For each rejected even composite candidate, record whether failure comes from:

- `e+1` prime
- `e+25` prime
- some other issue, if any

This is important because the research notes suggest that once `25` is the last odd term, the even tail is governed by these two shifts.

## Best Runtime Metrics to Keep

These metrics help both engineering and mathematical analysis.

### Core progress metrics

Track at fixed intervals:

- current accepted index `n`
- current accepted value `a(n)`
- current candidate value being tested
- number of candidates tested since the last checkpoint
- wall-clock runtime
- average time per accepted term

### Candidate filtering metrics

Track counts of:

- composite candidates tested
- accepted candidates
- rejected candidates
- rejected odd composites
- rejected even composites

This helps show whether the search is behaving as expected and whether certain filters are doing most of the work.

### Prime-testing workload metrics

Track:

- number of primality checks
- cache hits if a prime/composite cache is used
- maximum value tested for primality

This is useful for identifying the main bottleneck.

## Mathematically Important Derived Objects

The run should explicitly maintain or be able to reconstruct the following.

### Witness set

For odd composite `m > 25`, define:

- `W(m) = { e in A_{<m} : m + e is prime }`

where `A_{<m}` is the set of earlier accepted terms less than `m`.

Useful fields:

- `m`
- `|W(m)|`
- `min W(m)`
- `max W(m)`
- a small sample of witnesses

### Even admissible set

Define the candidate even tail set:

- `E = { e >= 8 : e is even composite, e+1 composite, e+25 composite }`

Track:

- how often accepted even terms agree with this rule
- density of accepted even terms among even composites
- density of `E` in growing intervals

### Sparse exceptional set

Maintain a table of odd composites with unusually small witness count, for example:

- `|W(m)| <= 5`
- `|W(m)| <= 10`

These are the most likely places where a proof will need delicate finite checking.

## Recommended Checkpoint Contents

Each checkpoint should store enough information to resume and enough metadata to avoid losing the proof-relevant trail.

Recommended fields:

- current accepted index
- accepted term list so far, or a resumable representation
- current candidate cursor
- prime/composite cache state, if serialized
- summary statistics accumulated so far
- current record-holder for the least witness function
- the list of exceptional odd composites found so far

## Recommended Output Tables

The computation should produce or be able to export the following tables.

### Accepted terms table

Fields:

- `n`
- `a_n`
- `parity`
- `is_odd_term`

### Rejection witness table

Fields:

- `candidate`
- `candidate_parity`
- `blocking_term`
- `prime_sum`
- `blocking_term_index` if convenient

### Odd-composite witness summary table

Fields:

- `m`
- `w_m`
- `witness_count`
- `record_least_witness`
- `sample_witnesses`

### Even admissibility table

Fields:

- `e`
- `accepted`
- `e_plus_1_composite`
- `e_plus_25_composite`

## Residue-Class Information Worth Tracking

For odd composites and witness behavior, keep counts by residue classes modulo:

- `6`
- `10`
- `30`
- `210`

This can reveal whether the hardest cases cluster in a small number of congruence classes.

Good things to record:

- count of odd composites in each residue class
- count of witness-poor odd composites in each residue class
- least-witness record-holders by residue class

## Red Flags Worth Logging Immediately

If any of the following happen, log them prominently:

- an odd term larger than `25` is accepted
- an odd composite candidate appears to have no witness
- an accepted even term fails the expected `+1` and `+25` composite rule
- the least witness function jumps much more than expected
- runtime per accepted term starts growing sharply

These are the events most likely to matter mathematically or reveal a bug.

## Best Short Answer to "What should we keep track of?"

If reduced to a single sentence:

Keep the full accepted-term list, the least and total witness data for every odd composite above `25`, record-breakers of the least witness function, compact rejection witnesses, and checkpointed runtime statistics.
