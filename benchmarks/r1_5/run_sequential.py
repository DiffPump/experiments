#!/usr/bin/env python3
"""
Run epsilon sensitivity analysis sequentially (DP5, eps sweep).

No SLURM required: runs every (instance, eps) pair one by one.
For SLURM, use gen_jobs.py + submit.sh instead.

Usage
-----
    python run_sequential.py \
        --instances-dir /path/to/miplib2017/mps \
        --results-dir   /path/to/results/r1_5 \
        [--solver scip|gurobi] [--seed 0] [--max-iters 1000] [--force]

Runs DP5 (the best variant) with the best Table 3 hyperparameters, sweeping
the soft-rounding parameter eps in {0.01, 0.05, 0.10, 0.15, 0.20, 0.30}.
This provides data to justify the eps=0.15 choice (Reviewer 1, R1.5).

See experiments/configs/r1_5.yaml for the full specification.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# DP5 best hyperparameters (Table 3 "All"), eps is swept.
# Ref: experiments/configs/r1_5.yaml
EPS_VALUES = [0.01, 0.05, 0.10, 0.15, 0.20, 0.30]

DP5_PARAMS = dict(
    eta=0.5, gamma=0.5, beta=0.9, lam=0.9, p=2.0, q=2,
    use_argmin_feas=True, eps_feas=0.0,
)


def _label(eps: float) -> str:
    return f"DP5_eps{eps:.2f}".replace(".", "")


def _build_cmd(
    instance: Path,
    eps: float,
    json_dir: Path,
    solver: str,
    seed: int,
    max_iters: int,
) -> list[str]:
    p = DP5_PARAMS
    cmd = [
        "diffpump", str(instance),
        "--json-dir",  str(json_dir),
        "--eta",       str(p["eta"]),
        "--gamma",     str(p["gamma"]),
        "--beta",      str(p["beta"]),
        "--lam",       str(p["lam"]),
        "--p",         str(p["p"]),
        "--q",         str(p["q"]),
        "--eps",       str(eps),
        "--eps-feas",  str(p["eps_feas"]),
        "--seed",      str(seed),
        "--max-iters", str(max_iters),
        "--solver",    solver,
        "--use-argmin-feas",
    ]
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run epsilon sensitivity analysis sequentially.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--instances-dir", required=True,
                    help="Directory containing *.mps instance files")
    ap.add_argument("--results-dir", required=True,
                    help="Root output directory (one subdir per eps value)")
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

    total = len(instances) * len(EPS_VALUES)
    done  = 0

    print(f"Instances : {len(instances)}")
    print(f"eps values: {EPS_VALUES}")
    print(f"Total jobs: {total}")
    print()

    n_errors = 0
    for inst in instances:
        for eps in EPS_VALUES:
            done += 1
            label    = _label(eps)
            json_dir = results_dir / label
            json_dir.mkdir(parents=True, exist_ok=True)
            out_file = json_dir / f"{inst.stem}.json"

            tag = f"[{done:>{len(str(total))}}/{total}] eps={eps:.2f} {inst.name}"
            if out_file.exists() and not args.force:
                print(f"  SKIP  {tag}")
                continue

            print(f"  RUN   {tag}", flush=True)
            cmd = _build_cmd(inst, eps, json_dir, args.solver, args.seed, args.max_iters)
            rc = subprocess.run(cmd).returncode
            if rc != 0:
                print(f"  WARN  diffpump exited {rc}", file=sys.stderr)
                n_errors += 1

    print()
    print(f"Done — {n_errors} error(s).")
    return 0 if n_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
