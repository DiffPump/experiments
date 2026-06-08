#!/usr/bin/env python3
"""
Generate jobs.csv for the Table 2 benchmark (FP + DP1–DP5).

Usage
-----
    python gen_jobs.py \
        --instances-dir /scratch/user/miplib2017/mps \
        --results-dir   /scratch/user/r2_2 \
        [--solver scip|gurobi] [--seed 0] [--out jobs.csv]

Produces jobs.csv — one row per (instance, variant).
Prints the recommended #SBATCH --array range.

Hyperparameters are the "All" best values from Table 3 of the paper.
"""

from __future__ import annotations

import argparse
import csv
import itertools
from pathlib import Path

# Table 3 "All" best hyperparameters for each variant.
# DP3: feasibility loss only → beta=0, lam=1.  η and γ from Table 3.
VARIANTS = [
    dict(label="FP",
         eta=1.0, gamma=1.0, beta=1.0, lam=0.0, p=1.0, q=2,
         use_argmin_feas=False, eps=0.15, eps_feas=0.0),
    dict(label="DP1",
         eta=0.55, gamma=0.95, beta=1.0, lam=0.0, p=1.0, q=2,
         use_argmin_feas=False, eps=0.15, eps_feas=0.0),
    dict(label="DP2",
         eta=0.8, gamma=0.65, beta=1.0, lam=0.0, p=2.0, q=2,
         use_argmin_feas=False, eps=0.15, eps_feas=0.0),
    dict(label="DP3",
         eta=0.45, gamma=0.9, beta=0.0, lam=1.0, p=1.0, q=2,
         use_argmin_feas=False, eps=0.15, eps_feas=0.0),
    dict(label="DP4",
         eta=0.6, gamma=0.7, beta=0.3, lam=0.1, p=2.0, q=2,
         use_argmin_feas=False, eps=0.15, eps_feas=0.0),
    dict(label="DP5",
         eta=0.5, gamma=0.5, beta=0.9, lam=0.9, p=2.0, q=2,
         use_argmin_feas=True, eps=0.15, eps_feas=0.0),
]

FIELDS = [
    "instance", "label", "json_dir",
    "eta", "gamma", "beta", "lam", "p", "q",
    "use_argmin_feas", "eps", "eps_feas",
    "seed", "max_iters", "solver",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances-dir", required=True,
                    help="Directory containing *.mps instance files")
    ap.add_argument("--results-dir", required=True,
                    help="Root directory for JSON output (one subdir per variant)")
    ap.add_argument("--solver", default="scip", choices=["scip", "gurobi"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-iters", type=int, default=1000)
    ap.add_argument("--out", default=None,
                    help="Output jobs CSV (default: <this_dir>/jobs.csv)")
    args = ap.parse_args()

    instances_dir = Path(args.instances_dir)
    results_dir   = Path(args.results_dir)
    out_path = Path(args.out) if args.out else Path(__file__).parent / "jobs.csv"

    mps_files = sorted(instances_dir.glob("*.mps"))
    if not mps_files:
        raise SystemExit(f"No .mps files found in {instances_dir}")

    rows = []
    for inst in mps_files:
        for v in VARIANTS:
            json_dir = str(results_dir / v["label"])
            row = {
                "instance":        str(inst),
                "label":           v["label"],
                "json_dir":        json_dir,
                "eta":             v["eta"],
                "gamma":           v["gamma"],
                "beta":            v["beta"],
                "lam":             v["lam"],
                "p":               v["p"],
                "q":               v["q"],
                "use_argmin_feas": v["use_argmin_feas"],
                "eps":             v["eps"],
                "eps_feas":        v["eps_feas"],
                "seed":            args.seed,
                "max_iters":       args.max_iters,
                "solver":          args.solver,
            }
            rows.append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    n = len(rows)
    print(f"Generated {n} jobs ({len(mps_files)} instances × {len(VARIANTS)} variants)")
    print(f"Jobs CSV  → {out_path}")
    print(f"Submit with:  sbatch --array=0-{n - 1} submit.sh")


if __name__ == "__main__":
    main()
