#!/usr/bin/env python3
"""Compute OEIS A068638 directly from the greedy definition."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import resource
import shutil
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


PREFIX = [1, 8, 14, 20, 24, 25, 26, 32, 38, 44]
DEFAULT_MILESTONES = [100000, 250000, 500000, 750000, 1000000]
DEFAULT_DENSITY_BOUNDS = [100, 1000, 10000]

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
MILESTONE_COLUMNS = [
    "accepted_terms",
    "largest_term",
    "elapsed_seconds",
    "checkpoint_file",
    "max_least_witness",
    "witness_count_eq_1",
    "witness_count_le_2",
    "witness_count_le_5",
    "witness_count_le_10",
    "accepted_even_density",
]


class ControlledStop(RuntimeError):
    """Raised to simulate an interrupted run after a checkpoint."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=100000)
    parser.add_argument("--prime-limit", type=int, default=1000000)
    parser.add_argument("--checkpoint-interval", type=int, default=10000)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-root", default=".")
    parser.add_argument("--baseline-root", default="")
    parser.add_argument("--shard-size", type=int, default=250000)
    parser.add_argument("--milestones", default="100000,250000,500000,750000,1000000")
    parser.add_argument("--stop-after-checkpoints", type=int, default=0)
    parser.add_argument("--deterministic-output", action="store_true")
    return parser.parse_args()


def parse_int_list(value: str) -> list[int]:
    if not value.strip():
        return []
    return [int(part.strip()) for part in value.split(",") if part.strip()]


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
    started = time.perf_counter()
    is_prime = build_sieve(new_limit)
    odd_prime_mask = build_odd_prime_mask(is_prime)
    stats["prime_limit_extensions"] += 1
    stats["prime_rebuild_seconds"] += time.perf_counter() - started
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


def write_gzip_json(path: Path, payload: dict[str, Any], deterministic: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("wb") as raw_handle:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_handle,
            mtime=0 if deterministic else None,
        ) as gz_handle:
            with io.TextIOWrapper(gz_handle, encoding="utf-8") as text_handle:
                json.dump(payload, text_handle, separators=(",", ":"))
    tmp_path.replace(path)


def load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def checkpoint_filename(term_count: int) -> str:
    return f"checkpoint_n{term_count:07d}.json.gz"


def latest_checkpoint(checkpoint_dir: Path) -> Path | None:
    files = sorted(checkpoint_dir.glob("checkpoint_n*.json.gz"))
    return files[-1] if files else None


def max_rss_mebibytes() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def format_seconds(seconds: float) -> str:
    return f"{seconds:.3f} s"


def measured_elapsed(started_at: float, deterministic_output: bool) -> float:
    if deterministic_output:
        return 0.0
    return time.perf_counter() - started_at


def load_baseline_terms(baseline_root: str) -> list[int]:
    if not baseline_root:
        return []
    baseline_path = Path(baseline_root).resolve() / "data" / "a068638_first_100000.csv"
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline term file not found at {baseline_path}")
    values: list[int] = []
    with baseline_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            values.append(int(row["a_n"]))
    return values


def load_baseline_records(baseline_root: str) -> list[list[str]]:
    if not baseline_root:
        return []
    baseline_path = Path(baseline_root).resolve() / "analysis" / "least-witness-records.csv"
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline least-witness record file not found at {baseline_path}")
    with baseline_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)
        return [row for row in reader]


def require_clean_output_root(output_root: Path, resume: bool) -> None:
    if resume or not output_root.exists():
        return
    if any(output_root.iterdir()):
        raise SystemExit(
            f"Output root {output_root} already exists and is not empty; use --resume or choose a fresh directory."
        )


class AcceptedTermsWriter:
    def __init__(self, data_dir: Path, target: int, resume: bool, rows_written: int = 0) -> None:
        term_stem = f"a068638_first_{target}"
        self.csv_path = data_dir / f"{term_stem}.csv"
        self.txt_path = data_dir / f"{term_stem}.txt"
        self.rows_written = rows_written
        data_dir.mkdir(parents=True, exist_ok=True)

        if resume:
            if not self.csv_path.exists() or not self.txt_path.exists():
                raise SystemExit("Cannot resume accepted term output; CSV/TXT files are missing.")
            csv_mode = "a"
            txt_mode = "a"
        else:
            csv_mode = "w"
            txt_mode = "w"

        self.csv_handle = self.csv_path.open(csv_mode, newline="", encoding="utf-8")
        self.txt_handle = self.txt_path.open(txt_mode, encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_handle)
        if not resume:
            self.csv_writer.writerow(ACCEPTED_COLUMNS)

    def write_term(self, n: int, value: int, last_checked_previous_term: int | None) -> None:
        self.csv_writer.writerow(
            [
                n,
                value,
                "odd" if value % 2 else "even",
                bool(value % 2),
                last_checked_previous_term,
            ]
        )
        self.txt_handle.write(f"{n} {value}\n")
        self.rows_written += 1

    def flush(self) -> None:
        self.csv_handle.flush()
        self.txt_handle.flush()

    def close(self) -> None:
        self.flush()
        self.csv_handle.close()
        self.txt_handle.close()


class ShardedCsvWriter:
    def __init__(
        self,
        analysis_dir: Path,
        base_name: str,
        headers: list[str],
        shard_size: int,
        json_columns: set[int] | None = None,
        resume_manifest: dict[str, Any] | None = None,
    ) -> None:
        self.analysis_dir = analysis_dir
        self.base_name = base_name
        self.headers = headers
        self.shard_size = shard_size
        self.json_columns = json_columns or set()
        self.shard_dir = analysis_dir / base_name
        self.manifest_path = analysis_dir / f"{base_name}.manifest.json"
        self.handle = None
        self.writer = None

        if resume_manifest is None:
            self.manifest = {
                "base_name": base_name,
                "headers": headers,
                "shard_size": shard_size,
                "total_rows": 0,
                "shards": [],
                "current_shard_index": 0,
                "current_shard_rows": 0,
            }
        else:
            self.manifest = resume_manifest

        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        self.shard_dir.mkdir(parents=True, exist_ok=True)

    def _shard_filename(self, shard_index: int) -> str:
        return f"{self.base_name}-{shard_index:06d}.csv.gz"

    def _work_filename(self, shard_index: int) -> str:
        return f"{self.base_name}-{shard_index:06d}.work.csv"

    def _open_new_shard(self) -> None:
        self.close_current_shard()
        self.manifest["current_shard_index"] += 1
        self.manifest["current_shard_rows"] = 0
        shard_index = self.manifest["current_shard_index"]
        filename = self._shard_filename(shard_index)
        work_filename = self._work_filename(shard_index)
        path = self.shard_dir / work_filename
        self.handle = path.open("w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.handle)
        self.writer.writerow(self.headers)
        self.manifest["shards"].append(
            {
                "file": f"{self.base_name}/{filename}",
                "work_file": f"{self.base_name}/{work_filename}",
                "rows": 0,
            }
        )

    def _open_existing_shard_for_resume(self) -> None:
        if not self.manifest["shards"]:
            self._open_new_shard()
            return
        filename = self.manifest["shards"][-1]["work_file"].split("/", 1)[1]
        path = self.shard_dir / filename
        if not path.exists():
            raise SystemExit(f"Missing shard file for resume: {path}")
        self.handle = path.open("a", newline="", encoding="utf-8")
        self.writer = csv.writer(self.handle)

    def open_for_resume(self) -> None:
        if self.manifest["current_shard_index"] == 0:
            self._open_new_shard()
        elif self.manifest["current_shard_rows"] >= self.shard_size:
            self._open_new_shard()
        else:
            self._open_existing_shard_for_resume()

    def close_current_shard(self) -> None:
        if self.handle is not None:
            self.handle.flush()
            self.handle.close()
            self.handle = None
            self.writer = None

    def _ensure_open(self) -> None:
        if self.writer is None:
            if self.manifest["current_shard_index"] == 0:
                self._open_new_shard()
            elif self.manifest["current_shard_rows"] >= self.shard_size:
                self._open_new_shard()
            else:
                self._open_existing_shard_for_resume()

    def write_row(self, row: list[Any]) -> None:
        if self.manifest["current_shard_rows"] >= self.shard_size:
            self._open_new_shard()
        self._ensure_open()
        converted: list[Any] = []
        for index, value in enumerate(row):
            if index in self.json_columns:
                converted.append(json_cell(value))
            else:
                converted.append(value)
        self.writer.writerow(converted)
        self.manifest["current_shard_rows"] += 1
        self.manifest["total_rows"] += 1
        self.manifest["shards"][-1]["rows"] += 1

    def flush(self) -> None:
        if self.handle is not None:
            self.handle.flush()

    def save_manifest(self) -> None:
        payload = {
            "base_name": self.base_name,
            "headers": self.headers,
            "shard_size": self.shard_size,
            "total_rows": self.manifest["total_rows"],
            "current_shard_index": self.manifest["current_shard_index"],
            "current_shard_rows": self.manifest["current_shard_rows"],
            "shards": [{"file": shard["file"], "rows": shard["rows"]} for shard in self.manifest["shards"]],
        }
        write_text(self.manifest_path, json.dumps(payload, indent=2) + "\n")

    def finalize(self) -> None:
        self.close_current_shard()
        for shard in self.manifest["shards"]:
            work_path = self.analysis_dir / shard["work_file"]
            final_path = self.analysis_dir / shard["file"]
            if not work_path.exists():
                continue
            final_path.parent.mkdir(parents=True, exist_ok=True)
            with work_path.open("rb") as source, final_path.open("wb") as sink:
                with gzip.GzipFile(fileobj=sink, mode="wb", mtime=0) as gz_handle:
                    shutil.copyfileobj(source, gz_handle)
            work_path.unlink()
        self.save_manifest()

    def close_unfinished(self) -> None:
        self.close_current_shard()

    def snapshot(self) -> dict[str, Any]:
        return {
            "base_name": self.base_name,
            "headers": self.headers,
            "shard_size": self.shard_size,
            "total_rows": self.manifest["total_rows"],
            "current_shard_index": self.manifest["current_shard_index"],
            "current_shard_rows": self.manifest["current_shard_rows"],
            "shards": self.manifest["shards"],
        }


def initialize_summary_state(target: int, milestones: list[int]) -> dict[str, Any]:
    filtered_milestones = [point for point in milestones if point <= target]
    return {
        "witness_count_freq": {},
        "witness_count_sum": 0,
        "witness_count_rows": 0,
        "witness_count_min": None,
        "witness_count_max": None,
        "unique_witness_ms": [],
        "witness_le_2_ms": [],
        "hard_le_5_count": 0,
        "hard_le_10_count": 0,
        "odd_rows_analyzed": 0,
        "max_least_witness_row": None,
        "record_rows": [],
        "total_mod_6": {},
        "hard_mod_6": {},
        "total_mod_30": {},
        "hard_mod_30": {},
        "hard_mod_210": {},
        "record_mod_210": {},
        "even_total_candidates": 0,
        "even_accepted_count": 0,
        "even_e_rule_count": 0,
        "even_rule_mismatches": 0,
        "density_bounds": DEFAULT_DENSITY_BOUNDS[:],
        "density_snapshots": [],
        "next_density_index": 0,
        "milestone_targets": filtered_milestones,
        "milestone_rows": [],
        "milestones_completed": [],
        "baseline_prefix_validated": False,
    }


def increment_counter(mapping: dict[str, int], key: int) -> None:
    text_key = str(key)
    mapping[text_key] = mapping.get(text_key, 0) + 1


def counter_from_mapping(mapping: dict[str, int]) -> Counter[int]:
    return Counter({int(key): value for key, value in mapping.items()})


def update_density_snapshots(summary: dict[str, Any], current_even: int) -> None:
    bounds = summary["density_bounds"]
    while summary["next_density_index"] < len(bounds) and bounds[summary["next_density_index"]] < current_even:
        bound = bounds[summary["next_density_index"]]
        total = summary["even_total_candidates"]
        accepted = summary["even_accepted_count"]
        e_rule = summary["even_e_rule_count"]
        summary["density_snapshots"].append(
            {
                "bound": bound,
                "even_total_candidates": total,
                "accepted_evens": accepted,
                "accepted_density": accepted / total if total else 0.0,
                "e_rule_candidates": e_rule,
                "e_rule_density": e_rule / total if total else 0.0,
            }
        )
        summary["next_density_index"] += 1


def maybe_record_milestone(
    summary: dict[str, Any],
    accepted_count: int,
    largest_term: int,
    elapsed_seconds: float,
    checkpoint_file: str,
) -> None:
    targets = summary["milestone_targets"]
    while summary["milestones_completed"] != targets[: len(summary["milestones_completed"])]:
        raise RuntimeError("Milestone state is inconsistent.")
    if len(summary["milestones_completed"]) >= len(targets):
        return
    next_target = targets[len(summary["milestones_completed"])]
    if accepted_count != next_target:
        return

    total_even = summary["even_total_candidates"]
    accepted_even = summary["even_accepted_count"]
    density = accepted_even / total_even if total_even else 0.0
    max_least = (
        summary["max_least_witness_row"]["least_witness"]
        if summary["max_least_witness_row"] is not None
        else None
    )
    milestone_row = {
        "accepted_terms": accepted_count,
        "largest_term": largest_term,
        "elapsed_seconds": elapsed_seconds,
        "checkpoint_file": checkpoint_file,
        "max_least_witness": max_least,
        "witness_count_eq_1": len(summary["unique_witness_ms"]),
        "witness_count_le_2": len(summary["witness_le_2_ms"]),
        "witness_count_le_5": summary["hard_le_5_count"],
        "witness_count_le_10": summary["hard_le_10_count"],
        "accepted_even_density": density,
    }
    summary["milestone_rows"].append(milestone_row)
    summary["milestones_completed"].append(next_target)


def build_runtime_state(accepted_values: list[int]) -> tuple[dict[int, int], list[int], int]:
    accepted_index_by_value: dict[int, int] = {}
    odd_terms: list[int] = []
    even_mask = 0
    for index, value in enumerate(accepted_values, start=1):
        accepted_index_by_value[value] = index
        if value % 2 == 0:
            even_mask |= 1 << (value // 2)
        else:
            odd_terms.append(value)
    return accepted_index_by_value, odd_terms, even_mask


def initialize_state(target: int, milestones: list[int]) -> dict[str, Any]:
    return {
        "target": target,
        "current_candidate": 4,
        "accepted_values": [1],
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
            "checkpoints_written": 0,
        },
        "summary": initialize_summary_state(target, milestones),
        "record_least_witness": -1,
        "elapsed_seconds": 0.0,
        "checkpoint_files": [],
        "accepted_rows_written": 0,
        "sharded_writers": {},
        "deterministic_output": False,
    }


def checkpoint_payload(state: dict[str, Any], prime_limit: int, checkpoint_interval: int) -> dict[str, Any]:
    return {
        "target": state["target"],
        "prime_limit": prime_limit,
        "checkpoint_interval": checkpoint_interval,
        "current_candidate": state["current_candidate"],
        "accepted_values": state["accepted_values"],
        "stats": state["stats"],
        "summary": state["summary"],
        "record_least_witness": state["record_least_witness"],
        "elapsed_seconds": state["elapsed_seconds"],
        "checkpoint_files": state["checkpoint_files"],
        "accepted_rows_written": state["accepted_rows_written"],
        "sharded_writers": state["sharded_writers"],
        "deterministic_output": state["deterministic_output"],
    }


def save_checkpoint(
    state: dict[str, Any],
    checkpoint_dir: Path,
    prime_limit: int,
    checkpoint_interval: int,
) -> str:
    term_count = len(state["accepted_values"])
    filename = checkpoint_filename(term_count)
    path = checkpoint_dir / filename
    if filename not in state["checkpoint_files"]:
        state["checkpoint_files"].append(filename)
    state["stats"]["checkpoints_written"] = len(state["checkpoint_files"])
    payload = checkpoint_payload(state, prime_limit, checkpoint_interval)
    write_gzip_json(path, payload, deterministic=state["deterministic_output"])
    return filename


def load_or_initialize_state(
    target: int,
    checkpoint_dir: Path,
    resume: bool,
    milestones: list[int],
) -> tuple[dict[str, Any], int]:
    if not resume:
        return initialize_state(target, milestones), 0

    checkpoint_path = latest_checkpoint(checkpoint_dir)
    if checkpoint_path is None:
        return initialize_state(target, milestones), 0

    payload = load_gzip_json(checkpoint_path)
    state = {
        "target": target,
        "current_candidate": payload["current_candidate"],
        "accepted_values": payload["accepted_values"],
        "stats": payload["stats"],
        "summary": payload["summary"],
        "record_least_witness": payload["record_least_witness"],
        "elapsed_seconds": payload["elapsed_seconds"],
        "checkpoint_files": payload.get("checkpoint_files", [checkpoint_path.name]),
        "accepted_rows_written": payload.get("accepted_rows_written", len(payload["accepted_values"])),
        "sharded_writers": payload.get("sharded_writers", {}),
        "deterministic_output": payload.get("deterministic_output", False),
    }
    if checkpoint_path.name not in state["checkpoint_files"]:
        state["checkpoint_files"].append(checkpoint_path.name)
    state["stats"]["checkpoints_written"] = len(state["checkpoint_files"])
    state["target"] = target
    return state, int(payload["prime_limit"])


def initialize_writers(
    output_root: Path,
    target: int,
    resume: bool,
    accepted_rows_written: int,
    shard_size: int,
    sharded_state: dict[str, Any],
) -> tuple[AcceptedTermsWriter, dict[str, ShardedCsvWriter]]:
    data_dir = output_root / "data"
    analysis_dir = output_root / "analysis"
    data_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    accepted_writer = AcceptedTermsWriter(data_dir, target, resume, accepted_rows_written)

    writer_specs = {
        "odd-composite-witnesses": (ODD_WITNESS_COLUMNS, {5}),
        "even-admissible-statistics": (EVEN_STATS_COLUMNS, set()),
        "rejection-witnesses": (REJECTION_COLUMNS, set()),
    }
    writers: dict[str, ShardedCsvWriter] = {}
    for base_name, (headers, json_columns) in writer_specs.items():
        manifest = sharded_state.get(base_name)
        writer = ShardedCsvWriter(
            analysis_dir,
            base_name,
            headers,
            shard_size,
            json_columns=json_columns,
            resume_manifest=manifest,
        )
        if resume:
            writer.open_for_resume()
        writers[base_name] = writer

    return accepted_writer, writers


def backfill_missing_accepted_rows(
    accepted_writer: AcceptedTermsWriter,
    accepted_values: list[int],
) -> None:
    if accepted_writer.rows_written >= len(accepted_values):
        return

    last_even_term = None
    last_odd_term = None
    for index, value in enumerate(accepted_values, start=1):
        if index <= accepted_writer.rows_written:
            if value % 2 == 0:
                last_even_term = value
            else:
                last_odd_term = value
            continue

        if index == 1:
            accepted_writer.write_term(index, value, None)
        elif value % 2 == 0:
            accepted_writer.write_term(index, value, last_odd_term)
        else:
            accepted_writer.write_term(index, value, last_even_term)

        if value % 2 == 0:
            last_even_term = value
        else:
            last_odd_term = value


def flush_all_outputs(
    accepted_writer: AcceptedTermsWriter,
    sharded_writers: dict[str, ShardedCsvWriter],
) -> None:
    accepted_writer.flush()
    for writer in sharded_writers.values():
        writer.flush()


def snapshot_writer_state(sharded_writers: dict[str, ShardedCsvWriter]) -> dict[str, Any]:
    return {name: writer.snapshot() for name, writer in sharded_writers.items()}


def record_even_summary(summary: dict[str, Any], e: int, accepted: bool, matches_rule: bool, e_rule: bool) -> None:
    update_density_snapshots(summary, e)
    summary["even_total_candidates"] += 1
    if accepted:
        summary["even_accepted_count"] += 1
    if e_rule:
        summary["even_e_rule_count"] += 1
    if not matches_rule:
        summary["even_rule_mismatches"] += 1


def record_odd_summary(
    summary: dict[str, Any],
    state: dict[str, Any],
    row: list[Any],
    record_row: list[Any] | None,
) -> None:
    m = row[0]
    least_witness = row[1]
    witness_count = row[2]
    residue_6 = row[6]
    residue_30 = row[7]
    residue_210 = row[8]

    summary["odd_rows_analyzed"] += 1
    summary["witness_count_sum"] += witness_count
    summary["witness_count_rows"] += 1
    summary["witness_count_min"] = (
        witness_count
        if summary["witness_count_min"] is None
        else min(summary["witness_count_min"], witness_count)
    )
    summary["witness_count_max"] = (
        witness_count
        if summary["witness_count_max"] is None
        else max(summary["witness_count_max"], witness_count)
    )
    frequency = summary["witness_count_freq"]
    frequency[str(witness_count)] = frequency.get(str(witness_count), 0) + 1

    if witness_count == 1:
        summary["unique_witness_ms"].append(m)
    if witness_count <= 2:
        summary["witness_le_2_ms"].append(m)
    if witness_count <= 5:
        summary["hard_le_5_count"] += 1
    if witness_count <= 10:
        summary["hard_le_10_count"] += 1

    increment_counter(summary["total_mod_6"], residue_6)
    increment_counter(summary["total_mod_30"], residue_30)
    if witness_count <= 5:
        increment_counter(summary["hard_mod_6"], residue_6)
    if witness_count <= 10:
        increment_counter(summary["hard_mod_30"], residue_30)
        increment_counter(summary["hard_mod_210"], residue_210)

    if (
        summary["max_least_witness_row"] is None
        or least_witness > summary["max_least_witness_row"]["least_witness"]
    ):
        summary["max_least_witness_row"] = {
            "m": m,
            "least_witness": least_witness,
            "witness_count": witness_count,
        }

    if record_row is not None:
        summary["record_rows"].append(record_row)
        increment_counter(summary["record_mod_210"], m % 210)
        state["record_least_witness"] = max(state["record_least_witness"], least_witness)


def maybe_validate_baseline_prefix(
    accepted_values: list[int],
    baseline_terms: list[int],
    new_value: int,
) -> None:
    if not baseline_terms:
        return
    n = len(accepted_values)
    if n <= len(baseline_terms) and new_value != baseline_terms[n - 1]:
        raise SystemExit(
            f"Baseline prefix mismatch at term {n}: got {new_value}, expected {baseline_terms[n - 1]}."
        )


def milestone_rows_as_table(rows: list[dict[str, Any]]) -> list[list[Any]]:
    table: list[list[Any]] = []
    for row in rows:
        table.append([row[column] for column in MILESTONE_COLUMNS])
    return table


def density_rows_from_summary(summary: dict[str, Any], final_value: int) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for snapshot in summary["density_snapshots"]:
        rows.append(
            [
                snapshot["bound"],
                snapshot["even_total_candidates"],
                snapshot["accepted_evens"],
                snapshot["accepted_density"],
                snapshot["e_rule_candidates"],
                snapshot["e_rule_density"],
            ]
        )
    total = summary["even_total_candidates"]
    accepted = summary["even_accepted_count"]
    e_rule = summary["even_e_rule_count"]
    rows.append(
        [
            final_value,
            total,
            accepted,
            accepted / total if total else 0.0,
            e_rule,
            e_rule / total if total else 0.0,
        ]
    )
    return rows


def median_from_histogram(histogram: dict[str, int], total_rows: int) -> float:
    if total_rows == 0:
        return 0.0
    items = sorted((int(key), value) for key, value in histogram.items())
    target_low = (total_rows - 1) // 2
    target_high = total_rows // 2
    running = 0
    low_value = None
    high_value = None
    for value, count in items:
        next_running = running + count
        if low_value is None and target_low < next_running:
            low_value = value
        if high_value is None and target_high < next_running:
            high_value = value
            break
        running = next_running
    if low_value is None or high_value is None:
        raise RuntimeError("Unable to compute histogram median.")
    return (low_value + high_value) / 2


def top_counter_lines(counter: Counter[int], limit: int = 10) -> list[str]:
    if not counter:
        return ["None."]
    return [f"- residue {residue}: {count}" for residue, count in counter.most_common(limit)]


def residue_summary_table(
    total_counts: Counter[int],
    hard_counts: Counter[int],
    record_counts: Counter[int],
    modulus: int,
    hard_limit: int,
) -> str:
    residues = sorted(total_counts)
    lines = [
        f"### Modulo {modulus}",
        "",
        f"| residue | odd composites | witness_count <= {hard_limit} | least-witness records |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for residue in residues:
        lines.append(
            f"| {residue} | {total_counts[residue]} | {hard_counts[residue]} | {record_counts[residue]} |"
        )
    return "\n".join(lines)


def write_run_artifacts(
    output_root: Path,
    state: dict[str, Any],
    target: int,
    baseline_terms: list[int],
) -> None:
    analysis_dir = output_root / "analysis"
    checkpoint_dir = output_root / "data" / "checkpoints"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    summary = state["summary"]
    accepted_values = state["accepted_values"]
    odd_terms = [value for value in accepted_values if value % 2 == 1]
    witness_total_rows = summary["witness_count_rows"]
    witness_mean = summary["witness_count_sum"] / witness_total_rows if witness_total_rows else 0.0
    witness_median = median_from_histogram(summary["witness_count_freq"], witness_total_rows)
    max_row = summary["max_least_witness_row"]
    density_rows = density_rows_from_summary(summary, accepted_values[-1])
    prime_limit = state["prime_limit"]
    is_prime = build_sieve(prime_limit)
    peak_memory = 0.0 if state.get("deterministic_output") else max_rss_mebibytes()

    checkpoint_manifest = {
        "checkpoint_files": state["checkpoint_files"],
        "checkpoint_interval": state.get("checkpoint_interval"),
        "final_term_count": len(accepted_values),
        "final_value": accepted_values[-1],
        "next_candidate": state["current_candidate"],
        "milestone_columns": MILESTONE_COLUMNS,
        "milestone_rows": milestone_rows_as_table(summary["milestone_rows"]),
    }
    write_text(checkpoint_dir / "manifest.json", json.dumps(checkpoint_manifest, indent=2) + "\n")

    write_csv(
        analysis_dir / "least-witness-records.csv",
        LEAST_RECORD_COLUMNS,
        summary["record_rows"],
    )
    write_csv(
        analysis_dir / "milestones.csv",
        MILESTONE_COLUMNS,
        milestone_rows_as_table(summary["milestone_rows"]),
    )

    baseline_prefix_ok = (
        accepted_values[: min(len(accepted_values), len(baseline_terms))]
        == baseline_terms[: min(len(accepted_values), len(baseline_terms))]
        if baseline_terms
        else None
    )
    odd_composites_tested_above_25 = state["stats"]["odd_composite_candidates_tested"] - sum(
        1 for value in range(3, 26, 2) if not is_prime[value]
    )

    run_summary_lines = [
        "# Run Summary",
        "",
        f"- Completed first `{target}` terms: {bool_str(len(accepted_values) == target)}",
        f"- Largest computed index: `{len(accepted_values)}`",
        f"- Largest computed value: `{accepted_values[-1]}`",
        f"- Total runtime: `{format_seconds(state['elapsed_seconds'])}`",
        f"- Peak resident memory: `{peak_memory:.2f} MiB`",
        f"- Prime sieve limit used: `{state['prime_limit']}`",
        f"- Prime lookups: `{state['stats']['prime_lookups']}`",
        f"- Odd bitset witness queries: `{state['stats']['odd_bitset_queries']}`",
        f"- Odd terms encountered: `{odd_terms}`",
        "",
        "## Correctness Checks",
        "",
        f"- Prefix check against `OEIS-A068638.md`: `{accepted_values[:len(PREFIX)] == PREFIX}`",
        (
            f"- First `100000` terms agree with baseline: `{baseline_prefix_ok}`"
            if baseline_prefix_ok is not None
            else "- First `100000` terms agree with baseline: `n/a`"
        ),
        f"- All accepted terms distinct: `{len(accepted_values) == len(set(accepted_values))}`",
        f"- All accepted terms beyond `a(1)` composite: `{all(value == 1 or not is_prime[value] for value in accepted_values)}`",
        f"- Rejected candidates with recorded witness rows: `{state['stats']['rejected_candidates']}`",
        "",
        "## Spot Checks",
        "",
        "- `a(6) = 25` survived because `25 + 1 = 26`, `25 + 8 = 33`, `25 + 14 = 39`, `25 + 20 = 45`, and `25 + 24 = 49` are all composite.",
        f"- Final accepted term `a({len(accepted_values)}) = {accepted_values[-1]}` is even, with `{accepted_values[-1] + 1}` and `{accepted_values[-1] + 25}` both composite.",
        (
            f"- Largest least witness in the tested odd-composite range is `{max_row['least_witness']}` at `m = {max_row['m']}` with witness count `{max_row['witness_count']}`."
            if max_row is not None
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
        f"- Odd composite candidates above `25` tested: `{odd_composites_tested_above_25}`",
        f"- Minimum / median / mean / maximum witness counts: `{summary['witness_count_min']}` / `{witness_median}` / `{witness_mean:.3f}` / `{summary['witness_count_max']}`",
        f"- Maximum least witness: `{max_row['least_witness'] if max_row is not None else 'n/a'}`",
        f"- Unique-witness odd composites: `{len(summary['unique_witness_ms'])}`",
        f"- Odd composites with at most 2 witnesses: `{len(summary['witness_le_2_ms'])}`",
        f"- Odd composites with at most 5 witnesses: `{summary['hard_le_5_count']}`",
        f"- Odd composites with at most 10 witnesses: `{summary['hard_le_10_count']}`",
        "",
        "## Milestones",
        "",
        "| accepted terms | largest term | elapsed seconds | checkpoint | max least witness | count = 1 | count <= 2 | count <= 5 | count <= 10 | accepted-even density |",
        "| ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["milestone_rows"]:
        run_summary_lines.append(
            f"| {row['accepted_terms']} | {row['largest_term']} | {row['elapsed_seconds']:.6f} | {row['checkpoint_file']} | {row['max_least_witness']} | {row['witness_count_eq_1']} | {row['witness_count_le_2']} | {row['witness_count_le_5']} | {row['witness_count_le_10']} | {row['accepted_even_density']:.6f} |"
        )
    run_summary_lines.extend(
        [
            "",
            "## Even-Tail Density Snapshots",
            "",
            "| bound | even composite candidates | accepted evens | accepted density | E-rule candidates | E-rule density |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
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
        f"- Exhaustively tested odd composite candidates in the run range: `{odd_composites_tested_above_25}`",
        f"- Every tested odd composite `m > 25` had a recorded prime witness: `{bool_str(odd_composites_tested_above_25 == summary['odd_rows_analyzed'])}`",
        "",
        "## Least-Witness Function",
        "",
        (
            f"- Maximum least witness: `{max_row['least_witness']}` at `m = {max_row['m']}`"
            if max_row is not None
            else "- Maximum least witness: `n/a`"
        ),
        f"- Number of least-witness record setters: `{len(summary['record_rows'])}`",
        f"- First five least-witness record rows: `{summary['record_rows'][:5]}`",
        "",
        "## Sparse Odd-Composite Cases",
        "",
        f"- Witness count `= 1`: `{summary['unique_witness_ms']}`",
        f"- Witness count `<= 2`: `{summary['witness_le_2_ms'][:20]}`",
        f"- Witness count `<= 5`: `{summary['hard_le_5_count']}` cases",
        f"- Witness count `<= 10`: `{summary['hard_le_10_count']}` cases",
        "",
        "## Even Tail",
        "",
        f"- Accepted even terms beyond `25` agree with the `e+1` and `e+25` composite rule in every recorded case: `{bool_str(summary['even_rule_mismatches'] == 0)}`",
        f"- Final term `a({len(accepted_values)}) = {accepted_values[-1]}` satisfies `e+1` and `e+25` composite checks.",
        "",
        "## Interpretation",
        "",
        f"The {len(accepted_values)}-term run supports the working picture from `RESEARCH.md`: after the early odd transient `{{1, 25}}`, every later odd composite is blocked by at least one accepted even witness, while the even tail is completely governed by the `+1` and `+25` composite conditions throughout the tested range.",
    ]
    write_text(analysis_dir / "conjecture-evidence.md", "\n".join(conjecture_lines) + "\n")

    total_mod_6 = counter_from_mapping(summary["total_mod_6"])
    hard_mod_6 = counter_from_mapping(summary["hard_mod_6"])
    total_mod_30 = counter_from_mapping(summary["total_mod_30"])
    hard_mod_30 = counter_from_mapping(summary["hard_mod_30"])
    hard_mod_210 = counter_from_mapping(summary["hard_mod_210"])
    record_mod_210 = counter_from_mapping(summary["record_mod_210"])
    record_mod_6 = Counter(int(row[0]) % 6 for row in summary["record_rows"])
    record_mod_30 = Counter(int(row[0]) % 30 for row in summary["record_rows"])

    residue_lines = [
        "# Residue-Class Notes",
        "",
        f"- Odd composite witness rows analyzed: `{summary['odd_rows_analyzed']}`",
        f"- Least-witness record rows analyzed: `{len(summary['record_rows'])}`",
        "",
        residue_summary_table(total_mod_6, hard_mod_6, record_mod_6, 6, 5),
        "",
        residue_summary_table(total_mod_30, hard_mod_30, record_mod_30, 30, 10),
        "",
        "### Modulo 210",
        "",
        "Hard residues with witness count `<= 10`:",
        *top_counter_lines(hard_mod_210, limit=20),
        "",
        "Record-setting residues modulo `210`:",
        *top_counter_lines(record_mod_210, limit=20),
    ]
    write_text(analysis_dir / "residue-class-notes.md", "\n".join(residue_lines) + "\n")


def verify_results(
    state: dict[str, Any],
    sharded_writers: dict[str, ShardedCsvWriter],
    baseline_terms: list[int],
) -> list[str]:
    issues: list[str] = []
    accepted_values = state["accepted_values"]
    accepted_set = set(accepted_values)
    odd_terms = [value for value in accepted_values if value % 2 == 1]
    even_terms = [value for value in accepted_values if value % 2 == 0]
    prime_limit = max(state["prime_limit"], accepted_values[-1] + (max(odd_terms) if odd_terms else 0) + 25)
    is_prime = build_sieve(prime_limit)

    if accepted_values[: len(PREFIX)] != PREFIX:
        issues.append("Initial prefix does not match OEIS-A068638.md.")

    if baseline_terms and (
        accepted_values[: min(len(accepted_values), len(baseline_terms))]
        != baseline_terms[: min(len(accepted_values), len(baseline_terms))]
    ):
        issues.append("Accepted-term prefix does not match the preserved 100000-term baseline.")

    for value in accepted_values[1:]:
        if is_prime[value]:
            issues.append(f"Accepted term {value} is prime.")
            break

    if len(accepted_values) != len(accepted_set):
        issues.append("Accepted terms are not distinct.")

    for odd_term in odd_terms:
        for even_term in even_terms:
            if is_prime[odd_term + even_term]:
                issues.append(f"Prime sum found between accepted terms {odd_term} and {even_term}.")
                return issues
        if odd_term > 1 and is_prime[odd_term + odd_term]:
            issues.append(f"Unexpected prime self-sum at odd term {odd_term}.")
            return issues

    summary = state["summary"]
    if sharded_writers["rejection-witnesses"].manifest["total_rows"] != state["stats"]["rejected_candidates"]:
        issues.append("Rejection shard row count does not match rejected candidate count.")
    if sharded_writers["odd-composite-witnesses"].manifest["total_rows"] != summary["odd_rows_analyzed"]:
        issues.append("Odd witness shard row count does not match odd witness summary count.")
    if sharded_writers["even-admissible-statistics"].manifest["total_rows"] != summary["even_total_candidates"]:
        issues.append("Even admissibility shard row count does not match even candidate count.")
    if summary["even_rule_mismatches"] != 0:
        issues.append("Accepted even tail no longer matches the E-rule in every case.")

    return issues


def verify_shard_manifests(output_root: Path) -> list[str]:
    issues: list[str] = []
    analysis_dir = output_root / "analysis"
    for manifest_path in sorted(analysis_dir.glob("*.manifest.json")):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        total_rows = 0
        for shard in payload["shards"]:
            shard_path = analysis_dir / shard["file"]
            if not shard_path.exists():
                issues.append(f"Missing shard listed in manifest {manifest_path.name}: {shard['file']}")
                continue
            with gzip.open(shard_path, "rt", newline="", encoding="utf-8") as handle:
                row_count = sum(1 for _ in csv.reader(handle)) - 1
            if row_count != shard["rows"]:
                issues.append(
                    f"Shard row mismatch for {shard['file']}: manifest says {shard['rows']}, actual {row_count}."
                )
            total_rows += row_count
        if total_rows != payload["total_rows"]:
            issues.append(
                f"Manifest total mismatch for {manifest_path.name}: manifest says {payload['total_rows']}, actual {total_rows}."
            )
    return issues


def baseline_headline_counts(output_root: Path) -> dict[str, Any]:
    summary_path = output_root / "analysis" / "run-summary.md"
    if not summary_path.exists():
        return {}
    text = summary_path.read_text(encoding="utf-8")
    values: dict[str, Any] = {}
    for line in text.splitlines():
        if "Odd composite candidates above `25` tested:" in line:
            values["odd_tested"] = int(line.split("`")[3])
        elif "Unique-witness odd composites:" in line:
            values["unique"] = int(line.split("`")[3])
        elif "Odd composites with at most 2 witnesses:" in line:
            values["le2"] = int(line.split("`")[3])
        elif "Odd composites with at most 5 witnesses:" in line:
            values["le5"] = int(line.split("`")[3])
        elif "Odd composites with at most 10 witnesses:" in line:
            values["le10"] = int(line.split("`")[3])
    return values


def compute_sequence(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, ShardedCsvWriter]]:
    output_root = Path(args.output_root).resolve()
    checkpoint_dir = output_root / "data" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    milestones = parse_int_list(args.milestones) or DEFAULT_MILESTONES
    baseline_terms = load_baseline_terms(args.baseline_root)
    state, checkpoint_prime_limit = load_or_initialize_state(
        args.target,
        checkpoint_dir,
        args.resume,
        milestones,
    )
    state["checkpoint_interval"] = args.checkpoint_interval
    state["deterministic_output"] = args.deterministic_output
    prime_limit = max(checkpoint_prime_limit, args.prime_limit)

    accepted_values = state["accepted_values"]
    accepted_index_by_value, odd_terms, even_mask = build_runtime_state(accepted_values)
    last_even_term = max((value for value in accepted_values if value % 2 == 0), default=None)

    accepted_writer, sharded_writers = initialize_writers(
        output_root,
        args.target,
        args.resume,
        state["accepted_rows_written"],
        args.shard_size,
        state["sharded_writers"],
    )
    backfill_missing_accepted_rows(accepted_writer, accepted_values)
    state["accepted_rows_written"] = accepted_writer.rows_written
    state["sharded_writers"] = snapshot_writer_state(sharded_writers)

    is_prime = build_sieve(prime_limit)
    odd_prime_mask = build_odd_prime_mask(is_prime)
    start_time = time.perf_counter()
    completed = False

    try:
        while len(accepted_values) < args.target:
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
            accepted_this_iteration = False

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
                matches_rule = accepted == (e_plus_1_composite and e_plus_25_composite)
                even_row = [
                    current,
                    accepted,
                    e_plus_1_composite,
                    e_plus_25_composite,
                    matches_rule,
                    blocking_term,
                    prime_sum,
                ]
                sharded_writers["even-admissible-statistics"].write_row(even_row)
                record_even_summary(
                    state["summary"],
                    current,
                    accepted,
                    matches_rule,
                    e_plus_1_composite and e_plus_25_composite,
                )

                if accepted:
                    accepted_values.append(current)
                    accepted_index_by_value[current] = len(accepted_values)
                    even_mask |= 1 << (current // 2)
                    last_even_term = current
                    accepted_this_iteration = True
                    state["stats"]["accepted_candidates"] += 1
                    accepted_writer.write_term(len(accepted_values), current, odd_terms[-1])
                    state["accepted_rows_written"] = accepted_writer.rows_written
                    maybe_validate_baseline_prefix(accepted_values, baseline_terms, current)
                else:
                    state["stats"]["rejected_candidates"] += 1
                    state["stats"]["even_rejected_composites"] += 1
                    sharded_writers["rejection-witnesses"].write_row(
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
                    accepted_values.append(current)
                    accepted_index_by_value[current] = len(accepted_values)
                    odd_terms.append(current)
                    accepted_this_iteration = True
                    state["stats"]["accepted_candidates"] += 1
                    accepted_writer.write_term(len(accepted_values), current, last_even_term)
                    state["accepted_rows_written"] = accepted_writer.rows_written
                    maybe_validate_baseline_prefix(accepted_values, baseline_terms, current)
                else:
                    least_witness_index = (witness_mask & -witness_mask).bit_length() - 1
                    least_witness = 2 * least_witness_index
                    witness_count = witness_mask.bit_count()
                    record_flag = current > 25 and least_witness > state["record_least_witness"]
                    state["stats"]["rejected_candidates"] += 1
                    state["stats"]["odd_rejected_composites"] += 1

                    if current > 25:
                        odd_row = [
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
                        record_row = None
                        if record_flag:
                            previous = state["record_least_witness"]
                            record_row = [
                                current,
                                least_witness,
                                previous if previous >= 0 else None,
                                (least_witness - previous) if previous >= 0 else None,
                                witness_count,
                            ]
                        sharded_writers["odd-composite-witnesses"].write_row(odd_row)
                        record_odd_summary(state["summary"], state, odd_row, record_row)

                    sharded_writers["rejection-witnesses"].write_row(
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

            accepted_count = len(accepted_values)
            if accepted_this_iteration:
                milestone_checkpoint = state["checkpoint_files"][-1] if state["checkpoint_files"] else "n/a"
                milestone_elapsed = state["elapsed_seconds"] + measured_elapsed(
                    start_time,
                    args.deterministic_output,
                )
                if accepted_count % args.checkpoint_interval == 0 or accepted_count == args.target:
                    state["elapsed_seconds"] += measured_elapsed(start_time, args.deterministic_output)
                    milestone_elapsed = state["elapsed_seconds"]
                    state["current_candidate"] = next_composite(current + 1, is_prime)
                    flush_all_outputs(accepted_writer, sharded_writers)
                    state["sharded_writers"] = snapshot_writer_state(sharded_writers)
                    milestone_checkpoint = save_checkpoint(
                        state,
                        checkpoint_dir,
                        prime_limit,
                        args.checkpoint_interval,
                    )
                    if args.stop_after_checkpoints and state["stats"]["checkpoints_written"] >= args.stop_after_checkpoints:
                        maybe_record_milestone(
                            state["summary"],
                            accepted_count,
                            accepted_values[-1],
                            milestone_elapsed,
                            milestone_checkpoint,
                        )
                        raise ControlledStop("Stopped after requested checkpoint count.")
                    start_time = time.perf_counter()

                maybe_record_milestone(
                    state["summary"],
                    accepted_count,
                    accepted_values[-1],
                    milestone_elapsed,
                    milestone_checkpoint,
                )

            state["current_candidate"] = next_composite(current + 1, is_prime)
        completed = True
    finally:
        state["elapsed_seconds"] += measured_elapsed(start_time, args.deterministic_output)
        flush_all_outputs(accepted_writer, sharded_writers)
        accepted_writer.close()
        for writer in sharded_writers.values():
            if completed:
                writer.finalize()
            else:
                writer.close_unfinished()

    state["prime_limit"] = prime_limit
    state["sharded_writers"] = snapshot_writer_state(sharded_writers)
    return state, sharded_writers


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root).resolve()
    require_clean_output_root(output_root, args.resume)

    baseline_terms = load_baseline_terms(args.baseline_root)
    try:
        state, sharded_writers = compute_sequence(args)
    except ControlledStop:
        return 0

    issues = verify_results(state, sharded_writers, baseline_terms)
    issues.extend(verify_shard_manifests(output_root))
    if issues:
        raise SystemExit("\n".join(issues))

    write_run_artifacts(output_root, state, args.target, baseline_terms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
