#!/usr/bin/env bash
# Idempotent: legt Test-User fuer External Validator in Staging an (Issue #110).
# Aufruf: bash scripts/setup-validator-user.sh
#
# #2961: Zugangsdaten gehen nie als Prozessargument an curl (sichtbar in `ps`),
# sondern per Konfiguration ueber stdin (-K -) bzw. als Datei mit 0600 in einem
# eigenen, per mktemp angelegten Verzeichnis, das am Ende geloescht wird.
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE=".claude/validator.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "FEHLER: $ENV_FILE fehlt. Kopiere .claude/validator.env.example und fuelle Werte aus." >&2
    exit 1
fi

# shellcheck source=/dev/null
set -a; source "$ENV_FILE"; set +a

URL="${GZ_VALIDATION_URL:-https://staging.gregor20.henemm.com}"
USER="${GZ_VALIDATOR_USER:?GZ_VALIDATOR_USER muss gesetzt sein}"
PASS="${GZ_VALIDATOR_PASS:?GZ_VALIDATOR_PASS muss gesetzt sein}"

umask 077
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Wert fuer eine curl-Konfigurationszeile in Anfuehrungszeichen setzen.
cfg_quote() {
    local v=$1
    v=${v//\\/\\\\}
    v=${v//\"/\\\"}
    printf '"%s"' "$v"
}

# JSON-Koerper als Datei (0600); Werte kommen per Umgebung, nicht per argv.
json_body() {  # json_body <datei> <mit_testflag: 0|1>
    GZ_U="$USER" GZ_P="$PASS" GZ_T="$2" python3 -c '
import json, os, sys
body = {"username": os.environ["GZ_U"], "password": os.environ["GZ_P"]}
if os.environ["GZ_T"] == "1":
    body["is_test_user"] = True
sys.stdout.write(json.dumps(body))
' > "$1"
}

# POST mit Basic-Auth aus stdin-Konfiguration; gibt den HTTP-Code aus.
post() {  # post <pfad> <body-datei> <antwort-datei>
    printf 'user = %s\n' "$(cfg_quote "$USER:$PASS")" | curl -s -K - \
        -o "$3" -w "%{http_code}" -X POST "$URL$1" \
        -H "Content-Type: application/json" \
        --data-binary @"$2"
}

# is_test_user:true (Issue #2152): Testkonto-Status kommt aus dem Profilfeld,
# nicht mehr aus dem Namen — sonst liefe der Validator-User im Fan-out mit.
json_body "$TMP/register.json" 1
HTTP_CODE=$(post /api/auth/register "$TMP/register.json" "$TMP/setup.out")

case "$HTTP_CODE" in
    201) echo "Test-User '$USER' angelegt auf $URL." ;;
    409|429)
        # 409 = User existiert bereits; 429 = Rate-Limit beim Register-Endpoint.
        # In beiden Fällen: Login verifizieren — User ist vermutlich bereits vorhanden.
        echo "Test-User '$USER' existiert bereits auf $URL (HTTP $HTTP_CODE) — Login wird verifiziert..."
        json_body "$TMP/login.json" 0
        LOGIN_CODE=$(post /api/auth/login "$TMP/login.json" "$TMP/login.out")
        if [ "$LOGIN_CODE" = "200" ]; then
            echo "Login OK."
        elif [ "$LOGIN_CODE" = "429" ]; then
            echo "WARN: Login-Endpunkt rate-limitiert (429) — Login-Verifikation übersprungen (Passwort als korrekt angenommen)."
        else
            echo "FEHLER: Login fehlgeschlagen (HTTP $LOGIN_CODE) — Passwort stimmt nicht mit validator.env überein." >&2
            echo "Reparatur: sqlite3 <DB_PFAD> \"DELETE FROM users WHERE id='$USER';\" && bash $0" >&2
            exit 1
        fi
        ;;
    *)
        echo "FEHLER: HTTP $HTTP_CODE beim Anlegen von '$USER':" >&2
        cat "$TMP/setup.out" >&2
        exit 1
        ;;
esac
