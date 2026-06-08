#!/bin/bash
# =============================================================================
# FeasPumpCollection SLURM job-array submission script (baseline)
# =============================================================================
#
# BEFORE SUBMITTING — edit the lines marked "EDIT ME":
#   1. --account=def-XXXX       ← your Compute Canada allocation
#   2. --array=0-NNN            ← replace NNN with (number_of_instances - 1)
#   3. FP2_BIN                  ← path printed by build.sh
#   4. INSTANCES_LIST           ← one MPS path per line (no header)
#   5. CONFIG                   ← path to fp.cfg (can leave as-is if run from repo root)
#   6. RESULTS_DIR              ← where per-task log files will be written
#   7. module load lines        ← match what you used in build.sh
#
# USAGE:
#   # 1. Build once (interactive session):
#   bash experiments/baselines/fp/build.sh
#
#   # 2. Generate instance list (one MPS path per line):
#   find experiments/instances/miplib2017/mps -name "*.mps" | sort \
#       > experiments/baselines/fp/instances.list
#   wc -l experiments/baselines/fp/instances.list   # → set --array accordingly
#
#   # 3. Edit --array and FP2_BIN below, then:
#   sbatch experiments/baselines/fp/submit.sh
#
#   # 4. After all tasks finish, collect results:
#   python experiments/baselines/fp/parse_results.py \
#       experiments/baselines/fp/logs \
#       --out experiments/baselines/fp/results.csv
# =============================================================================

#SBATCH --job-name=fp_baseline
#SBATCH --account=def-XXXX                # EDIT ME
#SBATCH --array=0-9                       # EDIT ME — set to 0-(N_instances - 1)
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:30:00                   # 1 h for fp.timeLimit=3600 + overhead
#SBATCH --output=experiments/baselines/fp/slurm_logs/%A_%a.out
#SBATCH --error=experiments/baselines/fp/slurm_logs/%A_%a.err

# ---------------------------------------------------------------------------
# EDIT ME — paths
# ---------------------------------------------------------------------------
FP2_BIN="$HOME/software/FeasPumpCollection/build/fp2"
INSTANCES_LIST="experiments/baselines/fp/instances.list"
CONFIG="experiments/baselines/fp/fp.cfg"
RESULTS_DIR="experiments/baselines/fp/logs"
SCIP_INSTALL="$HOME/software/scip_install"   # install prefix used in build.sh

# ---------------------------------------------------------------------------
# Modules — must match what was used in build.sh (no scip module needed;
# SCIP was built from source and the .so is picked up via LD_LIBRARY_PATH)
# ---------------------------------------------------------------------------
module purge
module load StdEnv/2023
module load gcc
export LD_LIBRARY_PATH="${SCIP_INSTALL}/lib:${LD_LIBRARY_PATH:-}"

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mkdir -p "${RESULTS_DIR}" experiments/baselines/fp/slurm_logs

TASK_ID=${SLURM_ARRAY_TASK_ID}

# Read the MPS path for this task (0-indexed)
INSTANCE=$(sed -n "$((TASK_ID + 1))p" "${INSTANCES_LIST}")

if [[ -z "${INSTANCE}" ]]; then
    echo "Error: no instance for TASK_ID=${TASK_ID}" >&2
    exit 1
fi

INSTANCE_NAME=$(basename "${INSTANCE}" .mps)
LOG_FILE="${RESULTS_DIR}/${TASK_ID}_${INSTANCE_NAME}.log"

echo "Task ${TASK_ID}: ${INSTANCE_NAME}"
echo "Log:  ${LOG_FILE}"

# ---------------------------------------------------------------------------
# Run FeasPump
# ---------------------------------------------------------------------------
"${FP2_BIN}" "${INSTANCE}" --config "${CONFIG}" > "${LOG_FILE}" 2>&1
EXIT_CODE=$?

if [[ ${EXIT_CODE} -ne 0 ]]; then
    echo "fp2 exited with code ${EXIT_CODE}" >&2
    exit ${EXIT_CODE}
fi

echo "Task ${TASK_ID} done."
