#!/usr/bin/env bash
# Idempotent: legt Test-User fuer External Validator in Staging an (Issue #110).
# Aufruf: bash scripts/setup-validator-user.sh
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE=".claude/validator.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "FEHLER: $ENV_FILE fehlt. Kopiere .claude/validator.env.example und fuelle Werte aus." >&2
    exit 1
fi

set -a; source "$ENV_FILE"; set +a

URL="${GZ_VALIDATION_URL:-https://staging.gregor20.henemm.com}"
USER="${GZ_VALIDATOR_USER:?GZ_VALIDATOR_USER muss gesetzt sein}"
PASS="${GZ_VALIDATOR_PASS:?GZ_VALIDATOR_PASS muss gesetzt sein}"

HTTP_CODE=$(curl -s -o /tmp/validator-setup.out -w "%{http_code}" -X POST "$URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}")

case "$HTTP_CODE" in
    201) echo "Test-User '$USER' angelegt auf $URL." ;;
    409) echo "Test-User '$USER' existiert bereits auf $URL — OK." ;;
    *)
        echo "FEHLER: HTTP $HTTP_CODE beim Anlegen von '$USER':" >&2
        cat /tmp/validator-setup.out >&2
        exit 1
        ;;
esac
