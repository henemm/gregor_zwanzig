#!/usr/bin/env bash
# Faehrt e2e/passkey-login.spec.ts in geteilten Playwright-Aufrufen mit einem
# Neustart des Go-Servers dazwischen.
#
# WARUM GETEILT (Spec docs/specs/modules/passkey_login_anordnung.md,
# Rate-Limit-Abschnitt): alle Passkey-Routen teilen EINEN IP-Eimer von 30
# Anfragen/Stunde (internal/router/router.go:97). Ein vollstaendiger
# Passkey-Login kostet ZWEI Anfragen (begin+finish), UND schon der blosse
# Aufruf von /login kann ueber die im Hintergrund laufende Autofill-Anbindung
# (discoverable/begin) ein weiteres Token ziehen. AC-9a/AC-9b/AC-10/AC-7
# rufen die Passkey-Routen wiederholt auf -- ein Lauf am Stueck liefe
# zuverlaessig in HTTP 429, sichtbar als "Knopf erscheint nicht" statt als
# Rate-Limit-Meldung (dasselbe Muster wie run-passkey-konto.sh).
#
# Aufteilung entlang der Anfragelast, nicht nach Testnummer:
#   Teil 1 "AC-1|AC-2|AC-5|AC-6|AC-8"   Positions-/Sichtbarkeits-/Hoehen-Tests,
#                                        pro Testfall hoechstens EIN /login-Aufruf
#                                        (also hoechstens ein discoverable/begin)
#   Teil 2 "AC-10"                      misst genau die discoverable/begin-Zaehlung,
#                                        eigener Lauf haelt den Zaehler unbeeinflusst
#   Teil 3 "AC-7|AC-9"                  volle Zeremonien (begin+finish je 2 Anfragen,
#                                        AC-9b zusaetzlich der verkuerzte Timeout-Weg)
#
# Voraussetzung: der Preview-Server laeuft auf Port 4173, und zwar gegen
# DENSELBEN Go-Port, den dieses Skript unten setzt (8096 -- nicht 8095, das
# ist der #2246-Stack). Zeigt der Preview woanders hin, tarnt sich das als
# "Knopf erscheint nicht" statt als Konfigurationsfehler:
#   cd frontend && GZ_API_BASE=http://localhost:8096 \
#     GZ_E2E_API_PROXY_TARGET=http://localhost:8096 bash e2e/start-preview.sh
# Bei belegtem Port beide Seiten gemeinsam umstellen, z.B. ueber
# GZ_CI_STACK_GO_PORT/GZ_CI_STACK_PY_PORT plus passendes GZ_API_BASE.
#
# Aufruf (aus dem Repo-Wurzelverzeichnis oder von ueberall):
#   bash frontend/e2e/run-passkey-login.sh
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$(dirname "$HIER")"
REPO="$(dirname "$FRONTEND")"

# Eigene Ports (Go 8096, Python 8006), damit weder Produktion (8090/8000) noch
# Staging (8091/8001) noch der #2246-Lauf (8095/8005) beruehrt wird.
export GZ_CI_STACK_GO_PORT="${GZ_CI_STACK_GO_PORT:-8096}"
export GZ_CI_STACK_PY_PORT="${GZ_CI_STACK_PY_PORT:-8006}"
export GZ_CI_STACK_STATE_DIR="${GZ_CI_STACK_STATE_DIR:-/tmp/gz-e2e-stack-2247}"
export GREGOR_SERVER_BIN="${GREGOR_SERVER_BIN:-/tmp/gregor-server-2247}"
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
	(cd "$FRONTEND" && npx playwright test e2e/passkey-login.spec.ts --project=tests -g "$filter" "${@:3}")
}

stack_neu
lauf 'AC-1|AC-2|AC-5|AC-6|AC-8' 'Teil 1: Position/Sichtbarkeit/Hoehe' "${@}"
ERGEBNIS_1=$?

stack_neu
lauf 'AC-10' 'Teil 2: Autofill-Anbindung bei leerem Feld' "${@}"
ERGEBNIS_2=$?

stack_neu
lauf 'AC-7|AC-9' 'Teil 3: echte Zeremonien' "${@}"
ERGEBNIS_3=$?

echo
if [ "$ERGEBNIS_1" -eq 0 ] && [ "$ERGEBNIS_2" -eq 0 ] && [ "$ERGEBNIS_3" -eq 0 ]; then
	echo "ALLE DREI TEILE GRUEN"
	exit 0
fi
echo "ROT -- Teil 1: Exit $ERGEBNIS_1, Teil 2: Exit $ERGEBNIS_2, Teil 3: Exit $ERGEBNIS_3"
exit 1
