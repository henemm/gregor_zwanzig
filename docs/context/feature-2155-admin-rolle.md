# Context: feature-2155-admin-rolle

Erhoben am 2026-09-28 für Issue #2155 (Epic #2138 Multi-User-Readiness), Scheibe S1 von vier.
Zeilenangaben gegen den Stand des Worktrees `next-ticket-2138` (Basis `origin/main` @ `b71b9e2f`).
Dieses Dokument wurde nach einem Verlust neu erstellt; Grundlage sind die Analyse im Issue-Kommentar
vom 26.09. und die erneute Prüfung des Quelltexts.

## Request Summary

Es gibt kein Rollen-/Admin-Konzept. Betriebs-Endpunkte (Scheduler-Trigger) sind für jeden
angemeldeten Nutzer erreichbar, und der „Briefing senden"-Knopf der Trip-Liste stößt über einen
dieser Trigger die Berichte **aller** Trips des Nutzers an. Für S1 wird ein Admin-Begriff
eingeführt (ENV-Liste), eine Middleware `RequireAdmin` geschaffen, die drei Trigger damit
geschützt und der Trip-Listen-Knopf so umgestellt, dass er nur noch den gewählten Trip anstößt.

## Schnitt in vier Scheiben (Issue-Kommentar vom 26.09.)

| Scheibe | Inhalt |
|---|---|
| **S1 (diese)** | `GZ_ADMIN_USER_IDS` (ADR-0078), `RequireAdmin`, drei Trigger geschützt, Trip-Liste auf `POST /api/trips/{id}/send`, abgeleitetes `role` in `GET /api/auth/profile` |
| S2 | Maschinen-Token für `GET /api/scheduler/status` (zuerst `check-gregor20.sh` in `henemm-infra` umstellen, dann aus der Allowlist nehmen), nutzerbezogener Ersatz `GET /api/scheduler/status/me`, Präfix `/api/debug/` hinter `RequireAdmin` |
| S3 | Admin-API: Nutzerliste, Tier setzen (Roh-Merge, `requested_tier` löschen), Konto sperren (`disabled`, Session-Sperre, `ClearSessions`, keine Selbstsperre) |
| S4 | UI `/admin` (Liste, Tier-Dropdown, Sperren), Navigationseintrag nur für Admins |

Jede Scheibe ist einzeln auslieferbar; normale Nutzer verlieren dabei keine Funktion. Das Issue
bleibt offen, bis S4 live ist.

## Analysis

### Router und Auth-Kette

- `internal/router/router.go:40` — globale Middleware-Kette; der Router kennt **keine Gruppen**
  (`r.Group`/`r.Route`). Eine Middleware pro Route wird deshalb über `r.With(...)` bzw. Wrapper
  am einzelnen Handler angelegt.
- `internal/router/router.go:273-275` — die drei Trigger `POST /api/scheduler/trip-reports`,
  `POST /api/scheduler/alert-checks`, `POST /api/scheduler/inbound-commands`, jeweils
  `handler.ProxyPostHandler(deps.Config.PythonCoreURL, …)`. Aktuell nur durch die globale
  Anmeldepflicht geschützt, es gibt keine Rollenprüfung.
- `internal/router/router.go:265` — `GET /api/scheduler/status` ist öffentlich (Allowlist in
  `internal/middleware/auth.go:33-34`), ebenso das Präfix `/api/debug/` (`auth.go:47`). Beides
  ist **nicht** Teil von S1 (siehe S2).
- `internal/middleware/auth.go:33` — `AuthMiddleware(secret, sessions)` ist das Muster für die
  neue Middleware; die Nutzerkennung kommt über `middleware.UserIDFromContext(r.Context())`.
- `internal/router/router.go:94` — `GET /api/auth/profile` wird heute ohne `Config` verdrahtet
  (`handler.GetProfileHandler(deps.Store)`); für das abgeleitete `role` braucht der Handler die
  Admin-Menge.

### Proxy

- `internal/handler/proxy.go:110-142` — `ProxyPostHandler` hängt die `user_id` des angemeldeten
  Nutzers an den Python-Aufruf an. Ein Trigger wirkt also immer auf die Trips des Aufrufers
  (bei `inbound-commands` global, `api/routers/scheduler.py:126-130`). Der Python-Core selbst
  kennt keine Rollen und bleibt in S1 **unverändert**.

### Cron-Betrieb ist vom Router entkoppelt

Der Go-Scheduler ruft den Python-Core **direkt** (`internal/scheduler/scheduler.go:629`, `:663`,
`:740`), nicht über den Router. Eine Middleware am Router berührt den geplanten Betrieb deshalb
nicht. Dafür ist ein eigener Test vorzusehen (Spec AC-6).

### Keine Aufrufer der Trigger außerhalb des Frontends

Keine Treffer in `henemm-infra`, `scripts/`, `tools/`, `.github/`. Zusätzlich blockt
`.claude/hooks/prod_send_gate.py` Aufrufe gegen Prod. Die Trigger werden also nur (a) vom
Frontend-Knopf und (b) händisch vom Betreiber benutzt. Python-Tests treffen den Python-Router
direkt, ohne Go-Auth — sie sind von S1 nicht betroffen. `docs/reference/api_contract.md`
nennt die Trigger an `:241-244`, `:1502` und `:1594`.

### Der Knopf der Trip-Liste stößt ALLE Trips an

`frontend/src/routes/trips/+page.svelte:320-337`: `runTestReport(trip, hour)` ruft
`POST /api/scheduler/trip-reports?hour=…`. Python ignoriert `hour` seit #1724
(`api/routers/scheduler.py:27`); es werden alle aktiven Trips des Nutzers verarbeitet. Die
Erfolgsmeldung (Z. 329) sagt ehrlich „Alle aktiven Trips für …:00 Uhr werden verarbeitet". Das
ist für einen normalen Nutzer der falsche Effekt (Doppelversand für unbeteiligte Trips) und
nach Schutz des Triggers ein 403.

Das Gegenstück existiert bereits: `POST /api/trips/{id}/send?report_type=…`
(`router.go:229`, `SendTripReportProxyHandler`; Python `api/routers/scheduler.py:212-296`).
Gültige Werte für `report_type` sind `morning` und `evening`
(`src/services/trip_report_scheduler.py:1098`); Default ist `evening`; alles andere ergibt 422.
Der Trip-Detail-Knopf nutzt das schon (`frontend/src/routes/trips/[id]/+page.svelte:236`). Das
mobile Action-Sheet ruft nichts davon auf. Fehlerantworten des `/send`-Endpunkts: 404 (Trip
unbekannt), 422 (keine Etappen / keine Wetterdaten / kein Versandweg / SMTP nicht konfiguriert /
ungültiger Typ), 409 (Versand läuft bereits); alle mit `detail`-Text.

### Nutzerprofil

`internal/handler/auth.go`: `profileResponse` (:718), `toProfileResponse` (:780-829),
`GetProfileHandler` (:831). `role` fehlt heute. `PUT /api/auth/profile` schreibt Nutzerfelder;
ein mitgesendetes `role` darf dort nie wirken.

### Bestehendes „Admin"-Fragment

`internal/config/config.go:41` — `AuthUser string envconfig:"AUTH_USER" default:"admin"` ist
**ungenutzt**. Suche nach `admin|role` in `internal/**` trifft nur diese Zeile. Tier-Freigaben
erfolgen weiterhin manuell per Hand in der `user.json` (`auth.go:798-801`).

### Admin-Kennung: reale Nutzerkennung ist hier NICHT bekannt

Das Admin-Konto ist konzeptionell `cfg.UserID` (`GZ_USER_ID`, `config.go:31`). In den beiden
`.env`-Dateien ist `GZ_USER_ID` **nicht gesetzt**, dort stehen nur `GZ_AUTH_USER`/`GZ_AUTH_PASS`.
Die reale Admin-Nutzerkennung muss deshalb **vor dem Rollout am Server ermittelt** werden
(Prod: `/home/hem/gregor_zwanzig/.env`; Staging: `/home/hem/gregor_zwanzig_staging/.env`, für
die Claude-Sitzung nicht lesbar) und ist hier unbekannt. Ohne Eintrag sind die drei Trigger für
niemanden erreichbar (fail-closed, gewollt).

### Entscheidung zur Speicherung (ADR-0078)

Kein Profilfeld `role` im Speicher, sondern Umgebungsvariable `GZ_ADMIN_USER_IDS`
(komma-getrennte Nutzerkennungen). Ein speicherbares Feld läge im per `PUT /api/auth/profile`
erreichbaren Nutzerobjekt (Rechteausweitung durch den Nutzer, Roh-Merge-Falle, Schema-Migration
mit Bestandsdaten-Pflicht). Die ENV-Liste ist vom Nutzer nicht schreibbar, braucht keine
Datenmigration und ist fail-closed. Parsing nach dem Muster `splitOrigins`
(`internal/config/webauthn.go:99-107`).

### Betroffene Tests / Vorbilder

- `internal/router/briefing_subscription_test.go` — `newBriefingTestRouter` (:51),
  `sessionCookieFor` (:112), Zwei-Nutzer-Muster (:567): Vorbild für den Router-Test mit echtem
  Router und zwei Sitzungen.
- Frontend-Tests laufen über `node --test` (kein Vitest).

## Risiken

- **Falsch gesetzte Kennung:** Trägt die ENV-Liste die falsche Kennung ein, sind die Trigger für
  den Betreiber gesperrt. Kein Datenverlust, Korrektur per `.env` + Neustart.
- **Vergessene Staging-/Prod-.env:** Ohne Eintrag sind die Trigger für alle gesperrt
  (gewollt), Staging-E2E, die die Trigger nutzen würden, schlügen mit 403 fehl. Es gibt dafür
  keinen bekannten Aufrufer (siehe oben).
- **Frontend-Umstellung:** Der Knopf bedient künftig nur noch **einen** Trip; wer sich auf den
  Sammel-Effekt verlassen hat, verliert ihn (gewollt, war ein Fehler).

## Nicht in S1

`GET /api/scheduler/status`, `/api/debug/` (S2); Admin-API, Tier setzen, Sperren (S3);
`/admin`-UI und Navigationseintrag (S4).
