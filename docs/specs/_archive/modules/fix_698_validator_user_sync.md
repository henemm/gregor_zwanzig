---
entity_id: fix_698_validator_user_sync
type: bugfix
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [bugfix, tooling, staging, validator, setup-script, validate-external, issue-698]
---

<!-- Issue #698 — fix: Validator-User-Passwort auf Staging stimmt nicht mit validator.env überein -->

# Bug #698 — Validator-User-Sync: stiller Passwort-Drift + fehlende Fehlerunterscheidung

## Approval

- [ ] Approved

## Purpose

`scripts/setup-validator-user.sh` erkennt zwar einen bereits vorhandenen User (HTTP 409),
prüft aber nicht, ob Login mit den aktuellen Credentials aus `validator.env` funktioniert.
Dadurch entsteht ein stiller Drift: Passwort geändert oder User anders angelegt → `setup`
meldet "OK", aber der Validator schlägt beim echten Login lautlos fehl.

Parallel dazu gibt `validate-external.sh` bei einem `claude --print`-Fehler (z.B. fehlendes
`ANTHROPIC_API_KEY`) dieselbe generische Fehlermeldung aus wie bei einem Gregor-Login-Fehler
(kein Cookie), was die Ursache verschleiert und den Fix erheblich verlangsamt. Beide Skripte
erhalten präzise Fehlerpfade, damit Drift sofort erkennbar ist und der Operator den richtigen
Reparaturschritt kennt.

## Source

- **File:** `scripts/setup-validator-user.sh`
- **Identifier:** 409-Zweig + Exit-Logik

- **File:** `.claude/validate-external.sh`
- **Identifier:** Login-Check + `claude --print`-Fehlerbehandlung

Schicht: **Tooling/Scripts** (Shell-Skripte außerhalb des App-Codes). Kein Go-API-Code,
kein Python-Backend-Code, kein Frontend-Code.

## Estimated Scope

- **LoC:** ~30 (+15 setup-validator-user.sh, +15 validate-external.sh)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `scripts/setup-validator-user.sh` | Shell-Script | Legt Validator-User auf Staging an; empfängt Login-Verify-Logik nach 409 |
| `.claude/validate-external.sh` | Shell-Script | Führt externe Validierung durch; empfängt differenzierte Fehlerbehandlung |
| `validator.env` | Konfigurationsdatei | Hält `VALIDATOR_USER` + `VALIDATOR_PASSWORD`; Referenzquelle für Login-Verify |
| `POST /api/auth/login` | Go-API-Endpoint (Staging) | Wird nach 409 im Setup-Script zum Login-Verify genutzt |
| `ANTHROPIC_API_KEY` | Umgebungsvariable | Fehlt sie im Subprocess, gibt `claude --print` einen 401-Anthropic-Fehler zurück |

## Implementation Details

### Schritt 1 — setup-validator-user.sh: Login nach 409 verifizieren

Im 409-Zweig direkt nach der `echo "existiert bereits"` Meldung einen echten Login-Call
gegen `POST /api/auth/login` mit den Credentials aus `validator.env` durchführen:

```bash
# nach HTTP_STATUS == 409:
LOGIN_RESPONSE=$(curl -s -o /tmp/validator_login.json -w "%{http_code}" \
  -X POST "${STAGING_BASE}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${VALIDATOR_USER}\",\"password\":\"${VALIDATOR_PASSWORD}\"}")

if [ "$LOGIN_RESPONSE" = "200" ]; then
  echo "User existiert und Login OK"
  exit 0
else
  echo "FEHLER: User existiert (409), aber Login fehlgeschlagen (HTTP $LOGIN_RESPONSE)"
  echo "Passwort stimmt nicht mit validator.env überein."
  echo "Reparatur: sqlite3 /path/to/gregor.db \"DELETE FROM users WHERE id='${VALIDATOR_USER}';\" && $0"
  exit 1
fi
```

Der SQLite-Pfad wird aus einer bekannten Konstante oder `STAGING_DB_PATH`-Env gelesen;
falls nicht gesetzt, wird er als Platzhalter mit Hinweis ausgegeben (fail-safe).

### Schritt 2 — validate-external.sh: Cookie-Fehler vs. Anthropic-API-Fehler unterscheiden

Beim Gregor-Login-Check den Cookie-Extrakt explizit auf leer prüfen und eine spezifische
Fehlermeldung ausgeben:

```bash
SESSION_COOKIE=$(umask 077; curl -s -c /tmp/validator_cookies.txt ... | grep -o 'session=[^;]*' || true)
if [ -z "$SESSION_COOKIE" ]; then
  echo "FEHLER: Gregor-Login fehlgeschlagen (kein Cookie) — setup-validator-user.sh ausführen"
  exit 1
fi
```

Beim `claude --print`-Aufruf die Ausgabe auf "Failed to authenticate" / "401" / "API key"
prüfen und gesondert abbrechen:

```bash
CLAUDE_OUTPUT=$(claude --print "$PROMPT" 2>&1)
if echo "$CLAUDE_OUTPUT" | grep -qiE "failed to authenticate|401|api key"; then
  echo "FEHLER: claude --print benötigt ANTHROPIC_API_KEY — Validator als Subagent spawnen statt dieses Script"
  exit 1
fi
```

Der Gregor-Login-Teil muss VOR dem `claude --print`-Aufruf vollständig durchlaufen —
sodass ein API-Key-Fehler nie den Login-Status verschleiert.

## Expected Behavior

- **Input:** `setup-validator-user.sh` läuft auf Staging gegen einen bereits existierenden User; `validate-external.sh` läuft mit fehlendem Gregor-Cookie oder fehlendem `ANTHROPIC_API_KEY`
- **Output:** Klare, aktionsorientierte Fehlermeldungen mit konkretem nächstem Schritt; kein generischer Fehlertext der mehrere Ursachen zusammenfasst
- **Side effects:** `setup-validator-user.sh` gibt bei Login-Erfolg nach 409 Exit 0 zurück; bei Login-Fehler Exit 1 mit SQLite-Anleitung. `validate-external.sh` gibt bei Cookie-Fehler Exit 1 mit Verweis auf setup-Script; bei Anthropic-Fehler Exit 1 mit Verweis auf Subagent-Modus.

## Acceptance Criteria

**AC-1:** Given validator-issue110 existiert bereits auf Staging (409) / When setup-validator-user.sh läuft / Then wird Login verifiziert; bei Erfolg: "User existiert und Login OK" + Exit 0; bei Misserfolg: Fehlermeldung mit SQLite-Anleitung zum Löschen + Exit 1
- Test: setup-validator-user.sh gegen Staging ausführen — bei korrektem Passwort: Exit 0 + "Login OK"-Meldung in stdout; danach Passwort in validator.env absichtlich falsch setzen + erneut ausführen → Exit 1 + Meldung enthält "sqlite3" und "DELETE"

**AC-2:** Given Login gegen Gregor-Staging schlägt fehl (kein Cookie in Response) / When validate-external.sh läuft / Then Meldung "FEHLER: Gregor-Login fehlgeschlagen (kein Cookie) — setup-validator-user.sh ausführen" + Exit 1
- Test: validate-external.sh mit falschem Passwort in validator.env ausführen → Exit 1, stderr/stdout enthält "kein Cookie" und "setup-validator-user.sh"

**AC-3:** Given validate-external.sh läuft und `claude --print` gibt "Failed to authenticate" zurück / When validate-external.sh läuft / Then Meldung "FEHLER: claude --print benötigt ANTHROPIC_API_KEY — Validator als Subagent spawnen statt dieses Script" + Exit 1; Gregor-Login-Teil läuft trotzdem sauber durch
- Test: ANTHROPIC_API_KEY unsetzen und validate-external.sh mit korrekten Gregor-Credentials ausführen → Exit 1, stderr/stdout enthält "ANTHROPIC_API_KEY" und "Subagent"; kein "kein Cookie"-Fehler davor sichtbar

## Known Limitations

- Der SQLite-Pfad für die Lösch-Anleitung in `setup-validator-user.sh` ist nur korrekt, wenn `STAGING_DB_PATH` gesetzt ist; sonst erscheint er als `<DB_PFAD>` mit Hinweistext — der Operator muss den Pfad manuell nachschlagen. Eine vollständige Automatisierung (automatisches Löschen + Neuanlegen) wurde bewusst nicht implementiert, da sie destruktiv ist und eine explizite Operator-Aktion erfordert.
- `validate-external.sh` unterscheidet Anthropic-Fehler per String-Match auf "Failed to authenticate"/"401"/"api key" — andere zukünftige `claude`-Fehlertexte werden nicht erkannt. Das ist ausreichend für den bekannten Fehlerfall aus Issue #698.

## Changelog

- 2026-06-10: Initial spec created
