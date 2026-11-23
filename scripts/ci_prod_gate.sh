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
# Kein reset, kein stash, HEAD und Arbeitsbaum bleiben unveraendert. Einziger
# Schreibzugriff (#3289): e2e_nachweis_holen.py legt die auf origin als Git-Note
# (refs/notes/e2e-verified) veroeffentlichten Nachweise als
# .claude/e2e_verified/<sha>.json ab (nur passende verified_commit, fail-closed).
# Die CI startet dieses Skript aus einer tmp-Kopie (git show origin/main:...);
# das Hol-Skript wird deshalb absolut ueber <repo>/scripts/ aufgeloest.
# GZ_SKIP_E2E_GATE wird hier bewusst NICHT gesetzt und eine geerbte Variable
# neutralisiert (Notausgang darf das CI-Gate nie oeffnen).
set -euo pipefail
unset GZ_SKIP_E2E_GATE

repo="${1:?Aufruf: ci_prod_gate.sh <repo>}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo"
repo="$(pwd)"

# Ziel aufloesbar machen. Scheitert der Fetch, bricht set -e hier ab (kein Gate-Satz).
git fetch origin >&2

# Nachweise von origin holen (#3289), BEVOR das Gate entscheidet. Quelle des
# Hol-Skripts: Checkout, sonst neben diesem Skript, sonst origin/main.
# Scheitert das Holen, bricht set -e ab (kein Gate-Satz, CI-Schritt wird rot).
holen="$repo/scripts/e2e_nachweis_holen.py"
holen_tmp=""
if [ ! -f "$holen" ]; then
  holen="$script_dir/e2e_nachweis_holen.py"
fi
if [ ! -f "$holen" ]; then
  holen_tmp="$(mktemp "${TMPDIR:-/tmp}/e2e_nachweis_holen.XXXXXX")"
  trap 'rm -f "$holen_tmp"' EXIT
  git show origin/main:scripts/e2e_nachweis_holen.py > "$holen_tmp"
  holen="$holen_tmp"
fi
python3 "$holen" "$repo" >&2

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
