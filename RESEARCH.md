# Research Report on OEIS A068638

Research date: 2026-03-25

## Executive Summary

OEIS A068638 is the greedy sequence

- `a(1) = 1`
- for `n >= 2`, `a(n)` is the smallest new composite number such that `a(n) + a(k)` is composite for every earlier term `a(k)`.

The current OEIS entry still includes the comment:

> Conjecture: 25 is the largest odd term of this sequence.

The most important useful reduction is this:

- Let `E` be the set of even composite integers `e >= 8` such that both `e+1` and `e+25` are composite.
- Then `25` is the largest odd term of A068638 if and only if every odd composite `m > 25` has at least one witness `e in E` with `e < m` and `m+e` prime.

So the conjecture can be reformulated as a prime-existence problem in the translates `m + E`.

I did not find any published proof or disproof of the `25` conjecture. The strongest directly relevant published material I found is broader:

- Yong-Gao Chen (2008): maximum-cardinality prime-sumset-free subsets of `[1,n]` are exactly parity classes.
- Ram Krishna Pandey (2012): lower-order extremal prime-sumset-free subsets eventually disappear for each fixed size.

Those papers are relevant context, but neither one resolves the greedy sequence A068638 itself.

## Current OEIS State

### A068638

Current OEIS description:

- `a(1) = 1`
- `a(n)` is the smallest distinct composite number such that `a(n) + a(k)` is composite for all `k = 1..n`.

Current OEIS facts I verified:

- The OEIS text entry revision is `#17`, dated `Dec 15 2022`.
- The entry explicitly says "Conjecture: 25 is the largest odd term of this sequence."
- OEIS links a current b-file with `10000` listed terms.
- That b-file ends at `a(10000) = 31654`.
- The only odd values in the b-file are `(n,a(n)) = (1,1)` and `(6,25)`.

### A025044

OEIS A025044 is:

- `0, 1, 8, 14, 20, 24, 25, 26, ...`
- description: `a(n) not of form prime - a(k), k < n`

This is essentially the same greedy process with an initial `0`. Therefore:

- `A068638(n) = A025044(n+1)` for `n >= 1`.

This reformulation is useful because the presence of `0` makes all primes automatically impossible, since `0 + p = p` would be prime.

## Direct Structural Facts

### Initial terms

The beginning is:

`1, 8, 14, 20, 24, 25, 26, 32, 38, 44, ...`

Why `25` appears:

- `25 + 1 = 26` composite
- `25 + 8 = 33` composite
- `25 + 14 = 39` composite
- `25 + 20 = 45` composite
- `25 + 24 = 49` composite

Why smaller odd composites do not appear:

- `9 + 14 = 23` prime
- `15 + 8 = 23` prime
- `21 + 8 = 29` prime

So `25` is indeed the first odd composite that survives.

### Key Lemma for the "next odd term" problem

Define

`E := {e >= 8 : e is even composite, e+1 is composite, and e+25 is composite}`.

Then:

`E = {8, 14, 20, 24, 26, 32, 38, 44, 50, 56, 62, ...}`

Lemma:

- Suppose `m > 25` is the first odd composite that could appear after `25`.
- Then every earlier term greater than `25` is even.
- For any even composite `e` with `25 < e < m`, the only odd earlier terms are `1` and `25`.
- Therefore such an `e` is admissible exactly when `e+1` and `e+25` are composite.
- Hence the earlier even terms below `m` are exactly `E cap [1, m-1]`.

This yields the exact equivalent reformulation:

### Equivalent form of the main conjecture

The following are equivalent:

1. `25` is the largest odd term of A068638.
2. For every odd composite `m > 25`, there exists `e in E` with `e < m` and `m+e` prime.

In other words, every odd composite `m > 25` must be hit by at least one prime in the translate

`m + (E cap [1, m-1])`.

This is the cleanest proof target I found.

## Computational Evidence

I ran fresh local computations in this repository on 2026-03-25.

### Verified from local generation

I generated the sequence directly from the definition and checked:

- Up to value `10000`, the only odd terms are `1` and `25`.
- For every odd composite `m <= 10000`, there is at least one earlier even witness `e` with `m+e` prime.
- For every even composite `e <= 10000`, membership agrees with the rule `e in E`, because there are no odd terms beyond `25` in that range.

### Witness statistics for odd composites up to 10000

For the `3767` odd composite numbers in `[27,10000]`:

- minimum number of witnesses: `1`
- median number of witnesses: `305`
- mean number of witnesses: `327.06`
- maximum number of witnesses: `752`

The unique-witness odd composites up to `10000` are:

- `49`
- `55`
- `85`
- `91`
- `115`

Their witnesses are:

- `49 -> 24`
- `55 -> 24`
- `85 -> 24`
- `91 -> 90`
- `115 -> 24`

So the genuinely delicate cases are very sparse.

### Evidence from the current OEIS b-file

From the current OEIS b-file for A068638:

- number of listed terms: `10000`
- final listed term: `31654`
- only odd terms present: `1` and `25`

Thus the conjecture has at least been computationally validated in the public OEIS data through `a(10000)`.

### Empirical density of the even tail

If the conjectural tail description is correct, then even admissible numbers should be common, because they only need to avoid prime values at the two odd shifts `+1` and `+25`.

Observed density of sequence values among even numbers:

- up to `100`: `0.3878`
- up to `1000`: `0.4990`
- up to `10000`: `0.5909`
- in the OEIS b-file range up to `31654`: `0.631745`

Heuristic:

- for even `e`, both `e+1` and `e+25` are odd
- each is prime with rough probability about `2 / log e`
- so one expects the density of `E` among even numbers to behave roughly like
  `(1 - 2/log e)^2`

This is only a heuristic, but it matches the observed trend that admissible even numbers become denser.

## Literature Context

### Chen (2008)

Yong-Gao Chen, "Integer Sequences Avoiding Prime Pairwise Sums", Journal of Integer Sequences 11 (2008), Article 08.5.6.

What it proves:

- If `A subseteq {1,...,n}` has maximum possible size subject to "no sum of two distinct elements is prime", then `|A| = floor((n+1)/2)`.
- Moreover, every such maximum-size set consists entirely of one parity class.

Why it matters here:

- A068638 is not trying to maximize cardinality; it is greedy and mixed-parity because it contains `1`, then `25`, then many evens.
- Still, Chen's theorem explains why the true extremal objects are parity classes, so A068638 should be viewed as a special extremal-but-not-maximum greedy construction.
- It also suggests that once a mixed-parity greedy set survives, the hard part is entirely in the interaction between a small odd set and a large even set.

### Pandey (2012)

Ram Krishna Pandey, "On Lower Order Extremal Integral Sets Avoiding Prime Pairwise Sums", Journal of Integer Sequences 15 (2012), Article 12.6.1.

What it proves:

- For `n >= 10`, there is no extremal prime-sumset-free subset of `[n]` of size `2`.
- For `n >= 13`, there is no extremal prime-sumset-free subset of `[n]` of size `3`.
- More generally, for each fixed `k >= 2`, there is some threshold `n_k` beyond which no extremal prime-sumset-free subset of size `k` exists.

Why it matters here:

- Prefixes of the A025044/A068638 greedy construction are natural extremal prime-sumset-free sets.
- Pandey's results say that tiny mixed structures cannot persist as extremal objects for large `n`.
- That fits the observed A068638 behavior: after a short transient, the sequence seems to settle into a broad even-dominated regime controlled by a tiny odd core `{1,25}`.

### What I did not find

I did not find:

- a published proof of the conjecture that `25` is the largest odd term of A068638
- a published disproof or counterexample
- a later paper specifically about A068638 or A025044 beyond OEIS itself

So at the moment, the best web-available context appears to be:

- the OEIS entry and b-file
- Chen's broad extremal theorem
- Pandey's extremal lower-order analysis

## Proof Directions That Look Most Promising

### 1. Prove the translate-prime reformulation directly

Target statement:

- For every odd composite `m > 25`, there exists an even composite `e < m` such that
  - `e+1` is composite
  - `e+25` is composite
  - `m+e` is prime

This is exact, not heuristic.

If proved, it immediately settles the conjecture.

### 2. Split the task into "small exceptional m" and "large m"

The computation suggests:

- only a handful of odd composites have very few witnesses
- most odd composites have hundreds of witnesses by `10000`

That strongly suggests a two-stage proof:

- finite computation for the small and sparse exceptional range
- an asymptotic theorem showing that for all sufficiently large odd composite `m`, the translate `m+E` must contain a prime

### 3. Treat `E` as a dense sifted set

The set `E` is not arbitrary. It is defined by only two forbidden prime shifts:

- `e+1`
- `e+25`

So `E` is a very dense subset of the even numbers.

A proof strategy could be:

- estimate `|E cap [1,x]|` from below by sieve methods
- then prove that every translate `m + (E cap [1,m-1])` contains a prime

This is the point where one would want a theorem of the form:

- dense enough structured subsets of an interval cannot avoid all primes in every odd translate

I did not find that theorem directly in the literature during this search, but this is the right shape.

### 4. Use the first-witness function

Define `w(m)` to be the least `e in E` with `m+e` prime.

Empirically:

- `w(m)` is usually very small
- up to `10000`, the largest least witness I found is `370`, attained only at `m = 7081`

That suggests another angle:

- search for a finite set `F subset E` that already covers all odd composites
- or prove such a finite covering statement by residue classes plus prime-distribution input

I do not know whether this finite-cover form is true, but it is computationally plausible enough to merit checking.

## Suggested Next Steps

1. Formalize the equivalence with the witness set `E` as a lemma in the project notes.

2. Extend the computation much further than `10000` and record:
   - the odd composites with the fewest witnesses
   - the distribution of the least witness `w(m)`
   - whether the maximum least witness keeps growing slowly or stabilizes

3. Search specifically for sieve or additive-combinatorial results about primes in dense translates of sifted sets.

4. Try to prove an asymptotic result first:
   - there exists `M` such that every odd composite `m >= M` has a witness in `E`

5. Then finish with a finite verification up to `M`.

This "asymptotic theorem plus finite check" route looks substantially more realistic than trying to control the entire greedy process directly.

## Source Links

- OEIS A068638: [https://oeis.org/A068638](https://oeis.org/A068638)
- OEIS A068638 text format: [https://oeis.org/search?q=id:A068638&fmt=text](https://oeis.org/search?q=id:A068638&fmt=text)
- OEIS A068638 b-file: [https://oeis.org/A068638/b068638.txt](https://oeis.org/A068638/b068638.txt)
- OEIS A025044: [https://oeis.org/A025044](https://oeis.org/A025044)
- OEIS A025044 text format: [https://oeis.org/search?q=id:A025044&fmt=text](https://oeis.org/search?q=id:A025044&fmt=text)
- Yong-Gao Chen, JIS 2008: [https://cs.uwaterloo.ca/journals/JIS/VOL11/Chen/chen67.pdf](https://cs.uwaterloo.ca/journals/JIS/VOL11/Chen/chen67.pdf)
- Ram Krishna Pandey, JIS 2012: [https://cs.uwaterloo.ca/journals/JIS/VOL15/Pandey/pandey5.pdf](https://cs.uwaterloo.ca/journals/JIS/VOL15/Pandey/pandey5.pdf)
- Related OEIS analogue A072545: [https://oeis.org/A072545](https://oeis.org/A072545)

