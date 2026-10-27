#!/usr/bin/env bash
#
# seven_hooks.sh — seven.io-Webhook (Event sms_mo) fuer den Premium-SMS-Eingang verwalten (#2439).
#
# Listet / registriert / entfernt Hooks der seven.io Hooks-API. 'set' ist idempotent:
# existiert schon ein Hook mit gleicher Ziel-URL UND gleichem Event, wird nichts angelegt.
# Jede Ausgabe maskiert das Pfad-Secret der Ziel-URL (.../api/webhooks/sms/****); API-Schluessel
# und Signing-Key werden nie ausgegeben (der Signing-Key kommt aus dem seven.io-Dashboard).
#
# Erforderliche ENV:
#   GZ_SEVEN_API_KEY           seven.io API-Schluessel (Header X-Api-Key)
#   GZ_PUBLIC_HOST             nur 'set': Basis-URL der Zielumgebung, z.B. https://gregor20.henemm.com
#   SEVEN_WEBHOOK_PATH_SECRET  nur 'set': Pfad-Secret (== ENV des Go-Prozesses der Zielumgebung)
#   SEVEN_SERVICE_NUMBER       nur 'set': Servicenummer; geht OHNE fuehrendes '+' als event_filter
# Optional:
#   SEVEN_API_BASE             Basis der Hooks-API (Default https://gateway.seven.io/api)
#
# Verwendung:
#   ./seven_hooks.sh list          # alle Hooks (ID, Event, Filter, Ziel, angelegt am)
#   ./seven_hooks.sh set           # Hook fuer GZ_PUBLIC_HOST registrieren (idempotent)
#   ./seven_hooks.sh delete <id>   # genau diesen Hook entfernen (Rollback)
#
set -euo pipefail

API="${SEVEN_API_BASE:-https://gateway.seven.io/api}"
EVENT="sms_mo"
MASKE='s#(/api/webhooks/sms/)[^/"[:space:]]+#\1****#g'

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

maskiert() {
	sed -E "$MASKE"
}

hooks_holen() {
	curl -fsS -H "X-Api-Key: ${GZ_SEVEN_API_KEY}" "${API}/hooks"
}

cmd="${1:-}"
case "$cmd" in
	list)
		require GZ_SEVEN_API_KEY
		hooks_holen | jq -r '.hooks[]? | "ID \(.id)  \(.event_type)  filter=\(.event_filter)  \(.target_url)  angelegt \(.created)"' | maskiert
		;;
	set)
		require GZ_SEVEN_API_KEY
		require GZ_PUBLIC_HOST
		require SEVEN_WEBHOOK_PATH_SECRET
		require SEVEN_SERVICE_NUMBER
		url="${GZ_PUBLIC_HOST%/}/api/webhooks/sms/${SEVEN_WEBHOOK_PATH_SECRET}"
		anzeige="$(printf '%s' "$url" | maskiert)"
		vorhanden="$(hooks_holen | jq -r --arg u "$url" --arg e "$EVENT" \
			'[.hooks[]? | select(.target_url == $u and .event_type == $e) | .id][0] // empty')"
		if [ -n "$vorhanden" ]; then
			echo "Hook bereits vorhanden — übersprungen, ID ${vorhanden}: ${anzeige}"
			exit 0
		fi
		antwort="$(curl -fsS -X POST "${API}/hooks" \
			-H "X-Api-Key: ${GZ_SEVEN_API_KEY}" \
			--data-urlencode "target_url=${url}" \
			--data-urlencode "event_type=${EVENT}" \
			--data-urlencode "event_filter=${SEVEN_SERVICE_NUMBER#+}" \
			--data-urlencode "request_method=POST")"
		neue_id="$(printf '%s' "$antwort" | jq -r '.id // empty')"
		echo "Hook angelegt, ID ${neue_id:-?}: ${anzeige}"
		;;
	delete)
		require GZ_SEVEN_API_KEY
		id="${2:-}"
		if [ -z "$id" ]; then
			echo "FEHLER: delete braucht die Hook-ID." >&2
			usage 1
		fi
		curl -fsS -G -X DELETE "${API}/hooks" \
			-H "X-Api-Key: ${GZ_SEVEN_API_KEY}" \
			--data-urlencode "id=${id}" >/dev/null
		echo "Hook ${id} entfernt."
		;;
	-h|--help|help)
		usage 0
		;;
	*)
		echo "Unbekannter Befehl: '${cmd}'" >&2
		usage 1
		;;
esac
