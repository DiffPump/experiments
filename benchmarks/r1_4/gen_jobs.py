#!/usr/bin/env python3
"""
Generate jobs.csv for the R1.4 benchmark (Reviewer 1, R1.4).

Fixes η=γ=1 and sweeps λ, β, p for DP4 and DP5, separating the benefit of
the feasibility loss from the ηγ relaxation.

Usage
-----
    python gen_jobs.py \
        --instances-dir /scratch/$USER/miplib2017/mps \
        --results-dir   /scratch/$USER/r1_4 \
        [--solver scip|gurobi] [--seed 0] [--out jobs.csv]

Grid:
    β  ∈ {0.1, 0.3, 0.5, 0.7, 0.9}
    λ  ∈ {0.1, 0.3, 0.5, 0.7, 0.9}
    p  ∈ {1, 2}
    → 50 configurations per variant × 2 variants = 100 configs × N instances
"""

from __future__ import annotations

import argparse
import csv
import itertools
from pathlib import Path

BETA_GRID = [0.1, 0.3, 0.5, 0.7, 0.9]
LAM_GRID  = [0.1, 0.3, 0.5, 0.7, 0.9]
P_GRID    = [1, 2]

FIELDS = [
    "instance", "label", "json_dir",
    "eta", "gamma", "beta", "lam", "p", "q",
    "use_argmin_feas", "eps", "eps_feas",
    "seed", "max_iters", "solver",
]


def _label(variant: str, beta: float, lam: float, p: int) -> str:
    return f"{variant}_b{beta}_l{lam}_p{p}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances-dir", required=True)
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--solver", default="scip", choices=["scip", "gurobi"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-iters", type=int, default=1000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    instances_dir = Path(args.instances_dir)
    results_dir   = Path(args.results_dir)
    out_path = Path(args.out) if args.out else Path(__file__).parent / "jobs.csv"

    mps_files = sorted(instances_dir.glob("*.mps"))
    if not mps_files:
        raise SystemExit(f"No .mps files found in {instances_dir}")

    rows = []
    grid = list(itertools.product(BETA_GRID, LAM_GRID, P_GRID))

    for inst in mps_files:
        for beta, lam, p in grid:
            # DP4: linear feasibility loss (eq. 20), η=γ=1
            label_dp4 = _label("DP4", beta, lam, p)
            rows.append({
                "instance":        str(inst),
                "label":           label_dp4,
                "json_dir":        str(results_dir / label_dp4),
                "eta":             1.0,
                "gamma":           1.0,
                "beta":            beta,
                "lam":             lam,
                "p":               float(p),
                "q":               2,
                "use_argmin_feas": False,
                "eps":             0.15,
                "eps_feas":        0.0,
                "seed":            args.seed,
                "max_iters":       args.max_iters,
                "solver":          args.solver,
            })
            # DP5: argmin feasibility loss (eq. 21, q=2), η=γ=1
            label_dp5 = _label("DP5", beta, lam, p)
            rows.append({
                "instance":        str(inst),
                "label":           label_dp5,
                "json_dir":        str(results_dir / label_dp5),
                "eta":             1.0,
                "gamma":           1.0,
                "beta":            beta,
                "lam":             lam,
                "p":               float(p),
                "q":               2,
                "use_argmin_feas": True,
                "eps":             0.15,
                "eps_feas":        0.0,
                "seed":            args.seed,
                "max_iters":       args.max_iters,
                "solver":          args.solver,
            })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    n_configs = len(grid) * 2  # DP4 + DP5
    n = len(rows)
    print(f"Generated {n} jobs ({len(mps_files)} instances × {n_configs} configs)")
    print(f"  Grid: {len(BETA_GRID)} β × {len(LAM_GRID)} λ × {len(P_GRID)} p × 2 variants")
    print(f"Jobs CSV  → {out_path}")
    print(f"Submit with:  sbatch --array=0-{n - 1} submit.sh")


if __name__ == "__main__":
    main()
