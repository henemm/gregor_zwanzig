#!/usr/bin/env bash
# #1771 S2 — isolierter Offline-Stack fuer CI-Job `e2e`: Python-Core +
# gebauter Go-Server, offline via GZ_TEST_FIXTURE_DIR + leere Datenwurzel.
# GZ_PORT=8091 PFLICHT als DEFAULT (prodUrlGuard.ts lehnt 8090 fail-closed
# ab, 8091 ist zugleich Default von GZ_API_BASE -- keine Frontend-Overrides
# noetig). Ports ueber GZ_CI_STACK_GO_PORT/GZ_CI_STACK_PY_PORT
# ueberschreibbar, damit sich das Skript lokal auf freien Ports pruefen
# laesst, ohne Staging (8091/8001) oder Prod (8090/8000) zu stoeren.
# GZ_SESSION_SECRET bleibt UNGESETZT (halbseitig gesetzt bricht die
# Cookie-Signatur). Health-Warteschleifen statt sleep (AC-3).
# GZ_USER_ID=admin: Go-Default waere "default" (internal/config/config.go),
# aber global.setup.ts meldet sich als E2E_USER ?? 'admin' an -- ohne diese
# Zeile scheitert die Anmeldung im e2e-Job garantiert an 401 (PR-Review
# #1771 S2, Defekt 1). Variante bewusst HIER statt `E2E_USER=default` in
# ci.yml: dieses Skript ist bereits die alleinige Quelle fuer den
# Auth-/Umgebungs-Zustand des isolierten Stacks (GZ_AUTH_PASS, GZ_ENV) --
# ein zweiter Stellhebel in ci.yml wuerde denselben Zustand doppelt pflegen.
# Aufruf: ci-stack.sh start|stop
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="${GZ_CI_STACK_STATE_DIR:-/tmp/gz-e2e-stack}"
DATA_ROOT="${GZ_CI_STACK_DATA_DIR:-${STATE_DIR}/data}"
GO_BIN="${GREGOR_SERVER_BIN:-/tmp/gregor-server}"
GO_PORT="${GZ_CI_STACK_GO_PORT:-8091}"
PY_PORT="${GZ_CI_STACK_PY_PORT:-8000}"
PY_HEALTH_URL="http://127.0.0.1:${PY_PORT}/health"
GO_HEALTH_URL="http://127.0.0.1:${GO_PORT}/api/health"
HEALTH_TIMEOUT_SEC="${GZ_CI_STACK_HEALTH_TIMEOUT:-60}"

wait_for_health() {
	local url="$1" name="$2" waited=0
	while ! curl -fsS -o /dev/null "$url" 2>/dev/null; do
		sleep 1
		waited=$((waited + 1))
		[ "$waited" -lt "$HEALTH_TIMEOUT_SEC" ] || {
			echo "FEHLER: $name unter $url nach ${HEALTH_TIMEOUT_SEC}s nicht bereit." >&2
			return 1
		}
	done
	echo "$name bereit nach ${waited}s ($url)."
}

start_stack() {
	mkdir -p "$STATE_DIR" "$DATA_ROOT/users"
	(
		cd "$REPO_ROOT"
		GZ_DATA_DIR="$DATA_ROOT" GZ_CACHE_DIR="$DATA_ROOT/cache" \
			GZ_TEST_FIXTURE_DIR=fixtures/openmeteo \
			uv run uvicorn api.main:app --host 127.0.0.1 --port "$PY_PORT" \
			> "$STATE_DIR/python-core.log" 2>&1 &
		echo $! > "$STATE_DIR/python-core.pid"
	)
	GZ_PORT="$GO_PORT" GZ_PYTHON_CORE_URL="http://localhost:${PY_PORT}" \
		GZ_DATA_DIR="$DATA_ROOT" GZ_CACHE_DIR="$DATA_ROOT/cache" \
		GZ_TEST_FIXTURE_DIR="$REPO_ROOT/fixtures/openmeteo" \
		GZ_USER_ID=admin GZ_AUTH_PASS=test1234 GZ_ENV=staging \
		"$GO_BIN" > "$STATE_DIR/go-server.log" 2>&1 &
	echo $! > "$STATE_DIR/go-server.pid"

	wait_for_health "$PY_HEALTH_URL" "Python-Core"
	wait_for_health "$GO_HEALTH_URL" "Go-Server"
}

stop_stack() {
	for pidfile in "$STATE_DIR/python-core.pid" "$STATE_DIR/go-server.pid"; do
		[ -f "$pidfile" ] || continue
		pid="$(cat "$pidfile")"
		if kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null || true; fi
		rm -f "$pidfile"
	done
}

case "${1:-}" in
	start) start_stack ;;
	stop) stop_stack ;;
	*) echo "Nutzung: $0 {start|stop}" >&2; exit 2 ;;
esac
