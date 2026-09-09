#!/usr/bin/env bash
# Faehrt e2e/passkey-konto.spec.ts in ZWEI Playwright-Aufrufen mit einem
# Neustart des Go-Servers dazwischen.
#
# WARUM GETEILT (gemessen 09.09.2026): die Datei loest 38 Anfragen auf den
# Passkey-Routen aus, das IP-Rate-Limit erlaubt 30 je Stunde
# (internal/router/router.go:94, NewIPRateLimiter(30, time.Hour)). Ein Lauf am
# Stueck endet deshalb zuverlaessig in HTTP 429 -- sichtbar als "Passkey
# erscheint nicht in der Liste" in den zuletzt laufenden Tests, NICHT als
# Rate-Limit-Meldung. Das ist kein Defekt der Anwendung. Dasselbe Muster faehrt
# die CI fuer bug-703-login-ratelimit.spec.ts (.github/workflows/ci.yml:330).
# Der Neustart des Go-Servers setzt den Zaehler zurueck.
#
# Aufteilung entlang der Anfragelast, nicht nach Testnummer:
#   Teil 1 "AC-"  ~28 Anfragen
#   Teil 2 "F00"  ~10 Anfragen
#
# Voraussetzung: der Preview-Server laeuft auf Port 4173:
#   cd frontend && GZ_API_BASE=http://localhost:8095 \
#     GZ_E2E_API_PROXY_TARGET=http://localhost:8095 bash e2e/start-preview.sh
#
# Aufruf (aus dem Repo-Wurzelverzeichnis oder von ueberall):
#   bash frontend/e2e/run-passkey-konto.sh
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$(dirname "$HIER")"
REPO="$(dirname "$FRONTEND")"

# Eigene Ports (Go 8095, Python 8005), damit weder Produktion (8090/8000) noch
# Staging (8091/8001) beruehrt wird.
export GZ_CI_STACK_GO_PORT="${GZ_CI_STACK_GO_PORT:-8095}"
export GZ_CI_STACK_PY_PORT="${GZ_CI_STACK_PY_PORT:-8005}"
export GZ_CI_STACK_STATE_DIR="${GZ_CI_STACK_STATE_DIR:-/tmp/gz-e2e-stack-2246}"
export GREGOR_SERVER_BIN="${GREGOR_SERVER_BIN:-/tmp/gregor-server-2246}"
export GZ_API_BASE="${GZ_API_BASE:-http://localhost:$GZ_CI_STACK_GO_PORT}"
export GZ_E2E_API_PROXY_TARGET="${GZ_E2E_API_PROXY_TARGET:-http://localhost:$GZ_CI_STACK_GO_PORT}"

# GZ_SESSION_SECRET muss BEIDSEITIG gesetzt sein: e2e/start-preview.sh zieht es
# aus der Repo-.env, ci-stack.sh laesst es fuer den Go-Server absichtlich weg --
# halbseitig gesetzt bricht die Cookie-Signatur und jede Anmeldung scheitert.
if [ -z "${GZ_SESSION_SECRET:-}" ] && [ -r "$REPO/.env" ]; then
	GZ_SESSION_SECRET="$(grep -m1 '^GZ_SESSION_SECRET=' "$REPO/.env" | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//')"
	export GZ_SESSION_SECRET
fi
[ -n "${GZ_SESSION_SECRET:-}" ] || { echo "GZ_SESSION_SECRET fehlt (.env oder Umgebung)" >&2; exit 1; }

stack_neu() {
	bash "$HIER/ci-stack.sh" stop >/dev/null 2>&1
	bash "$HIER/ci-stack.sh" start
}

lauf() {
	local filter="$1" name="$2"
	echo
	echo "=== $name (Filter: $filter) ==="
	(cd "$FRONTEND" && npx playwright test e2e/passkey-konto.spec.ts --project=tests -g "$filter" "${@:3}")
}

stack_neu
lauf 'AC-' 'Teil 1: AC-1 bis AC-9' "${@}"
ERGEBNIS_1=$?

# Zaehler zuruecksetzen -- ohne diesen Neustart laeuft Teil 2 in 429.
stack_neu
lauf 'F00' 'Teil 2: F001 bis F003 (Adversary-Nachtrag)' "${@}"
ERGEBNIS_2=$?

echo
if [ "$ERGEBNIS_1" -eq 0 ] && [ "$ERGEBNIS_2" -eq 0 ]; then
	echo "BEIDE TEILE GRUEN"
	exit 0
fi
echo "ROT -- Teil 1: Exit $ERGEBNIS_1, Teil 2: Exit $ERGEBNIS_2"
exit 1
