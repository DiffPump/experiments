#!/usr/bin/env python3
"""
Aggregate Table 2 benchmark results into a CSV + paper-style summary.

Usage
-----
    python aggregate.py \
        --results-dir /scratch/$USER/r2_2 \
        --out experiments/benchmarks/r2_2/r2_2_results.csv

Expects:
    <results-dir>/
        FP/     ← per-instance JSON files
        DP1/
        DP2/
        DP3/
        DP4/
        DP5/

Produces:
    r2_2_results.csv  — one row per (instance, label) with all JSON fields
    stdout              — summary table matching Table 2 of the paper
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

VARIANT_ORDER = ["FP", "DP1", "DP2", "DP3", "DP4", "DP5"]

FIELDS = [
    "label", "instance_name", "solver", "success", "timed_out",
    "n_iters", "n_restarts", "restart_ratio",
    "wall_time", "lp_time",
    "eta", "gamma", "beta", "lam", "p", "q",
    "use_argmin_feas", "eps_soft", "eps_feas", "seed",
]


def read_dir(json_dir: Path, label: str) -> list[dict]:
    rows = []
    for jf in sorted(json_dir.glob("*.json")):
        try:
            data = json.loads(jf.read_text())
            data["label"] = label
            rows.append(data)
        except Exception as exc:
            print(f"  Warning: could not read {jf}: {exc}", file=sys.stderr)
    return rows


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {}
    n           = len(rows)
    n_fail      = sum(1 for r in rows if not r.get("success", False))
    total_iters = sum(r.get("n_iters", 0) for r in rows)
    total_rst   = sum(r.get("n_restarts", 0) for r in rows)
    total_wall  = sum(r.get("wall_time", 0.0) for r in rows)
    return {
        "n":           n,
        "fail_pct":    100.0 * n_fail / n,
        "total_iters": total_iters,
        "restart_pct": 100.0 * total_rst / max(total_iters, 1),
        "mean_wall_s": total_wall / n,
    }


def print_summary_table(by_label: dict[str, list[dict]]) -> None:
    header = f"{'Variant':<8}  {'Fail%':>6}  {'Iters':>8}  {'Restart%':>9}  {'AvgTime(s)':>10}"
    print()
    print(header)
    print("-" * len(header))
    all_rows = []
    for label in VARIANT_ORDER:
        rows = by_label.get(label, [])
        if not rows:
            continue
        s = summarize(rows)
        all_rows.extend(rows)
        print(f"{label:<8}  {s['fail_pct']:>6.2f}  {s['total_iters']:>8d}"
              f"  {s['restart_pct']:>9.2f}  {s['mean_wall_s']:>10.3f}")
    # Any extra labels not in the canonical order
    for label in sorted(by_label):
        if label not in VARIANT_ORDER:
            rows = by_label[label]
            s = summarize(rows)
            all_rows.extend(rows)
            print(f"{label:<8}  {s['fail_pct']:>6.2f}  {s['total_iters']:>8d}"
                  f"  {s['restart_pct']:>9.2f}  {s['mean_wall_s']:>10.3f}")
    print("-" * len(header))
    if all_rows:
        s = summarize(all_rows)
        print(f"{'ALL':<8}  {s['fail_pct']:>6.2f}  {s['total_iters']:>8d}"
              f"  {s['restart_pct']:>9.2f}  {s['mean_wall_s']:>10.3f}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True,
                    help="Root directory containing per-label JSON subdirs")
    ap.add_argument("--out", default=None,
                    help="Output CSV path (default: <script_dir>/r2_2_results.csv)")
    args = ap.parse_args()

    results_dir = Path(args.results_dir)
    out_path    = Path(args.out) if args.out else Path(__file__).parent / "r2_2_results.csv"

    if not results_dir.is_dir():
        print(f"Error: {results_dir} is not a directory", file=sys.stderr)
        return 1

    by_label: dict[str, list[dict]] = {}
    all_rows: list[dict] = []

    for subdir in sorted(results_dir.iterdir()):
        if not subdir.is_dir():
            continue
        rows = read_dir(subdir, label=subdir.name)
        if rows:
            by_label[subdir.name] = rows
            all_rows.extend(rows)
            print(f"  {subdir.name:<8} {len(rows):>5} records")

    if not all_rows:
        print("No JSON files found.", file=sys.stderr)
        return 1

    # Write combined CSV
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        # Use union of all keys found (some may have extra fields)
        all_keys = FIELDS + [k for k in all_rows[0] if k not in FIELDS]
        writer = csv.DictWriter(fh, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print(f"\nTotal: {len(all_rows)} records across {len(by_label)} variants")
    print(f"CSV → {out_path}")

    print_summary_table(by_label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
