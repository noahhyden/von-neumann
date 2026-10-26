#!/usr/bin/env bash
# Reproduce every result in the repo in one command: run every module pytest
# suite, then the frontend's two test layers (A: pure model parity vs the Python
# CLI; B: the pimas contract) and its build. Exits nonzero if any suite fails.
#
# The frontend consumes pimas from npm as pimas-ui (aliased to "pimas" in
# frontend/package.json), so `npm ci` in frontend/ resolves it like any other
# registry dependency - no sibling checkout needed.
set -uo pipefail
cd "$(dirname "$0")/.." # repo root
ROOT="$(pwd)"

mapfile -t PY_MODULES < <(python3 scripts/depgraph.py --json | python3 -c "import json,sys; print(*json.load(sys.stdin)['modules'], 'scripts', sep='\n')")
[ "${#PY_MODULES[@]}" -gt 1 ] || { echo "FAIL: module list is empty"; exit 1; }
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
if ( cd "${ROOT}/frontend" && npm ci && npm test && npm run test:contract && npm run build ); then
  echo "   OK: frontend"
else
  echo "   FAIL: frontend"
  fail=1
fi

echo
if [ "${fail}" -eq 0 ]; then
  echo "ALL GREEN"
else
  echo "SOME SUITES FAILED"
fi
exit "${fail}"
