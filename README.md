# Experiments — Differentiable Feasibility Pump

Reproducibility package for the Mathematical Programming journal revision of
**The Differentiable Feasibility Pump** (Cacciola, Emine, Forel, Frangioni, Lodi).

This directory contains everything needed to reproduce the computational results
that address the reviewers' requests:

| Directory | Reviewer comment | What it does |
|---|---|---|
| `baselines/fp/` | R2.2 | Build and run FeasPumpCollection (Mexi et al.) as external baseline |
| `benchmarks/r2_2/` | R2.2 | Main comparison: FP reimplementation vs DP1–DP5 |
| `benchmarks/r1_4/` | R1.4 | Ablation: fix η=γ=1, sweep λ, β, p for DP4 and DP5 |
| `benchmarks/r1_5/` | R1.5 | Sensitivity analysis: sweep ε ∈ {0.01, 0.05, 0.10, 0.15, 0.20, 0.30} for DP5 |

Every benchmark has **two run modes**:
- **Sequential** (`run_sequential.py`) — no scheduler needed, runs jobs one by one. Use this on a workstation or when you have a few hundred instances.
- **SLURM array** (`gen_jobs.py` + `submit.sh`) — parallelises over a cluster. Use this on Compute Canada or any SLURM system for the full 851-instance run.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Directory layout](#2-directory-layout)
3. [Step 0 — Download instances](#3-step-0--download-instances)
4. [Part A — FP baseline (R2.2)](#4-part-a--fp-baseline-r22)
   - [A.1 Build](#a1-build)
   - [A.2 Run sequentially](#a2-run-sequentially)
   - [A.3 Run with SLURM](#a3-run-with-slurm)
   - [A.4 Parse results](#a4-parse-results)
5. [Part B — DiffPump setup](#5-part-b--diffpump-setup)
6. [Part C — DiffPump benchmarks](#6-part-c--diffpump-benchmarks)
   - [C.1 r2_2 — Main comparison](#c1-r2_2--main-comparison)
   - [C.2 r1_4 — Ablation η=γ=1](#c2-r1_4--ablation-γ1)
   - [C.3 r1_5 — ε sensitivity](#c3-r1_5--ε-sensitivity)
7. [Collecting DiffPump results](#7-collecting-diffpump-results)
8. [Adapting submit.sh for SLURM](#8-adapting-submitsh-for-slurm)
9. [File reference](#9-file-reference)

---

## 1. Prerequisites

### FP baseline (`baselines/fp/`)

| Requirement | Notes |
|---|---|
| C++ compiler (GCC ≥ 11) | GCC 15 patch is applied automatically by `build.sh` |
| CMake ≥ 3.16 | |
| Git | to clone SoPlex, SCIP, FeasPumpCollection |
| Boost (headers) | used by FeasPumpCollection |
| Internet access | first run only, to clone repos |

On **Compute Canada**, load these modules before building:

```bash
module load StdEnv/2023 cmake gcc boost
```

### DiffPump benchmarks (`benchmarks/`)

| Requirement | Notes |
|---|---|
| Python ≥ 3.10 | |
| One of: Gurobi ≥ 10 **or** SCIP ≥ 9 | must be installed and licensed |
| Internet access | first run only, to install diffpump from PyPI |

On **Compute Canada**:

```bash
module load StdEnv/2023 python gurobi   # or: python scip
```

---

## 2. Directory layout

```
experiments/
├── instances/
│   ├── instances.csv          # 851 MIPLIB 2017 instance names + metadata
│   ├── sample.csv             # 10 small instances for a quick smoke test
│   └── download.py            # downloads .mps.gz from miplib.zib.de and decompresses
│
├── baselines/
│   └── fp/
│       ├── build.sh           # builds SoPlex + SCIP + FeasPumpCollection from source
│       ├── fp.cfg             # fp2 settings (solver=scip, timeLimit=3600, seed=0)
│       ├── run.sh             # runs fp2 on a set of instances (sequential or parallel)
│       ├── submit.sh          # SLURM array template for fp2
│       └── parse_logs.py      # parses fp2 .log files into a CSV
│
└── benchmarks/
    ├── parse_jsons.py         # aggregates DiffPump JSON results from any benchmark → CSV
    │
    ├── r2_2/                  # Main comparison (addresses R2.2)
    │   ├── run_sequential.py  # runs FP + DP1–DP5 on all instances, one by one
    │   ├── gen_jobs.py        # generates jobs.csv for the SLURM array
    │   ├── submit.sh          # SLURM array worker for r2_2
    │   └── aggregate.py       # collects r2_2 JSONs → CSV + paper-style table
    │
    ├── r1_4/                  # Ablation η=γ=1 (addresses R1.4)
    │   ├── run_sequential.py  # runs DP4/DP5 grid sequentially
    │   ├── gen_jobs.py        # generates jobs.csv for the SLURM array
    │   └── submit.sh          # SLURM array worker for r1_4
    │
    └── r1_5/                  # ε sensitivity (addresses R1.5)
        ├── run_sequential.py  # runs DP5 with 6 ε values sequentially
        ├── gen_jobs.py        # generates jobs.csv for the SLURM array
        └── submit.sh          # SLURM array worker for r1_5
```

---

## 3. Step 0 — Download instances

All benchmarks use the **MIPLIB 2017 collection set** (851 instances).
The file `instances/instances.csv` lists every instance name, its size, and its type
(BP = binary, MBP = mixed-binary, MIP = general integer).

### Download all 851 instances

```bash
python experiments/instances/download.py \
    experiments/instances/instances.csv \
    --out /path/to/miplib2017/mps \
    --jobs 4
```

This downloads each `<name>.mps.gz` from `miplib.zib.de`, decompresses it, and writes
`<name>.mps` to the output directory. Already-downloaded files are skipped.
Use `--jobs N` to download in parallel with N threads (default: 1).

### Quick smoke test (10 small instances)

If you only want to verify the pipeline before running the full set:

```bash
python experiments/instances/download.py \
    experiments/instances/sample.csv \
    --out /path/to/miplib2017/mps
```

The 10 instances in `sample.csv` are small enough to finish in a few minutes on a laptop.

---

## 4. Part A — FP baseline (R2.2)

The FP baseline runs **FeasPumpCollection** (Mexi et al., [32]), the publicly available
reference implementation. This answers R2.2.

### A.1 Build

The build script compiles SoPlex, SCIP, and FeasPumpCollection from source and installs
everything under `~/software/`. Already-built steps are detected and skipped automatically.

```bash
# Default: 4 parallel build jobs, installs to ~/software/
bash experiments/baselines/fp/build.sh

# Custom number of build threads
JOBS=8 bash experiments/baselines/fp/build.sh
```

On **Compute Canada**, first start an interactive session:

```bash
salloc --time=2:00:00 --mem=8G --cpus-per-task=4 --account=def-XXXX
module load StdEnv/2023 cmake gcc boost
bash experiments/baselines/fp/build.sh
```

After a successful build, the binary is at:

```
~/software/FeasPumpCollection/build/fp2
```

### A.2 Run sequentially

`run.sh` runs `fp2` on a set of MPS instances one by one and writes one `.log` file per
instance. Pass any glob or list of paths as arguments.

```bash
# Run on all downloaded instances
bash experiments/baselines/fp/run.sh \
    "/path/to/miplib2017/mps/*.mps" \
    --out /path/to/fp_logs

# Run on the 10 sample instances
bash experiments/baselines/fp/run.sh \
    "/path/to/miplib2017/mps/blend2.mps" \
    "/path/to/miplib2017/mps/noswot.mps" \
    --out ./fp_logs_sample
```

Options:

| Flag | Default | Description |
|---|---|---|
| `--out DIR` | `./logs` next to `run.sh` | Directory for `.log` output files |
| `--config FILE` | `fp.cfg` next to `run.sh` | fp2 configuration file |
| `--jobs N` | `1` | Parallel workers (uses `xargs -P`) |
| `--force` | off | Re-run even if the log file already exists |

The default configuration (`fp.cfg`) sets:
- `solver = scip` (SCIP as LP solver)
- `timeLimit = 3600` (1 hour per instance)
- `numThreads = 1` (single-threaded)
- `seed = 0`

When the run finishes, `run.sh` prints a summary:

```
Done — solved: 612  failed: 239  total: 851
Logs: /path/to/fp_logs
```

### A.3 Run with SLURM

For the full 851-instance run on a cluster, use the SLURM array template.

**Step 1 — Generate the instance list.**

```bash
find /path/to/miplib2017/mps -name "*.mps" | sort \
    > experiments/baselines/fp/instances.list

wc -l experiments/baselines/fp/instances.list   # e.g. 851
```

**Step 2 — Edit `submit.sh`.** Open `experiments/baselines/fp/submit.sh` and update the
lines marked `# EDIT ME`:

```bash
#SBATCH --account=def-XXXX          # ← your Compute Canada allocation
#SBATCH --array=0-850               # ← 0 to (N_instances - 1), here 851 instances

FP2_BIN="$HOME/software/FeasPumpCollection/build/fp2"   # printed by build.sh
INSTANCES_LIST="experiments/baselines/fp/instances.list"
CONFIG="experiments/baselines/fp/fp.cfg"
RESULTS_DIR="/scratch/$USER/fp_logs"
SCIP_INSTALL="$HOME/software/scip_install"
```

Also update the `module load` line to match your cluster (the default assumes Compute Canada).

**Step 3 — Submit.**

```bash
sbatch experiments/baselines/fp/submit.sh
```

Each task reads one line from `instances.list` and writes one `.log` file to `RESULTS_DIR`.
SLURM stdout/stderr goes to `experiments/baselines/fp/slurm_logs/`.

### A.4 Parse results

Once all runs are done (sequential or SLURM), convert the `.log` files to a CSV:

```bash
python experiments/baselines/fp/parse_logs.py \
    /path/to/fp_logs \
    --out results/fp_results.csv
```

The CSV contains one row per instance with columns:
`instance_name, variant, success, n_iters, n_restarts, wall_time, lp_time, primal_bound, stage, seed`.

---

## 5. Part B — DiffPump setup

Before running any DiffPump benchmark, create a virtual environment and install the package.

```bash
# Create and activate the venv (once per machine)
python3 -m venv ~/envs/diffpump
source ~/envs/diffpump/bin/activate
pip install --upgrade pip

# Install DiffPump from the local source tree
pip install -e /path/to/diffpump/

# Verify the CLI is available
diffpump --help
```

On **Compute Canada**, do this in an interactive session first:

```bash
salloc --time=0:30:00 --mem=4G --cpus-per-task=1 --account=def-XXXX
module load StdEnv/2023 python gurobi
python3 -m venv ~/envs/diffpump
source ~/envs/diffpump/bin/activate
pip install --upgrade pip
pip install -e /path/to/diffpump/
```

The venv path `~/envs/diffpump` is the default expected by all three `submit.sh` files.
To use a different path, set `VENV_PATH` before submitting:

```bash
VENV_PATH=/scratch/$USER/envs/diffpump sbatch experiments/benchmarks/r2_2/submit.sh
```

---

## 6. Part C — DiffPump benchmarks

All three benchmarks share the same two-step pattern:

1. **Sequential** — run `run_sequential.py` directly (no scheduler).
2. **SLURM** — run `gen_jobs.py` to generate `jobs.csv`, then `sbatch submit.sh`.

Results are written as **one JSON file per instance** inside labelled subdirectories:

```
<results-dir>/
    FP/
        blend2.json
        noswot.json
        ...
    DP1/
        blend2.json
        ...
    DP5/
        ...
```

Jobs that already have a JSON output are **skipped automatically** by both run modes, so
interrupted runs can be safely resumed.

---

### C.1 r2_2 — Main comparison

Runs six variants (FP, DP1, DP2, DP3, DP4, DP5) on the full instance set using the
best hyperparameters from Table 3 of the paper ("All" column).

| Variant | η | γ | β | λ | p | Notes |
|---|---|---|---|---|---|---|
| FP | 1.0 | 1.0 | 1.0 | 0.0 | 1 | Standard feasibility pump |
| DP1 | 0.55 | 0.95 | 1.0 | 0.0 | 1 | Tune η, γ only |
| DP2 | 0.80 | 0.65 | 1.0 | 0.0 | 2 | Tune η, γ, p |
| DP3 | 0.45 | 0.90 | 0.0 | 1.0 | 1 | Feasibility loss only, ε=0.15 |
| DP4 | 0.60 | 0.70 | 0.3 | 0.1 | 2 | Both losses, linear, ε=0.15 |
| DP5 | 0.50 | 0.50 | 0.9 | 0.9 | 2 | Both losses, argmin (q=2), ε=0.15 |

#### Sequential (no SLURM)

```bash
source ~/envs/diffpump/bin/activate

python experiments/benchmarks/r2_2/run_sequential.py \
    --instances-dir /path/to/miplib2017/mps \
    --results-dir   /path/to/results/r2_2 \
    --solver scip                              # or: gurobi
```

Options:

| Flag | Default | Description |
|---|---|---|
| `--instances-dir DIR` | required | Directory containing `*.mps` files |
| `--results-dir DIR` | required | Root output directory (one subdir per variant) |
| `--solver scip\|gurobi` | `scip` | LP solver backend |
| `--seed N` | `0` | Random seed |
| `--max-iters N` | `1000` | Maximum pump iterations |
| `--force` | off | Re-run even if the JSON already exists |

Total jobs: **851 instances × 6 variants = 5 106 runs**.
On a single core each run takes on average a few minutes; expect many hours for the full set.

#### SLURM

```bash
# Step 1 — generate jobs.csv and get the array range
python experiments/benchmarks/r2_2/gen_jobs.py \
    --instances-dir /scratch/$USER/miplib2017/mps \
    --results-dir   /scratch/$USER/r2_2 \
    --solver scip
# → prints: Generated 5106 jobs (851 instances × 6 variants)
#           Submit with:  sbatch --array=0-5105 submit.sh

# Step 2 — edit submit.sh (see section 8), then submit
sbatch --array=0-5105 experiments/benchmarks/r2_2/submit.sh
```

#### Aggregate results

```bash
python experiments/benchmarks/r2_2/aggregate.py \
    --results-dir /path/to/results/r2_2 \
    --out         experiments/benchmarks/r2_2/r2_2_results.csv
```

This prints a summary table to stdout (matching Table 2 format) and writes the full CSV.

---

### C.2 r1_4 — Ablation η=γ=1

Addresses **Reviewer 1, comment R1.4**: "What about keeping fixed η=γ=1 and tuning only
the other hyperparameters in DP4 and DP5?"

Fixes η=γ=1 and sweeps the remaining parameters to isolate the contribution of the
feasibility loss term from the ηγ relaxation:

| Parameter | Values swept |
|---|---|
| β | 0.1, 0.3, 0.5, 0.7, 0.9 |
| λ | 0.1, 0.3, 0.5, 0.7, 0.9 |
| p | 1, 2 |

This produces **50 configurations × 2 variants (DP4, DP5) = 100 configs per instance**.

#### Sequential

```bash
source ~/envs/diffpump/bin/activate

python experiments/benchmarks/r1_4/run_sequential.py \
    --instances-dir /path/to/miplib2017/mps \
    --results-dir   /path/to/results/r1_4 \
    --solver scip
```

Total jobs: **851 instances × 100 configs = 85 100 runs**.
For the full set, using SLURM is strongly recommended.

#### SLURM

```bash
# Step 1 — generate jobs.csv
python experiments/benchmarks/r1_4/gen_jobs.py \
    --instances-dir /scratch/$USER/miplib2017/mps \
    --results-dir   /scratch/$USER/r1_4 \
    --solver scip
# → prints: Generated 85100 jobs (851 instances × 100 configs)
#           Submit with:  sbatch --array=0-85099 submit.sh

# Step 2 — edit submit.sh (see section 8), then submit
sbatch --array=0-85099 experiments/benchmarks/r1_4/submit.sh
```

#### Collect results

```bash
python experiments/benchmarks/parse_jsons.py \
    --results-dir /path/to/results/r1_4 \
    --out         results/r1_4_results.csv
```

---

### C.3 r1_5 — ε sensitivity

Addresses **Reviewer 1, comment R1.5**: justify the choice of ε=0.15 for soft rounding.

Runs **DP5** (the best variant) with its Table 3 hyperparameters (η=0.5, γ=0.5, β=0.9,
λ=0.9, p=2, q=2) and sweeps the soft-rounding parameter:

```
ε ∈ { 0.01, 0.05, 0.10, 0.15, 0.20, 0.30 }
```

#### Sequential

```bash
source ~/envs/diffpump/bin/activate

python experiments/benchmarks/r1_5/run_sequential.py \
    --instances-dir /path/to/miplib2017/mps \
    --results-dir   /path/to/results/r1_5 \
    --solver scip
```

Total jobs: **851 instances × 6 ε values = 5 106 runs**.

#### SLURM

```bash
# Step 1 — generate jobs.csv
python experiments/benchmarks/r1_5/gen_jobs.py \
    --instances-dir /scratch/$USER/miplib2017/mps \
    --results-dir   /scratch/$USER/r1_5 \
    --solver scip
# → prints: Generated 5106 jobs (851 instances × 6 eps values)
#           Submit with:  sbatch --array=0-5105 submit.sh

# Step 2 — edit submit.sh (see section 8), then submit
sbatch --array=0-5105 experiments/benchmarks/r1_5/submit.sh
```

#### Collect results

```bash
python experiments/benchmarks/parse_jsons.py \
    --results-dir /path/to/results/r1_5 \
    --out         results/r1_5_results.csv
```

---

## 7. Collecting DiffPump results

### `benchmarks/parse_jsons.py` — general aggregator

Works for all three DiffPump benchmarks. Walks a results directory, finds every JSON
file in every label subdirectory, and writes a single CSV.

```bash
# One benchmark
python experiments/benchmarks/parse_jsons.py \
    --results-dir /path/to/results/r2_2 \
    --out results/r2_2.csv

# Dry-run: print summary table without writing anything
python experiments/benchmarks/parse_jsons.py \
    --results-dir /path/to/results/r2_2 \
    --dry-run

# Multiple benchmarks in one shot
python experiments/benchmarks/parse_jsons.py \
    --results-dir /path/to/results/r2_2 \
                  /path/to/results/r1_4 \
                  /path/to/results/r1_5 \
    --out results/all_diffpump.csv
```

The CSV columns are:
`label, instance_name, success, timed_out, n_iters, n_restarts, restart_ratio,
wall_time, lp_time, seed, eta, gamma, beta, lam, p, q, use_argmin_feas, eps_soft, eps_feas, solver`

### `benchmarks/r2_2/aggregate.py` — paper-style table

Specific to `r2_2`. Reads the per-variant JSON subdirectories and prints a summary table
that directly matches the layout of Table 2 in the paper:

```
Variant   Fail%    Iters  Restart%  AvgTime(s)
-----------------------------------------------
FP        20.21     9842      8.12       3.821
DP1       18.33     8901      7.44       3.512
...
```

```bash
python experiments/benchmarks/r2_2/aggregate.py \
    --results-dir /path/to/results/r2_2 \
    --out         results/table2_paper.csv
```

---

## 8. Adapting submit.sh for SLURM

Each benchmark has a `submit.sh` file. The lines you **must** edit before submitting are
marked with `# EDIT ME` in the file. Here is a complete guide for each one.

### `baselines/fp/submit.sh`

```bash
#SBATCH --account=def-XXXX          # ← your Compute Canada allocation code
#SBATCH --array=0-850               # ← set to 0-(N_instances-1), e.g. 0-850 for 851 instances

FP2_BIN="$HOME/software/FeasPumpCollection/build/fp2"  # ← path printed by build.sh
INSTANCES_LIST="experiments/baselines/fp/instances.list"  # ← one MPS path per line
CONFIG="experiments/baselines/fp/fp.cfg"                  # ← usually leave as-is
RESULTS_DIR="/scratch/$USER/fp_logs"                      # ← where .log files go
SCIP_INSTALL="$HOME/software/scip_install"                # ← install prefix from build.sh

# module load line — adjust to match what you used in build.sh:
module load StdEnv/2023 gcc
```

### `benchmarks/r2_2/submit.sh`, `benchmarks/r1_4/submit.sh`, `benchmarks/r1_5/submit.sh`

All three DiffPump submit scripts have the same structure:

```bash
#SBATCH --account=def-XXXX          # ← your allocation code

# The --array flag is NOT in the file — pass it on the sbatch command line:
#   sbatch --array=0-NNNN submit.sh
# where NNNN is printed by gen_jobs.py (N_total_jobs - 1).

VENV_PATH="${VENV_PATH:-$HOME/envs/diffpump}"  # ← path to your diffpump venv
JOBS_CSV="experiments/benchmarks/<benchmark>/jobs.csv"  # ← generated by gen_jobs.py

# module load line — adjust to your cluster and solver:
module load StdEnv/2023 python gurobi   # use 'scip' instead of 'gurobi' if needed
```

### SLURM resource settings

The default resource request in all scripts is:

```bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
```

These are safe defaults for MIPLIB instances with a 1-hour fp2 time limit. If your
cluster has stricter limits or if you observe out-of-memory errors on large instances,
increase `--mem` accordingly (16G is safe for all MIPLIB 2017 instances).

### Checking job progress

```bash
# How many tasks are still running/pending?
squeue -u $USER

# How many JSON files have been written so far?
find /scratch/$USER/r2_2 -name "*.json" | wc -l

# Check for failed tasks (non-zero exit codes)
grep -l "FAILED\|ERROR" experiments/benchmarks/r2_2/slurm_logs/*.err 2>/dev/null
```

### Resuming interrupted runs

Both `run_sequential.py` and the SLURM array skip instances whose output JSON already
exists. To resume after a partial run:

- **Sequential**: just re-run the same command. Already-finished jobs are printed as `SKIP`.
- **SLURM**: re-generate `jobs.csv` (same command) and resubmit the full array. Tasks that
  find an existing JSON will exit immediately and consume negligible resources.

To force a full re-run, add `--force` (sequential) or delete the output directory first.

---

## 9. File reference

### Instance files

| File | Description |
|---|---|
| `instances/instances.csv` | 851 MIPLIB 2017 instance names, variable counts, and type (BP/MBP/MIP) |
| `instances/sample.csv` | 10 small instances for pipeline smoke tests |
| `instances/download.py` | Downloads and decompresses instances from `miplib.zib.de` |

### FP baseline

| File | Description |
|---|---|
| `baselines/fp/build.sh` | Builds SoPlex 7.1.6 + SCIP 9.2.4 + FeasPumpCollection into `~/software/` |
| `baselines/fp/fp.cfg` | fp2 configuration: SCIP solver, 1-hour time limit, single-threaded, seed 0 |
| `baselines/fp/run.sh` | Runs fp2 on a set of instances; writes one `.log` per instance |
| `baselines/fp/submit.sh` | SLURM array template for the FP baseline |
| `baselines/fp/parse_logs.py` | Parses fp2 `.log` files → CSV |

### DiffPump benchmarks

| File | Description |
|---|---|
| `benchmarks/parse_jsons.py` | Aggregates DiffPump JSON results from any benchmark into a single CSV |
| `benchmarks/r2_2/run_sequential.py` | Runs FP + DP1–DP5 on all instances sequentially |
| `benchmarks/r2_2/gen_jobs.py` | Generates `jobs.csv` for the r2_2 SLURM array |
| `benchmarks/r2_2/submit.sh` | SLURM array worker for r2_2 |
| `benchmarks/r2_2/aggregate.py` | Produces a paper-style Table 2 summary from r2_2 results |
| `benchmarks/r1_4/run_sequential.py` | Runs DP4/DP5 with η=γ=1 grid (100 configs) sequentially |
| `benchmarks/r1_4/gen_jobs.py` | Generates `jobs.csv` for the r1_4 SLURM array |
| `benchmarks/r1_4/submit.sh` | SLURM array worker for r1_4 |
| `benchmarks/r1_5/run_sequential.py` | Runs DP5 with 6 ε values sequentially |
| `benchmarks/r1_5/gen_jobs.py` | Generates `jobs.csv` for the r1_5 SLURM array |
| `benchmarks/r1_5/submit.sh` | SLURM array worker for r1_5 |
