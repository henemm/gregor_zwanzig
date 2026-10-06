#!/usr/bin/env bash
# CI-Prod-Gate (#2047 Scheibe 2): Liegt fuer den tatsaechlich auszuliefernden Stand
# (origin/main) ein echter /e2e-verify-Nachweis vor?
#
# Aufruf (auf dem Server, Haupt-Checkout): bash ci_prod_gate.sh <repo>
#   stdout  PROD_GATE=open    staging_gate --check besteht (Nachweis oder docs-only)
#           PROD_GATE=closed  staging_gate --check scheitert (Meldung auf stderr)
#   exit 0  genau dann, wenn eine PROD_GATE-Zeile ausgegeben wurde
#   exit !=0 ohne PROD_GATE-Zeile bei Fetch-/Skriptfehler (CI-Schritt wird rot)
#
# Read-only: kein reset, kein stash, kein Schreiben nach .claude/e2e_verified/.
# GZ_SKIP_E2E_GATE wird hier bewusst NICHT gesetzt und eine geerbte Variable
# neutralisiert (Notausgang darf das CI-Gate nie oeffnen).
set -euo pipefail
unset GZ_SKIP_E2E_GATE

repo="${1:?Aufruf: ci_prod_gate.sh <repo>}"
cd "$repo"

# Ziel aufloesbar machen. Scheitert der Fetch, bricht set -e hier ab (kein Gate-Satz).
git fetch origin >&2

# Steht HEAD bereits auf origin/main, ist der Diff HEAD..origin/main leer und
# staging_gate stuft ihn als docs-only ein (Gate offen OHNE Nachweis). Dann den
# Scope erzwingen: staging_gate verlangt den Nachweis fuer genau diese SHA.
scope_args=()
if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ]; then
  scope_args=(--scope backend)
fi

if python3 .claude/hooks/staging_gate.py --check --expected-commit origin/main "${scope_args[@]}" >&2; then
  echo "PROD_GATE=open"
else
  echo "PROD_GATE=closed"
fi
