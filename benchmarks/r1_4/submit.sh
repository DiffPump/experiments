#!/bin/bash
# =============================================================================
# Ablation benchmark — SLURM job-array worker (eta=gamma=1, DP4/DP5 grid)
# =============================================================================
#
# WORKFLOW:
#   # 1. Generate jobs.csv (run interactively or in a login session)
#   python experiments/benchmarks/r1_4/gen_jobs.py \
#       --instances-dir /scratch/$USER/miplib2017/mps \
#       --results-dir   /scratch/$USER/r1_4
#   # -> prints: sbatch --array=0-NNNN submit.sh
#
#   # 2. Submit the array
#   sbatch --array=0-NNNN experiments/benchmarks/r1_4/submit.sh
#
# EDIT ME — account and paths below.
# =============================================================================

#SBATCH --job-name=dfp_r1_4
#SBATCH --account=def-XXXX               # EDIT ME — your allocation
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=experiments/benchmarks/r1_4/slurm_logs/%A_%a.out
#SBATCH --error=experiments/benchmarks/r1_4/slurm_logs/%A_%a.err

# ---------------------------------------------------------------------------
# EDIT ME — paths
# ---------------------------------------------------------------------------
VENV_PATH="${VENV_PATH:-$HOME/envs/diffpump}"
JOBS_CSV="experiments/benchmarks/r1_4/jobs.csv"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
module purge
module load StdEnv/2023 python gurobi    # adjust for your cluster

source "${VENV_PATH}/bin/activate"

mkdir -p "experiments/benchmarks/r1_4/slurm_logs"

# ---------------------------------------------------------------------------
# Parse this task's row from jobs.csv
# ---------------------------------------------------------------------------
TASK_ID=${SLURM_ARRAY_TASK_ID}

eval "$(python3 - <<'PYEOF'
import csv, os, sys
jobs_csv = os.environ["JOBS_CSV"]
task_id  = int(os.environ.get("SLURM_ARRAY_TASK_ID", "0"))
with open(jobs_csv) as fh:
    rows = list(csv.DictReader(fh))
if task_id >= len(rows):
    print(f'echo "No job for task {task_id}"; exit 1')
    sys.exit(0)
row = rows[task_id]
for k, v in row.items():
    print(f'export JOB_{k.upper()}="{v}"')
PYEOF
)"

# ---------------------------------------------------------------------------
# Run diffpump
# ---------------------------------------------------------------------------
mkdir -p "${JOB_JSON_DIR}"

CMD="diffpump \"${JOB_INSTANCE}\""
CMD+=" --json-dir \"${JOB_JSON_DIR}\""
CMD+=" --eta ${JOB_ETA} --gamma ${JOB_GAMMA} --beta ${JOB_BETA}"
CMD+=" --lam ${JOB_LAM} --p ${JOB_P} --q ${JOB_Q}"
CMD+=" --eps ${JOB_EPS} --eps-feas ${JOB_EPS_FEAS}"
CMD+=" --seed ${JOB_SEED} --max-iters ${JOB_MAX_ITERS}"
CMD+=" --solver ${JOB_SOLVER}"
[[ "${JOB_USE_ARGMIN_FEAS}" == "True" ]] && CMD+=" --use-argmin-feas"

echo "Task ${TASK_ID} [${JOB_LABEL}]: $(basename "${JOB_INSTANCE}")"
eval "${CMD}"
EXIT_CODE=$?

[[ ${EXIT_CODE} -ne 0 ]] && { echo "diffpump exited with ${EXIT_CODE}" >&2; exit ${EXIT_CODE}; }
echo "Task ${TASK_ID} done."
