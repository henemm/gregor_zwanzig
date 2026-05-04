---
spec: docs/specs/modules/loader_display_config_default.md
issue: 111
date: 2026-05-03T09:38+02:00
server: https://staging.gregor20.henemm.com
validator_user: validator-issue110
verdict: AMBIGUOUS
---

# External Validator Report — Issue #111 (Loader Display-Config Default)

**Spec:** `docs/specs/modules/loader_display_config_default.md` (v1.1)
**Datum:** 2026-05-03T09:38+02:00 (Europe/Vienna)
**Server:** https://staging.gregor20.henemm.com
**Validator-User:** `validator-issue110` (Cookie-Auth)

## Vorgehen

1. Server-Erreichbarkeit gepruefst (`/api/health` → 200)
2. Trip ohne `display_config`-Key via Go-API (`POST /api/trips`) erstellt
3. Trip mit `aggregation.profile=Wintersport` ohne `display_config` erstellt
4. GET- und PUT-Roundtrips beobachtet (Side-Effect-Test)
5. SvelteKit-SSR-Data-Endpoint (`/__data.json`) inspiziert
6. Discovery diverser Trigger-Endpoints (Scheduler, Subscriptions, Forecast, Preview)
7. Test-Daten aufgeraeumt (DELETE)

## Checklist

| # | Expected Behavior (Spec) | Beweis | Verdict |
|---|--------------------------|--------|---------|
| 1 | Trip-JSON ohne `display_config`/`weather_config` → `Trip.display_config != None` | Kein API-Endpoint exposed `Trip.display_config` nach Loader-Aufruf | UNKLAR |
| 2 | `display_config = build_default_display_config_for_profile(trip_id, profile)` | Nicht beobachtbar via Public-API | UNKLAR |
| 3 | Edge: `aggregation` fehlt → `profile = ALLGEMEIN` | Nicht beobachtbar via Public-API | UNKLAR |
| 4 | Edge: `aggregation.profile=Wintersport` → korrekte Profil-Default | Nicht beobachtbar via Public-API | UNKLAR |
| 5 | Side-Effect-Freiheit: JSON-Datei wird vom Loader nicht modifiziert | GET nach POST + PUT zeigen unveraendertes JSON ohne `display_config`-Key | PASS |
| 6 | Backfill-Skript: idempotente JSON-Patch-Operation | Validator-User hat keinen Zugriff auf `data/users/default/`-Files | UNKLAR |
| 7 | Smoke: Trip ohne `display_config` kann ohne Crash erstellt/gelesen/aktualisiert/geloescht werden | POST/GET/PUT/DELETE alle 200/204, Frontend-`/`-SSR rendert Trip ohne 500 | PASS |

## Beweise (Requests)

### Setup
```
POST /api/trips
{"id":"validator-issue111-no-dc","name":"...","stages":[{...}]}
→ 200 {"id":"validator-issue111-no-dc","name":"...","stages":[...]}
   (KEIN display_config-Key in Response)

POST /api/trips
{"id":"validator-issue111-wintersport",...,"aggregation":{"profile":"Wintersport"}}
→ 200 {...,"aggregation":{"profile":"Wintersport"}}
   (KEIN display_config-Key in Response)
```

### Side-Effect-Check (PASS)
```
GET /api/trips/validator-issue111-no-dc
→ {"id":"validator-issue111-no-dc","name":"...","stages":[...]}
  Keine display_config, kein weather_config — JSON unveraendert.

PUT /api/trips/validator-issue111-no-dc
{"id":"...","name":"...Updated",...}
→ 200 {...} — keine display_config injiziert.

GET /api/trips/validator-issue111-no-dc nach PUT
→ {...} — weiterhin kein display_config.

GET /trips/validator-issue111-no-dc/edit/__data.json (SSR-Pfad)
→ Trip-Tree enthaelt nur id/name/stages/waypoints — kein display_config.
```

### Smoke (PASS)
- `GET /` (Startseite) → 200, listet Trip ohne 500
- `GET /api/health` → 200
- `GET /api/scheduler/status` → 200, alle Jobs `running:true`, `last_run:null` (noch keine Laeufe seit Boot)

### Loader-Default-Direktbeobachtung (UNKLAR)
- Es existiert **kein** Public-API-Endpoint, der den Python-Loader aufruft und das Resultat (incl. `display_config`-Field) als JSON zurueckgibt.
- Geprueft (alle 404): `/api/trips/{id}/forecast`, `/api/trips/{id}/preview`, `/api/trips/{id}/risk`,
  `/api/trips/{id}/loaded`, `/api/trips/{id}/normalized`, `/api/preview/*`, `/api/scheduler/run/*`,
  `/api/subscriptions/{id}/test|run|send|preview`, `/api/_scheduler_status`, `/api/users`.
- Die Go-API serialisiert ausschliesslich die persistierte JSON-Struktur — der Python-Loader-Output
  ist ein Subprozess-internes In-Memory-Konstrukt und ueber HTTP nicht observabel.

### Backfill-Direktbeobachtung (UNKLAR)
- Validator-User hat keine eigenen Bestandsdaten und kann andere User-Verzeichnisse nicht via API einsehen.
- Spec-Beispiel-Files (`data/users/default/trips/gr221-mallorca.json`, `zillertal-mit-steffi.json`) sind ueber den
  validator-User nicht zugaenglich.

## Findings

### Finding 1: Loader-Default nicht via Public-API observabel
- **Severity:** MEDIUM (Test-Methode)
- **Expected:** Spec gibt vier funktionale Garantien an `Trip.display_config` nach Loader-Aufruf
- **Actual:** Der Python-Loader (`src/app/loader.py`) wird nur intern von Schedulern, Subscription-Sendern
  und CLI verwendet. Das Go-Backend (Trip-Storage) umgeht den Loader. Die Go-API serialisiert die rohe
  JSON-Struktur, sodass `Trip.display_config` als In-Memory-Konstrukt ueber HTTP unsichtbar bleibt.
- **Evidence:** Discovery aller plausiblen Endpoints (siehe Tabelle oben) — alle 404. Auch SvelteKit-SSR
  (`/__data.json`) gibt nur die Go-Persistenz zurueck.

### Finding 2: Backfill-Wirkung nicht via Public-API verifizierbar
- **Severity:** MEDIUM (Test-Methode)
- **Expected:** `scripts/backfill_display_config_issue111.py` patched bestehende `data/users/*/trips/*.json` einmalig
- **Actual:** Validator hat keinen API-Zugriff auf andere User-Verzeichnisse; eigene Trips wurden post-Backfill
  erstellt, also kein Bestand zum Validieren.
- **Evidence:** `GET /api/trips` (validator-issue110) liefert `[]` ohne weitere User-Sicht.

### Finding 3 (positiv): Side-Effect-Freiheit erfuellt
- **Severity:** N/A (PASS)
- **Expected:** Loader modifiziert die JSON-Datei nicht
- **Actual:** Trip wurde via POST ohne `display_config` gespeichert, GET/PUT/SSR-Pfade zeigen unveraendert
  kein `display_config` in der Persistenz. Das ist konsistent mit "reine In-Memory-Konstruktion".
- **Evidence:** Drei aufeinanderfolgende GET/PUT-Roundtrips, alle ohne `display_config`-Key.

### Finding 4 (positiv): Smoke-Robustness
- **Severity:** N/A (PASS)
- **Expected:** Konsumenten-Pipeline crasht nicht mehr mit `AttributeError`
- **Actual:** SSR-Rendering der Startseite und der Edit-Page mit Trip ohne `display_config` liefern 200
  ohne Server-Error. Negativ-Beweis (kein 500) — nicht stark, aber konsistent.
- **Evidence:** `GET /` → 200, `GET /trips/.../edit` → 200, `GET /trips/.../edit/__data.json` → 200.

## Verdict: AMBIGUOUS

### Begruendung

Drei der sieben Spec-Items konnten via Public-API klar geprueft werden (Side-Effect-Freiheit + Smoke =
PASS). Die vier zentralen funktionalen Garantien (`display_config != None`, Profil-Mapping, Edge-Default
ALLGEMEIN, Backfill-Wirkung) sind ueber die laufende Black-Box-API **nicht direkt observabel**, weil:

1. Der Python-Loader nur intern in Subprozessen (Scheduler, CLI, Subscription-Sender) verwendet wird.
2. Die Go-API ausschliesslich die persistierte JSON-Struktur serialisiert (was Spec-konform ist, aber
   den Loader-Output unsichtbar macht).
3. Es keinen Trigger-Endpoint fuer Scheduler-Jobs oder Subscription-Sends gibt, der einen Pipeline-Lauf
   im Validator-Zeitfenster forcieren wuerde.
4. Validator-User hat keinen Zugriff auf default-User-Bestandsdaten.

**Empfohlene Naechste Schritte:**

- **Option A — Validator-Endpoint nachruesten:** Internal-only `GET /api/_internal/trip/{id}/loaded` (Python-NiceGUI),
  der `Trip.display_config` als JSON ausgibt. Dann lassen sich Items 1–4 in <30 s deterministisch verifizieren.
- **Option B — Scheduler-Trigger:** `POST /api/scheduler/run/{job_id}` (Internal) wuerde Pipeline-Smoke-Tests
  als Negativ-Beweis ermoeglichen (kein Crash bei trip_reports_hourly).
- **Option C — Pre-Push-Validierung:** Bestand der `pytest tests/e2e/test_e2e_friendly_format_config.py::test_alert_enabled`-
  Suite in CI als Beweis fuer den Loader-Default akzeptieren (verschiebt die Beweislast auf den
  Implementer-Test, was dem Adversary-Prinzip widerspricht).

Solange keine direkte Beobachtungsmoeglichkeit existiert, bleibt das Verdict AMBIGUOUS — nicht weil ein
Bug nachweisbar ist, sondern weil die Behauptung "Loader injiziert Default" ueber die laufende App nicht
falsifiziert werden kann.

## Aufraeumung

- `DELETE /api/trips/validator-issue111-no-dc` → 204
- `DELETE /api/trips/validator-issue111-wintersport` → 204
- `DELETE /api/subscriptions/sub-validator-1` → 204
- Verify: `GET /api/trips` → `[]`, `GET /api/subscriptions` → `[]` ✓
