#!/usr/bin/env python3
"""
Aggregate DiffPump JSON result files into a single CSV.

Works for all three benchmarks (r2_2, r1_4, r1_5).
Each benchmark writes per-instance JSON files into labelled subdirectories;
this script walks the whole results tree and collects every JSON it finds.

Usage
-----
    # Aggregate one benchmark
    python parse_jsons.py \
        --results-dir /path/to/results/jsons \
        --out results.csv

    # Aggregate multiple benchmarks into one file
    python parse_jsons.py \
        --results-dir /path/to/results/jsons/run1 /path/to/results/jsons/run2 \
        --out combined.csv

    # Dry-run: print summary only, no CSV written
    python parse_jsons.py \
        --results-dir /path/to/results/jsons/run1 \
        --dry-run

Expected directory structure
-----------------------------
    <results-dir>/
        <label>/                  e.g. FP, DP1, DP5_eps015, DP4_b0.1_l0.3_p2
            <instance_name>.json
            ...

JSON fields written by the diffpump CLI
----------------------------------------
    instance_name, solver, success, timed_out,
    n_iters, n_restarts, restart_ratio,
    wall_time, lp_time,
    eta, gamma, beta, lam, p, q,
    use_argmin_feas, eps_soft, eps_feas, seed
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

# Column order in the output CSV.
FIELDS = [
    "label",
    "instance_name",
    "success",
    "timed_out",
    "n_iters",
    "n_restarts",
    "restart_ratio",
    "wall_time",
    "lp_time",
    "seed",
    "eta",
    "gamma",
    "beta",
    "lam",
    "p",
    "q",
    "use_argmin_feas",
    "eps_soft",
    "eps_feas",
    "solver",
]


def _parse_json(path: Path, label: str) -> dict:
    data = json.loads(path.read_text())

    def _float(key: str) -> float:
        try:
            return float(data.get(key, math.nan))
        except (TypeError, ValueError):
            return math.nan

    def _int(key: str, default: int = 0) -> int:
        try:
            return int(data.get(key, default))
        except (TypeError, ValueError):
            return default

    return {
        "label":           label,
        "instance_name":   data.get("instance_name", path.stem),
        "success":         bool(data.get("success", False)),
        "timed_out":       bool(data.get("timed_out", False)),
        "n_iters":         _int("n_iters"),
        "n_restarts":      _int("n_restarts"),
        "restart_ratio":   _float("restart_ratio"),
        "wall_time":       _float("wall_time"),
        "lp_time":         _float("lp_time"),
        "seed":            _int("seed"),
        "eta":             _float("eta"),
        "gamma":           _float("gamma"),
        "beta":            _float("beta"),
        "lam":             _float("lam"),
        "p":               _float("p"),
        "q":               _int("q", default=2),
        "use_argmin_feas": bool(data.get("use_argmin_feas", False)),
        "eps_soft":        _float("eps_soft"),
        "eps_feas":        _float("eps_feas"),
        "solver":          data.get("solver", ""),
    }


def _collect(results_dir: Path) -> list[dict]:
    """Walk results_dir; each immediate subdir is a label, each *.json inside is one run."""
    rows: list[dict] = []
    n_errors = 0

    subdirs = sorted(d for d in results_dir.iterdir() if d.is_dir())
    if not subdirs:
        print(f"  Warning: no subdirectories in {results_dir}", file=sys.stderr)
        return rows

    for subdir in subdirs:
        label      = subdir.name
        json_files = sorted(subdir.glob("*.json"))
        if not json_files:
            print(f"  Warning: no JSON files in {subdir}", file=sys.stderr)
            continue

        n_ok = n_fail = 0
        for jf in json_files:
            try:
                row = _parse_json(jf, label)
                rows.append(row)
                if row["success"]:
                    n_ok += 1
                else:
                    n_fail += 1
            except Exception as exc:
                print(f"  PARSE ERROR {jf}: {exc}", file=sys.stderr)
                n_errors += 1

        total = n_ok + n_fail
        pct   = 100 * n_ok / total if total else 0.0
        print(f"  {label:<30}  {total:>4} instances  solved {n_ok:>4} ({pct:5.1f}%)")

    if n_errors:
        print(f"\n  {n_errors} parse error(s) — check stderr above.", file=sys.stderr)

    return rows


def _print_summary(rows: list[dict]) -> None:
    from collections import defaultdict
    by_label: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_label[r["label"]].append(r)

    header = (
        f"{'Label':<32}  {'N':>4}  {'Solved':>6}  {'Solved%':>7}  "
        f"{'AvgIters':>8}  {'AvgWall(s)':>10}"
    )
    sep = "-" * len(header)
    print()
    print(header)
    print(sep)
    for label in sorted(by_label):
        group  = by_label[label]
        n      = len(group)
        n_ok   = sum(1 for r in group if r["success"])
        iters  = sum(r["n_iters"] for r in group) / n if n else 0.0
        wall   = sum(r["wall_time"] for r in group) / n if n else 0.0
        pct    = 100 * n_ok / n if n else 0.0
        print(f"{label:<32}  {n:>4}  {n_ok:>6}  {pct:>7.1f}  {iters:>8.1f}  {wall:>10.3f}")
    print(sep)
    n_total = len(rows)
    n_ok    = sum(1 for r in rows if r["success"])
    iters   = sum(r["n_iters"] for r in rows) / n_total if n_total else 0.0
    wall    = sum(r["wall_time"] for r in rows) / n_total if n_total else 0.0
    pct     = 100 * n_ok / n_total if n_total else 0.0
    print(f"{'TOTAL':<32}  {n_total:>4}  {n_ok:>6}  {pct:>7.1f}  {iters:>8.1f}  {wall:>10.3f}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Aggregate DiffPump JSON results into a CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        "--results-dir", nargs="+", required=True,
        help="One or more benchmark result directories (each contains label subdirs).",
    )
    ap.add_argument(
        "--out", default=None,
        help="Output CSV path. Default: results.csv next to this script.",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Print summary only; do not write a CSV.",
    )
    args = ap.parse_args()

    all_rows: list[dict] = []
    for d in args.results_dir:
        results_dir = Path(d)
        if not results_dir.is_dir():
            print(f"Error: {results_dir} is not a directory.", file=sys.stderr)
            return 1
        print(f"\n{results_dir}/")
        all_rows.extend(_collect(results_dir))

    if not all_rows:
        print("\nNo results found.", file=sys.stderr)
        return 1

    _print_summary(all_rows)

    if args.dry_run:
        print("Dry-run — no CSV written.")
        return 0

    out_path = Path(args.out) if args.out else Path(__file__).parent / "results.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"CSV -> {out_path}  ({len(all_rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
