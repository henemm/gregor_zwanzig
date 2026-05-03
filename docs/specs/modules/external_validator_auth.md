---
entity_id: external_validator_auth
type: module
created: 2026-05-02
updated: 2026-05-02
status: draft
version: "1.0"
tags: [validator, auth, tooling, workflow]
---

# External Validator Auth

## Approval

- [ ] Approved

## Purpose

Der External Validator (`bash .claude/validate-external.sh`) prueft eingeloggte App-Routen in einer isolierten `claude --print`-Session. Da die App hinter einem `gz_session`-Cookie liegt, loggt sich der Launcher vor dem Session-Spawn automatisch via `POST /api/auth/login` ein, extrahiert den Cookie-Wert und injiziert ihn als Text in den Validator-Prompt — damit hat der Validator vollen Zugriff auf geschuetzte `/api/*`-Routen, ohne dass ein HMAC-Direkt-Bypass oder ein vierter Auth-Code-Pfad noetig wird.

## Source

- **File:** `.claude/validate-external.sh`
- **Identifier:** Launcher-Skript — Login-Block (vor `claude --print`-Spawn) und Auth-Block-Injection in den Prompt-Text. Sekundaer-Edits an `.claude/agents/external-validator.md` (Abschnitt `Authenticated Requests`) und neue Datei `scripts/setup-validator-user.sh` (siehe Implementation Details).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/auth.go::LoginHandler` | Go HTTP-Handler | Validator-Launcher nutzt `POST /api/auth/login` fuer Cookie-Erzeugung |
| `internal/handler/auth.go::RegisterHandler` | Go HTTP-Handler | Setup-Skript nutzt `POST /api/auth/register` fuer idempotenten Test-User-Setup |
| `internal/middleware/auth.go::AuthMiddleware` | Go Middleware | Setzt `gz_session`-Cookie als Voraussetzung fuer alle nicht-public `/api/*`-Routen |
| `staging.gregor20.henemm.com` | Externer Service | Ziel-Server fuer Validator-Tests (Default); kein Test-User auf Production |
| `.claude/validator.env` | Lokale Config (gitignored) | Username + Password des Test-Users (`GZ_VALIDATOR_USER`, `GZ_VALIDATOR_PASS`, `GZ_VALIDATION_URL`) |
| `claude --print` | CLI-Subprocess | Isolierte Validator-Session — Cookie wird im Prompt-Text injiziert, kein direkter Env-Zugriff |

## Implementation Details

### `.claude/validate-external.sh` — Login-Block (vor `claude --print`-Spawn)

```bash
ENV_FILE=".claude/validator.env"
if [ -f "$ENV_FILE" ]; then
    set -a; source "$ENV_FILE"; set +a
fi

VALIDATION_URL="${GZ_VALIDATION_URL:-https://staging.gregor20.henemm.com}"
USER="${GZ_VALIDATOR_USER:-validator}"
PASS="${GZ_VALIDATOR_PASS:-}"
COOKIE=""

if [ -n "$PASS" ]; then
    RESPONSE=$(curl -s -i -X POST "$VALIDATION_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}")
    COOKIE=$(echo "$RESPONSE" | grep -i "^set-cookie:" | grep -oE "gz_session=[^;]+" | head -1 || true)
    if [ -z "$COOKIE" ]; then
        echo "WARN: Login fehlgeschlagen — Validator laeuft ohne Auth (nur Public-Routen pruefbar)"
    fi
fi

# Auth-Block nur einbetten wenn Cookie vorhanden:
AUTH_BLOCK=""
if [ -n "$COOKIE" ]; then
    AUTH_BLOCK="
Auth-Cookie fuer /api/*-Routen: ${COOKIE}
Verwende: curl -H \"Cookie: ${COOKIE}\" ...
Public-Routen (/, /api/health, /api/scheduler/status, /api/auth/login) brauchen kein Cookie."
fi

PROMPT="Du bist der External Validator. ... [bestehender Prompt] ${AUTH_BLOCK}"
```

### `scripts/setup-validator-user.sh` — Idempotenter Test-User-Setup

```bash
#!/usr/bin/env bash
# Legt Test-User fuer External Validator in Staging an.
# Aufruf: bash scripts/setup-validator-user.sh
set -euo pipefail

source .claude/validator.env
URL="${GZ_VALIDATION_URL:-https://staging.gregor20.henemm.com}"

HTTP_CODE=$(curl -s -o /tmp/setup.out -w "%{http_code}" -X POST "$URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$GZ_VALIDATOR_USER\",\"password\":\"$GZ_VALIDATOR_PASS\"}")

case "$HTTP_CODE" in
    201) echo "Test-User '$GZ_VALIDATOR_USER' angelegt." ;;
    409) echo "Test-User '$GZ_VALIDATOR_USER' existiert bereits — OK." ;;
    *)   echo "FEHLER: HTTP $HTTP_CODE"; cat /tmp/setup.out; exit 1 ;;
esac
```

### `.claude/validator.env.example` — Credentials-Template (gitignored)

```bash
# External Validator Credentials (Issue #110)
# Kopiere zu .claude/validator.env und fuelle Werte aus.
# Diese Datei ist gitignored — niemals committen!
GZ_VALIDATOR_USER=validator
GZ_VALIDATOR_PASS=<sicheres-passwort-min-8-zeichen>
GZ_VALIDATION_URL=https://staging.gregor20.henemm.com
```

### `.claude/agents/external-validator.md` — Neuer Abschnitt `Authenticated Requests`

Einzufuegen nach dem bestehenden „Input"-Abschnitt:

```markdown
## Authenticated Requests

Wenn der Launcher dir einen `Auth-Cookie fuer /api/*-Routen`-Block uebergibt:

- Verwende fuer eingeloggte API-Routen: `curl -H "Cookie: gz_session=<value>" <url>`
- Public-Routen (`/`, `/api/health`, `/api/scheduler/status`, `/api/auth/login`) brauchen kein Cookie.
- Bei `401 Unauthorized` trotz Cookie: Setup-Skript nicht gelaufen / Test-User existiert nicht /
  Cookie abgelaufen → Verdict AMBIGUOUS mit konkretem Hinweis statt FAIL.
- Falls Browser-Test (Playwright) noetig: Cookie via
  `page.context().addCookies([{name:'gz_session', value:'...', domain:'staging.gregor20.henemm.com', path:'/'}])` setzen.
```

### `.claude/commands/5-implement.md` — Hinweis bei Step 8

Bestehenden Hinweis zu Issue #110 ersetzen durch:

```markdown
**Setup:** Einmalig `bash scripts/setup-validator-user.sh` ausfuehren, danach
`.claude/validator.env` mit User/Pass befuellen. Der Launcher loggt sich automatisch
ein und uebergibt dem Validator den Cookie.
```

### `.gitignore` — Ergaenzung

```
.claude/validator.env
```

## Expected Behavior

- **Input:** `bash .claude/validate-external.sh <SPEC_PATH>` wie bisher; optional ENV-Variablen `GZ_VALIDATION_URL`, `GZ_VALIDATOR_USER`, `GZ_VALIDATOR_PASS` (oder via `.claude/validator.env`).
- **Output:** Validator-Session erhaelt im Prompt-Text einen Auth-Cookie-Block (sofern Login erfolgreich) und nutzt `curl -H "Cookie: gz_session=<value>"` fuer `/api/*`-Calls. Bei fehlgeschlagenem Login: Warnung an stdout, Validator laeuft ohne Auth (nur Public-Routen pruefbar).
- **Side effects:** Login-Call gegen Staging-API erzeugt eine kurze Session (24h TTL). `setup-validator-user.sh` legt einen `validator`-User in Staging an (idempotent). Keine Aenderung an Production-Code, kein Auth-Bypass.

## Known Limitations

- Cookie-TTL ist 24h — bei sehr langen Validator-Laeufen (>24h) liefe das Cookie ab; praktisch irrelevant.
- Test-User existiert nur in Staging. Validator gegen Production laeuft ohne Auth (manuelle Smoke-Tests reichen fuer Final-Validation nach Prod-Deploy).
- `WebFetch` unterstuetzt keinen Cookie-Header → Validator muss `curl via Bash` nutzen, kein WebFetch fuer eingeloggte Routen.
- Aktuell nutzen Staging und Prod denselben `GZ_SESSION_SECRET` (Status quo, separates Sicherheitsthema). Falls die Secrets spaeter getrennt werden, muesste pro Stage ein eigener Test-User angelegt werden.

## Changelog

- 2026-05-02: Initial spec — Issue #110 (External Validator Auth via Login-Call)
