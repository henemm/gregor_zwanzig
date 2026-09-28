# Context: feature-2155-s2-status-token

## Request Summary
Issue #2155, Scheibe S2 (Schnitt siehe `docs/context/feature-2155-admin-rolle.md`): `GET /api/scheduler/status`
nicht mehr öffentlich, sondern per Maschinen-Token; nutzerbezogener Ersatz `GET /api/scheduler/status/me`
für die Konto-Karte; Präfix `/api/debug/` hinter `RequireAdmin` (S1, ADR-0078). `/api/health` bleibt öffentlich.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/middleware/auth.go:41-59` | Public-Allowlist: enthält `/api/scheduler/status` (exakt) und Präfix `/api/debug/` — beide müssen raus. Solange `/api/debug/` auf der Allowlist steht, setzt die Middleware keine User-ID ⇒ `RequireAdmin` würde immer 403 liefern |
| `internal/middleware/admin.go:9` | `RequireAdmin(admins)` aus S1 — liest `UserIDFromContext`, 403 `{"error":"forbidden"}` |
| `internal/router/router.go:43, 268, 271-273, 278-281` | `admins`-Map; Status-Route; `POST /api/debug/trigger-radar-alert` (nur `GZ_ENV=staging`); S1-Anwendung `r.With(requireAdmin)` |
| `internal/handler/scheduler_status.go:11` | gibt `sched.Status()` unverändert aus |
| `internal/scheduler/scheduler.go:1094`, `user_run_state.go:292` | Status-Inhalt: `running`, `timezone`, `jobs[]` (`id,name,next_run,last_run{time,status,error},overlap,users{Zählwerte}`), `briefing_health`, `warn_service_health`, `enrichment_health`, `forecast_budget`, `tier_request_health` — keine User-IDs (Privacy-Tests #2149/#1555), aber globale Betriebsdaten (Fehlertexte, Zählwerte aller Nutzer) |
| `internal/config/config.go:73-75` | Muster `AdminUserIDs envconfig:"ADMIN_USER_IDS"` (Präfix `GZ_`) — neues Token-Feld analog |
| `frontend/src/routes/account/+page.server.ts:24` | einziger Frontend-Aufrufer (serverseitig, Cookie `gz_session`); Fehler ⇒ `scheduler=null` ⇒ „Report-Zeitplan nicht verfügbar" |
| `frontend/src/routes/account/+page.svelte:482, 988-1010` | nutzt nur Job `trip_reports_hourly`: `id,next_run,last_run.status,last_run.time,last_run.error` |
| `frontend/src/lib/types.ts:573-584` | `SchedulerJob`/`SchedulerStatus` |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:119, ~826-855` | externer Aufrufer ohne Header, alle 5 min; wertet `jobs[].last_run/next_run`, Health-Blöcke, Tier-Schwelle aus. **Cron läuft direkt aus dem Repo-Arbeitsbaum ⇒ jede Änderung sofort live** |
| `/home/hem/henemm-infra/systemd/gregor-api.service:9-16`, `gregor-api-staging.service:9-11` | EnvironmentFiles (Prod: `gregor_zwanzig/.env`, `/etc/gregor/mail-prod.env`, `claude-mq/secrets/gregor.env`; Staging: `_staging/.env`, `gregor.env`) — Token muss auf beiden Seiten (Service + Skript) verfügbar sein |
| `api/routers/debug.py:19`, `api/main.py:116-118` | Python `/trigger-radar-alert?user_id=` (#830), nur staging, intern zusätzlich env-geprüft |

## Existing Patterns
- Webhook-Secret: `internal/handler/telegram_webhook.go:41-46` — Secret aus ENV, fail-closed 503 ohne Secret, Header-Vergleich (dort mit `!=`, nicht konstantzeitig — nicht übernehmen).
- Konstantzeit-Vergleich: `subtle.ConstantTimeCompare` (`internal/handler/auth_oauth.go:102`), `hmac.Equal` (`internal/middleware/auth.go:192`).
- Loopback-Guard `internal/handler/localhost_guard.go` (lehnt `X-Forwarded-*` ab) — laut Analyse S1 **nicht** geeignet, weil die SvelteKit-Durchleitung Go über localhost erreicht.
- Admin-Bestimmung fail-closed über ENV-Liste (ADR-0078).
- Staging-only-Routen außerhalb von `/api/debug/`: `/api/auth/verify-email/staging-token`, `/api/auth/sms/staging-code`, `/api/auth/staging-seed` (`router.go:89-91, 113-117`) — laufen über normale Session-Auth; Wächter gegen die Präfix-Falle: `internal/handler/staging_verify_token_test.go:180-196`.

## Dependencies
- Upstream: `AuthMiddleware` (Session/Cookie), `RequireAdmin`, `config.ParseAdminUserIDs`, Scheduler `Status()`.
- Downstream:
  - `check-gregor20.sh` (BetterStack-Heartbeat hängt daran) — Hauptbetroffener.
  - Konto-Seite (`/account`) → umstellen auf `/api/scheduler/status/me`.
  - SvelteKit-Proxy `frontend/src/routes/api/[...path]/+server.ts` — reine Durchleitung, keine eigene Liste.
  - Nicht betroffen: `.claude/hooks/*` (prod_selftest nutzt nur `/api/health`), `monitor.sh`, `deploy-gregor-prod.sh`, `auto-deploy-gregor-staging.sh`, henemm-n8n.

## Tests, die sich ändern müssen
- `internal/router/admin_trigger_test.go:249-256` — erwartet 200 für Nicht-Admin „bob" auf `GET /api/scheduler/status` (S1-Invariante, kippt mit S2).
- `internal/scheduler/briefing_health_test.go:78` — ruft Handler direkt, ohne Middleware (unberührt).
- `frontend/src/routes/account/__tests__/premium_sms_link_code_load.test.ts:138` — `fetch`-Stub kennt die Status-URL.
- `frontend/e2e/issue-294-home-kachel.spec.ts:126` — prüft nur Nicht-Aufruf.
- `tests/tdd/test_issue_830_radar_alert_validator.py:46`, `tests/tdd/test_bundle_h_908_973_987_staging_auth.py:101` — rufen `/api/debug/trigger-radar-alert` auf Staging nur mit Basic-Auth, ohne Session ⇒ nach S2 401/403. Brauchen Admin-Session oder werden angepasst.
- `tests/test_scheduler_router_requires_user_id.py:134,196` — TestClient direkt gegen Python (unberührt).

## Existing Specs / ADRs
- `docs/adr/0078-admin-rolle-ueber-env-liste-statt-profilfeld.md`
- `docs/specs/modules/admin_rolle_s1.md` (Z. 93-94, 236: „status und /api/debug/ bleiben öffentlich bis S2"; AC-7 Z. 187)
- Status-Endpunkt-Eigenschaften: `fix_2149_scheduler_nutzer_sichtbarkeit.md`, `fix_1555_tier_antrag_sichtbarkeit.md` (Z. 55/146 „öffentlich"), `fix_1581_enrichment_health.md`, `fix_1727_s5e_sperrcache_anzeige.md`, `external_validator_auth.md`, `user_auth_endpoints.md`

## Docs, die „öffentlich" behaupten (nachziehen)
- `CLAUDE.md` (Monitoring-Abschnitt: Status-Endpoint Port 8090)
- `.claude/validate-external.sh:68`, `.claude/agents/external-validator.md:32` („Public-Routen … /api/scheduler/status")
- `docs/reference/api_contract.md` Z. 243, 1297, 4381
- `docs/specs/modules/google_login_adress_verknuepfung.md:219`
- `docs/reference/operations_playbook.md:760`

## Risks & Considerations
- **Reihenfolge (Issue-Vorgabe):** erst `check-gregor20.sh` auf Token umstellen (Token vorab in beiden Umgebungen verteilen, Skript schickt Header — der alte Server ignoriert ihn), **erst danach** `status` aus der Allowlist nehmen. Sonst BetterStack-Fehlalarm bzw. — schlimmer — ein Skript, das 401 still als „ok" wertet. Prüfen, wie das Skript einen HTTP-Fehler behandelt (`curl -sf … || SCHED_RESPONSE=""`).
- **infra-Arbeitsbaum ist sofort live** — Skript-Änderung nur geprüft/committet einspielen, Mutationen nur in Kopien. Umsetzung durch diese Sitzung selbst (andere Instanzen sind auch Claude Code), Commit ins henemm-infra-Repo.
- **Secret-Verteilung:** Token darf nicht ins Repo; Ablageort muss für `gregor-api(-staging).service` und für den Cron-User von `check-gregor20.sh` lesbar sein (Kandidaten: `/etc/henemm/secrets.env`, `/etc/gregor/*.env`). Fail-closed: kein Token konfiguriert ⇒ Endpunkt verweigert (nicht öffentlich).
- **Admin-Zugriff auf `status`?** Offen, ob zusätzlich eine Admin-Session den vollen Status lesen darf (für die spätere `/admin`-UI S4) — in der Analyse entscheiden.
- **`/status/me`-Inhalt:** nur, was die Konto-Karte braucht (Job `trip_reports_hourly`: `next_run`, `last_run.time/status`). `last_run.error` ist ein globaler Fehlertext des Fan-out-Jobs — ob er nutzerbezogen gefiltert werden muss (Fremddaten-Leck?) klären; Zwei-Nutzer-Test Pflicht.
- **`/api/debug/` hinter `RequireAdmin`:** Staging-Tests, die nur Basic-Auth schicken, brechen; `GZ_ADMIN_USER_IDS` ist auf Prod nicht gesetzt, auf Staging klären (sonst Endpunkt dort für niemanden nutzbar).
- **Gesperrter Status-Zugang darf keine Existenz verraten** — 401 ohne Session, 403 für Nicht-Admin (S1-Konvention) oder einheitlich; in der Spec festlegen.
- **Nebenbefund (nicht S2):** Staging-Only-Routen `/api/auth/verify-email/staging-token` u. Geschwister nehmen den Ziel-`username` aus dem Body — jeder angemeldete Staging-Nutzer kann Token für fremde Konten holen. Nur Staging ⇒ Kandidat für Sammel-Issue #1199, kein eigenes Issue.

## Analysis

### Type
Feature (Scheibe S2 von #2155, Sicherheits-Härtung)

### Verifizierte Befunde (Phase 2)
- **Monitor wird bei 401 blind:** `check-gregor20.sh:119` `curl -sf … || SCHED_RESPONSE=""`; leere Antwort ⇒ Z.272-279 nur `systemctl is-active` ⇒ alle Job-/Health-Prüfungen entfallen still, Heartbeat pingt weiter (Readiness-Verstoß). Skript fragt nur Prod ab (localhost:8090), liest Secrets per `grep|cut|tr` aus `/home/hem/gregor_zwanzig/.env` (Muster Z.892-894), Cron-User `hem`.
- **Pro-Nutzer-Laufzustand existiert:** `trip_reports_hourly` ∈ `fanOutJobIDs` (`user_run_state.go:307`), `s.userState.Record(jobID, uid, …)` (`scheduler.go:351`, `RecordLate` Z.436) ⇒ `userJobRecord{LastRun, LastStatus, LastError}` je Nutzer vorhanden. Es fehlt nur ein Getter. `next_run` ist global (Cron-Entry, `scheduler.go:1101`). Globaler `last_run.error` ist ein Fan-out-Text ⇒ darf nicht an Nutzer.
- **Allowlist** `internal/middleware/auth.go:41`: `/api/scheduler/status` ist Gleichheitsvergleich (`==`) ⇒ `/api/scheduler/status/me` fällt NICHT darunter und läuft durch die Session-Auth. `/api/debug/` ist Präfix (`auth.go:59`).
- **`GZ_ADMIN_USER_IDS` weder auf Prod noch Staging gesetzt** ⇒ nach S2 ist `/api/debug/trigger-radar-alert` (nur `GZ_ENV=staging`, `router.go:272`, Python `api/routers/debug.py:51`) für niemanden nutzbar, bis ein Staging-Admin gesetzt ist.
- `.env`-Dateien Prod/Staging: `-rw-r----- hem:claude-gregor` ⇒ von dieser Sitzung (hem) beschreibbar, vom Dienst lesbar; kein neuer Ablageort nötig.

### Technical Approach (Entscheidungen)
1. **Maschinen-Token:** ENV `GZ_STATUS_TOKEN` (Config-Feld analog `AdminUserIDs`, `config.go:74`). Header `X-GZ-Status-Token` (nicht `Authorization` — Staging-Livetests belegen den bereits mit Basic-Auth). Vergleich: sha256 beider Seiten + `subtle.ConstantTimeCompare`. Fail-closed: kein Token konfiguriert ⇒ jede Anfrage abgewiesen (+ einmaliges Start-Log).
2. **Prüfort:** `/api/scheduler/status` bleibt exakt auf der Allowlist; neue Route-Middleware `RequireStatusToken`, per `r.With(...)` an der Route (`router.go:268`). Kein Sonderfall in `AuthMiddleware`.
3. **Antwort:** einheitlich **401** `{"error":"unauthorized"}` für fehlendes, falsches und unkonfiguriertes Token (keine Anmeldung ⇒ nicht 403, ADR-0078).
4. **`GET /api/scheduler/status/me`** (Session-Auth, `UserIDFromContext`): schlankes DTO in `SchedulerStatus`-kompatibler Form mit nur Job `trip_reports_hourly`: `id`, `name`, `next_run` (global), `last_run` **aus dem Pro-Nutzer-Zustand** (`time`, `status`, `error` = eigener `LastError`). Kein Eintrag ⇒ `last_run: null` (kein 404). Neuer Getter `userRunState` (jobID,userID) → Kopie **per Wert** unter `u.mu`. Frontend `account/+page.server.ts:24` auf `/me` umstellen; `types.ts` Status-Union auf die 6 Werte (`ok|partial|error|budget|skipped_in_flight|not_reached`) bzw. `string` lockern; Karte muss `null` und Nicht-ok/error-Werte sauber darstellen.
5. **`/api/debug/`:** Präfix aus der Allowlist entfernen, Route hinter `RequireAdmin` (S1). Staging: `GZ_ADMIN_USER_IDS` in `/home/hem/gregor_zwanzig_staging/.env` auf die **user_id** des bestehenden Staging-Test-Accounts (aus `tests/helpers/staging_auth.py`) setzen. Die zwei Staging-Livetests schicken zusätzlich eine echte Session (Login per `POST /api/auth/login`).
6. **Admin-Lesezugriff auf den vollen Status:** bewusst **nicht** in S2 (→ S4: zweite Route mit `requireAdmin` auf denselben Handler).

### Auslieferungs-Reihenfolge (PFLICHT, als prüfbare Vorbedingung in die Spec)
`/70-deploy` läuft autonom ⇒ die infra-Vorbedingung muss vor dem Merge **nachgewiesen** sein, nicht nur beschrieben:
1. Token (hex, **unquotiert** — Skript parst per `cut`) in Prod- und Staging-`.env` eintragen. **Kein manueller Dienst-Neustart** (verboten; der alte Server ignoriert den Header ohnehin).
2. infra-Commit `check-gregor20.sh`: Token lesen, Header senden (Token per stdin `-H @-`, nicht in `ps` sichtbar), `%{http_code}` auswerten — alles ≠ 200 sowie fehlendes Token ⇒ `FAIL` + `ERRORS++`; stiller `systemctl`-Fallback nur noch für Verbindungsfehler plus FAIL-Meldung. Änderung zuerst an einer Kopie testen (Arbeitsbaum ist sofort live).
3. Nachweis: ein grüner Check-Zyklus mit Header (Prod antwortet 200, kein Scheduler-`FAIL` im Log).
4. Erst dann gregor-PR mergen ⇒ Deploy startet Dienste neu, liest Token, Allowlist-Eintrag wird wirksam.
5. Staging-`GZ_ADMIN_USER_IDS` vor dem Staging-Deploy desselben Stands setzen (sonst rote Livetests).

### Affected Files
| File | Change | Beschreibung |
|------|--------|--------------|
| `internal/config/config.go` | MODIFY | Feld `StatusToken` (`GZ_STATUS_TOKEN`) |
| `internal/middleware/status_token.go` | CREATE | `RequireStatusToken` (Konstantzeit, fail-closed, 401) |
| `internal/middleware/auth.go` | MODIFY | Präfix `/api/debug/` raus |
| `internal/router/router.go` | MODIFY | Status-Route mit Token-Wächter, neue `/status/me`, Debug-Route mit `requireAdmin` |
| `internal/handler/scheduler_status.go` | MODIFY | Handler `/status/me` |
| `internal/scheduler/user_run_state.go` + `scheduler.go` | MODIFY | Getter je (jobID,userID), öffentliche Scheduler-Methode für den Handler |
| `frontend/src/routes/account/+page.server.ts`, `frontend/src/lib/types.ts`, ggf. `account/+page.svelte` | MODIFY | Umstellung auf `/me`, Status-Werte/`null` |
| `internal/router/admin_trigger_test.go:249-256` | MODIFY | Erwartung „bob → 200 auf status" kippt |
| neue Go-Tests (Router-Ebene) | CREATE | Token-Wächter, `/me` Zwei-Nutzer, Debug 401/403/Admin |
| `frontend/.../premium_sms_link_code_load.test.ts:138` | MODIFY | fetch-Stub-URL |
| `tests/tdd/test_issue_830_radar_alert_validator.py`, `tests/tdd/test_bundle_h_908_973_987_staging_auth.py` | MODIFY | Session-Login zusätzlich zu Basic-Auth |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | MODIFY (infra-Repo) | Header + HTTP-Code-Auswertung |
| Doku: `CLAUDE.md` (Monitoring), `.claude/validate-external.sh:68`, `.claude/agents/external-validator.md:32`, `docs/reference/api_contract.md` (243, 1297, 4381), `docs/specs/modules/google_login_adress_verknuepfung.md:219`, `docs/reference/operations_playbook.md:760` | MODIFY | „öffentlich" nachziehen |

### Scope Assessment
- Produktiver Code: Go ~90 LoC, TS ~15 LoC, infra-Skript ~20 LoC (anderes Repo) ⇒ unter 250, **ein Workflow**.
- Risk Level: **MEDIUM** — Code klein, aber Betriebsrisiko (Monitoring-Kette, Reihenfolge über zwei Repos, Secret-Verteilung).

### Test-Pflichten für die Spec
- **Token-Wächter über den echten Router** testen (nicht Handler direkt); Mutations-Gegenprobe: `r.With(RequireStatusToken)` entfernt ⇒ Test rot (Route steht weiter auf der Allowlist, es gibt keinen zweiten Schutz).
- Fälle: kein Header / falsches Token / leeres konfiguriertes Token ⇒ 401; richtiges ⇒ 200 mit vollem Status; Session-Cookie allein ⇒ 401.
- **Zwei-Nutzer-Test `/status/me`:** Nutzer A sieht nie `LastError`/Status von Nutzer B; ohne Session 401; Nutzer ohne Eintrag ⇒ `last_run: null`.
- `/api/debug/…` ohne Session 401, Nicht-Admin 403, Admin durchgelassen.
- Frontend: Konto-Karte mit `last_run: null` und mit Status `partial`/`budget`.

### Open Questions
- [x] Admin darf vollen Status lesen? → nein, S4.
- [x] 401 vs 403 → 401 einheitlich für Token-Route.
- [ ] Welche user_id hat der Staging-Test-Account? → in `/30` bzw. Umsetzung aus Staging-Daten/Login-Antwort ermitteln (technisch, keine PO-Frage).

### Nebenbefund (nicht S2)
- Staging-only-Routen `/api/auth/verify-email/staging-token` u. Geschwister nehmen den Ziel-`username` aus dem Body ⇒ jeder angemeldete Staging-Nutzer kann Token für fremde Konten holen. Nur Staging ⇒ Zeile im Sammel-Issue #1199.
