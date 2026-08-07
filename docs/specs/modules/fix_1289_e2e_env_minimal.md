---
entity_id: fix_1289_e2e_env_minimal
type: bugfix
created: 2026-08-07
updated: 2026-08-07
status: draft
version: "1.0"
tags: [e2e, secrets, playwright, security]
workflow: fix-1289-e2e-env-minimal
---

# Fix #1289 — E2E-Preview-Server bekommt nur die Environment-Variablen, die er wirklich liest

## Approval

- [ ] Approved

## Purpose

`frontend/e2e/start-preview.sh` sourced heute blanket die komplette
Haupt-`.env` (`set -a; source ../../.env; set +a`) und reicht damit alle
41 dort gesetzten Schlüssel — darunter echte Secrets wie `GZ_SMTP_PASS`,
`GZ_TELEGRAM_BOT_TOKEN`, `GZ_IMAP_PASS`, `GZ_METEOFRANCE_APIKEY` — in den
Prozess-Environment des lokalen Playwright-Preview-Servers weiter, obwohl
der SvelteKit-Preview-Prozess laut vollständiger Messung nur genau vier
Variablen tatsächlich liest. Der Fix verkleinert die Weitergabe auf exakt
diese vier, ohne das Verhalten des Preview-Servers zu ändern (Login/Session
funktionieren unverändert), und macht das E2E-Testtooling damit unabhängig
von der Sensitivität der Haupt-`.env` — Härtung derselben Fehlerklasse wie
#1537 (Repo ist öffentlich, Secrets dürfen nicht unnötig zirkulieren).

## Source

> **Schicht-Hinweis:** reines E2E-Tooling (Playwright, lokal), keine
> Produktions- oder Staging-Laufzeit betroffen. Berührt Bash-Skripte unter
> `frontend/e2e/` und einen Node-Test unter `frontend/src/lib/__tests__/`.
> Keine Go-Seite, keine Python-Core-Seite.

- **File:** `frontend/e2e/start-preview.sh`
- **Identifier:** `set -a; source ../../.env; set +a` (Blanket-Source-Zeile)
- **File (neu):** `frontend/e2e/e2e-env.sh`
- **File (neu):** `frontend/src/lib/__tests__/e2e_env_minimal.test.ts`

## Estimated Scope

- **LoC:** ~+45/-4
- **Files:** 3 (1 MODIFY, 2 CREATE)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/playwright.config.ts` (`webServer.command`) | READ (unverändert) | ruft `bash e2e/start-preview.sh` unverändert auf — Fix ändert nur, welche Variablen darin gesetzt werden, nicht die Aufrufschnittstelle |
| `frontend/e2e/global.setup.ts` | READ (unverändert) | Login-Flow hängt an einem korrekt verifizierbaren `gz_session`-Cookie, also indirekt an korrektem `GZ_SESSION_SECRET` |
| `frontend/src/hooks.server.ts:16` (`env.GZ_SESSION_SECRET ?? 'dev-secret-change-me'`) | READ (unverändert) | einziger Ort, der `GZ_SESSION_SECRET` aus der Preview-Server-Environment liest |
| `frontend/src/lib/server/apiBase.ts:5`, `frontend/src/routes/login/+page.server.ts`, `.../register/+page.server.ts`, `.../magic-link/verify/+page.server.ts` | READ (unverändert) | lesen `GZ_API_BASE`/`GZ_GOOGLE_CLIENT_ID`/`NODE_ENV` — bleiben wie bisher gesetzt, nicht Teil dieses Fixes |
| `internal/config/config.go:16`, `internal/middleware/auth.go` (Go-API, Staging Port 8091) | READ (unverändert, fremder Prozess) | signiert das `gz_session`-Cookie mit dem `GZ_SESSION_SECRET` aus der separaten Staging-Env-Datei (`/home/hem/gregor_zwanzig_staging/.env`) — muss weiterhin mit dem Wert übereinstimmen, den `e2e-env.sh` aus der Repo-`.env` extrahiert |
| `.env.e2e` (Repo-Root, git-getrackt) | UNVERÄNDERT | bleibt secret-frei (`GZ_TEST_FIXTURE_DIR=fixtures/openmeteo`), wird weiterhin separat gesourced — `GZ_SESSION_SECRET` wird bewusst NICHT dorthin dupliziert |

## Implementation Details

### 1. Neues Extraktions-Skript `frontend/e2e/e2e-env.sh`

Isolierte, für sich testbare Logik ohne `npm run build`/`preview` — nur
Environment-Setup. Liest genau zwei Schlüssel gezielt aus einer per
Umgebungsvariable überschreibbaren `.env`-Datei (Default: `../../.env`
relativ zum Skriptpfad, überschreibbar über `GZ_REPO_ENV_FILE` — das ist
der Haken, den der Test in Punkt 4 nutzt, um eine Fixture-Datei statt der
echten Repo-`.env` einzuspeisen) und exportiert nur diese beiden:

```bash
#!/usr/bin/env bash
# Issue #1289: nur die Variablen extrahieren, die der Preview-Server
# tatsächlich liest (siehe Kommentar unten) — kein Blanket-Source.
ENV_FILE="${GZ_REPO_ENV_FILE:-$(dirname "$0")/../../.env}"

_extract() {
  [ -f "$ENV_FILE" ] || return 0
  grep -m1 "^$1=" "$ENV_FILE" | cut -d= -f2-
}

GZ_SESSION_SECRET_VAL="$(_extract GZ_SESSION_SECRET)"
GZ_GOOGLE_CLIENT_ID_VAL="$(_extract GZ_GOOGLE_CLIENT_ID)"
[ -n "$GZ_SESSION_SECRET_VAL" ] && export GZ_SESSION_SECRET="$GZ_SESSION_SECRET_VAL"
[ -n "$GZ_GOOGLE_CLIENT_ID_VAL" ] && export GZ_GOOGLE_CLIENT_ID="$GZ_GOOGLE_CLIENT_ID_VAL"
```

Kein Schlüssel wird geloggt oder ausgegeben, nur exportiert.

### 2. `frontend/e2e/start-preview.sh` sourced das neue Skript

Die Blanket-Zeile `set -a; source ../../.env; set +a` wird ersetzt durch
`source "$(dirname "$0")/e2e-env.sh"`. Ein Kommentar an dieser Stelle
verweist auf #1289 und listet die vier tatsächlich benötigten Variablen
(`GZ_SESSION_SECRET`, `GZ_GOOGLE_CLIENT_ID`, `GZ_API_BASE`, `NODE_ENV`),
damit eine künftige Erweiterung bewusst erfolgt statt versehentlich wieder
auf Blanket-Sourcing zurückzufallen. Das `.env.e2e`-Sourcing (secret-frei)
sowie der bestehende `GZ_API_BASE`-Default-Export
(`export GZ_API_BASE="${GZ_API_BASE:-http://localhost:8091}"`) und der
`NODE_ENV`-Export bleiben unverändert an ihrer bisherigen Stelle im Skript.

### 3. Kern-Test `frontend/src/lib/__tests__/e2e_env_minimal.test.ts`

Node-Test (Testrunner `npm run test` in `frontend/`, Muster analog
`frontend/src/lib/__tests__/e2e_setup_guard_coverage.test.ts`):

1. Erzeugt eine Fixture-`.env` in einem Scratch-/Tempverzeichnis mit den
   erlaubten Schlüsseln (`GZ_SESSION_SECRET`, `GZ_GOOGLE_CLIENT_ID`) UND
   mindestens zwei verbotenen Secret-Schlüsseln (z. B.
   `GZ_SMTP_PASS=darf-nicht-durchsickern`, `GZ_TELEGRAM_BOT_TOKEN=...`).
2. Ruft `e2e-env.sh` per `child_process.spawnSync('bash', [...])` auf,
   mit `GZ_REPO_ENV_FILE` auf die Fixture-Datei gesetzt, und lässt den
   Kindprozess anschließend `env` ausgeben (z. B.
   `bash -c 'source e2e-env.sh && env'`).
3. Prüft die tatsächliche `env`-Ausgabe des Kindprozesses (kein
   Dateiinhalt-Check am Skript selbst, echtes Verhalten):
   - `GZ_SESSION_SECRET` und `GZ_GOOGLE_CLIENT_ID` sind vorhanden und
     tragen die Fixture-Werte (AC-1).
   - `GZ_SMTP_PASS` und `GZ_TELEGRAM_BOT_TOKEN` sind NICHT vorhanden
     (AC-2).

Kein Netzwerk, keine echte `.env`, keine echten Secrets im Test — alle
Werte sind erfundene Test-Fixtures.

## Expected Behavior

- **Input:** `start-preview.sh` wird von Playwright (`webServer.command`)
  mit einer Repo-`.env` gestartet, die sowohl `GZ_SESSION_SECRET` als auch
  36 weitere, für den Preview-Server irrelevante Schlüssel enthält
  (Secrets wie SMTP/IMAP/Telegram/Meteofrance sowie Nicht-Secrets).
- **Output:** Der laufende Preview-Server-Prozess hat `GZ_SESSION_SECRET`,
  `GZ_GOOGLE_CLIENT_ID`, `GZ_API_BASE`, `NODE_ENV` in seiner Environment —
  identisch zum bisherigen Verhalten für diese vier. Alle 37 übrigen
  Schlüssel aus der Haupt-`.env` fehlen im Prozess-Environment, wo sie
  vorher vorhanden waren.
- **Side effects:** Login/Session-Verifikation in E2E-Tests bleibt
  unverändert funktionsfähig (gleicher `GZ_SESSION_SECRET`-Wert wie
  bisher). Kein Verhaltensunterschied für `.env.e2e`-Werte, `GZ_API_BASE`
  oder `NODE_ENV`. Kein Effekt auf Staging oder Produktion — reines
  lokales Tooling.

## Acceptance Criteria

- **AC-1:** Given eine `.env`-Fixture enthält sowohl `GZ_SESSION_SECRET`
  als auch nicht benötigte Secrets / When der E2E-Preview-Server über
  `start-preview.sh`/`e2e-env.sh` mit dieser Datei gestartet wird / Then
  sind im resultierenden Prozess-Environment `GZ_SESSION_SECRET` und
  `GZ_GOOGLE_CLIENT_ID` vorhanden und tragen die erwarteten Werte (Login/
  Session funktionieren weiterhin).
  - Test: `frontend/src/lib/__tests__/e2e_env_minimal.test.ts` liest die
    `env`-Ausgabe des Kindprozesses und prüft beide Werte.

- **AC-2 (der eigentliche Sicherheitsgewinn):** Given dieselbe
  `.env`-Fixture enthält ein nicht benötigtes Secret wie `GZ_SMTP_PASS` /
  When derselbe Startvorgang läuft / Then ist `GZ_SMTP_PASS` NICHT im
  resultierenden Prozess-Environment vorhanden — die frühere
  Blanket-Weitergabe ist beseitigt.
  - Test: `frontend/src/lib/__tests__/e2e_env_minimal.test.ts` prüft die
    Abwesenheit von `GZ_SMTP_PASS` (und mindestens eines zweiten
    Fixture-Secrets, z. B. `GZ_TELEGRAM_BOT_TOKEN`) in der `env`-Ausgabe
    des Kindprozesses.

## Known Limitations

- Die Übereinstimmung von `GZ_SESSION_SECRET` zwischen Repo-`.env` und
  Staging-`.env` (`/home/hem/gregor_zwanzig_staging/.env`) ist weiterhin
  Konvention, keine technisch erzwungene Garantie — bei Rotation eines der
  beiden Werte ohne den anderen bricht die lokale E2E-Suite (stiller
  Redirect-Loop auf `/login`). Das bestand aber schon vor diesem Fix
  genauso und wird durch ihn weder verbessert noch verschlechtert.
- `GZ_GOOGLE_CLIENT_ID` wird weiterhin mitgenommen, obwohl kein E2E-Test
  sie prüft — bewusste Entscheidung: das Verhalten des Preview-Servers
  (Sichtbarkeit des Google-Login-Buttons) bleibt 1:1 erhalten, statt
  stillschweigend eine zweite, ungeprüfte Funktionsänderung einzuführen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** lokales E2E-Tooling-Skript, keine Architekturentscheidung
  im Sinne der ADR-Kategorien (Kanäle, Provider, Datenmodell/Persistenz,
  Auth-Konzept, Editor-Paradigma, Test-/Deploy-Strategie) — nur eine
  Härtung der bestehenden Env-Weitergabe an einen bereits existierenden
  lokalen Prozess, kein neues Konzept.

## Changelog

- 2026-08-07: Initial spec created. Umfang, Messung (4 tatsächlich
  gelesene Variablen, 41 gesetzte Schlüssel in Haupt-`.env`) und
  technischer Ansatz aus der Analyse zu Issue #1289 übernommen.
