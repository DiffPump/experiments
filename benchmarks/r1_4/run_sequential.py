#!/usr/bin/env python3
"""
Run R1.4 benchmark sequentially (DP4 + DP5 with eta=gamma=1, fixed).

No SLURM required: runs every (instance, config) pair one by one.
For SLURM, use gen_jobs.py + submit.sh instead.

Usage
-----
    python run_sequential.py \
        --instances-dir /path/to/miplib2017/mps \
        --results-dir   /path/to/results/r1_4 \
        [--solver scip|gurobi] [--seed 0] [--max-iters 1000] [--force]

Fixes eta=gamma=1 and sweeps lambda, beta, p for DP4 and DP5.
This separates the benefit of the feasibility loss from the eta*gamma relaxation.
See experiments/configs/r1_4.yaml for the full specification.

Grid: beta in {0.1, 0.3, 0.5, 0.7, 0.9}
      lam  in {0.1, 0.3, 0.5, 0.7, 0.9}
      p    in {1, 2}
      -> 50 configurations x 2 variants = 100 configs x N instances
"""

from __future__ import annotations

import argparse
import itertools
import subprocess
import sys
from pathlib import Path

# Grid — keep in sync with gen_jobs.py
# Ref: experiments/configs/r1_4.yaml
BETA_GRID = [0.1, 0.3, 0.5, 0.7, 0.9]
LAM_GRID  = [0.1, 0.3, 0.5, 0.7, 0.9]
P_GRID    = [1, 2]


def _label(variant: str, beta: float, lam: float, p: int) -> str:
    return f"{variant}_b{beta}_l{lam}_p{p}"


def _build_cmd(
    instance: Path,
    variant: str,
    beta: float,
    lam: float,
    p: int,
    json_dir: Path,
    solver: str,
    seed: int,
    max_iters: int,
) -> list[str]:
    cmd = [
        "diffpump", str(instance),
        "--json-dir",  str(json_dir),
        "--eta",       "1.0",
        "--gamma",     "1.0",
        "--beta",      str(beta),
        "--lam",       str(lam),
        "--p",         str(float(p)),
        "--q",         "2",
        "--eps",       "0.15",
        "--eps-feas",  "0.0",
        "--seed",      str(seed),
        "--max-iters", str(max_iters),
        "--solver",    solver,
    ]
    if variant == "DP5":
        cmd.append("--use-argmin-feas")
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run R1.4 benchmark sequentially (eta=gamma=1 grid search).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--instances-dir", required=True,
                    help="Directory containing *.mps instance files")
    ap.add_argument("--results-dir", required=True,
                    help="Root output directory (one subdir per config label)")
    ap.add_argument("--solver", default="scip", choices=["scip", "gurobi"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-iters", type=int, default=1000)
    ap.add_argument("--force", action="store_true",
                    help="Re-run even if output JSON already exists")
    args = ap.parse_args()

    instances_dir = Path(args.instances_dir)
    results_dir   = Path(args.results_dir)

    instances = sorted(instances_dir.glob("*.mps"))
    if not instances:
        print(f"Error: no .mps files found in {instances_dir}", file=sys.stderr)
        return 1

    grid = list(itertools.product(BETA_GRID, LAM_GRID, P_GRID))
    n_configs = len(grid) * 2  # DP4 + DP5
    total     = len(instances) * n_configs
    done      = 0

    print(f"Instances : {len(instances)}")
    print(f"Configs   : {n_configs}  ({len(BETA_GRID)} beta x {len(LAM_GRID)} lam x {len(P_GRID)} p x 2 variants)")
    print(f"Total jobs: {total}")
    print()

    n_errors = 0
    for inst in instances:
        for beta, lam, p in grid:
            for variant in ["DP4", "DP5"]:
                done += 1
                label    = _label(variant, beta, lam, p)
                json_dir = results_dir / label
                json_dir.mkdir(parents=True, exist_ok=True)
                out_file = json_dir / f"{inst.stem}.json"

                tag = f"[{done:>{len(str(total))}}/{total}] {label} {inst.name}"
                if out_file.exists() and not args.force:
                    print(f"  SKIP  {tag}")
                    continue

                print(f"  RUN   {tag}", flush=True)
                cmd = _build_cmd(inst, variant, beta, lam, p,
                                 json_dir, args.solver, args.seed, args.max_iters)
                rc = subprocess.run(cmd).returncode
                if rc != 0:
                    print(f"  WARN  diffpump exited {rc}", file=sys.stderr)
                    n_errors += 1

    print()
    print(f"Done — {n_errors} error(s).")
    return 0 if n_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
