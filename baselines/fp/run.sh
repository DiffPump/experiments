#!/bin/bash
# =============================================================================
# Run FeasPumpCollection on a set of MPS instances
#
# This script is standalone — copy it (with fp.cfg) anywhere and run it.
#
# Usage:
#   bash run.sh "path/to/mps/*.mps"
#   bash run.sh path/to/mps/noswot.mps path/to/mps/blend2.mps
#   bash run.sh "path/to/mps/*.mps" --out /scratch/results --config fp.cfg
#
# Options:
#   --out     Output directory for .log files   (default: ./logs)
#   --config  Path to fp2 config file           (default: fp.cfg next to this script)
#   --jobs    Parallel workers                  (default: 1)
#   --force   Re-run even if log already exists
#
# Prerequisites:
#   build.sh must have been run first (installs fp2 to ~/software/).
#   The fp2 binary location can be overridden with:
#     FP2_BIN=/path/to/fp2 bash run.sh ...
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
FP2_BIN="${FP2_BIN:-$HOME/software/FeasPumpCollection/build/fp2}"
SCIP_LIB="${SCIP_LIB:-$HOME/software/scip_install/lib}"
CONFIG="${SCRIPT_DIR}/fp.cfg"
OUT_DIR="${SCRIPT_DIR}/logs"
JOBS=1
FORCE=0

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --out)    OUT_DIR="$2";  shift 2 ;;
        --config) CONFIG="$2";   shift 2 ;;
        --jobs)   JOBS="$2";     shift 2 ;;
        --force)  FORCE=1;       shift   ;;
        --help|-h)
            sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
            exit 0
            ;;
        *) POSITIONAL+=("$1");   shift   ;;
    esac
done

# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
if [[ ${#POSITIONAL[@]} -eq 0 ]]; then
    echo "Error: no instances specified." >&2
    echo "Usage: bash run.sh \"path/to/mps/*.mps\" [--out DIR] [--config FILE]" >&2
    exit 1
fi

if [[ ! -x "${FP2_BIN}" ]]; then
    echo "Error: fp2 binary not found at ${FP2_BIN}" >&2
    echo "Run build.sh first, or set FP2_BIN=/path/to/fp2." >&2
    exit 1
fi

if [[ ! -f "${CONFIG}" ]]; then
    echo "Error: config file not found at ${CONFIG}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Expand globs into a list of MPS files
# ---------------------------------------------------------------------------
INSTANCES=()
for pattern in "${POSITIONAL[@]}"; do
    if [[ -f "${pattern}" ]]; then
        INSTANCES+=("${pattern}")
    else
        # Let the shell expand the glob
        for f in ${pattern}; do
            [[ -f "${f}" ]] && INSTANCES+=("${f}") || true
        done
    fi
done

if [[ ${#INSTANCES[@]} -eq 0 ]]; then
    echo "Error: no .mps files matched." >&2
    exit 1
fi

mkdir -p "${OUT_DIR}"

# ---------------------------------------------------------------------------
# Make SCIP shared libraries findable
# ---------------------------------------------------------------------------
export LD_LIBRARY_PATH="${SCIP_LIB}:${LD_LIBRARY_PATH:-}"

# ---------------------------------------------------------------------------
# Runner function
# ---------------------------------------------------------------------------
run_one() {
    local mps="$1"
    local name
    name="$(basename "${mps}" .mps)"
    local log="${OUT_DIR}/${name}.log"

    if [[ -f "${log}" && "${FORCE}" -eq 0 ]]; then
        echo "  SKIP  ${name}"
        return
    fi

    local t0 t1 elapsed status
    t0=$(date +%s%N)
    "${FP2_BIN}" "${mps}" --config "${CONFIG}" > "${log}" 2>&1
    t1=$(date +%s%N)
    elapsed=$(( (t1 - t0) / 1000000 ))   # ms

    # Quick success check — numSols > 0 in the results block
    if grep -q "numSols = [1-9]" "${log}" 2>/dev/null; then
        status="OK  "
    else
        status="FAIL"
    fi

    printf "  %s  %6d ms  %s\n" "${status}" "${elapsed}" "${name}"
}

export -f run_one
export FP2_BIN CONFIG OUT_DIR FORCE

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
TOTAL=${#INSTANCES[@]}
echo "Instances : ${TOTAL}"
echo "Config    : ${CONFIG}"
echo "Output    : ${OUT_DIR}"
echo "Workers   : ${JOBS}"
echo ""

if [[ "${JOBS}" -gt 1 ]]; then
    printf '%s\n' "${INSTANCES[@]}" \
        | xargs -P "${JOBS}" -I{} bash -c 'run_one "$@"' _ {}
else
    for inst in "${INSTANCES[@]}"; do
        run_one "${inst}"
    done
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
OK=0
for f in "${OUT_DIR}"/*.log; do
    [[ -f "$f" ]] || continue
    grep -q "numSols = [1-9]" "$f" 2>/dev/null && (( OK++ )) || true
done
FAIL=$(( TOTAL - OK ))
echo ""
echo "Done — solved: ${OK}  failed: ${FAIL}  total: ${TOTAL}"
echo "Logs: ${OUT_DIR}"
