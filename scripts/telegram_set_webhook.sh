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
#   ./telegram_set_webhook.sh info     # Webhook-Status als ja/nein-Auswertung
#
# Registrierte URL: ${GZ_PUBLIC_BASE_URL}/api/webhooks/telegram/inbound (Issue
# #1814, kein Secret im Pfad). Secret und rohe getWebhookInfo-Antwort werden
# nie ausgegeben.
#
set -euo pipefail

API="https://api.telegram.org"

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

json_ok() {
	# Liest eine Telegram-API-Antwort (JSON) von stdin, gibt "ja"/"nein" für ok aus.
	python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    d = {}
print("ja" if isinstance(d, dict) and d.get("ok") is True else "nein")
'
}

info_auswertung() {
	# Wertet getWebhookInfo (stdin) aus, ohne URL oder Secret auszugeben.
	python3 -c '
import json, os, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    d = {}
res = d.get("result") if isinstance(d, dict) else None
res = res if isinstance(res, dict) else {}
url = str(res.get("url") or "")
secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
def jn(b):
    return "ja" if b else "nein"
print("→ Antwort ok: " + jn(isinstance(d, dict) and d.get("ok") is True))
print("→ URL endet auf /api/webhooks/telegram/inbound: " + jn(url.endswith("/api/webhooks/telegram/inbound")))
if secret:
    print("→ URL frei von Secret: " + jn(bool(url) and secret not in url))
else:
    print("→ URL frei von Secret: übersprungen (TELEGRAM_WEBHOOK_SECRET nicht gesetzt)")
print("→ last_error_message leer: " + jn(not res.get("last_error_message")))
'
}

cmd="${1:-}"
case "$cmd" in
	set)
		require TELEGRAM_BOT_TOKEN
		require TELEGRAM_WEBHOOK_SECRET
		require GZ_PUBLIC_BASE_URL
		# Issue #1814: Die registrierte URL enthält KEIN Secret. Einziger
		# Auth-Träger ist secret_token (Telegram sendet ihn als Header
		# X-Telegram-Bot-Api-Secret-Token).
		url="${GZ_PUBLIC_BASE_URL%/}/api/webhooks/telegram/inbound"
		echo "Registriere Webhook → ${url}"
		resp="$({
			cfg url "${API}/bot${TELEGRAM_BOT_TOKEN}/setWebhook"
			cfg data-urlencode "url=${url}"
			cfg data-urlencode "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
			cfg data-urlencode "drop_pending_updates=false"
		} | curl -fsS -X POST -K -)"
		ok="$(printf '%s' "$resp" | json_ok)"
		echo "→ setWebhook ok: ${ok}"
		[ "$ok" = "ja" ] || exit 1
		;;
	delete)
		require TELEGRAM_BOT_TOKEN
		echo "Entferne Webhook (Rollback → Polling möglich)…"
		{
			cfg url "${API}/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"
			cfg data-urlencode "drop_pending_updates=false"
		} | curl -fsS -X POST -K - | sed 's/.*/→ &/'
		echo
		;;
	info)
		require TELEGRAM_BOT_TOKEN
		# Issue #1814: getWebhookInfo NIE roh ausgeben (die URL kann bei
		# Alt-Registrierungen das Secret enthalten) — nur ja/nein-Auswertung.
		cfg url "${API}/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | curl -fsS -K - | info_auswertung
		;;
	-h|--help|help)
		usage 0
		;;
	*)
		echo "Unbekannter Befehl: '${cmd}'" >&2
		usage 1
		;;
esac
