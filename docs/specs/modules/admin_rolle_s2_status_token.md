---
entity_id: admin_rolle_s2_status_token
type: module
created: 2026-09-28
updated: 2026-09-28
status: draft
version: "1.0"
tags: [admin, auth, scheduler, status, monitoring, epic-2138]
---

# Admin-Rolle S2: Betriebsstatus per Maschinen-Token, `/status/me`, `/api/debug/` hinter RequireAdmin

## Approval

- [ ] Approved

## Purpose

`GET /api/scheduler/status` ist heute ohne jede Anmeldung erreichbar und zeigt globale
Betriebsdaten (Fehlertexte, Zählwerte aller Nutzer). Diese Scheibe schließt den
Endpunkt hinter ein Maschinen-Token, damit nur der externe Monitor
(`check-gregor20.sh`) ihn noch lesen kann. Die Konto-Karte bekommt einen eigenen,
nutzerbezogenen Ersatz `GET /api/scheduler/status/me` (nur die eigenen Daten, per
Sitzung). Das Präfix `/api/debug/` verliert seine Ausnahme in der Allowlist und
steht künftig hinter `RequireAdmin` (S1, ADR-0078). Scheibe S2 von vier in Issue
#2155 (Epic #2138).

## Source

- **File:** `internal/config/config.go`, `internal/middleware/status_token.go` (neu),
  `internal/middleware/auth.go`, `internal/router/router.go`,
  `internal/handler/scheduler_status.go`, `internal/scheduler/user_run_state.go`,
  `internal/scheduler/scheduler.go`, `frontend/src/routes/account/+page.server.ts`,
  `frontend/src/lib/types.ts`, `frontend/src/routes/account/+page.svelte`,
  `/home/hem/henemm-infra/scripts/check-gregor20.sh` (separates Repo)
- **Identifier:** `Config.StatusToken`, `middleware.RequireStatusToken`,
  `handler.SchedulerStatusHandler`, `handler.SchedulerStatusMeHandler` (neu),
  `userRunState`-Getter je `(jobID, userID)` (neu), `Scheduler`-Methode dafür (neu)

> **Schicht-Hinweis:** Diese Änderung betrifft die **Go-API** (`internal/`), das
> **Frontend** (`frontend/src/routes/account/`) und ein **separates Repo**
> (`henemm-infra/scripts/check-gregor20.sh`, Monitoring-Skript, nicht Teil dieses
> Workflows/dieser LoC-Zählung). Der **Python-Core (`api/`, `src/`) ist nur über den
> bestehenden `/api/debug/trigger-radar-alert`-Proxy betroffen** (keine Python-Änderung
> nötig — siehe Implementation Details Punkt 5).

## Estimated Scope

- **LoC:** Produktivcode ~90 (Go: Config-Feld, Middleware, Router-Verdrahtung,
  `/status/me`-Handler, Scheduler-/`userRunState`-Getter), Frontend ~15 (TS:
  `+page.server.ts` URL, `types.ts` Status-Union), infra-Skript ~20 (separates Repo,
  zählt nicht auf das 250-LoC-Limit dieses Workflows)
- **Files:** ~9 produktiv (6 Go, 3 TS) plus Testdateien; ADR und Doku-Nachzug zählen
  nicht (siehe „Betroffene Dokumentation" unten)
- **Effort:** medium
- **Hinweis:** LoC-Zählung erfasst nur produktive Dateien; `docs/`/`*.md` zählen nicht.
  Bei Überschreitung `loc_limit_override 500`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/config/config.go:74` (`AdminUserIDs envconfig:"ADMIN_USER_IDS"`) | reference-pattern | Vorbild für das neue Feld `StatusToken` (`envconfig:"STATUS_TOKEN"`, Präfix `GZ_`) |
| `internal/handler/auth_oauth.go:102` (`subtle.ConstantTimeCompare`) | reference-pattern | Konstantzeit-Vergleich; hier zusätzlich beide Seiten vorher per sha256 auf gleiche Länge bringen |
| `internal/handler/telegram_webhook.go:41-46` | reference-pattern | Fail-closed-Muster (kein konfiguriertes Secret ⇒ Endpunkt sperrt sich selbst) — der dortige `!=`-Vergleich wird NICHT übernommen (nicht konstantzeitig) |
| `internal/middleware/admin.go` (`RequireAdmin`) | dependency | Wird 1:1 auf die Debug-Route angewandt, kein neuer Code nötig |
| `internal/middleware/auth.go:41-59` (`AuthMiddleware`) | dependency | Public-Allowlist: `/api/scheduler/status` bleibt exakter Eintrag (Wächter kommt on top per `r.With`), Präfix `/api/debug/` (Zeile 59) entfällt |
| `internal/handler/proxy.go:110-158` (`ProxyPostHandler`, `appendUserID`) | dependency | **Bereits vorhanden:** `appendUserID` ersetzt jeden client-seitigen `user_id`-Query-Parameter durch `middleware.UserIDFromContext(r.Context())` (Anti-Spoofing, Bug #200/#199). Die Debug-Route nutzt bereits `ProxyPostHandler` — sobald sie durch `AuthMiddleware` läuft (Kontext gesetzt) und `RequireAdmin` passiert, überschreibt dieser bestehende Mechanismus automatisch ein mitgeschicktes `user_id=default`. Kein neuer Handler nötig. |
| `internal/scheduler/user_run_state.go:253` (`Record`), `:292` (`Aggregate`) | reference-pattern | Vorbild für einen dritten, lesenden Getter `(jobID, userID) → userJobRecord` unter `u.mu`, Rückgabe **per Wert** (keine geteilten Zeiger nach außen) |
| `internal/scheduler/scheduler.go:1094-1120` (`Status`, `usersField`) | reference-pattern | `next_run` für `trip_reports_hourly` kommt aus derselben Cron-Entry-Auflösung wie hier (Sub-Job unter einem unified cron entry, `s.entryMap`/`meta.subs`) — Wiederverwendung, kein zweiter Ermittlungsweg |
| `internal/router/admin_trigger_test.go` (`newBriefingTestRouter`, Zwei-Nutzer-Muster) | reference-pattern | Testvorbild für Token-Wächter- und `/status/me`-Tests über den echten Router |
| `tests/helpers/staging_auth.py` (`httpx_auth`, `_load_validator_env`) | reference-pattern | Vorbild für einen neuen, GETRENNTEN Loader der Staging-Admin-App-Login-Credentials (nicht aus `.claude/validator.env` — das ist Basic-Auth, wird von einem infra-Sync-Skript verwaltet) |
| ADR-0078 | reference-pattern | Admin-Begriff (`GZ_ADMIN_USER_IDS`, fail-closed, `RequireAdmin`) — hier nur angewandt, nicht verändert |
| ADR-0079 (neu) | new | hält die Entscheidung „Maschinen-Token statt Loopback-Ausnahme oder Admin-Session" fest |

## Implementation Details

**1. Konfiguration.** `Config` bekommt `StatusToken string` mit
`envconfig:"STATUS_TOKEN" default:""` (Präfix `GZ_`, also `GZ_STATUS_TOKEN`), analog zu
`AdminUserIDs`. Leer/nicht gesetzt ist ein gültiger (fail-closed) Zustand, kein Fehler
beim Programmstart.

**2. Middleware `RequireStatusToken(token string) func(http.Handler) http.Handler`**
in `internal/middleware/status_token.go` (neue Datei). Liest den Header
`X-GZ-Status-Token`. Vergleich: beide Seiten (konfiguriertes Token und Header-Wert)
werden zuerst mit `sha256.Sum256` auf feste 32 Byte gebracht, danach
`subtle.ConstantTimeCompare`. Das verhindert sowohl einen zeitbasierten
Zeicheninhalts-Seitenkanal als auch einen Längenvergleich am Rohwert. Ist `token == ""`
(nicht konfiguriert) **oder** stimmt der Vergleich nicht überein: HTTP 401,
`Content-Type: application/json`, Body `{"error":"unauthorized"}`, Handler läuft nicht.
Eine gültige Sitzung (Cookie) allein ersetzt das Token nicht — die Middleware prüft
ausschließlich den Header, unabhängig vom Auth-Kontext. Beim Aufbau der Middleware
(einmalig beim Routen-Setup, nicht pro Anfrage) wird bei leerem Token einmalig geloggt:
„GZ_STATUS_TOKEN nicht gesetzt — /api/scheduler/status ist für alle Anfragen gesperrt."

**3. Router (`router.go`).** `/api/scheduler/status` bleibt exakt auf der
Public-Allowlist in `auth.go` (unverändert, keine Fallunterscheidung dort). Der Schutz
kommt ausschließlich über die Route selbst:

```
statusGuard := middleware.RequireStatusToken(deps.Config.StatusToken)
r.With(statusGuard).Get("/api/scheduler/status", handler.SchedulerStatusHandler(deps.Scheduler))
r.Get("/api/scheduler/status/me", handler.SchedulerStatusMeHandler(deps.Scheduler))
```

`/api/scheduler/status/me` steht NICHT auf der Allowlist — sie läuft durch die normale
`AuthMiddleware` (Session-Pflicht, 401 ohne Cookie) wie jede andere geschützte Route.

**4. `GET /api/scheduler/status/me`** (neuer Handler `SchedulerStatusMeHandler` in
`internal/handler/scheduler_status.go`): liest `middleware.UserIDFromContext(r.Context())`
und liefert ein zu `SchedulerStatus` kompatibles, aber auf einen Job verengtes DTO:

```json
{
  "jobs": [
    {
      "id": "trip_reports_hourly",
      "name": "Trip Reports (hourly check)",
      "next_run": "<global, wie in Status()>",
      "last_run": { "time": "...", "status": "ok", "error": "" } | null
    }
  ]
}
```

`next_run` kommt aus derselben Cron-Entry-Auflösung wie `Status()` (kein zweiter Weg,
kein Duplikat der `meta.subs`-Logik — als gemeinsame kleine Hilfsfunktion faktorisiert).
`last_run` kommt NICHT aus dem globalen `s.lastRuns["trip_reports_hourly"]`
(Fan-out-Fehlertext, s. `usersField`/`Aggregate`), sondern aus einem neuen,
dritten Getter auf `userRunState`:

```go
func (u *userRunState) UserRecord(jobID, userID string) (userJobRecord, bool)
```

Unter `u.mu`, Rückgabe **per Wert** (keine geteilten Zeiger). Kein Eintrag für den
aufrufenden Nutzer ⇒ `"last_run": null` (kein 404, kein Fehler — ein Nutzer ohne
bisherigen Lauf ist ein gültiger Zustand). `error` im DTO ist ausschließlich
`userJobRecord.LastError` **dieses** Nutzers, nie der globale Fan-out-Text. Ohne Sitzung
greift die globale `AuthMiddleware` (401), der Handler wird nicht erreicht.

**5. `/api/debug/`-Präfix.** In `internal/middleware/auth.go` entfällt die Zeile
`strings.HasPrefix(r.URL.Path, "/api/debug/")` aus der Allowlist (Zeile 59). Die
bestehende, unter `GZ_ENV=staging` registrierte Route
`POST /api/debug/trigger-radar-alert` (`router.go`) bekommt `r.With(requireAdmin)`
(derselbe `requireAdmin`, der bereits für die drei S1-Trigger existiert — kein neuer
Admin-Mechanismus). Damit läuft die Route ab sofort durch die normale
`AuthMiddleware`: ohne Sitzung 401, mit Sitzung wird der Auth-Kontext (`user_id`)
gesetzt. `RequireAdmin` filtert danach Nicht-Admins mit 403 aus. Für Admins gilt der
**bereits vorhandene** Mechanismus aus `ProxyPostHandler`/`appendUserID`
(`internal/handler/proxy.go:110-158`, Anti-Spoofing Bug #200/#199): dieser ersetzt einen
mitgeschickten Query-Parameter `user_id` **immer** durch die authentifizierte
Nutzerkennung aus dem Kontext. Solange die Route auf der öffentlichen Allowlist stand,
lief sie ohne Auth-Kontext (`user_id`-Ersetzung griff nicht, weil `UserIDFromContext`
leer war) — das ist die Ursache, warum bisher `?user_id=default` durchging. Mit Schritt
5 entfällt dieser Zustand ersatzlos, **ohne dass der Proxy-Code geändert werden muss**.

**6. Admin-Vollzugriff auf `status`.** Bewusst NICHT Teil von S2 (siehe Known
Limitations / Nicht-Ziele).

**7. Staging-Admin-Konto (Betriebsschritt, kein Code).** Ein dediziertes
Staging-Admin-Konto wird auf Staging registriert (Least Privilege — NICHT das
bestehende `GZ_AUTH_USER`-Konto, damit die S1-403-Invarianten für normale Nutzer weiter
messbar bleiben). Ablauf: Registrierung/Login auf Staging, `GET /api/auth/profile`
liefert die `user_id`; diese wird in `GZ_ADMIN_USER_IDS` der Staging-`.env`
(`/home/hem/gregor_zwanzig_staging/.env`) eingetragen (Merge, bestehende IDs bleiben
erhalten). Die Zugangsdaten (E-Mail/Passwort) des Staging-Admin-Kontos liegen in einer
**neuen** Datei `.claude/staging_admin.env` (gitignoriert, Modus 600, Format wie
`.claude/validator.env.example`: `KEY=WERT`), **nicht** in `.claude/validator.env` (die
wird von einem infra-Sync-Skript verwaltet und trägt Nginx-Basic-Auth, keine
App-Login-Daten). `.gitignore` bekommt eine neue Zeile `.claude/staging_admin.env`
(analog Zeile 31 `.claude/validator.env`). Prod-`GZ_ADMIN_USER_IDS` bleibt unberührt
(Nicht-Ziel dieser Scheibe).

**8. Frontend.** `frontend/src/routes/account/+page.server.ts` (Zeile 24): Fetch-URL
`${API()}/api/scheduler/status` → `${API()}/api/scheduler/status/me`. Cookie-Weiterleitung
bleibt unverändert (Session-Auth trägt bereits). `frontend/src/lib/types.ts`
(`SchedulerJob.last_run.status`): Union `'ok' | 'error'` → `'ok' | 'partial' | 'error' |
'budget' | 'skipped_in_flight' | 'not_reached' | string` (die sechs Werte aus
`userJobRecord.LastStatus`, plus `string` als Sicherheitsnetz gegen künftige neue Werte,
damit die Karte nie hart bricht). `frontend/src/routes/account/+page.svelte`
(Z. 988-1010): Farbpunkt-Logik (`class:bg-green-500`/`class:bg-red-500`/`class:bg-gray-300`)
bekommt einen dritten, neutralen Zustand für Nicht-`ok`/Nicht-`error`-Werte (z. B.
`partial`, `budget`) statt implizit auf „grau/kein Lauf" zu fallen; `job.last_run === null`
bleibt der bestehende Zweig „Zuletzt: —".

**9. Auslieferungs-Reihenfolge (infra vor Merge).**
`/home/hem/henemm-infra/scripts/check-gregor20.sh` (~Zeile 892, Muster `grep|cut|tr` aus
der Prod-`.env`) liest `GZ_STATUS_TOKEN` und schickt ihn per `curl -H @-` (Token per
stdin, nicht in `ps` sichtbar) als `X-GZ-Status-Token`-Header an
`/api/scheduler/status`; `%{http_code}` wird ausgewertet. HTTP ≠ 200 ODER Token leer ⇒
FAIL-Meldung + `ERRORS++` ⇒ kein Heartbeat-Ping. Der bisherige stille
`systemctl is-active`-Fallback gilt nur noch bei echtem Verbindungsfehler (curl-Exit ≠
0 durch Netzwerkproblem) und erzeugt dann zusätzlich eine FAIL-Meldung statt stillen
Erfolgs. Diese Änderung wird zuerst an einer Kopie des Skripts geprüft (der
Arbeitsbaum von `check-gregor20.sh` ist sofort live, Cron läuft direkt daraus), dann im
`henemm-infra`-Repo committet — VOR dem Merge dieser Spec, siehe Acceptance Criteria.

## Test Plan

Die Zuordnung Test ↔ AC steht je AC unter „Test:". Überblick:

| Testdatei | Art | Deckt |
|-----------|-----|-------|
| `internal/router/status_token_test.go` (neu) | Kern, echter Router | Token-Wächter: kein Header / falsches / leeres konfiguriertes Token / nur Session ⇒ 401; richtiges Token ⇒ 200 |
| `internal/router/scheduler_status_me_test.go` (neu) | Kern, echter Router, zwei Nutzer | `/status/me`: nur eigener Laufzustand, `last_run: null` ohne Eintrag, 401 ohne Session, globaler Fehlertext nie sichtbar |
| `internal/router/admin_debug_trigger_test.go` (neu) | Kern, echter Router + `httptest`-Proxy-Ziel | `/api/debug/…`: 401 / 403 / Admin durch; fremder `user_id`-Query wird durch Session-`user_id` ersetzt |
| `frontend/src/routes/account/__tests__/scheduler-status-me-render.test.ts` (neu) | Kern, `node --test` | Konto-Karte mit `last_run: null`, `partial`, `budget` |
| `internal/router/admin_trigger_test.go:249-256` (Bestand, anpassen) | Kern | bisherige Erwartung „Nicht-Admin bob ⇒ 200 auf `status`" wird 401 |
| `frontend/src/routes/account/__tests__/premium_sms_link_code_load.test.ts:138` (Bestand, anpassen) | Kern | `fetch`-Stub-URL auf `/api/scheduler/status/me` |
| `tests/tdd/test_issue_830_radar_alert_validator.py`, `tests/tdd/test_bundle_h_908_973_987_staging_auth.py` (Bestand, anpassen) | Live (`-m staging`) | Admin-Session statt `user_id=default` |
| Skriptlauf-Log `check-gregor20.sh` (Artefakt) + Post-Deploy-curl | Betrieb | Auslieferungs-Reihenfolge und Wirkung auf Prod/Staging |

**Mutations-Gegenprobe (Pflicht für den Adversary):** `r.With(RequireStatusToken)` an der Status-Route entfernt ⇒ `status_token_test.go` rot; `requireAdmin` an der Debug-Route entfernt ⇒ `admin_debug_trigger_test.go` rot; Getter liefert globalen statt Pro-Nutzer-Zustand ⇒ `scheduler_status_me_test.go` rot.

## Expected Behavior

- **Input:** `GET /api/scheduler/status` mit/ohne Header `X-GZ-Status-Token`;
  `GET /api/scheduler/status/me` mit/ohne Sitzungscookie; `POST /api/debug/…` ohne
  Sitzung, mit Sitzung eines normalen Nutzers, mit Sitzung eines Admins (mit/ohne
  fremden `user_id`-Query-Parameter).
- **Output:** Richtiges Token ⇒ 200 mit vollem Status. Fehlendes/falsches/leeres
  konfiguriertes Token ⇒ 401 `{"error":"unauthorized"}` (auch mit gültiger Sitzung).
  `/status/me`: Sitzung ⇒ 200 mit nur den eigenen Daten des Jobs
  `trip_reports_hourly`, kein Eintrag ⇒ `last_run: null`; ohne Sitzung 401.
  `/api/debug/…`: ohne Sitzung 401, normaler Nutzer 403 `{"error":"forbidden"}`, Admin
  200 — und die Anfrage an Python trägt IMMER die `user_id` der Admin-Sitzung, nie einen
  mitgeschickten Query-Wert.
- **Side effects:** Keine Datenänderung, keine Migration. Deploy braucht `GZ_STATUS_TOKEN`
  in Prod- und Staging-`.env` sowie `GZ_ADMIN_USER_IDS` in der Staging-`.env`
  (Staging-Admin-Konto) VOR dem jeweiligen Deploy-Zyklus (siehe AC-9/AC-10/AC-11).

## Acceptance Criteria

- **AC-1:** Given `GZ_STATUS_TOKEN` ist konfiguriert / When `GET /api/scheduler/status`
  mit korrektem Header `X-GZ-Status-Token: <Token>` aufgerufen wird / Then antwortet der
  Server mit HTTP 200 und dem vollständigen Status (Feld `jobs`, `running`, `timezone`).
  - Test: `internal/router/status_token_test.go` (neu) — echter Router
    (Vorbild `newBriefingTestRouter`), `httptest`-Aufruf mit korrektem Header

- **AC-2:** Given `GZ_STATUS_TOKEN` ist konfiguriert / When `GET /api/scheduler/status`
  aufgerufen wird ohne Header, mit falschem Token, mit leerem Header-Wert ODER nur mit
  einem gültigen Sitzungscookie (kein Token-Header) / Then antwortet der Server in
  jedem dieser vier Fälle mit HTTP 401 und Body `{"error":"unauthorized"}`, der Handler
  liefert keine Statusdaten. Mutations-Gegenprobe: wird `r.With(statusGuard)` von der
  Route entfernt, muss dieser Test rot werden — es gibt keinen zweiten Schutz, die
  Route bleibt sonst nur wegen der (weiterhin bestehenden) Allowlist erreichbar.
  - Test: `internal/router/status_token_test.go`

- **AC-3:** Given `GZ_STATUS_TOKEN` ist leer/nicht gesetzt / When `GET
  /api/scheduler/status` mit einem beliebigen, auch korrekt geratenem Header-Wert
  aufgerufen wird / Then antwortet der Server mit HTTP 401 — ein leeres konfiguriertes
  Token öffnet den Endpunkt niemals (fail-closed).
  - Test: `internal/router/status_token_test.go`

- **AC-4:** Given zwei angemeldete Nutzer A und B, A hat einen protokollierten Lauf von
  `trip_reports_hourly` mit einem Fehlertext, B hat keinen / When beide
  `GET /api/scheduler/status/me` mit ihrer eigenen Sitzung aufrufen / Then sieht A nur
  seinen eigenen `last_run.status`/`last_run.error`, B bekommt `last_run: null`, und in
  keiner der beiden Antworten erscheint der globale Fan-out-Fehlertext oder eine Angabe
  über den jeweils anderen Nutzer.
  - Test: `internal/router/scheduler_status_me_test.go` (neu) — Zwei-Nutzer-Test mit
    echten Sitzungscookies (Vorbild `admin_trigger_test.go`)

- **AC-5:** Given eine Anfrage ohne Sitzungscookie / When `GET
  /api/scheduler/status/me` aufgerufen wird / Then antwortet der Server mit HTTP 401 —
  dieselbe Anmeldepflicht wie jede andere geschützte Route.
  - Test: `internal/router/scheduler_status_me_test.go`

- **AC-6:** Given `POST /api/debug/trigger-radar-alert` (nur bei `GZ_ENV=staging`
  registriert) / When die Anfrage ohne Sitzungscookie, mit der Sitzung eines normalen
  Nutzers bzw. mit der Sitzung eines Admins (Kennung in `GZ_ADMIN_USER_IDS`) erfolgt /
  Then antwortet der Server mit 401 (ohne Sitzung), 403 `{"error":"forbidden"}`
  (normaler Nutzer, Proxy-Ziel nicht aufgerufen) bzw. leitet zum
  Python-Proxy-Ziel weiter (Admin).
  - Test: `internal/router/admin_debug_trigger_test.go` (neu, Vorbild
    `admin_trigger_test.go`) — `httptest`-Python-Server als Proxy-Ziel, Aufrufzähler

- **AC-7:** Given ein Admin ruft `POST /api/debug/trigger-radar-alert?user_id=fremde-id`
  mit seiner eigenen Sitzung auf / When die Anfrage den Proxy erreicht / Then trägt die
  an Python weitergeleitete Anfrage als `user_id` ausschließlich die Kennung der
  Admin-Sitzung, niemals `fremde-id` — der mitgeschickte Query-Parameter wird verworfen.
  - Test: `internal/router/admin_debug_trigger_test.go` — `httptest`-Proxy-Ziel prüft
    den empfangenen Query-Parameter `user_id`

- **AC-8:** Given die Konto-Karte lädt `data.scheduler` mit `last_run: null` bzw. mit
  einem Status außerhalb von `ok`/`error` (z. B. `partial`, `budget`) / When die Seite
  gerendert wird / Then zeigt sie „Zuletzt: —" (kein Absturz) bzw. einen erkennbaren
  neutralen Zustand statt eines falschen grünen oder roten Punkts.
  - Test: `frontend/src/routes/account/__tests__/scheduler-status-me-render.test.ts`
    (neu, `node --test`, KEIN Vitest) — rendert/prüft die Ableitung von Punktfarbe und
    Text für `null`, `partial`, `budget` als reine Funktion (kein Dateiinhalt-Grep)

- **AC-9:** (Vorbedingung VOR dem Merge, nachweisbar) Given das Token ist bereits in
  Prod- und Staging-`.env` eingetragen (ohne Dienst-Neustart) / When der überarbeitete
  `check-gregor20.sh` einmal manuell gegen den ALTEN (noch ungeschützten) Prod-Server
  läuft / Then sendet das Skript den Header, wertet `%{http_code}` aus, meldet
  **keinen** Scheduler-FAIL (Server antwortet noch 200, ignoriert den Header), und ein
  fingierter Lauf mit falschem/fehlendem Token erzeugt eine FAIL-Meldung samt
  `ERRORS++` statt eines stillen `systemctl`-Fallbacks (der nur noch bei echtem
  Verbindungsfehler greift).
  - Test: Log-Artefakt eines echten Skriptlaufs, abgelegt unter
    `docs/artifacts/feature-2155-s2-status-token/check-gregor20-pre-merge.log`

- **AC-10:** Given (Post-Deploy-Nachweis Prod, da `prod_selftest.py` nur `/api/health` prüft)
  der Prod-Deploy dieser Scheibe ist abgeschlossen / When `curl
  localhost:8090/api/scheduler/status` ohne Header bzw. mit dem Token aus der
  Prod-`.env` aufgerufen wird / Then liefert der erste Aufruf 401, der zweite 200 mit
  einem nicht-leeren `jobs`-Array, und der nächste `check-gregor20.sh`-Zyklus zeigt
  keinen Scheduler-FAIL bei weiterlaufendem Heartbeat.
  - Test: manueller Nachweis im Deploy-Schritt (kein automatisierter Unit-Test, siehe
    `docs/reference/operations_playbook.md`)

- **AC-11:** (Post-Deploy-Nachweis Staging) Given der Staging-Deploy desselben Stands
  ist abgeschlossen und das Staging-Admin-Konto ist in `GZ_ADMIN_USER_IDS` eingetragen /
  When dieselben Aufrufe auf Staging erfolgen, zusätzlich `GET
  /api/scheduler/status/me` als `GZ_AUTH_USER` und `POST
  /api/debug/trigger-radar-alert` ohne Sitzung / als `GZ_AUTH_USER` / als
  Staging-Admin / Then ergibt sich dieselbe Matrix wie in AC-10 plus: `/status/me` 200
  als `GZ_AUTH_USER`, Debug-Trigger 401/403/200 in genau dieser Reihenfolge — `GZ_AUTH_USER`
  bleibt dabei Nicht-Admin (403), sodass die S1-Invariante weiter messbar bleibt.
  - Test: manueller Nachweis im Deploy-Schritt

- **AC-12:** Given die beiden bestehenden Staging-Livetests
  `tests/tdd/test_issue_830_radar_alert_validator.py` und
  `tests/tdd/test_bundle_h_908_973_987_staging_auth.py` / When sie nach dieser Scheibe
  laufen / Then melden sie sich zusätzlich zur Nginx-Basic-Auth mit einer echten
  Staging-Admin-App-Sitzung an (Login, Session-Cookie) und rufen
  `/api/debug/trigger-radar-alert` ohne `user_id`-Query-Parameter auf; beide Tests sind
  weiterhin grün.
  - Test: Testlauf `uv run pytest -m staging tests/tdd/test_issue_830_radar_alert_validator.py tests/tdd/test_bundle_h_908_973_987_staging_auth.py -v` gegen Staging

## Known Limitations

- **Nicht-Ziel: Admin-Vollzugriff auf `status`.** Eine zweite Route (Admin-Session liest
  den vollen, ungefilterten Status) ist ausdrücklich NICHT Teil von S2 — kommt mit S4
  (Admin-UI).
- **Nicht-Ziel: Prod-Admin-Kennung festlegen.** `GZ_ADMIN_USER_IDS` auf Prod bleibt in
  dieser Scheibe unberührt (S1 hat das offengelassen, S2 ändert daran nichts;
  betrifft nur `/api/debug/`, das auf Prod ohnehin nicht registriert wird —
  `GZ_ENV=staging`-Gate).
- **Nicht-Ziel: S3/S4.** Admin-API zum Setzen von Tiers/Sperren (S3) und `/admin`-UI
  (S4) folgen in eigenen Scheiben.
- **Issue #2155 bleibt nach S2 offen** — S3/S4 folgen im selben Issue.
- **Rollout-Reihenfolge ist hart:** Token muss in beiden `.env`-Dateien stehen, BEVOR
  der Merge das Feature scharf schaltet; sonst sperrt sich der Endpunkt für den Monitor
  (Readiness-Verstoß, s. AC-9/AC-10).
- **Nebenbefund (nicht Teil dieser Scheibe):** Die Staging-only-Routen
  `/api/auth/verify-email/staging-token` und Geschwister nehmen den Ziel-`username` aus
  dem Body entgegen — jeder angemeldete Staging-Nutzer könnte Token für fremde Konten
  holen. Nur Staging betroffen ⇒ Zeile im Sammel-Issue #1199, kein eigenes Issue.

### Betroffene Dokumentation (nachzuziehen, NICHT Teil dieser Spec-Umsetzung)

| Datei | Anpassung |
|---|---|
| `CLAUDE.md` (Monitoring-Abschnitt) | Status-Endpoint ist nicht mehr öffentlich, Token-Pflicht erwähnen |
| `.claude/validate-external.sh:68` | `/api/scheduler/status` aus der Liste der Public-Routen streichen |
| `.claude/agents/external-validator.md:32` | dito |
| `docs/reference/api_contract.md:243,1297,4381` | Endpunkt-Beschreibung: Token-Pflicht statt „öffentlich"; `/status/me` neu dokumentieren |
| `docs/specs/modules/google_login_adress_verknuepfung.md:219` | Verweis auf „öffentlich" korrigieren |
| `docs/reference/operations_playbook.md:760` | Monitoring-Abschnitt: Token-Header nennen |
| `docs/specs/modules/admin_rolle_s1.md` | Hinweis „status und /api/debug/ bleiben öffentlich bis S2" als erledigt markieren (S2 ist jetzt umgesetzt) |
| `.env.example` | `GZ_STATUS_TOKEN` dokumentieren (Format, Pflicht für den Monitor) |
| `.gitignore` | Neue Zeile `.claude/staging_admin.env` |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0079
- **Rationale:** Ein Maschinen-Token ist ein neuer Authentifizierungsmechanismus
  (Entscheidungsfläche Auth) — weder die bestehende Loopback-Ausnahme noch eine
  Admin-Session passen, weil der Monitor ohne Nutzerkontext läuft und die
  SvelteKit-Durchleitung Go ohnehin über localhost erreicht (Loopback wäre kein
  Unterscheidungsmerkmal). Details:
  `docs/adr/0079-betriebsstatus-per-maschinen-token.md`.

## Changelog

- 2026-09-28: Initial spec created (#2155 S2)
