---
entity_id: admin_rolle_s1
type: module
created: 2026-09-28
updated: 2026-09-28
status: draft
version: "1.0"
tags: [admin, auth, scheduler, trips, epic-2138]
---

# Admin-Rolle S1: ENV-Liste, RequireAdmin, geschützte Scheduler-Trigger

## Approval

- [ ] Approved

## Purpose

Es gibt erstmals einen Admin-Begriff: Admin ist, wessen Nutzerkennung in der
Umgebungsvariable `GZ_ADMIN_USER_IDS` steht. Eine neue Middleware `RequireAdmin`
schützt die drei Betriebs-Trigger `POST /api/scheduler/trip-reports|alert-checks|inbound-commands`,
die bisher jeder angemeldete Nutzer auslösen konnte. Der Knopf „Briefing senden" der
Trip-Liste, der über einen dieser Trigger ALLE Trips des Nutzers anstieß, sendet künftig
nur noch den gewählten Trip. `GET /api/auth/profile` liefert ein abgeleitetes
`role: "admin"|"user"`. Scheibe S1 von vier in Issue #2155 (Epic #2138).

## Source

- **File:** `internal/config/config.go`, `internal/config/admin.go` (neu),
  `internal/middleware/admin.go` (neu), `internal/router/router.go`,
  `internal/handler/auth.go`, `frontend/src/routes/trips/+page.svelte`,
  `docs/reference/api_contract.md`, `.env.example`
- **Identifier:** `Config.AdminUserIDs`, `config.ParseAdminUserIDs`,
  `middleware.RequireAdmin`, `handler.GetProfileHandler`, `profileResponse.Role`,
  `toProfileResponse`, `runTestReport`

> **Schicht-Hinweis:** Diese Änderung betrifft die **Go-API** (`internal/`) und das
> **Frontend** (`frontend/src/routes/trips/+page.svelte`). Der **Python-Core
> (`api/`, `src/`) bleibt unverändert** — der Go-Scheduler ruft ihn direkt
> (`scheduler.go:629/663/740`), Python-Tests treffen den Python-Router ohne Go-Auth.
> Rollenprüfung ist ausschließlich Sache der Go-Schicht.

## Estimated Scope

- **LoC:** Produktivcode ~200 (Go ~150-250 inkl. Konfiguration, Middleware, Router,
  Profil; Frontend ~40), Tests zusätzlich ~250
- **Files:** ~10 produktiv/Doku (6 Go, 1 Svelte, `api_contract.md`, `.env.example`,
  ADR), plus Testdateien
- **Effort:** medium
- **Hinweis:** LoC-Zählung erfasst nur produktive Dateien; `docs/`/`*.md` zählen nicht.
  Bei Überschreitung `loc_limit_override 500`. Ratschen/`ci_tdd_excludes.txt` werden
  NICHT angefasst.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/middleware/auth.go` (`AuthMiddleware`, `UserIDFromContext`) | reference-pattern | Vorbild für Bauart; `RequireAdmin` liest die Nutzerkennung aus dem Auth-Kontext, den die globale Kette gesetzt hat |
| `internal/config/webauthn.go:99-107` (`splitOrigins`) | reference-pattern | Muster für das Aufteilen der komma-getrennten Liste (Leerzeichen und leere Einträge fallen weg) |
| `internal/handler/proxy.go:110-142` (`ProxyPostHandler`) | dependency | Proxy der drei Trigger; unverändert, wird nur eingehüllt |
| `internal/router/router.go:229` (`SendTripReportProxyHandler`) | dependency | Ziel des umgestellten Trip-Listen-Knopfs, existiert bereits und ist nicht rollen-geschützt |
| `frontend/src/routes/trips/[id]/+page.svelte:236` (`handleTestBriefing`) | reference-pattern | Vorbild für Aufruf und Fehlertext-Behandlung von `/send` |
| `internal/router/briefing_subscription_test.go` | reference-pattern | `newBriefingTestRouter` (:51), `sessionCookieFor` (:112), Zwei-Nutzer-Test (:567) als Test-Vorbild |
| ADR-0078 | new | hält die Entscheidung ENV-Liste statt Profilfeld fest |

## Implementation Details

**1. Konfiguration.** `Config` bekommt `AdminUserIDs string` mit `envconfig:"ADMIN_USER_IDS"`
(Präfix `GZ_`, also `GZ_ADMIN_USER_IDS`). Neue Funktion
`config.ParseAdminUserIDs(raw string) map[string]struct{}` nach dem Muster von
`splitOrigins`: an Kommas trennen, jeden Eintrag trimmen, leere Einträge verwerfen. Vergleich
ist exakt (Groß-/Kleinschreibung wird nicht verändert, keine Teilstring-Treffer).
Leerer/fehlender Wert ergibt eine leere Menge.

**2. Middleware `RequireAdmin(admins map[string]struct{}) func(http.Handler) http.Handler`**
in `internal/middleware/admin.go`. Liest `UserIDFromContext(r.Context())`. Ist die
Kennung leer (kein Auth-Kontext) oder nicht in `admins`: HTTP 403 mit
`Content-Type: application/json` und Body `{"error":"forbidden"}`, der Handler wird NICHT
aufgerufen. Sonst weiter. Fail-closed: leere Menge ⇒ niemand kommt durch. „Nicht angemeldet"
bleibt 401 — das liefert unverändert die globale `AuthMiddleware`, die vor `RequireAdmin`
läuft. `RequireAdmin` prüft die Anmeldung nicht selbst.

**3. Router (`router.go:273-275`).** Die Menge wird einmal aus `deps.Config.AdminUserIDs`
berechnet. Der Router hat keine Gruppen; die Middleware wird **pro Route** angewandt:

```
admin := middleware.RequireAdmin(config.ParseAdminUserIDs(deps.Config.AdminUserIDs))
r.With(admin).Post("/api/scheduler/trip-reports", ProxyPostHandler(...))
r.With(admin).Post("/api/scheduler/alert-checks", ProxyPostHandler(...))
r.With(admin).Post("/api/scheduler/inbound-commands", ProxyPostHandler(...))
```

Exakt diese drei Routen. NICHT in S1: `GET /api/scheduler/status` und `/api/debug/`
(beide seit S2 umgesetzt — Maschinen-Token bzw. `RequireAdmin`, siehe
`docs/specs/modules/admin_rolle_s2_status_token.md`, ADR-0079), Admin-API/Tier
setzen/Sperren (S3), `/admin`-UI (S4).

**4. Cron-Betrieb.** Der Go-Scheduler ruft den Python-Core direkt (`scheduler.go:629/663/740`),
nicht über den Router. `RequireAdmin` wird nirgends im Scheduler verdrahtet; der geplante
Betrieb bleibt unabhängig von `GZ_ADMIN_USER_IDS`.

**5. Profil-`role`.** `profileResponse` bekommt `Role string` (`json:"role"`).
`GetProfileHandler` (router.go:94) erhält die Admin-Menge (zusätzlicher Parameter);
`toProfileResponse` setzt `Role` auf `"admin"`, wenn die Nutzerkennung in der Menge steht,
sonst `"user"`. Der Wert wird **nie** aus Nutzereingabe oder aus der gespeicherten
`user.json` gelesen: `model.User` bekommt KEIN `role`-Feld. `PUT /api/auth/profile` ignoriert
ein mitgesendetes `role` (das Feld ist im Update-Request nicht vorhanden bzw. wird verworfen)
und schreibt es nicht in die `user.json`.

**6. Frontend-Umstellung (`frontend/src/routes/trips/+page.svelte`, `runTestReport`,
Z. 320-337).** Der Aufruf `POST /api/scheduler/trip-reports?hour=…` entfällt. Neu:
`POST /api/trips/${trip.id}/send?report_type=<Wert>` (Vorbild
`frontend/src/routes/trips/[id]/+page.svelte:236`). Gültige Werte in
`api/routers/scheduler.py` bzw. `send_test_report_outcome`: `morning` und `evening`
(Default `evening`, alles andere 422). Abbildung des Dialog-Parameters `hour`:

| `hour` | `report_type` |
|---|---|
| 7 | `morning` |
| 18 | `evening` |

Erfolgstext benennt „dieser Trip" (z. B. „Test-Report (Morning) für diesen Trip wurde
ausgelöst.") statt „Alle aktiven Trips …". Fehler: `detail` aus der Antwort anzeigen
(422/409/404 tragen einen sprechenden `detail`), sonst `error`, sonst ein allgemeiner
Text; 5xx zeigt die handlungsleitende Meldung ohne Rohtext, wie in
`trips/[id]/+page.svelte:237-260`. `TestReportDialog` bleibt unverändert (Parameter `hour`,
`running`, `result`, `error`). Die Abbildung `hour → report_type` liegt als reine Funktion
in derselben Datei oder einem kleinen Helfer, damit sie testbar ist.

**7. Doku.** `docs/reference/api_contract.md`: Abschnitt `GET /api/auth/profile` (ab :3128)
um Feld `role` (Beispiel + Feldtabelle: „`admin` genau dann, wenn die Kennung in
`GZ_ADMIN_USER_IDS` steht, sonst `user`; nicht schreibbar, in `PUT` ignoriert"); an den
Trigger-Stellen (:241-244, :1502, :1594) Vermerk „nur Admin (403 `{"error":"forbidden"}`
sonst)"; Changelog-Eintrag am Ende. `.env.example`: `GZ_ADMIN_USER_IDS` mit Erklärung
(komma-getrennt; leer = niemand ist Admin; Änderung wirkt erst nach Neustart).

## Expected Behavior

- **Input:** Anfragen an die drei Trigger mit Sitzungscookie eines Admins, eines normalen
  Nutzers oder ohne Cookie; `GET`/`PUT /api/auth/profile`; Klick auf „Briefing senden" in
  der Trip-Liste.
- **Output:** Admin ⇒ Anfrage erreicht den Proxy wie bisher. Normaler Nutzer ⇒ HTTP 403
  `{"error":"forbidden"}`, Python-Core wird nicht angesprochen. Ohne Cookie ⇒ 401
  (globale Kette). Profil enthält `role`. Trip-Liste stößt genau einen Trip an.
- **Side effects:** Keine Datenänderung, keine Migration. Trigger wirken weiterhin auf die
  Trips des aufrufenden Nutzers (`ProxyPostHandler` hängt `user_id` an). Deploy braucht
  `GZ_ADMIN_USER_IDS` in Prod- und Staging-`.env` (siehe Known Limitations).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer, dessen Kennung in `GZ_ADMIN_USER_IDS` steht, mit gültiger
  Sitzung / When er `POST /api/scheduler/trip-reports`, `/api/scheduler/alert-checks` und
  `/api/scheduler/inbound-commands` aufruft / Then erreicht jede der drei Anfragen den
  Python-Proxy und liefert dessen Antwort (kein 403).
  - Test: `internal/router/admin_trigger_test.go` → echter Router (Vorbild
    `newBriefingTestRouter`), Proxy-Ziel als `httptest`-Server, Zähler je Route = 1

- **AC-2:** Given ein normaler angemeldeter Nutzer, dessen Kennung NICHT in
  `GZ_ADMIN_USER_IDS` steht / When er eine der drei Trigger-Routen aufruft / Then
  antwortet der Server mit HTTP 403 und dem Body `{"error":"forbidden"}` und das
  Proxy-Ziel wurde nicht aufgerufen.
  - Test: `internal/router/admin_trigger_test.go` → Zwei-Nutzer-Test (Admin und
    normaler Nutzer, echte Sitzungscookies): normaler Nutzer 403 auf allen drei Routen,
    Aufrufzähler des Proxy-Ziels bleibt 0, Admin im selben Lauf 200

- **AC-3:** Given eine Anfrage ohne Sitzungscookie / When sie eine der drei
  Trigger-Routen aufruft / Then antwortet der Server mit HTTP 401 (nicht 403) — die
  Anmeldepflicht bleibt Sache der globalen Kette.
  - Test: `internal/router/admin_trigger_test.go` → ohne Cookie, 401 auf allen drei Routen

- **AC-4:** Given `GZ_ADMIN_USER_IDS` ist leer oder nicht gesetzt / When ein beliebiger
  angemeldeter Nutzer (auch `cfg.UserID`) einen der drei Trigger aufruft / Then
  antwortet der Server mit HTTP 403 — fail-closed, niemand ist Admin.
  - Test: `internal/middleware/admin_test.go` und Router-Fall mit leerer Konfiguration →
    jeder Nutzer 403

- **AC-5:** Given `GZ_ADMIN_USER_IDS` = `" alice , ,bob,"` / When die Liste geparst wird /
  Then sind genau `alice` und `bob` Admins; `ali`, `alice2`, `carol` und die leere
  Kennung sind es nicht.
  - Test: `internal/config/admin_test.go` (Parsing: Leerzeichen, leere Einträge,
    exakter Vergleich) und `internal/middleware/admin_test.go` (Kennung leer ⇒ 403)

- **AC-6:** Given `GZ_ADMIN_USER_IDS` ist leer / When der Go-Scheduler seinen geplanten
  Lauf ausführt / Then ruft er den Python-Core weiterhin direkt auf, ohne dass
  `RequireAdmin` beteiligt ist — der Cron-Betrieb bleibt unberührt.
  - Test: `internal/scheduler/…_test.go` (bestehende oder neue Datei) → Scheduler-Lauf
    gegen `httptest`-Python-Server bei leerer Admin-Konfiguration erreicht das Ziel

- **AC-7:** Given ein normaler Nutzer (kein Admin) / When er `GET /api/scheduler/status`
  und `POST /api/trips/{id}/send` für einen eigenen Trip aufruft / Then werden beide wie
  bisher bedient (S1 ändert nur die drei Trigger).
  - *Überholt für `status` durch #2155 S2 (ADR-0079): `GET /api/scheduler/status` ist
    seither token-pflichtig ⇒ 401 für Nutzer-Sitzungen; `/send` unverändert.*
  - Test: `internal/router/admin_trigger_test.go` → `status` 200 ohne 403, `/send`
    erreicht das Proxy-Ziel

- **AC-8:** Given ein Admin `alice` und ein normaler Nutzer `bob` / When jeder
  `GET /api/auth/profile` aufruft / Then enthält die Antwort für `alice` `"role":"admin"`
  und für `bob` `"role":"user"`.
  - Test: `internal/handler/auth_profile_role_test.go` (oder Erweiterung von
    `auth_test.go`) → Zwei-Nutzer-Test mit echtem Store

- **AC-9:** Given der normale Nutzer `bob` / When er `PUT /api/auth/profile` mit einem
  zusätzlichen Feld `"role":"admin"` sendet / Then bleibt sein `role` im folgenden
  `GET /api/auth/profile` `"user"`, die drei Trigger antworten ihm weiter mit 403, und
  die gespeicherte `user.json` enthält kein Feld `role`.
  - Test: `internal/handler/auth_profile_role_test.go` → PUT mit `role`, danach GET,
    Trigger-Aufruf und Byte-Prüfung der `user.json` (kein `role`-Schlüssel)

- **AC-10:** Given die Trip-Liste mit Trip `t1` / When der Nutzer bei `t1` „Briefing
  senden" für 7 Uhr bzw. 18 Uhr auslöst / Then erfolgt genau ein Aufruf
  `POST /api/trips/t1/send?report_type=morning` bzw. `…report_type=evening` und KEIN
  Aufruf an `/api/scheduler/trip-reports`.
  - Test: `frontend/…/trips-list-send.test.ts` (`node --test`, KEIN Vitest) → prüft das
    Verhalten der Funktion `runTestReport` mit aufgezeichneten Aufrufen (Anzahl, URL,
    Methode), kein Quelltext-Grep; ergänzend ein Playwright-Staging-E2E-Hinweis:
    Trip-Liste „Briefing senden" ⇒ Request-URL `/api/trips/<id>/send?report_type=…`

- **AC-11:** Given ein erfolgreicher bzw. abgewiesener Sendeversuch aus der Trip-Liste /
  When die Antwort 200, 409 oder 422 (mit `detail`) lautet / Then zeigt der
  `TestReportDialog` bei Erfolg einen Text, der sich auf „diesen Trip" bezieht (nicht
  „Alle aktiven Trips"), und bei 409/422 den `detail`-Text der Antwort.
  - Test: `frontend/…/trips-list-send.test.ts` → Ergebnis-/Fehlertext je Antwort

## Known Limitations

- **Rollout:** `GZ_ADMIN_USER_IDS` muss in der Prod-`.env`
  (`/home/hem/gregor_zwanzig/.env`) und der Staging-`.env`
  (`/home/hem/gregor_zwanzig_staging/.env`, für die Claude-Sitzung nicht lesbar) gesetzt
  und in `.env.example` dokumentiert werden; Wirkung erst nach Neustart. Die reale
  Admin-Nutzerkennung ist hier nicht bekannt: `GZ_USER_ID` ist in den `.env`-Dateien nicht
  gesetzt (dort nur `GZ_AUTH_USER`/`GZ_AUTH_PASS`) und muss vor dem Rollout am Server
  ermittelt werden.
- **Fail-closed:** Ohne Eintrag sind die drei Trigger für ALLE gesperrt. Das ist gewollt.
  Die Ops-Nutzung der Trigger geschieht ohnehin nur durch den Betreiber; kein
  Skript/Cron/infra ruft sie auf (keine Treffer in `henemm-infra`, `scripts/`, `tools/`,
  `.github`), und `.claude/hooks/prod_send_gate.py` blockt Prod-Aufrufe zusätzlich.
- Adminvergabe bleibt Betreiber-Aufgabe (`.env` + Neustart); spätere Scheiben (S3
  Admin-API) ändern die Liste nicht.
- `GET /api/scheduler/status` und `/api/debug/` waren zum Zeitpunkt dieser Scheibe (S1)
  noch öffentlich — S2 hat beide inzwischen geschützt (Maschinen-Token bzw.
  `RequireAdmin`, `docs/specs/modules/admin_rolle_s2_status_token.md`, ADR-0079).
- Die mobile Action-Sheet der Trip-Liste ruft keinen Trigger auf und ist nicht betroffen.
- Das ungenutzte `AuthUser` (`config.go:41`, Default `admin`) bleibt unangetastet und
  begründet KEINE Admin-Rolle.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0078
- **Rationale:** Admin wird über die ENV-Liste `GZ_ADMIN_USER_IDS` bestimmt, nicht über ein
  Profilfeld `role`. Ein speicherbares Feld läge im per `PUT /api/auth/profile` erreichbaren
  Nutzerobjekt (Rechteausweitung durch den Nutzer, Roh-Merge-Falle, Datenmigration nötig);
  die ENV-Liste ist nicht nutzerschreibbar, braucht keine Migration und ist fail-closed.
  Details: `docs/adr/0078-admin-rolle-ueber-env-liste-statt-profilfeld.md`.

## Changelog

- 2026-09-28: Initial spec created (#2155 S1)
- 2026-09-28: Nachtrag (docs-updater) — Known Limitations korrigiert: `GET
  /api/scheduler/status` und `/api/debug/` sind mit S2 geschützt worden, siehe
  `docs/specs/modules/admin_rolle_s2_status_token.md`, ADR-0079.
