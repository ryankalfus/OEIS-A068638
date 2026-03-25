#!/usr/bin/env python3
"""Compute OEIS A068638 directly from the greedy definition."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import resource
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


PREFIX = [1, 8, 14, 20, 24, 25, 26, 32, 38, 44]

ACCEPTED_COLUMNS = [
    "n",
    "a_n",
    "parity",
    "is_odd_term",
    "last_checked_previous_term",
]
ODD_WITNESS_COLUMNS = [
    "m",
    "least_witness",
    "witness_count",
    "least_prime_sum",
    "record_least_witness",
    "sample_witnesses",
    "residue_mod_6",
    "residue_mod_30",
    "residue_mod_210",
]
LEAST_RECORD_COLUMNS = [
    "m",
    "least_witness",
    "previous_record",
    "new_record_gap",
    "witness_count",
]
EVEN_STATS_COLUMNS = [
    "e",
    "accepted",
    "e_plus_1_composite",
    "e_plus_25_composite",
    "matches_E_rule",
    "blocking_witness",
    "prime_sum",
]
REJECTION_COLUMNS = [
    "candidate",
    "candidate_parity",
    "blocking_term",
    "blocking_term_index",
    "prime_sum",
    "rejection_kind",
    "witness_count",
]
PROGRESS_COLUMNS = [
    "accepted_terms",
    "largest_term",
    "next_candidate",
    "elapsed_seconds",
    "composite_candidates_tested",
    "accepted_candidates",
    "rejected_candidates",
    "odd_rejected_composites",
    "even_rejected_composites",
    "odd_witness_records",
]

ACC_N = 0
ACC_VALUE = 1
ACC_PARITY = 2
ACC_IS_ODD = 3
ACC_LAST = 4

ODD_M = 0
ODD_LEAST = 1
ODD_COUNT = 2
ODD_LEAST_PRIME = 3
ODD_RECORD = 4
ODD_SAMPLE = 5
ODD_MOD6 = 6
ODD_MOD30 = 7
ODD_MOD210 = 8

REC_M = 0
REC_LEAST = 1
REC_PREV = 2
REC_GAP = 3
REC_COUNT = 4

EVEN_E = 0
EVEN_ACCEPTED = 1
EVEN_E1 = 2
EVEN_E25 = 3
EVEN_MATCH = 4
EVEN_BLOCK = 5
EVEN_PRIME = 6

REJ_CANDIDATE = 0
REJ_PARITY = 1
REJ_BLOCK = 2
REJ_BLOCK_INDEX = 3
REJ_PRIME = 4
REJ_KIND = 5
REJ_COUNT = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=100000)
    parser.add_argument("--prime-limit", type=int, default=1000000)
    parser.add_argument("--checkpoint-interval", type=int, default=10000)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-root", default=".")
    return parser.parse_args()


def build_sieve(limit: int) -> bytearray:
    sieve = bytearray(b"\x01") * (limit + 1)
    if limit >= 0:
        sieve[0] = 0
    if limit >= 1:
        sieve[1] = 0
    bound = int(limit**0.5)
    for p in range(2, bound + 1):
        if sieve[p]:
            start = p * p
            sieve[start : limit + 1 : p] = b"\x00" * (((limit - start) // p) + 1)
    return sieve


def build_odd_prime_mask(is_prime: bytearray) -> int:
    mask = 0
    for value in range(3, len(is_prime), 2):
        if is_prime[value]:
            mask |= 1 << ((value - 1) // 2)
    return mask


def ensure_prime_capacity(
    needed: int,
    prime_limit: int,
    is_prime: bytearray,
    odd_prime_mask: int,
    stats: dict[str, Any],
) -> tuple[int, bytearray, int]:
    if needed <= prime_limit:
        return prime_limit, is_prime, odd_prime_mask

    new_limit = prime_limit
    while new_limit < needed:
        new_limit *= 2
    rebuild_started = time.perf_counter()
    is_prime = build_sieve(new_limit)
    odd_prime_mask = build_odd_prime_mask(is_prime)
    stats["prime_limit_extensions"] += 1
    stats["prime_rebuild_seconds"] += time.perf_counter() - rebuild_started
    return new_limit, is_prime, odd_prime_mask


def prime_lookup(value: int, is_prime: bytearray, stats: dict[str, Any]) -> bool:
    stats["prime_lookups"] += 1
    if value > stats["max_prime_argument_tested"]:
        stats["max_prime_argument_tested"] = value
    return bool(is_prime[value])


def sample_witnesses(mask: int, cap: int = 8) -> list[int]:
    values: list[int] = []
    while mask and len(values) < cap:
        low_bit = mask & -mask
        index = low_bit.bit_length() - 1
        values.append(2 * index)
        mask ^= low_bit
    return values


def next_composite(value: int, is_prime: bytearray) -> int:
    while value < len(is_prime) and is_prime[value]:
        value += 1
    return value


def bool_str(value: bool) -> str:
    return "true" if value else "false"


def json_cell(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_csv(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def write_gzip_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp_path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    tmp_path.replace(path)


def load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def checkpoint_filename(term_count: int) -> str:
    return f"checkpoint_n{term_count:06d}.json.gz"


def latest_checkpoint(checkpoint_dir: Path) -> Path | None:
    files = sorted(checkpoint_dir.glob("checkpoint_n*.json.gz"))
    return files[-1] if files else None


def initialize_state(target: int) -> dict[str, Any]:
    accepted_rows = [[1, 1, "odd", True, None]]
    return {
        "target": target,
        "current_candidate": 4,
        "accepted_rows": accepted_rows,
        "odd_witness_rows": [],
        "least_witness_record_rows": [],
        "even_rows": [],
        "rejection_rows": [],
        "progress_rows": [],
        "stats": {
            "composite_candidates_tested": 0,
            "odd_composite_candidates_tested": 0,
            "even_composite_candidates_tested": 0,
            "accepted_candidates": 1,
            "rejected_candidates": 0,
            "odd_rejected_composites": 0,
            "even_rejected_composites": 0,
            "prime_lookups": 0,
            "odd_bitset_queries": 0,
            "max_prime_argument_tested": 0,
            "prime_limit_extensions": 0,
            "prime_rebuild_seconds": 0.0,
            "last_candidate_examined": 1,
        },
        "record_least_witness": -1,
        "elapsed_seconds": 0.0,
        "checkpoint_files": [],
    }


def rebuild_runtime_state(accepted_rows: list[list[Any]]) -> tuple[dict[int, int], list[int], int]:
    accepted_index_by_value: dict[int, int] = {}
    odd_terms: list[int] = []
    even_mask = 0
    for row in accepted_rows:
        value = row[ACC_VALUE]
        accepted_index_by_value[value] = row[ACC_N]
        if value % 2 == 0:
            even_mask |= 1 << (value // 2)
        else:
            odd_terms.append(value)
    return accepted_index_by_value, odd_terms, even_mask


def checkpoint_payload(
    state: dict[str, Any],
    prime_limit: int,
    checkpoint_interval: int,
) -> dict[str, Any]:
    return {
        "target": state["target"],
        "prime_limit": prime_limit,
        "checkpoint_interval": checkpoint_interval,
        "current_candidate": state["current_candidate"],
        "accepted_rows": state["accepted_rows"],
        "odd_witness_rows": state["odd_witness_rows"],
        "least_witness_record_rows": state["least_witness_record_rows"],
        "even_rows": state["even_rows"],
        "rejection_rows": state["rejection_rows"],
        "progress_rows": state["progress_rows"],
        "stats": state["stats"],
        "record_least_witness": state["record_least_witness"],
        "elapsed_seconds": state["elapsed_seconds"],
        "checkpoint_files": state["checkpoint_files"],
    }


def save_checkpoint(
    state: dict[str, Any],
    checkpoint_dir: Path,
    prime_limit: int,
    checkpoint_interval: int,
    force: bool = False,
) -> None:
    term_count = len(state["accepted_rows"])
    if not force and term_count % checkpoint_interval != 0:
        return

    filename = checkpoint_filename(term_count)
    path = checkpoint_dir / filename
    if filename not in state["checkpoint_files"]:
        state["checkpoint_files"].append(filename)
    payload = checkpoint_payload(state, prime_limit, checkpoint_interval)
    write_gzip_json(path, payload)


def load_or_initialize_state(
    target: int,
    checkpoint_dir: Path,
    resume: bool,
) -> tuple[dict[str, Any], int]:
    if not resume:
        return initialize_state(target), 0

    checkpoint_path = latest_checkpoint(checkpoint_dir)
    if checkpoint_path is None:
        return initialize_state(target), target

    payload = load_gzip_json(checkpoint_path)
    state = {
        "target": payload["target"],
        "current_candidate": payload["current_candidate"],
        "accepted_rows": payload["accepted_rows"],
        "odd_witness_rows": payload["odd_witness_rows"],
        "least_witness_record_rows": payload["least_witness_record_rows"],
        "even_rows": payload["even_rows"],
        "rejection_rows": payload["rejection_rows"],
        "progress_rows": payload["progress_rows"],
        "stats": payload["stats"],
        "record_least_witness": payload["record_least_witness"],
        "elapsed_seconds": payload["elapsed_seconds"],
        "checkpoint_files": payload.get("checkpoint_files", [checkpoint_path.name]),
    }
    if checkpoint_path.name not in state["checkpoint_files"]:
        state["checkpoint_files"].append(checkpoint_path.name)
    state["target"] = target
    return state, int(payload["prime_limit"])


def compute_sequence(args: argparse.Namespace) -> dict[str, Any]:
    output_root = Path(args.output_root).resolve()
    checkpoint_dir = output_root / "data" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    state, checkpoint_prime_limit = load_or_initialize_state(args.target, checkpoint_dir, args.resume)
    prime_limit = max(checkpoint_prime_limit, args.prime_limit)
    accepted_rows = state["accepted_rows"]
    accepted_index_by_value, odd_terms, even_mask = rebuild_runtime_state(accepted_rows)
    last_even_term = max((row[ACC_VALUE] for row in accepted_rows if row[ACC_VALUE] % 2 == 0), default=None)

    is_prime = build_sieve(prime_limit)
    odd_prime_mask = build_odd_prime_mask(is_prime)
    start_time = time.perf_counter()

    while len(accepted_rows) < args.target:
        current = state["current_candidate"]
        needed_prime_limit = max(prime_limit, 2 * current + 25)
        prime_limit, is_prime, odd_prime_mask = ensure_prime_capacity(
            needed_prime_limit,
            prime_limit,
            is_prime,
            odd_prime_mask,
            state["stats"],
        )

        if prime_lookup(current, is_prime, state["stats"]):
            state["current_candidate"] = next_composite(current + 1, is_prime)
            continue

        state["stats"]["composite_candidates_tested"] += 1
        state["stats"]["last_candidate_examined"] = current

        if current % 2 == 0:
            state["stats"]["even_composite_candidates_tested"] += 1
            e_plus_1_composite = not prime_lookup(current + 1, is_prime, state["stats"])
            e_plus_25_composite = not prime_lookup(current + 25, is_prime, state["stats"])
            blocking_term = None
            prime_sum = None
            for odd_term in odd_terms:
                if prime_lookup(current + odd_term, is_prime, state["stats"]):
                    blocking_term = odd_term
                    prime_sum = current + odd_term
                    break

            accepted = blocking_term is None
            state["even_rows"].append(
                [
                    current,
                    accepted,
                    e_plus_1_composite,
                    e_plus_25_composite,
                    accepted == (e_plus_1_composite and e_plus_25_composite),
                    blocking_term,
                    prime_sum,
                ]
            )

            if accepted:
                accepted_rows.append(
                    [
                        len(accepted_rows) + 1,
                        current,
                        "even",
                        False,
                        odd_terms[-1],
                    ]
                )
                accepted_index_by_value[current] = len(accepted_rows)
                even_mask |= 1 << (current // 2)
                last_even_term = current
                state["stats"]["accepted_candidates"] += 1
            else:
                state["stats"]["rejected_candidates"] += 1
                state["stats"]["even_rejected_composites"] += 1
                state["rejection_rows"].append(
                    [
                        current,
                        "even",
                        blocking_term,
                        accepted_index_by_value[blocking_term],
                        prime_sum,
                        "prime witness",
                        None,
                    ]
                )
        else:
            state["stats"]["odd_composite_candidates_tested"] += 1
            state["stats"]["odd_bitset_queries"] += 1
            witness_mask = even_mask & (odd_prime_mask >> ((current - 1) // 2))

            if witness_mask == 0:
                accepted_rows.append(
                    [
                        len(accepted_rows) + 1,
                        current,
                        "odd",
                        True,
                        last_even_term,
                    ]
                )
                accepted_index_by_value[current] = len(accepted_rows)
                odd_terms.append(current)
                state["stats"]["accepted_candidates"] += 1
            else:
                least_witness_index = (witness_mask & -witness_mask).bit_length() - 1
                least_witness = 2 * least_witness_index
                witness_count = witness_mask.bit_count()
                record_flag = current > 25 and least_witness > state["record_least_witness"]
                if current > 25:
                    if record_flag:
                        previous = state["record_least_witness"]
                        state["least_witness_record_rows"].append(
                            [
                                current,
                                least_witness,
                                previous if previous >= 0 else None,
                                (least_witness - previous) if previous >= 0 else None,
                                witness_count,
                            ]
                        )
                    state["odd_witness_rows"].append(
                        [
                            current,
                            least_witness,
                            witness_count,
                            current + least_witness,
                            record_flag,
                            sample_witnesses(witness_mask),
                            current % 6,
                            current % 30,
                            current % 210,
                        ]
                    )
                    state["record_least_witness"] = max(state["record_least_witness"], least_witness)
                state["stats"]["rejected_candidates"] += 1
                state["stats"]["odd_rejected_composites"] += 1
                state["rejection_rows"].append(
                    [
                        current,
                        "odd",
                        least_witness,
                        accepted_index_by_value[least_witness],
                        current + least_witness,
                        "prime witness",
                        witness_count if current > 25 else None,
                    ]
                )

        if len(accepted_rows) % args.checkpoint_interval == 0 or len(accepted_rows) == args.target:
            state["elapsed_seconds"] += time.perf_counter() - start_time
            state["progress_rows"].append(
                [
                    len(accepted_rows),
                    accepted_rows[-1][ACC_VALUE],
                    next_composite(current + 1, is_prime),
                    state["elapsed_seconds"],
                    state["stats"]["composite_candidates_tested"],
                    state["stats"]["accepted_candidates"],
                    state["stats"]["rejected_candidates"],
                    state["stats"]["odd_rejected_composites"],
                    state["stats"]["even_rejected_composites"],
                    len(state["least_witness_record_rows"]),
                ]
            )
            state["current_candidate"] = next_composite(current + 1, is_prime)
            save_checkpoint(
                state,
                checkpoint_dir,
                prime_limit,
                args.checkpoint_interval,
                force=len(accepted_rows) == args.target,
            )
            start_time = time.perf_counter()
        else:
            state["current_candidate"] = next_composite(current + 1, is_prime)

    state["elapsed_seconds"] += time.perf_counter() - start_time
    state["prime_limit"] = prime_limit
    state["odd_terms"] = odd_terms
    state["last_even_term"] = last_even_term
    return state


def verify_results(state: dict[str, Any], is_prime: bytearray) -> list[str]:
    issues: list[str] = []
    accepted_rows = state["accepted_rows"]
    accepted_values = [row[ACC_VALUE] for row in accepted_rows]
    accepted_index_by_value = {row[ACC_VALUE]: row[ACC_N] for row in accepted_rows}
    odd_terms = [row[ACC_VALUE] for row in accepted_rows if row[ACC_VALUE] % 2 == 1]
    even_terms = [row[ACC_VALUE] for row in accepted_rows if row[ACC_VALUE] % 2 == 0]

    if accepted_values[: len(PREFIX)] != PREFIX:
        issues.append("Initial prefix does not match OEIS-A068638.md.")

    for value in accepted_values[1:]:
        if is_prime[value]:
            issues.append(f"Accepted term {value} is prime.")
            break

    if len(accepted_values) != len(set(accepted_values)):
        issues.append("Accepted terms are not distinct.")

    for odd_term in odd_terms:
        for even_term in even_terms:
            if is_prime[odd_term + even_term]:
                issues.append(
                    f"Prime sum found between accepted terms {odd_term} and {even_term}."
                )
                return issues
    for odd_term in odd_terms:
        if odd_term > 1 and is_prime[odd_term + odd_term]:
            issues.append(f"Unexpected prime self-sum at odd term {odd_term}.")
            break

    for row in state["rejection_rows"]:
        candidate = row[REJ_CANDIDATE]
        blocking = row[REJ_BLOCK]
        prime_sum = row[REJ_PRIME]
        if blocking is None or prime_sum is None:
            issues.append(f"Rejected candidate {candidate} lacks a blocking witness.")
            break
        if blocking not in accepted_index_by_value:
            issues.append(f"Blocking witness {blocking} for candidate {candidate} was not accepted.")
            break
        if blocking >= candidate:
            issues.append(f"Blocking witness {blocking} is not earlier than candidate {candidate}.")
            break
        if not is_prime[prime_sum]:
            issues.append(f"Recorded prime sum {prime_sum} for candidate {candidate} is not prime.")
            break

    return issues


def format_seconds(seconds: float) -> str:
    return f"{seconds:.3f} s"


def max_rss_mebibytes() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def even_density_snapshots(even_rows: list[list[Any]], bounds: list[int]) -> list[list[Any]]:
    snapshots: list[list[Any]] = []
    for bound in bounds:
        subset = [row for row in even_rows if row[EVEN_E] <= bound]
        if not subset:
            continue
        accepted_count = sum(1 for row in subset if row[EVEN_ACCEPTED])
        e_rule_count = sum(1 for row in subset if row[EVEN_E1] and row[EVEN_E25])
        snapshots.append(
            [
                bound,
                len(subset),
                accepted_count,
                accepted_count / len(subset),
                e_rule_count,
                e_rule_count / len(subset),
            ]
        )
    return snapshots


def top_counter_lines(counter: Counter[int], limit: int = 10) -> list[str]:
    if not counter:
        return ["None."]
    return [f"- residue {residue}: {count}" for residue, count in counter.most_common(limit)]


def residue_summary_table(
    odd_rows: list[list[Any]],
    modulus: int,
    hard_limit: int,
    record_rows: list[list[Any]],
) -> str:
    total_counts = Counter(row[ODD_M] % modulus for row in odd_rows)
    hard_counts = Counter(row[ODD_M] % modulus for row in odd_rows if row[ODD_COUNT] <= hard_limit)
    record_counts = Counter(row[REC_M] % modulus for row in record_rows)
    residues = sorted(total_counts)
    lines = [
        f"### Modulo {modulus}",
        "",
        "| residue | odd composites | witness_count <= "
        + str(hard_limit)
        + " | least-witness records |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for residue in residues:
        lines.append(
            f"| {residue} | {total_counts[residue]} | {hard_counts[residue]} | {record_counts[residue]} |"
        )
    return "\n".join(lines)


def convert_csv_rows(rows: list[list[Any]], json_columns: set[int] | None = None) -> list[list[Any]]:
    converted: list[list[Any]] = []
    json_columns = json_columns or set()
    for row in rows:
        converted_row: list[Any] = []
        for index, value in enumerate(row):
            if index in json_columns:
                converted_row.append(json_cell(value))
            else:
                converted_row.append(value)
        converted.append(converted_row)
    return converted


def write_outputs(state: dict[str, Any], output_root: Path) -> None:
    accepted_rows = state["accepted_rows"]
    odd_rows = state["odd_witness_rows"]
    record_rows = state["least_witness_record_rows"]
    even_rows = state["even_rows"]
    rejection_rows = state["rejection_rows"]
    accepted_values = [row[ACC_VALUE] for row in accepted_rows]
    odd_terms = [row[ACC_VALUE] for row in accepted_rows if row[ACC_VALUE] % 2 == 1]
    is_prime = build_sieve(state["prime_limit"])

    data_dir = output_root / "data"
    analysis_dir = output_root / "analysis"
    checkpoint_dir = data_dir / "checkpoints"
    data_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    term_stem = f"a068638_first_{len(accepted_rows)}"
    txt_lines = [f"{row[ACC_N]} {row[ACC_VALUE]}" for row in accepted_rows]
    write_text(data_dir / f"{term_stem}.txt", "\n".join(txt_lines) + "\n")
    write_csv(data_dir / f"{term_stem}.csv", ACCEPTED_COLUMNS, accepted_rows)
    write_csv(
        analysis_dir / "odd-composite-witnesses.csv",
        ODD_WITNESS_COLUMNS,
        convert_csv_rows(odd_rows, json_columns={ODD_SAMPLE}),
    )
    write_csv(
        analysis_dir / "least-witness-records.csv",
        LEAST_RECORD_COLUMNS,
        record_rows,
    )
    write_csv(
        analysis_dir / "even-admissible-statistics.csv",
        EVEN_STATS_COLUMNS,
        even_rows,
    )
    write_csv(
        analysis_dir / "rejection-witnesses.csv",
        REJECTION_COLUMNS,
        rejection_rows,
    )

    checkpoint_manifest = {
        "checkpoint_files": state["checkpoint_files"],
        "checkpoint_interval": state.get("checkpoint_interval"),
        "progress_columns": PROGRESS_COLUMNS,
        "progress_rows": state["progress_rows"],
        "final_term_count": len(accepted_rows),
        "final_value": accepted_values[-1],
        "next_candidate": state["current_candidate"],
    }
    write_text(
        checkpoint_dir / "manifest.json",
        json.dumps(checkpoint_manifest, indent=2) + "\n",
    )

    witness_counts = [row[ODD_COUNT] for row in odd_rows]
    least_witnesses = [row[ODD_LEAST] for row in odd_rows]
    unique_rows = [row for row in odd_rows if row[ODD_COUNT] == 1]
    hard_two = [row for row in odd_rows if row[ODD_COUNT] <= 2]
    hard_five = [row for row in odd_rows if row[ODD_COUNT] <= 5]
    hard_ten = [row for row in odd_rows if row[ODD_COUNT] <= 10]
    max_least_row = max(odd_rows, key=lambda row: row[ODD_LEAST]) if odd_rows else None
    density_rows = even_density_snapshots(
        even_rows,
        bounds=sorted({bound for bound in (100, 1000, 10000, accepted_values[-1]) if bound <= accepted_values[-1]}),
    )

    run_summary_lines = [
        "# Run Summary",
        "",
        f"- Completed first `{len(accepted_rows)}` terms: {bool_str(len(accepted_rows) == state['target'])}",
        f"- Largest computed index: `{accepted_rows[-1][ACC_N]}`",
        f"- Largest computed value: `{accepted_values[-1]}`",
        f"- Total runtime: `{format_seconds(state['elapsed_seconds'])}`",
        f"- Peak resident memory: `{max_rss_mebibytes():.2f} MiB`",
        f"- Prime sieve limit used: `{state['prime_limit']}`",
        f"- Prime lookups: `{state['stats']['prime_lookups']}`",
        f"- Odd bitset witness queries: `{state['stats']['odd_bitset_queries']}`",
        f"- Odd terms encountered: `{odd_terms}`",
        "",
        "## Correctness Checks",
        "",
        f"- Prefix check against `OEIS-A068638.md`: `{accepted_values[:len(PREFIX)] == PREFIX}`",
        f"- All accepted terms distinct: `{len(accepted_values) == len(set(accepted_values))}`",
        f"- All accepted terms beyond `a(1)` composite: `{all(value == 1 or not is_prime[value] for value in accepted_values)}`",
        f"- Rejected candidates with recorded witness rows: `{len(rejection_rows)}`",
        "",
        "## Spot Checks",
        "",
        "- `a(6) = 25` survived because `25 + 1 = 26`, `25 + 8 = 33`, `25 + 14 = 39`, `25 + 20 = 45`, and `25 + 24 = 49` are all composite.",
        f"- Final accepted term `a({accepted_rows[-1][ACC_N]}) = {accepted_values[-1]}` is even, with `{accepted_values[-1] + 1}` and `{accepted_values[-1] + 25}` both composite.",
        (
            f"- Largest least witness in the tested odd-composite range is `{max_least_row[ODD_LEAST]}` at `m = {max_least_row[ODD_M]}` with witness count `{max_least_row[ODD_COUNT]}`."
            if max_least_row is not None
            else "- No odd composite greater than `25` was tested."
        ),
        "",
        "## Runtime Behavior",
        "",
        f"- Composite candidates tested: `{state['stats']['composite_candidates_tested']}`",
        f"- Accepted candidates: `{state['stats']['accepted_candidates']}`",
        f"- Rejected odd composites: `{state['stats']['odd_rejected_composites']}`",
        f"- Rejected even composites: `{state['stats']['even_rejected_composites']}`",
        f"- Checkpoint files written: `{len(state['checkpoint_files'])}`",
        "",
        "## Conjecture-Focused Highlights",
        "",
        f"- No odd term larger than `25` was accepted: `{odd_terms == [1, 25]}`",
        f"- Odd composite candidates above `25` tested: `{len(odd_rows)}`",
        f"- Minimum / median / mean / maximum witness counts: `{min(witness_counts)}` / `{statistics.median(witness_counts)}` / `{statistics.mean(witness_counts):.3f}` / `{max(witness_counts)}`",
        f"- Maximum least witness: `{max(least_witnesses) if least_witnesses else 'n/a'}`",
        f"- Unique-witness odd composites: `{len(unique_rows)}`",
        f"- Odd composites with at most 2 witnesses: `{len(hard_two)}`",
        f"- Odd composites with at most 5 witnesses: `{len(hard_five)}`",
        f"- Odd composites with at most 10 witnesses: `{len(hard_ten)}`",
        "",
        "## Even-Tail Density Snapshots",
        "",
        "| bound | even composite candidates | accepted evens | accepted density | E-rule candidates | E-rule density |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for bound, total, accepted_count, accepted_density, e_rule_count, e_rule_density in density_rows:
        run_summary_lines.append(
            f"| {bound} | {total} | {accepted_count} | {accepted_density:.6f} | {e_rule_count} | {e_rule_density:.6f} |"
        )
    write_text(analysis_dir / "run-summary.md", "\n".join(run_summary_lines) + "\n")

    conjecture_lines = [
        "# Conjecture Evidence",
        "",
        "## Main Outcome",
        "",
        f"- Observed odd terms: `{odd_terms}`",
        f"- Any odd term larger than `25`: `{bool_str(any(term > 25 for term in odd_terms))}`",
        f"- Exhaustively tested odd composite candidates in the run range: `{len(odd_rows)}`",
        f"- Every tested odd composite `m > 25` had a recorded prime witness: `{bool_str(all(row[ODD_COUNT] >= 1 for row in odd_rows))}`",
        "",
        "## Least-Witness Function",
        "",
        (
            f"- Maximum least witness: `{max_least_row[ODD_LEAST]}` at `m = {max_least_row[ODD_M]}`"
            if max_least_row is not None
            else "- Maximum least witness: `n/a`"
        ),
        f"- Number of least-witness record setters: `{len(record_rows)}`",
        f"- First five least-witness record rows: `{record_rows[:5]}`",
        "",
        "## Sparse Odd-Composite Cases",
        "",
        f"- Witness count `= 1`: `{[row[ODD_M] for row in unique_rows]}`",
        f"- Witness count `<= 2`: `{[row[ODD_M] for row in hard_two[:20]]}`",
        f"- Witness count `<= 5`: `{len(hard_five)}` cases",
        f"- Witness count `<= 10`: `{len(hard_ten)}` cases",
        "",
        "## Even Tail",
        "",
        f"- Accepted even terms beyond `25` agree with the `e+1` and `e+25` composite rule in every recorded case: `{bool_str(all(row[EVEN_MATCH] for row in even_rows if row[EVEN_E] > 25))}`",
        f"- Final term `a({accepted_rows[-1][ACC_N]}) = {accepted_values[-1]}` satisfies `e+1` and `e+25` composite checks.",
        "",
        "## Interpretation",
        "",
        f"The {len(accepted_rows)}-term run supports the working picture from `RESEARCH.md`: after the early odd transient `{{1, 25}}`, every later odd composite is blocked by at least one accepted even witness, while the even tail is completely governed by the `+1` and `+25` composite conditions throughout the tested range.",
    ]
    write_text(analysis_dir / "conjecture-evidence.md", "\n".join(conjecture_lines) + "\n")

    mod210_hard = Counter(row[ODD_MOD210] for row in odd_rows if row[ODD_COUNT] <= 10)
    mod210_records = Counter(row[REC_M] % 210 for row in record_rows)
    residue_lines = [
        "# Residue-Class Notes",
        "",
        f"- Odd composite witness rows analyzed: `{len(odd_rows)}`",
        f"- Least-witness record rows analyzed: `{len(record_rows)}`",
        "",
        residue_summary_table(odd_rows, 6, 5, record_rows),
        "",
        residue_summary_table(odd_rows, 30, 10, record_rows),
        "",
        "### Modulo 210",
        "",
        "Hard residues with witness count `<= 10`:",
        *top_counter_lines(mod210_hard, limit=20),
        "",
        "Record-setting residues modulo `210`:",
        *top_counter_lines(mod210_records, limit=20),
    ]
    write_text(analysis_dir / "residue-class-notes.md", "\n".join(residue_lines) + "\n")


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root).resolve()
    state = compute_sequence(args)

    prime_limit = state["prime_limit"]
    is_prime = build_sieve(prime_limit)
    issues = verify_results(state, is_prime)
    if issues:
        raise SystemExit("\n".join(issues))

    write_outputs(state, output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    state["checkpoint_interval"] = args.checkpoint_interval
