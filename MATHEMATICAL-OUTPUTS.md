# Mathematical Outputs to Produce While Computing OEIS A068638

This file describes the most useful proof-oriented artifacts to generate alongside a computation of the first `100000` terms of OEIS `A068638`.

The central goal is not just to confirm many terms, but to extract structure that can support a later proof of the conjecture:

> `25` is the largest odd term of the sequence.

## Main Mathematical Principle

The research notes already identify the key reformulation.

Let

- `E = { e >= 8 : e is even composite, e+1 is composite, and e+25 is composite }`

Then the conjecture is equivalent to:

- for every odd composite `m > 25`, there exists `e in E` with `e < m` such that `m+e` is prime

So the best mathematical outputs are the ones that illuminate:

- the structure and density of `E`
- the witness sets `W(m)`
- the rare odd composites that have unusually few witnesses

## Most Important Files to Generate

If the computation creates many outputs, these are the most mathematically useful ones.

### 1. Full term list

Purpose:

- provides the actual computed sequence
- lets later work reproduce every downstream table

Recommended file:

- `data/a068638_first_100000.csv`

Recommended columns:

- `n`
- `a_n`
- `parity`
- `is_odd_term`

### 2. Odd composite witness table

Purpose:

- directly addresses the conjecture
- shows how every odd composite beyond `25` is blocked

Recommended file:

- `analysis/odd-composite-witnesses.csv`

Recommended columns:

- `m`
- `least_witness`
- `witness_count`
- `least_prime_sum`
- `record_least_witness`
- `sample_witnesses`

This is arguably the single best file to preserve.

### 3. Least-witness record table

Purpose:

- isolates the hardest odd composites
- sharply reduces the finite cases worth human attention

Recommended file:

- `analysis/least-witness-records.csv`

Recommended columns:

- `m`
- `least_witness`
- `previous_record`
- `new_record_gap`
- `witness_count`

### 4. Even admissible statistics table

Purpose:

- tests the conjectural even-tail rule
- measures how accurately the set `E` predicts the computed tail

Recommended file:

- `analysis/even-admissible-statistics.csv`

Recommended columns:

- `e`
- `accepted`
- `e_plus_1_composite`
- `e_plus_25_composite`
- `matches_E_rule`

### 5. Exceptional odd composite table

Purpose:

- identifies the sparse cases most likely to matter in a proof

Recommended file:

- `analysis/exceptional-odd-composites.csv`

Suggested inclusion rule:

- include all odd composites `m > 25` with `witness_count <= 10`

Recommended columns:

- `m`
- `least_witness`
- `witness_count`
- `all_witnesses` if feasible
- `nearby_exception_count`

## Mathematical Summaries Worth Writing in Markdown

CSV tables are useful, but short human-readable summaries are also important.

### Conjecture evidence note

Recommended file:

- `analysis/conjecture-evidence.md`

Include:

- the odd terms actually observed
- whether any odd term larger than `25` appeared
- the maximum least witness observed
- how many odd composites had only `1`, `2`, `3`, or at most `10` witnesses
- whether the difficult cases become rarer with size

### Residue-class note

Recommended file:

- `analysis/residue-class-notes.md`

Include:

- witness-poor odd composites by residue mod `6`
- witness-poor odd composites by residue mod `30`
- witness-poor odd composites by residue mod `210`
- any residue classes that appear overrepresented among hard cases

### Finite-cover experiment note

Recommended file:

- `analysis/finite-cover-experiments.md`

Include experiments such as:

- does a fixed finite subset `F subset E` cover every odd composite up to the search bound
- how small can such a set `F` be
- which witnesses appear most frequently as least witnesses

This is valuable because a successful finite-cover pattern would be a strong clue toward a proof strategy.

## Derived Quantities to Compute

The following derived quantities are especially worth computing.

### 1. The least witness function

Define:

- `w(m) = min { e in E : e < m and m+e is prime }`

Why it matters:

- it measures how far one must look into the even admissible set before finding a blocking prime
- large values of `w(m)` indicate difficult odd composites

Important statistics:

- maximum of `w(m)` in growing ranges
- average of `w(m)` in growing ranges
- histogram of `w(m)` bucketed into ranges

### 2. The witness count function

Define:

- `c(m) = |W(m)|`

Why it matters:

- low values of `c(m)` identify sparse exceptional cases
- high values indicate that the conjecture is locally robust

Important statistics:

- minimum of `c(m)` in growing ranges
- median and mean values in growing ranges
- count of `m` with `c(m) <= 1`, `<= 2`, `<= 5`, `<= 10`

### 3. Density of the even tail

For growing bounds `X`, estimate:

- density of accepted even terms up to `X`
- density of `E` among even composites up to `X`

Why it matters:

- if the conjectural even-tail rule is right, these densities should align closely
- density growth supports the idea that the even side of the sequence is structurally simple after the odd transient

### 4. Frequency of individual witnesses

Track how often each witness `e` is:

- a witness at all
- the least witness

Why it matters:

- certain small witnesses may dominate the blocking mechanism
- that could suggest finite-cover or residue-based arguments

## Best Small-Case Artifacts to Save

Large tables are useful, but some compact finite artifacts are disproportionately valuable.

### Unique-witness cases

Save every odd composite with exactly one witness.

Why:

- these are the closest things to counterexamples
- they deserve manual mathematical inspection

### Near-record windows

For each record-holder of the least witness function, save a local window around it, for example:

- all odd composites in `[m-100, m+100]`
- their witness counts
- their least witnesses

Why:

- hard cases may come in local clusters
- local patterns sometimes reveal congruence obstructions

### First deviations, if any

If any of the following ever happen, save a dedicated note immediately:

- an odd term larger than `25` is accepted
- an odd composite has no witness
- an accepted even term fails the `E` rule

These would be mathematically decisive events.

## Best Interpretation of the Large Run

A `100000`-term computation is most useful if it answers questions like:

- how rare are the genuinely hard odd composites
- how quickly does the even tail settle into the `E` description
- does the least witness function grow very slowly
- do a few small witnesses explain most rejections
- do difficult cases concentrate in a few congruence classes

If the outputs are designed around those questions, the run becomes a research instrument rather than a brute-force checklist.
