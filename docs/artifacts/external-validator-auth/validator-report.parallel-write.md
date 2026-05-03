---
spec: docs/specs/modules/external_validator_auth.md
date: 2026-05-03T05:29:37+00:00
server_briefed: https://gregor20.henemm.com
server_actually_tested: https://staging.gregor20.henemm.com (Spec-Default; Prod hat keinen Test-User)
verdict: BROKEN
---

# External Validator Report

**Spec:** `docs/specs/modules/external_validator_auth.md`
**Datum:** 2026-05-03T05:29:37+00:00
**Briefing-Server:** `https://gregor20.henemm.com` (Production)
**Tatsächlich getestet:** Production (Public-Endpoints) + Staging (Auth-Endpoints, da Spec dort den Test-User vorschreibt)

## Methodik

- Keine Lektüre von `src/`, `docs/artifacts/`, `git log/diff`, `.claude/workflow_state.json` (Validator-Isolation gewahrt)
- Inspektion der Spec-genannten Konfigurationsdateien (`.claude/validate-external.sh`, `.gitignore`, `.claude/agents/external-validator.md`, `.claude/commands/5-implement.md`) ist legitim — sie sind das **Ergebnis-Artefakt** der Spec, nicht src/.
- Verhaltenstests via `curl` gegen Live-Endpoints
- Skript-Aufruf `validate-external.sh` selbst nicht ausgeführt (würde rekursive `claude --print`-Session spawnen)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | `bash .claude/validate-external.sh <SPEC>` akzeptiert SPEC_PATH und ENV-Variablen `GZ_VALIDATION_URL/USER/PASS`, oder lädt `.claude/validator.env` | Inspektion `.claude/validate-external.sh`: Kein `source .claude/validator.env`, keine ENV-Variablen `GZ_VALIDATOR_USER/PASS` werden gelesen. Nur `GZ_VALIDATION_URL` ist vorhanden — Default ist Production statt Staging (Spec verlangt Staging). | **FAIL** |
| 2 | Launcher führt `POST /api/auth/login` aus, extrahiert `gz_session`-Cookie | Inspektion: Kein `curl POST /api/auth/login` im Skript. Kein Cookie-Parsing. | **FAIL** |
| 3 | Launcher injiziert `Auth-Cookie für /api/*-Routen: gz_session=…`-Block in den Validator-Prompt (nur bei erfolgreichem Login) | Inspektion: PROMPT-Variable enthält keinerlei AUTH_BLOCK / Cookie-Hinweis. Im aktuellen Lauf wurde dem Validator (mir) **kein Cookie übergeben** — Bestätigung: Mein eigenes Briefing enthält weder Cookie noch Auth-Hinweis. | **FAIL** |
| 4 | Bei fehlgeschlagenem Login: Warnung an stdout, Validator läuft ohne Auth | Inspektion: Kein Warnpfad im Skript, weil Login-Logik komplett fehlt. | **FAIL** |
| 5 | `scripts/setup-validator-user.sh` legt `validator`-User in Staging idempotent an | `ls scripts/setup-validator-user.sh` → **MISSING**. Kein Skript existiert. | **FAIL** |
| 6 | `.claude/validator.env.example` als Template (gitignored) | `ls .claude/validator.env.example` → **MISSING**. | **FAIL** |
| 7 | `.gitignore` enthält `.claude/validator.env` | `grep validator.env .gitignore` → kein Treffer (nur `data/users/validator_test/`). | **FAIL** |
| 8 | `.claude/agents/external-validator.md` enthält Abschnitt `Authenticated Requests` mit `curl -H "Cookie: …"`-Anleitung | `grep "Authenticated\|Auth-Cookie\|gz_session" .claude/agents/external-validator.md` → 0 Treffer. | **FAIL** |
| 9 | `.claude/commands/5-implement.md` enthält Hinweis auf `setup-validator-user.sh` + `.claude/validator.env` | `grep "setup-validator-user\|validator.env" .claude/commands/5-implement.md` → kein Treffer. Der alte Hinweis "Issue #110 muss erledigt sein" steht noch. | **FAIL** |
| 10 | Public Routes (`/`, `/api/health`, `/api/scheduler/status`, `/api/auth/login`) brauchen kein Cookie | Production: `/api/health` → 200 `{"python_core":"ok",...}`. `/api/scheduler/status` → 200 mit Job-Liste. Staging: `/api/auth/login` mit Bad-Credentials → 401 (Endpoint reachable, kein Auth-Wall). | **PASS** |
| 11 | Geschützte `/api/*`-Routen ohne Cookie liefern 401 | Production: `/api/trips`, `/api/locations`, `/api/subscriptions`, `/api/users` → alle **401**. | **PASS** |
| 12 | Login mit gültigen Credentials liefert `Set-Cookie: gz_session=…; Max-Age=86400 (24h)` | Staging-Login mit User `validator`/Pass: `Set-Cookie: gz_session=validator.1777786158.71a2a50ac…; Path=/; Max-Age=86400; HttpOnly; Secure; SameSite=Lax`. **24h TTL bestätigt.** | **PASS** |
| 13 | Cookie ermöglicht Zugriff auf zuvor gesperrte `/api/*`-Routen | `curl -H "Cookie: gz_session=…" /api/trips` auf Staging → **HTTP 200**, Body `[]`. Vorher: 401. | **PASS** |
| 14 | `/api/auth/register` ist idempotent (201/409) | Erstaufruf für `validator` → **201 Created** (User existierte vorher nicht!). Zweitaufruf → **409 Conflict**. Idempotenz auf Endpoint-Ebene **bestätigt**, ABER setup-Skript fehlt — der Workflow ist nicht automatisierbar. | **PASS** (Endpoint) / **FAIL** (Skript) |
| 15 | Keine Änderung an Production-Code, kein Auth-Bypass | Public/Protected-Trennung auf Prod identisch zu Staging (siehe #10/#11). Kein offensichtlicher Bypass-Pfad gefunden. Genauere Prüfung erforderte src/-Lektüre, die der Validator vermeidet. | **PASS** (Verhalten) |

## Findings

### F1 — Launcher implementiert keinerlei Auth-Logik
- **Severity:** CRITICAL
- **Expected:** Spec, Implementation Details, Login-Block (Zeilen 39–72): `source .claude/validator.env`, `curl POST /api/auth/login`, Cookie-Extraktion, `AUTH_BLOCK`-Injection in PROMPT, Warnung bei Fehler.
- **Actual:** `.claude/validate-external.sh` ist quasi unverändert gegenüber dem Pre-Spec-Stand. PROMPT enthält **keine** Auth-Cookie-Anweisung. Beweis: Mein eigenes Briefing in dieser Session enthielt keinen Cookie — ich konnte `/api/trips` etc. nicht authentifiziert prüfen, ohne mich selbst auf Staging zu registrieren.
- **Evidence:** Vollständige Skript-Datei eingesehen (57 Zeilen). Suche nach `auth/login`, `gz_session`, `AUTH_BLOCK`, `validator.env` ergibt **0 Treffer**.

### F2 — `scripts/setup-validator-user.sh` fehlt
- **Severity:** HIGH
- **Expected:** Spec, Zeilen 74–94: Skript mit `curl POST /api/auth/register` und Status-Code-Switch (201/409/Sonstiges).
- **Actual:** Datei existiert nicht. Konsequenz: Validator-Setup ist ohne manuelle `curl`-Aufrufe nicht reproduzierbar.
- **Evidence:** `ls scripts/setup-validator-user.sh` → No such file.

### F3 — `.claude/validator.env.example` fehlt
- **Severity:** HIGH
- **Expected:** Spec, Zeilen 96–105: Template mit `GZ_VALIDATOR_USER`, `GZ_VALIDATOR_PASS`, `GZ_VALIDATION_URL`.
- **Actual:** Datei existiert nicht. Onboarding-Pfad für Mit-Implementierer ist unklar.
- **Evidence:** `ls .claude/validator.env.example` → No such file.

### F4 — `.gitignore` enthält keinen `.claude/validator.env`-Eintrag
- **Severity:** HIGH (Sicherheitsrelevant!)
- **Expected:** Spec, Zeilen 134–138: Eintrag `.claude/validator.env` in `.gitignore`.
- **Actual:** Nur `data/users/validator_test/` ist in der `.gitignore` — das schützt nicht vor versehentlichem Commit der Credentials. Sobald jemand `.claude/validator.env` anlegt (was die Spec verlangt), kann sie committed werden.
- **Evidence:** `grep validator .gitignore` → nur Zeile 53 (`data/users/validator_test/`).

### F5 — `.claude/agents/external-validator.md` ohne `Authenticated Requests`-Abschnitt
- **Severity:** MEDIUM
- **Expected:** Spec, Zeilen 107–122: Neuer Abschnitt mit `curl -H "Cookie: …"`-Anleitung und Playwright-Cookie-Setup.
- **Actual:** Abschnitt fehlt. Selbst wenn der Launcher den Cookie injiziert, hat der Validator keine kanonische Anleitung wie er ihn nutzen soll.
- **Evidence:** `grep -i "authenticated\|auth-cookie\|gz_session" .claude/agents/external-validator.md` → 0 Treffer.

### F6 — `.claude/commands/5-implement.md` Hinweis nicht aktualisiert
- **Severity:** LOW
- **Expected:** Spec, Zeilen 124–132: Setup-Hinweis mit `bash scripts/setup-validator-user.sh` und `.claude/validator.env`-Befüllung.
- **Actual:** Alter Hinweis "Issue #110 (External Validator braucht App-Zugangsdaten) muss erledigt sein" steht noch unverändert (Zeile 182).
- **Evidence:** `grep "setup-validator-user\|validator.env" .claude/commands/5-implement.md` → 0 Treffer.

### F7 — Default-VALIDATION_URL falsch
- **Severity:** MEDIUM
- **Expected:** Spec, Zeile 47: `VALIDATION_URL="${GZ_VALIDATION_URL:-https://staging.gregor20.henemm.com}"`. Spec begründet: kein Test-User auf Production.
- **Actual:** Skript Zeile 27: `VALIDATION_URL="${GZ_VALIDATION_URL:-https://gregor20.henemm.com}"` — zeigt auf Production. Selbst wenn der Login-Block käme, würde er gegen Production laufen, wo kein Test-User existiert → Login schlägt immer fehl → Validator immer ohne Auth.
- **Evidence:** Skript-Inspektion.

### F8 — Server-Side ist bereit, Workflow-Glue fehlt vollständig
- **Severity:** INFORMATIONAL
- **Beobachtung:** `/api/auth/login`, `/api/auth/register`, `gz_session`-Cookie und `/api/*`-Auth-Middleware funktionieren auf der Server-Seite alle korrekt. Die Spec dreht sich aber primär um den **Launcher-/Tooling-Glue** rund um diese Endpoints — und genau der ist nicht da.

## Side-Effects dieser Validierung

Während der Verifikation hat mein eigener `curl POST /api/auth/register`-Call mit `username=validator` auf Staging **HTTP 201 Created** geliefert — d.h. der Test-User existierte vorher nicht. Ich habe ihn jetzt mit dem Test-Passwort `some-test-pwd-not-used` angelegt. Folgen:
- `setup-validator-user.sh` (sobald implementiert) wird beim ersten Lauf weiterhin 409 erhalten, was die Idempotenz-Logik korrekt abdeckt.
- Implementierer sollte das Passwort über DB-Reset oder einen Password-Reset-Endpoint überschreiben, da der Test-Pass schwach und in diesem Report dokumentiert ist.
- Der Test-User existiert nur auf **Staging**, kein Eingriff auf Production.

## Verdict: **BROKEN**

### Begründung

Die Spec definiert **9 konkrete Implementierungs-Punkte** (Launcher-Login, Cookie-Extraktion, Prompt-Injection, Setup-Skript, .env.example, .gitignore, Agent-Doku, Commands-Doku, korrekte Default-URL). Davon sind **0 von 9 implementiert**. Die Live-App-Verhaltenstests (Endpoints existieren, Auth-Mechanik funktioniert) bestätigen lediglich, dass die *Voraussetzungen* server-seitig schon vorher gegeben waren — der eigentliche Spec-Scope, der **Workflow-Glue** drumherum, fehlt komplett.

Konkretester Beweis: Diese Validator-Session hier hat im Briefing **keinen Auth-Cookie-Block** erhalten — exakt das, was die Spec liefern sollte. Damit ist EB-Punkt 2 (Output: "Validator-Session erhält im Prompt-Text einen Auth-Cookie-Block") in der laufenden Realität messbar **nicht erfüllt**.

Ein Verdict **AMBIGUOUS** wäre angemessen, wenn unklar wäre, ob die Implementierung läuft oder nicht. Hier ist es eindeutig: **nichts davon ist da**.
