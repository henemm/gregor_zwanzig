# Context: #773 Alerts testen (kritisch)

## Request Summary
Der PO hat dauerhaft eine Test-Tour aktiv, aber **noch nie** einen Alert bekommen.
Komplette Alert-Kette analysieren und **echte E2E-Tests** bauen, die einen Alert real
inszenieren (kein Mock).

## Die Alert-Kette (Ist-Zustand)

```
Go-Cron (internal/scheduler/scheduler.go)
  job "alert_checks" alle 30 min  →  runForAllUsers("/api/scheduler/alert-checks")
       │
       ▼
api/routers/scheduler.py  POST /alert-checks?user_id=X
       │
       ▼
TripAlertService(user_id).check_all_trips()      ← NUR Wetter-Änderungs-Alerts
       │
       ├─ load_all_trips(user_id)
       ├─ Gate: active alert_rules ODER report_config.alert_on_changes (default True)
       ├─ Gate: trip.end_date >= today
       ├─ Gate: cached = WeatherSnapshotService.load(trip.id)   ← Snapshot PFLICHT
       ├─ check_and_send_alerts(trip, cached):
       │     Gate: Kanal (SMTP|Telegram), QuietHours, Throttle/Cooldown
       │     fresh = _fetch_fresh_weather()
       │     significant = _detect_all_changes(cached, fresh)   ← Delta-Schwelle
       │     _send_alert() → EmailOutput/Telegram → Snapshot überschreiben → Throttle/Log
```

## Befund 1 (HAUPT-ROOT-CAUSE): Radar/Gewitter-Alert ist nicht verdrahtet
`TripAlertService.check_radar_alerts()` (proaktive Gewitter-/Regen-Onset-Warnung, ≤20 min,
„⚠️ Gewitter") existiert vollständig + ist unit-getestet (#656/#660), wird aber **von
keinem Endpoint und keinem Scheduler-Job aufgerufen**. Aufrufer im gesamten Repo: nur Tests.
→ Die sicherheitskritischste, proaktive Warnung **feuert in Produktion nie**.
Es gibt keinen `/api/scheduler/radar-*`-Endpoint und keinen Cron-Job dafür.

## Befund 2 (Mit-Ursache): Wetter-Änderungs-Alert hat enge Voraussetzungen
`check_all_trips()` feuert nur, wenn ein **Snapshot existiert** (wird nur nach einer
Briefing-Mail gespeichert, `trip_report_scheduler.py:564`) UND zwischen Snapshot und
frischer Vorhersage eine **signifikante Delta-Schwelle** überschritten wird. Jeder
gesendete Alert *und* jede Briefing-Mail überschreiben den Snapshot → Baseline wandert
mit → Änderungen werden selten als „signifikant" erkannt. Plausibel, dass dieser Pfad in
der Praxis fast nie auslöst.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py` | `check_all_trips` (verdrahtet), `check_radar_alerts` (verwaist), `check_and_send_alerts` |
| `api/routers/scheduler.py` | Trigger-Endpoints — **kein** Radar-Endpoint |
| `internal/scheduler/scheduler.go` | Go-Cron — Job `alert_checks` ruft nur `check_all_trips` |
| `src/services/weather_snapshot.py` | Snapshot load/save (Baseline für Änderungs-Alert) |
| `src/services/weather_change_detection.py` | Delta-Detektor + Schwellen |
| `src/services/radar_nowcast.py` (ff.) | Nowcast-Quelle für Radar-Alert |

## Existing Specs
- `docs/specs/modules/radar_nowcast.md` (#656) — AC-4 definiert `check_radar_alerts`, aber NUR Service-Ebene, keine Scheduler-Verdrahtung
- `docs/specs/modules/radar_convective_stage.md` (#660) — Gewitter-Kennzeichnung
- `docs/specs/modules/issue_684_alert_email_guard.md` — Kanal-Guard
- `docs/specs/modules/issue_222_w1_alert_rules_service.md` — alert_rules-Priorität

## E2E-Inszenierung (Kerngedanke)
Frische Vorhersage = echte API (nicht steuerbar), **aber der Snapshot ist eine Datei unter
unserer Kontrolle**. Für den Änderungs-Alert: Snapshot mit extremen Werten schreiben →
garantiertes Delta → `check_all_trips` → reale Alert-Mail per IMAP nachweisen. Für den
Radar-Alert: realer Nowcast an einer Koordinate mit aktuellem Niederschlag-Onset, ODER
der Verdrahtungs-Nachweis (Endpoint/Job existiert und ruft `check_radar_alerts`).

## Risks & Considerations
- Mandantentrennung: Endpoint/Job MUSS `user_id` durchreichen (kein `default`-Fallback).
- Observability: neuer Job braucht `last_run`-Tracking im Status-Endpoint (Monitoring-Pflicht).
- Throttle-Persistenz zwischen Test-Läufen (`radar_alert_throttle.json`) muss zurückgesetzt werden.
- Keine Mocks: echte Mail via SMTP → IMAP-Verifikation (Stalwart-Test-Postfach).
