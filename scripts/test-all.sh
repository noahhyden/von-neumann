#!/usr/bin/env bash
# Reproduce every result in the repo in one command: run all eight module pytest
# suites, then the frontend's two test layers (A: pure model parity vs the Python
# CLI; B: the pimas contract) and its build. Exits nonzero if any suite fails.
#
# The frontend depends on pimas (frontend/package.json -> "pimas": "file:../../pimas"),
# a separate, first-party repo that must be cloned as a SIBLING of von-neumann and
# built first. See the README "Reproducing all results" section. If pimas is absent,
# the Python suites still run and the frontend step is reported as skipped.
set -uo pipefail
cd "$(dirname "$0")/.." # repo root
ROOT="$(pwd)"

PY_MODULES=(closure-sim probe-sim power-budget launch-economics mission multi-probe swarm spine)
fail=0

for m in "${PY_MODULES[@]}"; do
  echo "== ${m} (pytest) =="
  if ( cd "${m}" && uv run --extra dev pytest -q ); then
    echo "   OK: ${m}"
  else
    echo "   FAIL: ${m}"
    fail=1
  fi
done

echo "== frontend =="
PIMAS="${ROOT}/../pimas"
PINNED="$(cat "${ROOT}/frontend/.pimas-good-sha")"
if [ ! -d "${PIMAS}" ]; then
  echo "   SKIP: pimas not found at ${PIMAS}"
  echo "   Clone it as a sibling and check out the pinned SHA, then re-run:"
  echo "     git clone https://github.com/noahhyden/pimas ../pimas"
  echo "     git -C ../pimas checkout ${PINNED}"
  fail=1
else
  head="$(git -C "${PIMAS}" rev-parse HEAD 2>/dev/null || echo unknown)"
  if [ "${head}" != "${PINNED}" ]; then
    echo "   NOTE: pimas HEAD ${head} != pinned ${PINNED} (the frontend is pinned to the latter;"
    echo "         'git -C ../pimas checkout ${PINNED}' to reproduce the pinned build exactly)."
  fi
  if ( cd "${PIMAS}" && npm ci && npm run build ); then
    if ( cd "${ROOT}/frontend" && npm ci && npm test && npm run test:contract && npm run build ); then
      echo "   OK: frontend"
    else
      echo "   FAIL: frontend"
      fail=1
    fi
  else
    echo "   FAIL: pimas build"
    fail=1
  fi
fi

echo
if [ "${fail}" -eq 0 ]; then
  echo "ALL GREEN"
else
  echo "SOME SUITES FAILED"
fi
exit "${fail}"
