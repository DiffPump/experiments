#!/bin/bash
# =============================================================================
# Build SoPlex + SCIP + FeasPumpCollection
#
# Everything is compiled and installed under ~/software/.
# This script is standalone — copy it anywhere and run it.
# Already-built steps are skipped automatically.
#
# Usage:
#   bash build.sh              # installs to ~/software/ (default)
#   JOBS=8 bash build.sh       # parallel build with 8 cores
#
# After a successful build the fp2 binary is at:
#   ~/software/FeasPumpCollection/build/fp2
#
# On Compute Canada, start an interactive session first:
#   salloc --time=2:00:00 --mem=8G --cpus-per-task=4 --account=def-XXXX
#   module load StdEnv/2023 cmake gcc boost
# =============================================================================

set -euo pipefail

JOBS="${JOBS:-4}"
SOFTWARE="$HOME/software"
PREFIX="${SOFTWARE}/scip_install"   # shared install prefix for SoPlex + SCIP

# Tags as they appear on GitHub (no dots — release-716, v924, etc.)
SOPLEX_TAG="release-716"   # SoPlex 7.1.6
SCIP_TAG="v924"            # SCIP 9.2.4

FP_SRC="${SOFTWARE}/FeasPumpCollection"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
step()    { echo; echo "=== $* ==="; }
skip()    { echo "  already built — skipping."; }

# ---------------------------------------------------------------------------
# 1. SoPlex
# ---------------------------------------------------------------------------
step "SoPlex (${SOPLEX_TAG})"

SOPLEX_SRC="${SOFTWARE}/soplex"
if [[ -f "${PREFIX}/lib/libsoplex.so" || -f "${PREFIX}/lib/libsoplex.a" ]]; then
    skip
else
    if [[ ! -d "${SOPLEX_SRC}" ]]; then
        git clone --branch "${SOPLEX_TAG}" --depth 1 \
            https://github.com/scipopt/soplex.git "${SOPLEX_SRC}"
    fi
    cmake -S "${SOPLEX_SRC}" -B "${SOPLEX_SRC}/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}"
    make -C "${SOPLEX_SRC}/build" -j"${JOBS}"
    make -C "${SOPLEX_SRC}/build" install
fi

# ---------------------------------------------------------------------------
# 2. SCIP
# ---------------------------------------------------------------------------
step "SCIP (${SCIP_TAG})"

SCIP_SRC="${SOFTWARE}/scip"
if [[ -f "${PREFIX}/lib/libscip.so" || -f "${PREFIX}/lib/libscip.a" ]]; then
    skip
else
    if [[ ! -d "${SCIP_SRC}" ]]; then
        git clone --branch "${SCIP_TAG}" --depth 1 \
            https://github.com/scipopt/scip.git "${SCIP_SRC}"
    fi
    cmake -S "${SCIP_SRC}" -B "${SCIP_SRC}/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DSOPLEX_DIR="${PREFIX}" \
        -DLPS=spx \
        -DZIMPL=OFF \
        -DIPOPT=OFF \
        -DPAPILO=OFF \
        -DSHARED=ON
    make -C "${SCIP_SRC}/build" -j"${JOBS}"
    make -C "${SCIP_SRC}/build" install
fi

# ---------------------------------------------------------------------------
# 3. FeasPumpCollection
# ---------------------------------------------------------------------------
step "FeasPumpCollection"

if [[ -f "${FP_SRC}/build/fp2" ]]; then
    skip
else
    if [[ ! -d "${FP_SRC}" ]]; then
        git clone https://github.com/GioniMexi/FeasPumpCollection "${FP_SRC}"
    fi
    # GCC 15 removed several implicit includes — patch the bundled libraries
    grep -q "#include <limits>" "${FP_SRC}/extern/utils/src/cutpool.cpp" || \
        sed -i 's|#include <algorithm>|#include <algorithm>\n#include <limits>|' \
            "${FP_SRC}/extern/utils/src/cutpool.cpp"
    grep -q "#include <iostream>" "${FP_SRC}/src/scipmodel.cpp" || \
        sed -i 's|#include <cassert>|#include <cassert>\n#include <iostream>|' \
            "${FP_SRC}/src/scipmodel.cpp"
    cmake -S "${FP_SRC}" -B "${FP_SRC}/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_FLAGS_RELEASE="-O3" \
        -DSCIP_DIR="${PREFIX}/lib/cmake/scip" \
        -DSCIP_LIBRARY="${PREFIX}/lib/libscip.so" \
        -DSCIP_INCLUDE_DIR="${PREFIX}/include" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5
    make -C "${FP_SRC}/build" -j"${JOBS}"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "=============================="
echo "Build complete."
echo "Binary : ${FP_SRC}/build/fp2"
echo "SCIP   : ${PREFIX}"
echo "=============================="
