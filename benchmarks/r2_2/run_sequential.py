#!/usr/bin/env python3
"""
Run Table 2 benchmark sequentially (FP + DP1-DP5).

No SLURM required: runs every (instance, variant) pair one by one.
For SLURM, use gen_jobs.py + submit.sh instead.

Usage
-----
    python run_sequential.py \
        --instances-dir /path/to/miplib2017/mps \
        --results-dir   /path/to/results/r2_2 \
        [--solver scip|gurobi] [--seed 0] [--max-iters 1000] [--force]

Hyperparameters are the "All" best values from Table 3 of the paper.
See experiments/configs/r2_2.yaml for the full specification.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Table 3 "All" best hyperparameters — keep in sync with gen_jobs.py
# Ref: experiments/configs/r2_2.yaml
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


def _build_cmd(
    instance: Path,
    v: dict,
    json_dir: Path,
    solver: str,
    seed: int,
    max_iters: int,
) -> list[str]:
    cmd = [
        "diffpump", str(instance),
        "--json-dir",  str(json_dir),
        "--eta",       str(v["eta"]),
        "--gamma",     str(v["gamma"]),
        "--beta",      str(v["beta"]),
        "--lam",       str(v["lam"]),
        "--p",         str(v["p"]),
        "--q",         str(v["q"]),
        "--eps",       str(v["eps"]),
        "--eps-feas",  str(v["eps_feas"]),
        "--seed",      str(seed),
        "--max-iters", str(max_iters),
        "--solver",    solver,
    ]
    if v["use_argmin_feas"]:
        cmd.append("--use-argmin-feas")
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run Table 2 benchmark sequentially.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--instances-dir", required=True,
                    help="Directory containing *.mps instance files")
    ap.add_argument("--results-dir", required=True,
                    help="Root output directory (one subdir per variant)")
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

    total = len(instances) * len(VARIANTS)
    done  = 0
    print(f"Instances : {len(instances)}")
    print(f"Variants  : {len(VARIANTS)}")
    print(f"Total jobs: {total}")
    print()

    n_errors = 0
    for inst in instances:
        for v in VARIANTS:
            done += 1
            json_dir = results_dir / v["label"]
            json_dir.mkdir(parents=True, exist_ok=True)
            out_file = json_dir / f"{inst.stem}.json"

            tag = f"[{done:>{len(str(total))}}/{total}] {v['label']:<4} {inst.name}"
            if out_file.exists() and not args.force:
                print(f"  SKIP  {tag}")
                continue

            print(f"  RUN   {tag}", flush=True)
            cmd = _build_cmd(inst, v, json_dir, args.solver, args.seed, args.max_iters)
            rc = subprocess.run(cmd).returncode
            if rc != 0:
                print(f"  WARN  diffpump exited {rc}", file=sys.stderr)
                n_errors += 1

    print()
    print(f"Done — {n_errors} error(s).")
    print(f"Aggregate with:")
    print(f"  python aggregate.py --results-dir {results_dir}")
    return 0 if n_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
