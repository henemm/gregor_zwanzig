---
entity_id: issue_773_radar_alert_wiring
type: module
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [alerts, scheduler, radar, e2e, wiring, mandantentrennung]
---

# Issue #773 — Radar-Alert verdrahten + echte E2E-Tests für beide Alert-Pfade

## Approval

- [ ] Approved

## Purpose

Schließt die sicherheitskritischste Lücke im Alert-System: `TripAlertService.check_radar_alerts()` (proaktive Gewitter-/Regen-Onset-Warnung ≤ 20 min) ist vollständig implementiert und unit-getestet, wird aber von keinem Scheduler-Job und keinem Endpoint aufgerufen — feuert in Produktion also nie. Zusätzlich fehlen echte E2E-Tests, die nachweisen, dass beide Alert-Pfade (Wetter-Änderungs-Alert und Radar-Alert) tatsächlich eine Mail zustellen. Diese Spec verdrahtet den Radar-Alert und schafft die fehlenden Beweistests.

## Source

- **File (Go):** `internal/scheduler/scheduler.go` — neuer Cron-Job `radar_alert_checks`
- **File (Python):** `api/routers/scheduler.py` — neuer Endpoint `POST /api/scheduler/radar-alert-checks`
- **File (Tests):** `tests/tdd/test_773_alert_e2e.py` — mock-freie E2E-Tests für beide Alert-Pfade
- **Schicht:** Go-API (`internal/scheduler/`) + Python-Backend (`api/routers/`) + Tests

## Estimated Scope

- **LoC:** ~80–110 (Go ~30, Python ~20, Tests ~50)
- **Files:** 3 produktiv + 1 Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.trip_alert.TripAlertService.check_radar_alerts` | service | Radar-Alert-Logik — UNVERÄNDERT, nur aufrufen |
| `services.trip_alert.TripAlertService.check_all_trips` | service | Wetter-Änderungs-Alert — UNVERÄNDERT, nur aufrufen |
| `services.weather_snapshot.WeatherSnapshotService.save` | service | Snapshot-Datei schreiben (Baseline für Änderungs-Alert-E2E) |
| `Scheduler.runForAllUsers` | method | Bestehender Go-Helper — neuer Job nutzt ihn direkt |
| `Scheduler.recordRun` | method | Bestehender Go-Helper — setzt `last_run` für Observability |
| `Scheduler.entryMap` | field | Registriert Job-Metadaten für Status-Endpoint |
| `outputs.email.EmailOutput` | output | Echte SMTP-Zustellung im E2E-Test |

## Implementation Details

### A) Neuer Python-Endpoint (`api/routers/scheduler.py`)

```python
@router.post("/radar-alert-checks")
def trigger_radar_alert_checks(user_id: str):  # PFLICHT, kein Default → fehlend = HTTP 422
    """Trigger radar-based alert checks for one user (called by Go scheduler)."""
    from services.trip_alert import TripAlertService

    service = TripAlertService(user_id=user_id)
    count = service.check_radar_alerts()
    return {"status": "ok", "count": count}
```

Muster identisch zu `/alert-checks` — kein neuer Mechanismus, lediglich
`check_radar_alerts()` statt `check_all_trips()`. Parameter `user_id` kommt aus dem
Query-String (analog aller anderen Scheduler-Endpoints); NIEMALS auf `"default"`
zurückfallen, da `user_id` stets explizit vom Go-Scheduler übergeben wird.

### B) Neuer Go-Cron-Job (`internal/scheduler/scheduler.go`)

Neuer Eintrag in `jobs []jobDef` in `New()`:

```go
{"*/15 * * * *", s.radarAlertChecks, "radar_alert_checks", "Radar Alert Checks (every 15 min)"},
```

Zugehörige Methode:

```go
func (s *Scheduler) radarAlertChecks() {
    s.recordRun("radar_alert_checks", func() error {
        return s.runForAllUsers("radar_alert_checks", "/api/scheduler/radar-alert-checks")
    })
}
```

Takt 15 Minuten (`*/15`): Das Nowcast-Onset-Fenster beträgt 20 Minuten; 30 Minuten
wäre zu grob, 15 Minuten ist das kleinste sinnvolle Intervall, das noch unterhalb des
Onset-Fensters liegt. Kein eigener Heartbeat-URL vorgesehen (wie `alert_checks`
ebenfalls keinen hat); fehlende Heartbeat-URL löst keine Warnung aus — das externe
Monitoring deckt den Job über `last_run` im Status-Endpoint ab.

`Start()` gibt künftig „5 jobs" aus (Zähler im Log-String anpassen).

### C) Wetter-Änderungs-Alert E2E (`tests/tdd/test_773_alert_e2e.py`)

**Strategie:** Der Snapshot ist eine Datei unter unserer Kontrolle.
Test schreibt einen Snapshot mit Extremwerten (Temperatur +40 °C, Wind 0 km/h), die garantiert
ein Delta zur echten API-Vorhersage erzeugen. Danach `check_all_trips()` direkt aufrufen —
die frische Vorhersage kommt von der echten API. Mindestens ein Alert muss ankommen.

```
1. Test-Trip anlegen (echter Trip in data/users/tdd-773-change/, heutige/zukünftige Etappe,
   ≥2 Waypoints, SMTP-konfigurierter User)
2. Throttle-Datei für diesen Trip löschen/zurücksetzen (radar_alert_throttle.json)
3. WeatherSnapshotService.save(trip.id, extremer_snapshot) schreiben
4. TripAlertService(user_id=...).check_all_trips() aufrufen
5. Per IMAP (GZ_IMAP_*, Stalwart-Postfach gregor-test@henemm.com) prüfen:
   - Eine neue Mail im Postfach (Subject enthält "Alert" oder Trip-Name)
6. Alert-Log-Datei lesen und Eintrag verifizieren
```

### D) Radar-Alert Verdrahtungs-E2E (`tests/tdd/test_773_alert_e2e.py`)

**Strategie (zweiteilig):**

1. **Endpoint-Nachweis:** Echter HTTP-Call via FastAPI `TestClient` gegen
   `POST /api/scheduler/radar-alert-checks?user_id=<user>` → antwortet `200`, Body
   `{"status": "ok", "count": <int>}`. Zwei verschiedene `user_id`-Werte belegen
   Mandantentrennung (jeder User sieht nur seine Trips).

2. **Job-Registrierungs-Nachweis:** Echter HTTP-Call gegen den laufenden Staging-Server
   `GET https://staging.gregor20.henemm.com/api/scheduler/status` → JSON-Antwort enthält
   Job mit `"id": "radar_alert_checks"` und Feld `"last_run"` (nicht absent).
   Alternativ: Unit-Test instanziiert `Scheduler` mit Test-Config und prüft
   `len(s.entryMap) == 5` und dass ein Eintrag `id == "radar_alert_checks"` enthält.

## Expected Behavior

- **Input (Endpoint):** `POST /api/scheduler/radar-alert-checks?user_id=X` — user_id aus Query, kein Default-Fallback im authentifizierten Pfad.
- **Output (Endpoint):** `{"status": "ok", "count": N}` — N = Anzahl ausgelöster Radar-Alerts.
- **Input (Go-Job):** Cron-Tick alle 15 Minuten.
- **Output (Go-Job):** HTTP-POST pro User, `last_run`-Eintrag in `lastRuns["radar_alert_checks"]`.
- **Side effects:** Throttle-Persistenz (`radar_alert_throttle.json`), `alert_log`, Alert-Mail/Telegram — alles innerhalb von `check_radar_alerts()`, unverändert.

## Acceptance Criteria

**AC-1:** Given der Go-Scheduler ist gestartet / When `GET /api/scheduler/status` aufgerufen wird / Then enthält das `jobs`-Array einen Eintrag mit `"id": "radar_alert_checks"`, `"name"` nicht leer und einem `"last_run"`-Feld (darf `null` sein, muss aber im JSON vorhanden sein) — der Job ist registriert und trägt zur Observability bei.
- Test: Echter HTTP-Call gegen Staging (`GET https://staging.gregor20.henemm.com/api/scheduler/status`) nach Deploy; assert job mit `id == "radar_alert_checks"` in `response.json()["jobs"]`; oder Go-Unit-Test mit Test-Scheduler-Instanz und `Status()`-Aufruf.

**AC-2:** Given zwei unterschiedliche Nutzer (`tdd-773-ac1`, `tdd-773-ac2`) jeweils mit eigenem Trip-Datenverzeichnis unter `data/users/` / When `POST /api/scheduler/radar-alert-checks?user_id=tdd-773-ac1` und danach `?user_id=tdd-773-ac2` via TestClient aufgerufen werden / Then antworten beide Requests mit HTTP 200 und `{"status": "ok", "count": <int>}`, und der zweite Request sieht ausschließlich Trips des zweiten Nutzers (Mandantentrennung: kein Cross-User-Datenleck).
- Test: Echter TestClient-Aufruf (FastAPI) mit zwei isolierten Testnutzer-Verzeichnissen; je ein Trip pro Nutzer; assert HTTP 200 + Status-ok; assert count-Rückgabe bezieht sich nur auf den jeweiligen Nutzer (Einzeltrip → count 0 oder 1, abhängig von Radar-Lage).

**AC-3:** Given ein Test-Trip mit heutiger aktiver Etappe, aktivem Alerting, konfiguriertem SMTP (`GZ_IMAP_*`) und einem gespeicherten Snapshot mit Extremwerten (die garantiert ein signifikantes Delta zur echten API erzeugen) / When `TripAlertService(user_id=...).check_all_trips()` aufgerufen wird / Then wird genau eine Alert-Mail im Stalwart-Test-Postfach (`gregor-test@henemm.com`) per IMAP nachweisbar zugestellt und ein `alert_log`-Eintrag geschrieben — kein Mock.
- Test: Mock-freier E2E: Test-Trip + Extremwert-Snapshot in `data/users/tdd-773-change/`; Throttle-Datei vor Lauf löschen; `check_all_trips()` direkt aufrufen; IMAP-Check (GZ_IMAP_*, Stalwart) prüft neue Mail mit Trip-Name oder „Alert" im Subject; alert_log-Datei enthält neuen Eintrag mit `trip_id`; keine Mocks.

**AC-4:** Given ein Test-Trip, bei dem der Wetter-Änderungs-Alert bereits einmal ausgelöst und der Throttle gesetzt wurde / When `check_all_trips()` erneut aufgerufen wird (innerhalb des Throttle-Fensters) / Then wird kein weiterer Alert versendet und das IMAP-Postfach enthält keine zweite neue Mail.
- Test: Direkter Folgeaufruf nach AC-3 (Throttle-Datei bleibt erhalten); assert count == 0; IMAP-Postfach hat keine weitere neue Alert-Mail (Zeitstempel-Vergleich).

**AC-5:** Given der neue Endpoint `POST /api/scheduler/radar-alert-checks` ist deployed / When ein Aufruf ohne `user_id`-Parameter gemacht wird / Then antwortet der Endpoint mit HTTP 422 oder liefert `count: 0` ohne stillen `"default"`-Fallback auf produktive Nutzerdaten — ein fehlender `user_id`-Parameter darf nicht zu Cross-User-Datenzugriffen führen.
- Test: TestClient-Aufruf ohne `user_id`; assert HTTP-Status ist 422 oder Response-Body dokumentiert explizit, dass kein Default-User verwendet wird; alternativ: Verhalten bei fehlendem Parameter vs. explizitem `user_id=tdd-773-ac1` ist nachweisbar unterschiedlich.

## Known Limitations

- Der Radar-Alert-E2E (AC-3) ist wetter- und koordinatenabhängig: er erzwingt das Delta durch einen Extremwert-Snapshot, nicht durch Steuerung der echten Vorhersage. Bei instabiler API-Antwort (Timeout, leer) scheitert der Test mit einem klaren Fehler, nicht einem False-Positive.
- `check_radar_alerts()` selbst bleibt unverändert — ob ein Radar-Alert tatsächlich feuert, hängt von der aktuellen Nowcast-Lage ab. AC-2 prüft daher Verdrahtung und Mandantentrennung, nicht die Alarm-Auslösung selbst.
- Kein BetterStack-Heartbeat für `radar_alert_checks` vorgesehen — das externe `check-gregor20.sh`-Monitoring überwacht den Job über `last_run` im Status-Endpoint.
- `Start()`-Log-Ausgabe „4 jobs" muss auf „5 jobs" aktualisiert werden.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_ac1_radar_alert_job_registered_in_scheduler_status` |
| AC-2 | `test_ac2_radar_alert_endpoint_mandantentrennung` |
| AC-3 | `test_ac3_weather_change_alert_sends_real_mail_via_imap` |
| AC-4 | `test_ac4_weather_change_alert_throttled_on_second_run` |
| AC-5 | `test_ac5_radar_alert_endpoint_no_default_fallback` |

Testdatei: `tests/tdd/test_773_alert_e2e.py` (mock-frei).

## Changelog

- 2026-06-12: Initial spec created (Issue #773). Root Cause: `check_radar_alerts` hat keinen Scheduler-Job und keinen Endpoint; `check_all_trips` feuert in der Praxis fast nie wegen enger Snapshot-Voraussetzung.
