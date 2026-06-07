#!/usr/bin/env bash
#
# telegram_set_webhook.sh — Telegram Inbound Webhook verwalten (Issue #637).
#
# Registriert / entfernt / inspiziert den Telegram-Webhook für den Gregor-Bot.
# Der öffentliche Go-Endpoint prüft das Secret über den von Telegram gesendeten
# Header X-Telegram-Bot-Api-Secret-Token. setWebhook registriert diesen
# secret_token bei Telegram.
#
# Erforderliche ENV:
#   TELEGRAM_BOT_TOKEN       Bot-Token (Prod vs. Staging GETRENNT!)
#   TELEGRAM_WEBHOOK_SECRET  geheimes Token (== ENV des Go-Prozesses)
#   GZ_PUBLIC_BASE_URL       z.B. https://gregor20.henemm.com (nur für 'set')
#
# Verwendung:
#   ./telegram_set_webhook.sh set      # Webhook registrieren/aktualisieren
#   ./telegram_set_webhook.sh delete   # Webhook entfernen (Rollback → Polling)
#   ./telegram_set_webhook.sh info     # aktuellen Webhook-Status anzeigen
#
set -euo pipefail

API="https://api.telegram.org"

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

cmd="${1:-}"
case "$cmd" in
	set)
		require TELEGRAM_BOT_TOKEN
		require TELEGRAM_WEBHOOK_SECRET
		require GZ_PUBLIC_BASE_URL
		# Das {secret}-Pfadsegment ist Defense-in-Depth-Routing, NICHT der
		# Auth-Träger — die echte Prüfung läuft über secret_token (Header).
		url="${GZ_PUBLIC_BASE_URL%/}/api/webhooks/telegram/${TELEGRAM_WEBHOOK_SECRET}"
		echo "Registriere Webhook → ${GZ_PUBLIC_BASE_URL%/}/api/webhooks/telegram/<secret>"
		curl -fsS -X POST "${API}/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
			--data-urlencode "url=${url}" \
			--data-urlencode "secret_token=${TELEGRAM_WEBHOOK_SECRET}" \
			--data-urlencode "drop_pending_updates=false" | sed 's/.*/→ &/'
		echo
		;;
	delete)
		require TELEGRAM_BOT_TOKEN
		echo "Entferne Webhook (Rollback → Polling möglich)…"
		curl -fsS -X POST "${API}/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook" \
			--data-urlencode "drop_pending_updates=false" | sed 's/.*/→ &/'
		echo
		;;
	info)
		require TELEGRAM_BOT_TOKEN
		curl -fsS "${API}/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | sed 's/.*/→ &/'
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
