#!/usr/bin/env bash
#
# telegram_set_commands.sh — Telegram Bot-Menü verwalten (Issue #650).
#
# Registriert / entfernt / inspiziert die Bot-Befehlsliste (setMyCommands).
# Telegram-Clients zeigen die Befehle als antippbares Menü an.
#
# Die maßgebliche Befehlsliste lebt im Code (src/outputs/telegram.py → BOT_COMMANDS).
# Dieses Script ist der dünne Ops-Wrapper für das einmalige Deploy-Setup; für 'set'
# wird die Liste aus BOT_COMMANDS abgeleitet, damit es genau EINE Quelle gibt.
#
# Erforderliche ENV:
#   TELEGRAM_BOT_TOKEN   Bot-Token (Prod vs. Staging GETRENNT!)
#
# Verwendung:
#   ./telegram_set_commands.sh set      # BOT_COMMANDS registrieren/aktualisieren
#   ./telegram_set_commands.sh info     # aktuelle Befehlsliste anzeigen (getMyCommands)
#   ./telegram_set_commands.sh delete   # Befehlsmenü entfernen (deleteMyCommands)
#
set -euo pipefail

API="https://api.telegram.org"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# #2961: Geheimnisse (Bot-Token in der URL, Secrets, API-Schluessel) gehen nie als
# Prozessargument an curl (sichtbar in `ps`), sondern als curl-Konfiguration ueber
# stdin (`-K -`). cfg schreibt eine Konfigurationszeile mit Escaping; printf ist ein
# bash-Builtin und erzeugt keinen eigenen Prozess.
cfg() {
	local v=$2
	v=${v//\\/\\\\}
	v=${v//\"/\\\"}
	printf '%s = "%s"\n' "$1" "$v"
}

usage() {
	grep '^#' "$0" | sed 's/^# \{0,1\}//'
	exit "${1:-0}"
}

require() {
	local name="$1"
	if [ -z "${!name:-}" ]; then
		echo "FEHLER: ENV-Variable \$$name ist nicht gesetzt." >&2
		exit 1
	fi
}

# BOT_COMMANDS aus dem Code als JSON ableiten — einzige Quelle der Wahrheit.
# Nutzt die Projekt-Umgebung (uv), damit der app.config/pydantic-Importpfad steht.
commands_json() {
	( cd "${REPO_ROOT}" && PYTHONPATH="${REPO_ROOT}/src" uv run --quiet python3 -c \
		'import json; from outputs.telegram import BOT_COMMANDS; print(json.dumps(BOT_COMMANDS, ensure_ascii=False))' )
}

cmd="${1:-}"
case "$cmd" in
	set)
		require TELEGRAM_BOT_TOKEN
		echo "Registriere Bot-Menü (setMyCommands) aus BOT_COMMANDS…"
		cfg url "${API}/bot${TELEGRAM_BOT_TOKEN}/setMyCommands" | curl -fsS -X POST -K - \
			-H "Content-Type: application/json" \
			--data-binary "{\"commands\": $(commands_json)}" | sed 's/.*/→ &/'
		echo
		;;
	info)
		require TELEGRAM_BOT_TOKEN
		cfg url "${API}/bot${TELEGRAM_BOT_TOKEN}/getMyCommands" | curl -fsS -K - | sed 's/.*/→ &/'
		echo
		;;
	delete)
		require TELEGRAM_BOT_TOKEN
		echo "Entferne Bot-Menü (deleteMyCommands)…"
		cfg url "${API}/bot${TELEGRAM_BOT_TOKEN}/deleteMyCommands" | curl -fsS -X POST -K - | sed 's/.*/→ &/'
		echo
		;;
	-h|--help|help)
		usage 0
		;;
	*)
		echo "Unbekannter Befehl: '${cmd}'" >&2
		usage 1
		;;
esac
