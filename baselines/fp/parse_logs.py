"""
Parse FeasPumpCollection output logs into a CSV comparable to DiffPump results.

Usage
-----
    python parse_logs.py /path/to/logs
    python parse_logs.py /path/to/logs --out /path/to/results.csv

fp2 log format
--------------
Sections are introduced by a header line like [config], [results], etc.
Key-value pairs within a section look like:
    probName = blend2
    numSols = 1
    time = 0.121172317

Output columns (mirrors DiffPump's ResultRecord):
    instance_name, variant, success, n_iters, n_restarts,
    wall_time, lp_time, primal_bound, stage, seed
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


_RE_SECTION = re.compile(r"^\[([^\]]+)\]$")          # [section name]
_RE_ITEM    = re.compile(r"^([\w.]+)\s*=\s*(.+)$")   # key = value


def _parse_log(path: Path) -> dict:
    """Extract key metrics from one fp2 log file.

    Parses [config] for probName/runName/seed and [results] for all metrics.
    """
    config: dict[str, str] = {}
    results: dict[str, str] = {}
    current: dict[str, str] | None = None

    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        sec = _RE_SECTION.match(line)
        if sec:
            name = sec.group(1).strip()
            if name == "config":
                current = config
            elif name == "results":
                current = results
            else:
                current = None
            continue
        if current is not None:
            kv = _RE_ITEM.match(line)
            if kv:
                current[kv.group(1)] = kv.group(2).strip()

    instance_name = config.get("probName", path.stem)
    success = int(results.get("numSols", "0")) > 0

    def _float(d: dict, key: str) -> float:
        try:
            return float(d.get(key, "nan"))
        except ValueError:
            return float("nan")

    def _int(d: dict, key: str) -> int:
        try:
            return int(float(d.get(key, "0")))
        except ValueError:
            return 0

    return {
        "instance_name": instance_name,
        "variant":    config.get("runName", "fp2scip"),
        "success":    success,
        "n_iters":    _int(results,  "iterations"),
        "n_restarts": _int(results,  "perturbationCnt"),
        "wall_time":  _float(results, "time"),
        "lp_time":    _float(results, "totalLpTime"),
        "primal_bound": _float(results, "primalBound"),
        "stage":      _int(results,  "stage"),
        "seed":       _int(config,   "seed"),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Parse fp2 log files into CSV.")
    p.add_argument("logs_dir", help="Directory containing *.log files from SLURM jobs")
    p.add_argument(
        "--out",
        default=None,
        help="Output CSV path (default: ./results.csv)",
    )
    args = p.parse_args(argv)

    logs_dir = Path(args.logs_dir)
    if not logs_dir.is_dir():
        print(f"Error: {logs_dir} is not a directory", file=sys.stderr)
        return 1

    log_files = sorted(logs_dir.glob("*.log"))
    if not log_files:
        print(f"No .log files found in {logs_dir}", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else Path("results.csv")

    fields = [
        "instance_name", "variant", "success", "n_iters", "n_restarts",
        "wall_time", "lp_time", "primal_bound", "stage", "seed",
    ]

    rows = []
    n_ok = n_fail = n_parse_err = 0

    for log in log_files:
        try:
            row = _parse_log(log)
        except Exception as exc:  # noqa: BLE001
            print(f"  PARSE ERROR {log.name}: {exc}", file=sys.stderr)
            n_parse_err += 1
            continue

        rows.append(row)
        status = "OK  " if row["success"] else "FAIL"
        print(f"  {status}  iters={row['n_iters']:>5}  time={row['wall_time']:>8.2f}s"
              f"  {row['instance_name']}")
        if row["success"]:
            n_ok += 1
        else:
            n_fail += 1

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    print()
    print(f"Parsed {total} logs — solved: {n_ok}  failed: {n_fail}"
          f"  parse errors: {n_parse_err}")
    print(f"Results written to {out_path}")

    if total > 0:
        pct = 100 * n_ok / total
        print(f"Success rate: {pct:.1f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
