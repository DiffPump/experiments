#!/usr/bin/env python3
"""
Generate jobs.csv for the epsilon sensitivity analysis (Reviewer 1, R1.5).

Runs DP5 with the best Table 3 hyperparameters, sweeping the soft-rounding
parameter eps in {0.01, 0.05, 0.10, 0.15, 0.20, 0.30}.

Usage
-----
    python gen_jobs.py \
        --instances-dir /scratch/$USER/miplib2017/mps \
        --results-dir   /scratch/$USER/r1_5 \
        [--solver scip|gurobi] [--seed 0] [--out jobs.csv]

Produces jobs.csv — one row per (instance, eps).
Prints the recommended #SBATCH --array range.

See experiments/configs/r1_5.yaml for the full specification.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

# Ref: experiments/configs/r1_5.yaml
EPS_VALUES = [0.01, 0.05, 0.10, 0.15, 0.20, 0.30]

DP5_PARAMS = dict(
    eta=0.5, gamma=0.5, beta=0.9, lam=0.9, p=2.0, q=2,
    use_argmin_feas=True, eps_feas=0.0,
)

FIELDS = [
    "instance", "label", "json_dir",
    "eta", "gamma", "beta", "lam", "p", "q",
    "use_argmin_feas", "eps", "eps_feas",
    "seed", "max_iters", "solver",
]


def _label(eps: float) -> str:
    return f"DP5_eps{eps:.2f}".replace(".", "")


def main() -> None:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--instances-dir", required=True,
                    help="Directory containing *.mps instance files")
    ap.add_argument("--results-dir", required=True,
                    help="Root directory for JSON output (one subdir per eps value)")
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

    p = DP5_PARAMS
    rows = []
    for inst in mps_files:
        for eps in EPS_VALUES:
            label    = _label(eps)
            json_dir = str(results_dir / label)
            rows.append({
                "instance":        str(inst),
                "label":           label,
                "json_dir":        json_dir,
                "eta":             p["eta"],
                "gamma":           p["gamma"],
                "beta":            p["beta"],
                "lam":             p["lam"],
                "p":               p["p"],
                "q":               p["q"],
                "use_argmin_feas": p["use_argmin_feas"],
                "eps":             eps,
                "eps_feas":        p["eps_feas"],
                "seed":            args.seed,
                "max_iters":       args.max_iters,
                "solver":          args.solver,
            })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    n = len(rows)
    print(f"Generated {n} jobs ({len(mps_files)} instances x {len(EPS_VALUES)} eps values)")
    print(f"Jobs CSV  -> {out_path}")
    print(f"Submit with:  sbatch --array=0-{n - 1} submit.sh")


if __name__ == "__main__":
    main()
