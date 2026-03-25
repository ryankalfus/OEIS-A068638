Add every change to this log as its own bullet. Start each bullet with the date in `mm/dd/yyyy:` format. Update the log after each individual change, and split large updates into multiple bullets when needed.

- 03/25/2026: Created startup files
- 03/25/2026: Created GitHub repo and connected local git repo to `origin`
- 03/25/2026: Created `OEIS-A068638.md`
- 03/25/2026: Added rule to `CODEX.md` to read `OEIS-A068638.md` before every response
- 03/25/2026: Added `RESEARCH.md` with current web research, computational evidence, and proof-oriented reformulations for OEIS A068638
- 03/25/2026: Added `PROMPT-COMPUTE-FIRST-100000.md` with a formal Codex prompt for computing and analyzing the first 100000 terms
- 03/25/2026: Added `RUNTIME-TRACKING.md` describing the highest-value runtime metrics and witness data to preserve during long computations
- 03/25/2026: Added `MATHEMATICAL-OUTPUTS.md` specifying the proof-oriented datasets, summaries, and derived quantities most useful for studying A068638
- 03/25/2026: Added `scripts/compute_a068638.py` to compute A068638 directly from the greedy rule with checkpointing, audit datasets, and report generation
- 03/25/2026: Refined `scripts/compute_a068638.py` checkpoint handling, resume defaults, and verification/report generation details before the full run
- 03/25/2026: Corrected `scripts/compute_a068638.py` report inputs and verification checks after inspecting the first draft of the computation script
- 03/25/2026: Fixed the odd self-sum verification branch in `scripts/compute_a068638.py`
- 03/25/2026: Polished `scripts/compute_a068638.py` report text and density snapshots after the isolated smoke test
- 03/25/2026: Generated `data/a068638_first_100000.txt` and `data/a068638_first_100000.csv` from a fresh direct computation of A068638 through 100000 terms
- 03/25/2026: Generated ten resumable checkpoint snapshots in `data/checkpoints/` together with `data/checkpoints/manifest.json`
- 03/25/2026: Generated `analysis/odd-composite-witnesses.csv` and `analysis/least-witness-records.csv` for the odd-composite witness and least-witness analyses
- 03/25/2026: Generated `analysis/even-admissible-statistics.csv` and `analysis/rejection-witnesses.csv` for the even-tail checks and rejection-audit trail
- 03/25/2026: Generated `analysis/run-summary.md`, `analysis/conjecture-evidence.md`, and `analysis/residue-class-notes.md` from the completed 100000-term run
